"""[모듈 4] LLM (텍스트 입출력 전담).

    extract_guidance  컨콜 텍스트 -> 다음 분기 출하, 가격 전망(guidance dict)
    generate_brief    계산 결과 -> 개인투자자용 3~5문장 브리프

LLM 호출은 _call_llm 한 곳에서만 한다. .env에 ANTHROPIC_API_KEY가 있으면 실제 Claude API를 부르고,
없으면 규칙 기반 mock이 응답한다(USE_MOCK). mock 응답의 문장에는 "[MOCK] "이 붙는다.
LLM은 숫자를 계산하지 않는다. JSON 해석, 허용값 검사, 숫자 검사는 mock과 실제 응답에 똑같이 적용한다.
프롬프트 지시문은 prompts/ 폴더의 txt 파일에서 읽는다.
"""

import json
import logging
import math
import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"
USE_MOCK: bool = not (os.getenv(ANTHROPIC_API_KEY_ENV) or "").strip()
MOCK_PREFIX = "[MOCK] "

CLAUDE_MODEL_NAME = "claude-sonnet-5-5"
CLAUDE_MAX_TOKENS = 2048
CLAUDE_TIMEOUT_SEC = 20.0
# Sonnet 5.5는 thinking을 생략하면 적응형 사고가 켜져 느려지므로 가장 낮은 단계로 둔다.
# Sonnet 5.5에서 temperature, top_p는 400 오류라 보내지 않는다. 다른 모델로 바꾸면 이 값을 그 모델에 맞게 고친다
CLAUDE_THINKING: dict | None = {"type": "between_tools"}

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
GUIDANCE_MARKER = "[원문]"
BRIEF_MARKER = "[입력]"

STATUS_OK = "ok"
STATUS_EMPTY_INPUT = "empty_input"
STATUS_PARSE_ERROR = "parse_error"
OUTLOOK_UP = "상승"
OUTLOOK_FLAT = "보합"
OUTLOOK_DOWN = "하락"
OUTLOOK_NONE = "언급없음"
OUTLOOK_NA = "NA"
ALLOWED_PRICE_OUTLOOKS = (OUTLOOK_UP, OUTLOOK_FLAT, OUTLOOK_DOWN, OUTLOOK_NONE)
BIT_GROWTH_MIN = -50.0
BIT_GROWTH_MAX = 100.0
MAX_HBM_COMMENT_LEN = 100
MAX_EVIDENCE_COUNT = 3

FORECAST_STATUS_OK = "ok"
FORECAST_STATUS_INSUFFICIENT = "insufficient_history"
BRIEF_NO_DATA_MESSAGE = "대상 분기의 수출 자료가 아직 없어 매출을 추정할 수 없습니다."
BRIEF_INSUFFICIENT_MESSAGE = "비교할 과거 실적이 4개 분기보다 적어 매출을 추정할 수 없습니다."
FACT_UNAVAILABLE = "확인 불가"
FACT_KEYS = ("quarter", "estimate", "range", "qoq", "months", "ratio", "export_yoy", "anomaly", "consistency")
KRW_PER_TRILLION = 1e12
BRIEF_MIN_SENTENCES = 3
BRIEF_MAX_SENTENCES = 5
# 설명에 쓰는 고정 숫자: 3개월(분기 개월 수), 4개 분기(비율 기준 분기 수), 12개월(전년 동월 비교)
ALLOWED_EXTRA_NUMBERS = ("3", "4", "12")
BRIEF_BANNED_PHRASES = ("매수", "매도")
# LLM 응답이 형식을 어기거나 facts에 없는 숫자를 쓰면 이 문장 틀로 대신한다 (mock도 같은 틀을 쓴다)
BRIEF_TEMPLATES = (
    "{quarter} 예상 매출은 {estimate}({range})이며, 직전 분기 대비 {qoq} 변화가 예상됩니다.",
    "{months} 수출 자료에 최근 4개 분기 평균 비율({ratio})을 적용한 추정입니다.",
    "최근 월 이천, 청주 메모리 수출은 전년 동월 대비 {export_yoy}(이상치 판정: {anomaly})이며, "
    "가이던스 비교 결과는 {consistency}입니다.",
)

