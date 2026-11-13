""" 함수: fetch_regional_exports (작성: 신해성).

관세청_시군구별 품목별 수출입실적 (공공데이터포털 15134343, XML)에서 이천시, 청주시가 속한 시도의
HS 854232 월별 수출입 실적을 가공 없이 받아온다. 

- 요청 주소, 요청 변수(serviceKey, strtYymm, endYymm, HsSgn, sidoCd)는 포털 명세에서 확인한 값이다.
- [확인 필요] 응답 필드 이름, 시도 코드, 조회 기간 한도, numOfRows/pageNo 지원 여부는 활용신청 후
  실제 응답으로 확정한다. 응답 필드 이름이 정해지면 clean_exports의 RAW_COLUMN_MAP을 같이 고친다
  (이 함수는 열 이름을 바꾸지 않는다).
- data_loader.py로 합칠 때: 아래 load_dotenv() 호출은 강민규 코드(fetch_fx_rates)에도 있으므로 한 번만 둔다.
"""

import os
import xml.etree.ElementTree as ET
from datetime import date

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

CUSTOMS_API_URL: str = (
    "https://apis.data.go.kr/1220000/sigunguperprlstperacrs/getSigunguPerPrlstPerAcrs"
)
CUSTOMS_API_KEY_ENV: str = "CUSTOMS_API_KEY"  # 공공데이터포털 "일반 인증키(Decoding)" 값을 넣는다
CUSTOMS_API_ERROR_PREFIX: str = "관세청 API 호출 실패"
CUSTOMS_HS_CODE: str = "854232"  # 메모리 반도체 (HS 6단위)
# 대상 지역 -> 그 지역이 속한 시도 코드. API가 시도 단위로만 요청을 받으므로 시도별로 받고,
# 이천시, 청주시만 남기는 일은 clean_exports(ALLOWED_REGIONS)가 한다.
# [확인 필요] 관세청조회코드 xlsx의 시도 코드. 2026-07-01부터 일부 시군구 코드가 바뀌었다고 공지됨
CUSTOMS_REGION_SIDO_CODES: dict[str, str] = {"이천시": "41", "청주시": "43"}
CUSTOMS_MAX_MONTHS_PER_REQUEST: int = 12  # [확인 필요] 명세 예시가 12개월 범위
CUSTOMS_PAGE_SIZE: int = 1000  # [확인 필요] 페이지 변수를 무시하는 API면 첫 페이지에 전부 온다
CUSTOMS_MAX_PAGES: int = 100  # 페이지 반복이 끝나지 않는 응답을 막는 안전장치
CUSTOMS_SUCCESS_CODES: tuple[str, ...] = ("00", "000")
CUSTOMS_NO_DATA_CODES: tuple[str, ...] = ("03",)  # 공공데이터포털 NODATA_ERROR
CUSTOMS_GATEWAY_ERROR_TAG: str = "OpenAPI_ServiceResponse"  # 인증키 오류 등 게이트웨이 오류 응답
CUSTOMS_REQUEST_TIMEOUT_SEC: int = 10
CUSTOMS_FORMAT_ERROR_REASON: str = "응답 형식 오류"
COLLECTED_AT_COLUMN: str = "collected_at"
COLLECTED_AT_FORMAT: str = "%Y-%m-%d"
MONTHS_PER_YEAR: int = 12


