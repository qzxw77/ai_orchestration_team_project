import json
import math
import re

# --- 상수 설정 (파일 상단 배치) ---
ALLOWED_PRICE_OUTLOOKS: tuple[str, ...] = ("상승", "보합", "하락", "언급없음")
BIT_GROWTH_MIN: float = -50.0
BIT_GROWTH_MAX: float = 100.0
MAX_HBM_COMMENT_LEN: int = 100
MAX_EVIDENCE_COUNT: int = 3
QUARTER_PATTERN: re.Pattern[str] = re.compile(r"\d{4}Q[1-4]")

GUIDANCE_PROMPT_TEMPLATE: str = """다음 컨퍼런스콜 원문에서 다음 분기 가이던스 정보를 추출하여 JSON 객체로만 응답하세요.
설명이나 코드 블록 없이 순수 JSON 문자열만 출력해야 합니다.

[추출 키 및 허용값 규칙]
- "target_quarter": 대상 분기 문자열 ("YYYYQn" 형식, 예: "2026Q4"). 원문에 없으면 null.
- "dram_bit_growth_pct": D램 출하량 증가율 전망 숫자(% 단위 기호 제외한 수치, 부호·소수점 허용). 원문에 없는 숫자는 절대 추측하지 말고 null.
- "nand_bit_growth_pct": 낸드 출하량 증가율 전망 숫자(% 단위 기호 제외한 수치, 부호·소수점 허용). 원문에 없는 숫자는 절대 추측하지 말고 null.
- "price_outlook": 가격 전망 ("상승", "보합", "하락", "언급없음" 중 하나만 허용).
- "hbm_comment": HBM 관련 핵심 언급 1문장 (100자 이내 문자열, 언급이 없으면 "").
- "evidence": 가이던스 판단 근거가 된 원문 문장 배열 (최대 3개, 없으면 []).

[원문]
"""


def extract_guidance(transcript_text: str) -> dict:
    """컨퍼런스콜 텍스트에서 다음 분기 출하·가격 전망을 LLM으로 뽑아 guidance 형식으로 정리한다.

    Args:
        transcript_text (str): 분석할 컨퍼런스콜 원문 텍스트.

    Returns:
        dict: 추출 및 검증이 완료된 guidance 딕셔너리.
            항상 다음 7개 키를 포함한다:
            - status (str): "ok", "empty_input", "parse_error" 중 하나
            - target_quarter (str | None): "YYYYQn" 형식 분기 문자열 또는 None
            - dram_bit_growth_pct (float | None): D램 출하 증가율(-50.0~100.0) 또는 None
            - nand_bit_growth_pct (float | None): 낸드 출하 증가율(-50.0~100.0) 또는 None
            - price_outlook (str): "상승", "보합", "하락", "언급없음", "NA" 중 하나
            - hbm_comment (str): 100자 이내의 HBM 관련 언급 문자열 (없으면 "")
            - evidence (list[str]): 근거 원문 문장 목록 (최대 3개)

    Raises:
        없음: 빈 입력이나 파싱 실패, 규격 외 값은 예외를 발생시키지 않고 status 및 기본값으로 처리한다.
    """
    default_guidance: dict = {
        "target_quarter": None,
        "dram_bit_growth_pct": None,
        "nand_bit_growth_pct": None,
        "price_outlook": "NA",
        "hbm_comment": "",
        "evidence": [],
    }

    # 1. 빈 입력 또는 공백뿐인 입력 검사 (_call_llm 호출 금지)
    if transcript_text is None or not isinstance(transcript_text, str) or not transcript_text.strip():
        return {**default_guidance, "status": "empty_input"}

    # 2. 프롬프트 조립 및 LLM 단일 호출 지점(_call_llm) 호출
    prompt: str = f"{GUIDANCE_PROMPT_TEMPLATE}{transcript_text}"
    raw_response: str = _call_llm(prompt)

    if not isinstance(raw_response, str) or not raw_response.strip():
        return {**default_guidance, "status": "parse_error"}

    # 3. 응답 앞뒤의 마크다운 코드 블록 표시(```json ... ``` 등) 제거 후 JSON 해석
    cleaned_response: str = raw_response.strip()
    fence_match = re.match(
        r"^```(?:json)?\s*(.*?)\s*```$",
        cleaned_response,
         flags=re.DOTALL | re.IGNORECASE,
    )
    if fence_match:
        cleaned_response = fence_match.group(1).strip()

    try:
        parsed_data = json.loads(cleaned_response)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {**default_guidance, "status": "parse_error"}

    if not isinstance(parsed_data, dict):
        return {**default_guidance, "status": "parse_error"}

    # 4. 기본값에 응답의 6개 키 값만 덮어쓰기 (그 밖의 키는 버리고, 빠진 키는 기본값 유지)
    result: dict = {
        key: parsed_data.get(key, default_val)
        for key, default_val in default_guidance.items()
    }

    # 5. 개별 필드 유효성 검증 및 정규화
    # (1) price_outlook 검증
    if result["price_outlook"] not in ALLOWED_PRICE_OUTLOOKS:
        result["price_outlook"] = "NA"

    # (2) dram_bit_growth_pct, nand_bit_growth_pct 검증
    for growth_key in ("dram_bit_growth_pct", "nand_bit_growth_pct"):
        val = result[growth_key]
        if (
            isinstance(val, bool)
            or not isinstance(val, (int, float))
            or math.isnan(val)
            or math.isinf(val)
            or not (BIT_GROWTH_MIN <= float(val) <= BIT_GROWTH_MAX)
        ):
            result[growth_key] = None
        else:
            result[growth_key] = float(val)

    # (3) target_quarter 검증 ("YYYYQn" 형식)
    tq = result["target_quarter"]
    if not isinstance(tq, str) or not QUARTER_PATTERN.fullmatch(tq):
        result["target_quarter"] = None

    # (4) hbm_comment 검증 (문자열이 아니면 "", 100자 초과 시 앞 100자)
    hbm = result["hbm_comment"]
    if not isinstance(hbm, str):
        result["hbm_comment"] = ""
    else:
        result["hbm_comment"] = hbm[:MAX_HBM_COMMENT_LEN]

    # (5) evidence 검증 (문자열인 항목만 남겨 앞에서부터 최대 3개)
    ev = result["evidence"]
    if not isinstance(ev, list):
        result["evidence"] = []
    else:
        result["evidence"] = [item for item in ev if isinstance(item, str)][:MAX_EVIDENCE_COUNT]

    result["status"] = "ok"
    return result