QUARTER_PATTERN = re.compile(r"[0-9]{4}Q[1-4]")
CODE_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)
# 문장 속 숫자 검사용. \d는 전각 숫자도 잡고 float()도 읽으므로 전각으로 쓴 숫자도 같은 값으로 비교된다
NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")
MOCK_SENTENCE_SPLIT = re.compile(r"(?<![0-9])\.(?![0-9])|\n+")
MOCK_QUARTER_PATTERN = re.compile(r"([0-9]{4})\s*년\s*([1-4])\s*분기")
MOCK_DRAM_PATTERN = re.compile(r"(?:D램|DRAM).*?(-?[0-9]+(?:\.[0-9]+)?)%", re.IGNORECASE)
MOCK_NAND_PATTERN = re.compile(r"(?:낸드|NAND).*?(-?[0-9]+(?:\.[0-9]+)?)%", re.IGNORECASE)
MOCK_HBM_PATTERN = re.compile(r"HBM", re.IGNORECASE)


def _read_prompt(filename: str) -> str:
    """prompts/ 폴더의 지시문을 읽는다. 표시 줄([원문], [입력])은 코드가 붙이므로 파일에 쓰지 않는다.

    Returns:
        앞뒤 공백을 지운 지시문.

    Raises:
        FileNotFoundError: 프롬프트 파일이 없을 때 (import할 때 바로 드러나게 한다).
    """
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8").strip()


GUIDANCE_INSTRUCTIONS = _read_prompt("guidance_extraction.txt")
BRIEF_INSTRUCTIONS = _read_prompt("brief_generation.txt")


# =============================================================================
# LLM 호출
# =============================================================================
def _call_llm(prompt: str) -> str:
    """프롬프트를 LLM에 보내고 응답 텍스트를 받는다 (LLM 호출의 유일한 지점).

    Args:
        prompt: 지시문 + 표시 줄 + 입력으로 된 프롬프트.

    Returns:
        응답 텍스트. 실패하면 "" (예외를 밖으로 내지 않는다).
    """
    if not isinstance(prompt, str):
        return ""
    if USE_MOCK:
        return _mock_response(prompt)
    return _call_real(prompt)


def _call_real(prompt: str) -> str:
    """Claude API(Messages)를 호출해 text 블록만 이어 붙여 돌려준다.

    실패 원인은 logging 경고로 남긴다(키는 남기지 않는다).

    Returns:
        응답 텍스트. 키가 없거나, anthropic 패키지가 없거나, API 오류(인증, 모델, 시간 초과 등)면 "".
    """
    api_key = (os.getenv(ANTHROPIC_API_KEY_ENV) or "").strip()
    if not api_key:
        return ""
    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic 패키지가 없어 LLM을 호출하지 못했습니다 (pip install -r requirements.txt)")
        return ""

    request: dict = {
        "model": CLAUDE_MODEL_NAME,
        "max_tokens": CLAUDE_MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
    }
    if CLAUDE_THINKING is not None:
        request["thinking"] = CLAUDE_THINKING
    try:
        client = anthropic.Anthropic(api_key=api_key, timeout=CLAUDE_TIMEOUT_SEC, max_retries=1)
        message = client.messages.create(**request)
    except (anthropic.AnthropicError, OSError, ValueError, TypeError) as exc:
        status = getattr(exc, "status_code", None)
        detail = str(getattr(exc, "message", "") or "")[:200]
        logger.warning(
            "LLM 호출 실패: %s%s%s",
            type(exc).__name__,
            f" (HTTP {status})" if status else "",
            f" {detail}" if detail else "",
        )
        return ""
    # Sonnet 5.5 응답은 thinking 블록으로 시작할 수 있어 content[0]이 아니라 text 블록을 골라 읽는다
    return "".join(getattr(block, "text", "") for block in message.content if getattr(block, "type", "") == "text")


def _strip_code_fence(text: str) -> str:
    """응답 앞뒤의 공백과 코드 블록 표시(```json ... ```)를 지운다.

    Returns:
        코드 블록 안쪽 문자열 (없으면 앞뒤 공백만 지운 문자열).
    """
    cleaned = text.strip()
    match = CODE_FENCE_PATTERN.match(cleaned)
    return match.group(1).strip() if match else cleaned