def fetch_regional_exports(start_ym: str, end_ym: str) -> pd.DataFrame:
    """관세청 API에서 이천시, 청주시 메모리 반도체(HS 854232)의 월별 수출액을 가공 없이 받아온다.

    대상 지역이 속한 시도(경기도, 충청북도)를 CUSTOMS_MAX_MONTHS_PER_REQUEST개월씩 나눠 요청하고,
    응답의 item을 열 이름 그대로 이어 붙인 뒤 collected_at(실행한 날짜) 열을 더한다.
    검사 순서는 월 인자 -> API 키 -> 관세청 요청이며, 앞 단계에서 실패하면 요청하지 않는다.

    Args:
        start_ym: 조회 시작 월. "YYYY-MM" 문자열 (예: "2021-01").
        end_ym: 조회 끝 월. "YYYY-MM" 문자열이며 start_ym과 같거나 늦어야 한다.

    Returns:
        raw_exports 표. 열은 관세청 응답 필드 이름 그대로(값은 문자열) + collected_at("YYYY-MM-DD").
        시도 안의 다른 시군구 행, 합계 행도 그대로 둔다(거르는 것은 clean_exports).
        응답에 행이 없으면 collected_at 열만 있는 0행 표를 돌려준다.

    Raises:
        ValueError: "월 형식 오류: <값>" 월 인자가 "YYYY-MM"(ASCII 숫자, 월 01~12)이 아닌 경우.
        ValueError: "시작월이 끝월보다 늦습니다: <start_ym> > <end_ym>"
        RuntimeError: "관세청 API 키가 없습니다" 환경변수 CUSTOMS_API_KEY가 없거나 공백뿐인 경우.
        RuntimeError: "관세청 API 호출 실패: <지역>, <원인>" 연결 오류, 시간 초과, HTTP 오류,
            응답 속 오류 코드, XML이 아닌 응답. <원인>에는 URL, API 키, str(e)를 넣지 않는다.
    """
    _validate_months(start_ym, end_ym)
    api_key: str = _get_customs_api_key()
    collected_at: str = date.today().strftime(COLLECTED_AT_FORMAT)

    rows: list[dict[str, str]] = []
    requested_sido_codes: set[str] = set()
    for region, sido_code in CUSTOMS_REGION_SIDO_CODES.items():
        # 두 지역이 같은 시도에 있으면 같은 자료를 두 번 받게 되므로 한 번만 요청한다
        if sido_code in requested_sido_codes:
            continue
        requested_sido_codes.add(sido_code)
        for chunk_start, chunk_end in _month_chunks(start_ym, end_ym):
            rows.extend(
                _fetch_customs_rows(api_key, region, sido_code, chunk_start, chunk_end)
            )

    return _to_raw_exports_table(rows, collected_at)


def _validate_months(start_ym: str, end_ym: str) -> None:
    """월 인자 두 개를 검사한다. 두 값의 형식 검사를 먼저 끝내고 그다음 순서를 검사한다.

    Args:
        start_ym: 조회 시작 월 ("YYYY-MM").
        end_ym: 조회 끝 월 ("YYYY-MM").

    Returns:
        None. 문제가 없으면 아무것도 돌려주지 않는다.

    Raises:
        ValueError: 형식이 틀리면 "월 형식 오류: <값>",
            시작월이 끝월보다 늦으면 "시작월이 끝월보다 늦습니다: <start_ym> > <end_ym>".
    """
    for value in (start_ym, end_ym):
        # 전각 숫자("２０２６")는 isdecimal()을 통과하므로 isascii()로 한정한다 (schema.md 1.1)
        if (
            not isinstance(value, str)
            or len(value) != 7
            or not value.isascii()
            or value[4] != "-"
            or not value[:4].isdecimal()
            or not value[5:].isdecimal()
            or not 1 <= int(value[5:]) <= MONTHS_PER_YEAR
        ):
            raise ValueError(f"월 형식 오류: {value}")

    # 형식을 통과한 "YYYY-MM"은 문자열 순서와 시간 순서가 같다
    if start_ym > end_ym:
        raise ValueError(f"시작월이 끝월보다 늦습니다: {start_ym} > {end_ym}")


def _get_customs_api_key() -> str:
    """환경변수에서 관세청(공공데이터포털) API 키를 읽는다.

    검사는 앞뒤 공백을 뺀 값으로 하고, 돌려주는 값은 환경변수에 적힌 원래 값이다.

    Args:
        없음.

    Returns:
        API 키 문자열.

    Raises:
        RuntimeError: "관세청 API 키가 없습니다" 키가 없거나 공백뿐인 경우.
    """
    api_key: str | None = os.getenv(CUSTOMS_API_KEY_ENV)
    if not api_key or not api_key.strip():
        raise RuntimeError("관세청 API 키가 없습니다")
    return api_key


