import json
import math
import os
import re

# --- 상수 설정 (schema.md 1.3절, 5.1절 반영) ---
USE_MOCK: bool = True  # 13주차에 False로 전환
MOCK_PREFIX: str = "[MOCK] "

STATUS_OK: str = "ok"
STATUS_EMPTY_INPUT: str = "empty_input"
STATUS_PARSE_ERROR: str = "parse_error"

OUTLOOK_UP: str = "상승"
OUTLOOK_FLAT: str = "보합"
OUTLOOK_DOWN: str = "하락"
OUTLOOK_NONE: str = "언급없음"
OUTLOOK_NA: str = "NA"
ALLOWED_PRICE_OUTLOOKS: tuple[str, ...] = (
    OUTLOOK_UP,
    OUTLOOK_FLAT,
    OUTLOOK_DOWN,
    OUTLOOK_NONE,
)

BIT_GROWTH_MIN: float = -50.0
BIT_GROWTH_MAX: float = 100.0
MAX_HBM_COMMENT_LEN: int = 100
MAX_EVIDENCE_COUNT: int = 3

CLAUDE_MODEL_NAME: str = "claude-3-5-sonnet-latest"
CLAUDE_MAX_TOKENS: int = 1024
CLAUDE_TIMEOUT_SEC: float = 20.0

# ASCII 숫자만 허용하는 정규식 패턴 (schema.md 1.1절 반영)
QUARTER_PATTERN: re.Pattern[str] = re.compile(r"^[0-9]{4}Q[1-4]$", re.ASCII)
SENTENCE_SPLIT_PATTERN: re.Pattern[str] = re.compile(
    r"(?<![0-9])\.(?![0-9])|\n+", re.ASCII
)
TARGET_QUARTER_KO_PATTERN: re.Pattern[str] = re.compile(
    r"([0-9]{4})\s*년\s*([1-4])\s*분기", re.ASCII
)
DRAM_GROWTH_PATTERN: re.Pattern[str] = re.compile(
    r"(?:D램|DRAM).*?(-?[0-9]+(?:\.[0-9]+)?)%", re.IGNORECASE | re.ASCII
)
NAND_GROWTH_PATTERN: re.Pattern[str] = re.compile(
    r"(?:낸드|NAND).*?(-?[0-9]+(?:\.[0-9]+)?)%", re.IGNORECASE | re.ASCII
)
HBM_KEYWORD_PATTERN: re.Pattern[str] = re.compile(r"HBM", re.IGNORECASE | re.ASCII)

BRIEF_TEMPLATES: tuple[str, str, str] = (
    "{quarter} 예상 매출은 {estimate}({range})입니다.",
    "직전 분기 대비 {qoq} 변화가 예상됩니다.",
    "최근 수출 흐름은 {anomaly}, 가이던스 비교 결과는 {consistency}입니다.",
)

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


def _new_default_guidance() -> dict:
    """호출마다 새로운 기본값 guidance dict를 생성하여 반환한다."""
    return {
        "target_quarter": None,
        "dram_bit_growth_pct": None,
        "nand_bit_growth_pct": None,
        "price_outlook": OUTLOOK_NA,
        "hbm_comment": "",
        "evidence": [],
    }


def _is_valid_quarter(val: object) -> bool:
    """문자열이 6글자 ASCII 'YYYYQn' 형식인지 검사한다."""
    return (
        isinstance(val, str)
        and len(val) == 6
        and val.isascii()
        and bool(QUARTER_PATTERN.fullmatch(val))
    )