def _parse_json_object(text: object) -> dict | None:
    """LLM 응답에서 JSON 객체 하나를 꺼낸다. 앞뒤에 설명 문장이 붙어 있으면 첫 "{"부터 마지막 "}"까지 다시 읽는다.

    Returns:
        dict. JSON 객체를 찾지 못하면 None.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    cleaned = _strip_code_fence(text)
    candidates = [cleaned]
    if "{" in cleaned and "}" in cleaned:
        candidates.append(cleaned[cleaned.find("{"): cleaned.rfind("}") + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


# =============================================================================
# mock (API 키가 없을 때 _call_llm이 대신 부른다)
# =============================================================================
def _mock_response(prompt: str) -> str:
    """프롬프트의 마지막 표시 줄로 요청 종류를 구분해 mock 응답을 만든다.

    Returns:
        가이던스 또는 브리프 JSON 문자열. 표시 줄이 없으면 "".
    """
    for marker, responder in ((GUIDANCE_MARKER, _mock_guidance), (BRIEF_MARKER, _mock_brief)):
        separator = f"\n{marker}\n"
        if separator in prompt:
            return responder(prompt.rsplit(separator, 1)[1])
    return ""


def _mock_guidance(transcript_text: str) -> str:
    """컨콜 텍스트에 규칙을 적용해 가이던스 JSON을 만든다.

    가격은 "상승"만 있으면 상승, "하락"만 있으면 하락, 그 밖에는 언급없음. 출하 증가율은 D램(DRAM), 낸드(NAND)
    뒤에 처음 나오는 "N%". 분기는 "YYYY년 N분기". hbm_comment와 evidence 문장 앞에는 "[MOCK] "을 붙인다.

    Returns:
        guidance 응답 JSON 문자열 (키 6개).
    """
    sentences = [part.strip() for part in MOCK_SENTENCE_SPLIT.split(transcript_text) if part.strip()]
    has_up, has_down = OUTLOOK_UP in transcript_text, OUTLOOK_DOWN in transcript_text
    if has_up and not has_down:
        price_outlook = OUTLOOK_UP
    elif has_down and not has_up:
        price_outlook = OUTLOOK_DOWN
    else:
        price_outlook = OUTLOOK_NONE

    def first_number(pattern: re.Pattern) -> float | None:
        for sentence in sentences:
            match = pattern.search(sentence)
            if match:
                return float(match.group(1))
        return None

    quarter_match = MOCK_QUARTER_PATTERN.search(transcript_text)
    hbm_sentence = next((sentence for sentence in sentences if MOCK_HBM_PATTERN.search(sentence)), "")
    evidence = [
        f"{MOCK_PREFIX}{sentence}"
        for sentence in sentences
        if OUTLOOK_UP in sentence or OUTLOOK_DOWN in sentence or "%" in sentence
    ][:MAX_EVIDENCE_COUNT]
    payload = {
        "target_quarter": f"{quarter_match.group(1)}Q{quarter_match.group(2)}" if quarter_match else None,
        "dram_bit_growth_pct": first_number(MOCK_DRAM_PATTERN),
        "nand_bit_growth_pct": first_number(MOCK_NAND_PATTERN),
        "price_outlook": price_outlook,
        "hbm_comment": f"{MOCK_PREFIX}{hbm_sentence}"[:MAX_HBM_COMMENT_LEN] if hbm_sentence else "",
        "evidence": evidence,
    }
    return json.dumps(payload, ensure_ascii=False)


def _mock_brief(facts_json: str) -> str:
    """facts를 BRIEF_TEMPLATES에 채우고 문장마다 "[MOCK] "을 붙인다.

    Returns:
        {"sentences": [...]} JSON 문자열. facts를 읽을 수 없으면 "".
    """
    facts = _parse_json_object(facts_json)
    if facts is None:
        return ""
    values = {key: str(facts.get(key, FACT_UNAVAILABLE)) for key in FACT_KEYS}
    sentences = [f"{MOCK_PREFIX}{template.format(**values)}" for template in BRIEF_TEMPLATES]
    return json.dumps({"sentences": sentences}, ensure_ascii=False)


# =============================================================================
# extract_guidance
# =============================================================================
def extract_guidance(transcript_text: str) -> dict:
    """컨콜 텍스트에서 다음 분기 출하, 가격 전망을 LLM으로 뽑아 guidance dict로 정리한다.

    빈 입력이면 LLM을 부르지 않는다. 응답 값은 허용값과 범위를 검사하고, 벗어나면 기본값으로 둔다.

    Args:
        transcript_text: 직전 분기 컨콜 정리 텍스트 (없으면 "").

    Returns:
        guidance dict
            status ("ok", "empty_input", "parse_error"), target_quarter (str "YYYYQn" | None),
            dram_bit_growth_pct, nand_bit_growth_pct (float | None, -50~100),
            price_outlook ("상승", "보합", "하락", "언급없음", 추출 실패면 "NA"),
            hbm_comment (str, 100자 이내), evidence (list[str], 최대 3개).
        status가 "ok"가 아니면 나머지 키는 기본값(None, "NA", "", [])이다.

    Raises:
        없음.
    """
    result = {
        "status": STATUS_OK,
        "target_quarter": None,
        "dram_bit_growth_pct": None,
        "nand_bit_growth_pct": None,
        "price_outlook": OUTLOOK_NA,
        "hbm_comment": "",
        "evidence": [],
    }
    if not isinstance(transcript_text, str) or not transcript_text.strip():
        result["status"] = STATUS_EMPTY_INPUT
        return result

    parsed = _parse_json_object(_call_llm(f"{GUIDANCE_INSTRUCTIONS}\n\n{GUIDANCE_MARKER}\n{transcript_text.strip()}"))
    if parsed is None:
        result["status"] = STATUS_PARSE_ERROR
        return result

    quarter = parsed.get("target_quarter")
    if isinstance(quarter, str) and QUARTER_PATTERN.fullmatch(quarter):
        result["target_quarter"] = quarter
    for key in ("dram_bit_growth_pct", "nand_bit_growth_pct"):
        value = parsed.get(key)
        if _finite_number(value) is not None and BIT_GROWTH_MIN <= float(value) <= BIT_GROWTH_MAX:
            result[key] = float(value)
    outlook = parsed.get("price_outlook")
    if isinstance(outlook, str) and outlook in ALLOWED_PRICE_OUTLOOKS:
        result["price_outlook"] = outlook
    hbm_comment = parsed.get("hbm_comment")
    if isinstance(hbm_comment, str):
        result["hbm_comment"] = hbm_comment.strip()[:MAX_HBM_COMMENT_LEN]
    evidence = parsed.get("evidence")
    if isinstance(evidence, list):
        result["evidence"] = [item.strip() for item in evidence if isinstance(item, str) and item.strip()][
            :MAX_EVIDENCE_COUNT
        ]
    return result


# =============================================================================
# generate_brief
# =============================================================================
def generate_brief(forecast: dict, anomaly: dict, consistency: dict) -> str:
    """계산 결과와 근거를 개인투자자용 3~5문장 설명으로 바꾼다.

    forecast의 status가 "ok"가 아니면 LLM을 부르지 않고 안내 문장 하나를 돌려준다.
    응답이 문장 3~5개의 JSON이 아니거나, facts와 ALLOWED_EXTRA_NUMBERS에 없는 숫자가 있거나,
    투자 권유 표현이 있으면 BRIEF_TEMPLATES 문장으로 대신한다. "투자 권유 아님" 고지는 main이 붙인다.

    Args:
        forecast: estimate_revenue 결과.
        anomaly: detect_anomaly 결과 (없으면 {}).
        consistency: compare_guidance 결과 (없으면 {}).

    Returns:
        브리프 문자열 (문장을 공백 하나로 이음). "insufficient_history"면 BRIEF_INSUFFICIENT_MESSAGE,
        그 밖의 "ok"가 아닌 status면 BRIEF_NO_DATA_MESSAGE.

    Raises:
        없음.
    """
    status = forecast.get("status") if isinstance(forecast, dict) else None
    if status == FORECAST_STATUS_INSUFFICIENT:
        return BRIEF_INSUFFICIENT_MESSAGE
    if status != FORECAST_STATUS_OK:
        return BRIEF_NO_DATA_MESSAGE

    facts = build_brief_facts(forecast, anomaly, consistency)
    prompt = f"{BRIEF_INSTRUCTIONS}\n\n{BRIEF_MARKER}\n{json.dumps(facts, ensure_ascii=False)}"
    sentences = _parse_brief_sentences(_call_llm(prompt))
    if sentences is None or not _uses_only_fact_numbers(sentences, facts) or _has_banned_phrase(sentences):
        sentences = [template.format(**facts) for template in BRIEF_TEMPLATES]
    return " ".join(sentences)


def build_brief_facts(forecast: dict, anomaly: dict, consistency: dict) -> dict[str, str]:
    """세 결과 dict에서 LLM에 넘길 facts(표시용 문자열 9개)를 만든다. 화면에서도 같은 표기를 쓸 수 있다.

    Returns:
        FACT_KEYS를 모두 가진 새 dict. 값이 없으면 "확인 불가".
        예: {"quarter": "2026Q4", "estimate": "26.1조 원", "range": "24.4~27.8조 원", "qoq": "+16.5%",
             "months": "2개월", "ratio": "1.50", "export_yoy": "+40.0%", "anomaly": "정상", "consistency": "일치"}
    """
    forecast = forecast if isinstance(forecast, dict) else {}
    anomaly = anomaly if isinstance(anomaly, dict) else {}
    consistency = consistency if isinstance(consistency, dict) else {}
    lower, upper = _finite_number(forecast.get("lower_krw")), _finite_number(forecast.get("upper_krw"))
    months = forecast.get("months_available")
    ratio = _finite_number(forecast.get("ratio_used"))
    return {
        "quarter": _text_or_unavailable(forecast.get("quarter")),
        "estimate": _format_trillion(forecast.get("estimate_krw")),
        "range": (
            f"{lower / KRW_PER_TRILLION:.1f}~{upper / KRW_PER_TRILLION:.1f}조 원"
            if lower is not None and upper is not None
            else FACT_UNAVAILABLE
        ),
        "qoq": _format_signed_pct(forecast.get("qoq_change_pct")),
        "months": f"{months}개월" if isinstance(months, int) and not isinstance(months, bool) else FACT_UNAVAILABLE,
        "ratio": f"{ratio:.2f}" if ratio is not None else FACT_UNAVAILABLE,
        "export_yoy": _format_signed_pct(anomaly.get("yoy_pct")),
        "anomaly": _text_or_unavailable(anomaly.get("reason")),
        "consistency": _text_or_unavailable(consistency.get("status")),
    }


def _finite_number(value: object) -> float | None:
    """bool이 아닌 유한한 숫자를 float로 바꾼다.

    Returns:
        float 값. 숫자가 아니거나 bool, NaN, 무한대이면 None.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