def _month_chunks(start_ym: str, end_ym: str) -> list[tuple[str, str]]:
    """조회 기간을 CUSTOMS_MAX_MONTHS_PER_REQUEST개월 이하 구간으로 나눈다.

    Args:
        start_ym: 검사를 통과한 시작 월 ("YYYY-MM").
        end_ym: 검사를 통과한 끝 월 ("YYYY-MM").

    Returns:
        (구간 시작, 구간 끝) 목록. 값은 요청 변수 형식 "YYYYMM"이고 오래된 구간부터 담는다.

    Raises:
        없음.
    """
    start_index: int = int(start_ym[:4]) * MONTHS_PER_YEAR + int(start_ym[5:]) - 1
    end_index: int = int(end_ym[:4]) * MONTHS_PER_YEAR + int(end_ym[5:]) - 1

    chunks: list[tuple[str, str]] = []
    for chunk_start in range(start_index, end_index + 1, CUSTOMS_MAX_MONTHS_PER_REQUEST):
        chunk_end: int = min(chunk_start + CUSTOMS_MAX_MONTHS_PER_REQUEST - 1, end_index)
        chunks.append((_index_to_param_ym(chunk_start), _index_to_param_ym(chunk_end)))
    return chunks


def _index_to_param_ym(month_index: int) -> str:
    """연 x 12 + 월 - 1 꼴의 월 번호를 요청 변수 형식 "YYYYMM"으로 바꾼다.

    Args:
        month_index: 월 번호 (예: 2026년 1월 = 2026 * 12 + 0).

    Returns:
        "YYYYMM" 문자열.

    Raises:
        없음.
    """
    year, month_offset = divmod(month_index, MONTHS_PER_YEAR)
    return f"{year:04d}{month_offset + 1:02d}"


def _fetch_customs_rows(
    api_key: str, region: str, sido_code: str, strt_yymm: str, end_yymm: str
) -> list[dict[str, str]]:
    """한 시도, 한 기간 구간의 item을 마지막 페이지까지 받아 모은다.

    totalCount가 없으면 페이지 변수를 쓰지 않는 API로 보고 첫 페이지에서 멈춘다.

    Args:
        api_key: API 키. 요청 변수에만 넣고 다른 곳에 쓰지 않는다.
        region: 오류 메시지에 쓸 대상 지역 이름 (예: "이천시").
        sido_code: 요청할 시도 코드.
        strt_yymm: 구간 시작 월 ("YYYYMM").
        end_yymm: 구간 끝 월 ("YYYYMM").

    Returns:
        응답 순서대로 모은 item dict 목록 ({응답 필드 이름: 문자열 값}).

    Raises:
        RuntimeError: "관세청 API 호출 실패: <지역>, <원인>" (_request_customs_xml, _parse_customs_page에서 발생).
    """
    rows: list[dict[str, str]] = []
    for page_no in range(1, CUSTOMS_MAX_PAGES + 1):
        params: dict[str, str | int] = {
            "serviceKey": api_key,
            "strtYymm": strt_yymm,
            "endYymm": end_yymm,
            "HsSgn": CUSTOMS_HS_CODE,
            "sidoCd": sido_code,
            "numOfRows": CUSTOMS_PAGE_SIZE,
            "pageNo": page_no,
        }
        page_rows, total_count = _parse_customs_page(
            _request_customs_xml(params, region), region
        )
        rows.extend(page_rows)
        if total_count is None or not page_rows or len(rows) >= total_count:
            return rows

    raise _customs_api_error(region, "페이지 수 초과")


def _request_customs_xml(params: dict[str, str | int], region: str) -> ET.Element:
    """관세청 API에 GET 요청을 보내고 응답 본문을 XML로 해석한다.

    params에는 API 키가 들어 있고, requests 예외 문자열에는 키가 든 URL이 담기므로
    오류 메시지에는 예외 클래스 이름이나 상태 코드만 쓰고 from None으로 올린다.

    Args:
        params: 요청 변수 (API 키 포함).
        region: 오류 메시지에 쓸 대상 지역 이름.

    Returns:
        XML 최상위 요소.

    Raises:
        RuntimeError: "관세청 API 호출 실패: <지역>, <예외 클래스 이름>" 연결 오류, 시간 초과 등.
        RuntimeError: "관세청 API 호출 실패: <지역>, HTTP <상태 코드>" HTTP 4xx, 5xx.
        RuntimeError: "관세청 API 호출 실패: <지역>, 응답 형식 오류" 본문이 XML이 아닌 경우.
    """
    try:
        response: requests.Response = requests.get(
            CUSTOMS_API_URL, params=params, timeout=CUSTOMS_REQUEST_TIMEOUT_SEC
        )
    except requests.RequestException as exc:
        raise _customs_api_error(region, type(exc).__name__) from None

    try:
        response.raise_for_status()
    except requests.HTTPError:
        raise _customs_api_error(region, f"HTTP {response.status_code}") from None

    try:
        return ET.fromstring(response.content)
    except ET.ParseError:
        raise _customs_api_error(region, CUSTOMS_FORMAT_ERROR_REASON) from None