def _mock_guidance(transcript_text: str) -> str:
    """컨퍼런스콜 원문에 규칙을 적용하여 가이던스 JSON 문자열을 생성한다 (내부 목 도우미).

    schema.md 4.3절 및 5.1절에 따라 비어 있지 않은 hbm_comment와
    evidence 각 문장 앞에 '[MOCK] ' 표식을 붙이며, 100자 제한은 표식을 포함한 길이로 적용한다.

    Args:
        transcript_text (str): '[원문]' 줄 아래의 컨퍼런스콜 텍스트.

    Returns:
        str: 6개 가이던스 키를 담은 JSON 문자열.

    Raises:
        없음
    """
    text: str = transcript_text or ""

    sentences: list[str] = [
        s.strip() for s in SENTENCE_SPLIT_PATTERN.split(text) if s.strip()
    ]

    has_up: bool = OUTLOOK_UP in text
    has_down: bool = OUTLOOK_DOWN in text
    if has_up and not has_down:
        price_outlook: str = OUTLOOK_UP
    elif has_down and not has_up:
        price_outlook = OUTLOOK_DOWN
    else:
        price_outlook = OUTLOOK_NONE

    dram_growth: float | None = None
    nand_growth: float | None = None

    for sentence in sentences:
        if dram_growth is None:
            dram_match = DRAM_GROWTH_PATTERN.search(sentence)
            if dram_match:
                dram_growth = float(dram_match.group(1))
        if nand_growth is None:
            nand_match = NAND_GROWTH_PATTERN.search(sentence)
            if nand_match:
                nand_growth = float(nand_match.group(1))

    quarter_match = TARGET_QUARTER_KO_PATTERN.search(text)
    target_quarter: str | None = (
        f"{quarter_match.group(1)}Q{quarter_match.group(2)}" if quarter_match else None
    )

    hbm_comment: str = ""
    for sentence in sentences:
        if HBM_KEYWORD_PATTERN.search(sentence):
            hbm_comment = f"{MOCK_PREFIX}{sentence}"[:MAX_HBM_COMMENT_LEN]
            break

    evidence: list[str] = []
    for sentence in sentences:
        if OUTLOOK_UP in sentence or OUTLOOK_DOWN in sentence or "%" in sentence:
            evidence.append(f"{MOCK_PREFIX}{sentence}")
            if len(evidence) >= MAX_EVIDENCE_COUNT:
                break

    payload: dict = {
        "target_quarter": target_quarter,
        "dram_bit_growth_pct": dram_growth,
        "nand_bit_growth_pct": nand_growth,
        "price_outlook": price_outlook,
        "hbm_comment": hbm_comment,
        "evidence": evidence,
    }
    return json.dumps(payload, ensure_ascii=False)


def _mock_brief(facts_json: str) -> str:
    """facts JSON 문자열을 받아 BRIEF_TEMPLATES에 값을 채우고 '[MOCK] '을 붙인 JSON 문자열을 반환한다.

    Args:
        facts_json (str): '[입력]' 줄 아래의 facts JSON 문자열.

    Returns:
        str: {"sentences": [...]} 형식의 JSON 문자열 (해석 실패 시 빈 문자열 "").

    Raises:
        없음
    """
    try:
        facts = json.loads(facts_json.strip())
    except (json.JSONDecodeError, TypeError, ValueError):
        return ""

    if not isinstance(facts, dict):
        return ""

    sentences: list[str] = [
        f"{MOCK_PREFIX}"
        + template.format(
            quarter=facts.get("quarter", "확인 불가"),
            estimate=facts.get("estimate", "확인 불가"),
            range=facts.get("range", "확인 불가"),
            qoq=facts.get("qoq", "확인 불가"),
            months=facts.get("months", "확인 불가"),
            ratio=facts.get("ratio", "확인 불가"),
            export_yoy=facts.get("export_yoy", "확인 불가"),
            anomaly=facts.get("anomaly", "확인 불가"),
            consistency=facts.get("consistency", "확인 불가"),
        )
        for template in BRIEF_TEMPLATES
    ]
    return json.dumps({"sentences": sentences}, ensure_ascii=False)


def _mock_response(prompt: str) -> str:
    """프롬프트 내 표시 줄('[원문]' 또는 '[입력]')에 따라 알맞은 목 응답을 반환한다."""
    raw_match = re.search(r"(?:^|\n)\[원문\]\s*\n(.*)", prompt, flags=re.DOTALL)
    if raw_match is not None:
        return _mock_guidance(raw_match.group(1))

    input_match = re.search(r"(?:^|\n)\[입력\]\s*\n(.*)", prompt, flags=re.DOTALL)
    if input_match is not None:
        return _mock_brief(input_match.group(1))

    return ""