def _text_or_unavailable(value: object) -> str:
    """비어 있지 않은 문자열이면 그대로 돌려준다.

    Returns:
        문자열 또는 "확인 불가".
    """
    return value if isinstance(value, str) and value.strip() else FACT_UNAVAILABLE


def _format_trillion(value: object) -> str:
    """원 단위 금액을 조 원 소수 첫째 자리로 바꾼다.

    Returns:
        "26.1조 원" 형식 문자열 또는 "확인 불가".
    """
    number = _finite_number(value)
    return f"{number / KRW_PER_TRILLION:.1f}조 원" if number is not None else FACT_UNAVAILABLE


def _format_signed_pct(value: object) -> str:
    """퍼센트 값을 부호를 붙여 소수 첫째 자리로 바꾼다 (-0.0%는 +0.0%로).

    Returns:
        "+16.5%" 형식 문자열 또는 "확인 불가".
    """
    number = _finite_number(value)
    if number is None:
        return FACT_UNAVAILABLE
    text = f"{number:+.1f}%"
    return "+0.0%" if text == "-0.0%" else text


def _parse_brief_sentences(raw_response: str) -> list[str] | None:
    """브리프 응답 {"sentences": [...]}에서 문장 목록을 꺼낸다.

    Returns:
        앞뒤 공백을 지운 문장 3~5개. 형식이 다르면 None.
    """
    parsed = _parse_json_object(raw_response)
    sentences = parsed.get("sentences") if parsed else None
    if (
        not isinstance(sentences, list)
        or not BRIEF_MIN_SENTENCES <= len(sentences) <= BRIEF_MAX_SENTENCES
        or any(not isinstance(item, str) or not item.strip() for item in sentences)
    ):
        return None
    return [item.strip() for item in sentences]


def _uses_only_fact_numbers(sentences: list[str], facts: dict[str, str]) -> bool:
    """문장 속 숫자가 모두 facts 값이나 ALLOWED_EXTRA_NUMBERS에 있는지 확인한다 (부호는 보지 않는다).

    Returns:
        모두 허용된 숫자면 True.
    """
    allowed = {float(token) for token in ALLOWED_EXTRA_NUMBERS}
    for value in facts.values():
        allowed.update(float(token) for token in NUMBER_PATTERN.findall(value))
    return all(float(token) in allowed for sentence in sentences for token in NUMBER_PATTERN.findall(sentence))


def _has_banned_phrase(sentences: list[str]) -> bool:
    """문장에 투자 권유 표현(BRIEF_BANNED_PHRASES)이 있는지 확인한다.

    Returns:
        하나라도 있으면 True.
    """
    return any(phrase in sentence for sentence in sentences for phrase in BRIEF_BANNED_PHRASES)