def _parse_customs_page(
    root: ET.Element, region: str
) -> tuple[list[dict[str, str]], int | None]:
    """관세청 응답 한 페이지를 검사하고 item 목록과 전체 건수를 꺼낸다.

    Args:
        root: _request_customs_xml이 돌려준 XML 최상위 요소.
        region: 오류 메시지에 쓸 대상 지역 이름.

    Returns:
        (item dict 목록, totalCount 정수 또는 None). 데이터 없음 결과 코드이면 ([], 0).
        item dict는 {자식 요소 이름: 텍스트}이며 텍스트가 없으면 "".

    Raises:
        RuntimeError: "관세청 API 호출 실패: <지역>, <결과 코드> <메시지>" 오류 결과 코드, 게이트웨이 오류 응답.
        RuntimeError: "관세청 API 호출 실패: <지역>, 응답 형식 오류" header/resultCode가 없는 경우.
    """
    if root.tag == CUSTOMS_GATEWAY_ERROR_TAG:
        # 인증키 미등록, 트래픽 초과 같은 게이트웨이 오류는 HTTP 200에 이 형식으로 온다
        reason_code: str = (root.findtext("./cmmMsgHeader/returnReasonCode") or "").strip()
        auth_message: str = (root.findtext("./cmmMsgHeader/returnAuthMsg") or "").strip()
        raise _customs_api_error(
            region, f"{reason_code} {auth_message}".strip() or CUSTOMS_FORMAT_ERROR_REASON
        )

    result_code: str | None = root.findtext("./header/resultCode")
    if result_code is None:
        raise _customs_api_error(region, CUSTOMS_FORMAT_ERROR_REASON)

    result_code = result_code.strip()
    if result_code in CUSTOMS_NO_DATA_CODES:
        return [], 0
    if result_code not in CUSTOMS_SUCCESS_CODES:
        result_message: str = (root.findtext("./header/resultMsg") or "").strip()
        raise _customs_api_error(region, f"{result_code} {result_message}".strip())

    page_rows: list[dict[str, str]] = [
        {child.tag: child.text or "" for child in item}
        for item in root.findall("./body/items/item")
    ]
    total_text: str = (root.findtext("./body/totalCount") or "").strip()
    total_count: int | None = int(total_text) if total_text.isdecimal() else None
    return page_rows, total_count


def _customs_api_error(region: str, reason: str) -> RuntimeError:
    """관세청 호출 실패 예외 객체를 만든다. raise _customs_api_error(...) from None 으로 쓴다.

    Args:
        region: 요청하던 대상 지역 이름.
        reason: 실패 원인. 예외 클래스 이름, "HTTP <상태 코드>", "<결과 코드> <메시지>",
            CUSTOMS_FORMAT_ERROR_REASON 중 하나. URL, API 키, str(e)는 넣지 않는다.

    Returns:
        메시지가 "관세청 API 호출 실패: <지역>, <reason>"인 RuntimeError.

    Raises:
        없음. 예외를 만들어 돌려줄 뿐 발생시키지 않는다.
    """
    return RuntimeError(f"{CUSTOMS_API_ERROR_PREFIX}: {region}, {reason}")


def _to_raw_exports_table(rows: list[dict[str, str]], collected_at: str) -> pd.DataFrame:
    """모은 item을 raw_exports 표로 바꾸고 collected_at 열을 더한다.

    열 이름 바꾸기, 형식 변환, 필터는 하지 않는다 (clean_exports의 역할).

    Args:
        rows: _fetch_customs_rows가 모은 item dict 목록.
        collected_at: 이 함수를 실행한 날짜 ("YYYY-MM-DD").

    Returns:
        응답 필드 열 + collected_at 열을 가진 표. rows가 비었으면 collected_at 열만 있는 0행 표.

    Raises:
        없음.
    """
    table: pd.DataFrame = pd.DataFrame(rows)
    table[COLLECTED_AT_COLUMN] = collected_at
    return table