def _call_real(prompt: str) -> str:
    """실제 Claude API를 호출하여 응답 텍스트를 반환한다 (13주차 이후 사용, 실패 시 "")."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return ""

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key, timeout=CLAUDE_TIMEOUT_SEC)
        message = client.messages.create(
            model=CLAUDE_MODEL_NAME,
            max_tokens=CLAUDE_MAX_TOKENS,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        if not message.content:
            return ""
        first_block = message.content[0]
        return str(getattr(first_block, "text", "") or "")
    except (ImportError, OSError, ValueError, RuntimeError, LookupError, AttributeError):
        return ""


def _call_llm(prompt: str) -> str:
    """프롬프트를 받아 LLM 응답 문자열을 돌려준다 (LLM 호출 단일 지점).

    schema.md 5.1절에 따라 상수 USE_MOCK으로 목/실제 모드를 전환하며,
    오류 시 예외를 밖으로 내지 않고 빈 문자열("")을 반환한다.

    Args:
        prompt (str): LLM에 전달할 프롬프트 문자열.

    Returns:
        str: LLM 응답 문자열 (실패 시 "").

    Raises:
        없음
    """
    if not isinstance(prompt, str):
        return ""

    if USE_MOCK:
        return _mock_response(prompt)
    return _call_real(prompt)


def extract_guidance(transcript_text: str) -> dict:
    """컨퍼런스콜 텍스트에서 다음 분기 출하·가격 전망을 LLM으로 뽑아 guidance 형식으로 정리한다.

    Args:
        transcript_text (str): 분석할 컨퍼런스콜 원문 텍스트.

    Returns:
        dict: 추출 및 검증이 완료된 guidance 딕셔너리 (7개 키 고정, 순수 파이썬 기본 타입).

    Raises:
        없음: 빈 입력이나 파싱 실패, 규격 외 값은 예외 없이 status 및 기본값으로 처리한다.
    """
    result: dict = _new_default_guidance()

    # 1. 빈 입력(None, 공백뿐) 검사 -> LLM 호출 금지
    if transcript_text is None or not isinstance(transcript_text, str) or not transcript_text.strip():
        result["status"] = STATUS_EMPTY_INPUT
        return result

    # 2. 프롬프트 생성 및 _call_llm 호출
    prompt: str = f"{GUIDANCE_PROMPT_TEMPLATE}{transcript_text}"
    raw_response: str = _call_llm(prompt)

    if not isinstance(raw_response, str) or not raw_response.strip():
        result["status"] = STATUS_PARSE_ERROR
        return result

    # 3. 앞뒤 코드 블록 표시 제거 후 JSON 해석
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
        result["status"] = STATUS_PARSE_ERROR
        return result

    if not isinstance(parsed_data, dict):
        result["status"] = STATUS_PARSE_ERROR
        return result

    # 4. 기본값에 응답의 6개 키 값만 덮어쓰기
    for key in result:
        if key in parsed_data:
            result[key] = parsed_data[key]

    # 5. 필드별 검증 및 파이썬 기본 타입 강제 (schema.md 1.3절, 4.3절)
    if (
        not isinstance(result["price_outlook"], str)
        or result["price_outlook"] not in ALLOWED_PRICE_OUTLOOKS
    ):
        result["price_outlook"] = OUTLOOK_NA
    else:
        result["price_outlook"] = str(result["price_outlook"])

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

    if not _is_valid_quarter(result["target_quarter"]):
        result["target_quarter"] = None
    else:
        result["target_quarter"] = str(result["target_quarter"])

    hbm = result["hbm_comment"]
    if not isinstance(hbm, str):
        result["hbm_comment"] = ""
    else:
        result["hbm_comment"] = str(hbm)[:MAX_HBM_COMMENT_LEN]

    ev = result["evidence"]
    if not isinstance(ev, list):
        result["evidence"] = []
    else:
        result["evidence"] = [str(item) for item in ev if isinstance(item, str)][
            :MAX_EVIDENCE_COUNT
        ]

    result["status"] = STATUS_OK
    return result