"""[모듈 1] 데이터 수집과 적재.

    fetch_regional_exports  관세청 API -> 이천시, 청주시가 속한 시도의 HS 854232 월별 수출 원자료
    fetch_fx_rates          한국은행 ECOS API -> 일별 원/달러 환율
    load_actuals            팀이 DART 공시로 작성한 분기 확정 매출 CSV

API 키는 .env에서 읽는다. 키가 든 요청 URL이 오류 메시지나 traceback에 남지 않도록,
API 오류는 원인(예외 이름, HTTP 상태, 결과 코드)만 담은 RuntimeError로 바꿔 from None으로 올린다.
"""

import math
import os
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

REQUEST_TIMEOUT_SEC = 10
DATE_FORMAT = "%Y-%m-%d"
MONTHS_PER_YEAR = 12
FORMAT_ERROR = "응답 형식 오류"
# ASCII 숫자만 인정한다. \d와 isdecimal()은 전각 숫자("２０２６")도 통과시킨다
YM_PATTERN = re.compile(r"[0-9]{4}-(0[1-9]|1[0-2])")
DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
QUARTER_PATTERN = re.compile(r"[0-9]{4}Q[1-4]")

# 관세청_시군구별 품목별 수출입실적 (공공데이터포털 15134343, XML)
CUSTOMS_API_URL = "https://apis.data.go.kr/1220000/sigunguperprlstperacrs/getSigunguPerPrlstPerAcrs"
CUSTOMS_API_KEY_ENV = "CUSTOMS_API_KEY"
CUSTOMS_HS_CODE = "854232"
# 대상 지역 -> 그 지역이 속한 시도 코드. API가 시도 단위로만 받으므로 시도 전체를 받고 지역 필터는 clean_exports가 한다
CUSTOMS_SIDO_CODES = {"이천시": "41", "청주시": "43"}
CUSTOMS_MAX_MONTHS_PER_REQUEST = 12
CUSTOMS_PAGE_SIZE = 1000
CUSTOMS_MAX_PAGES = 100
CUSTOMS_SUCCESS_CODES = ("00", "000")
CUSTOMS_NO_DATA_CODES = ("03",)
CUSTOMS_GATEWAY_ERROR_TAG = "OpenAPI_ServiceResponse"

# 한국은행 ECOS: 731Y001(주요국 통화의 대원화 환율), 0000001(원/미국달러 매매기준율), D(일별)
ECOS_BASE_URL = "https://ecos.bok.or.kr/api/StatisticSearch"
ECOS_API_KEY_ENV = "ECOS_API_KEY"
ECOS_STAT_CODE = "731Y001"
ECOS_ITEM_CODE = "0000001"
ECOS_CYCLE = "D"
ECOS_PAGE_SIZE = 1000
ECOS_NO_DATA_CODE = "INFO-200"

FX_COLUMNS = ("date", "usdkrw")
ACTUALS_COLUMNS = ("quarter", "revenue_krw", "announced_date")
COLLECTED_AT_COLUMN = "collected_at"

# 프로세스가 시작된 뒤 보낸 요청 수 (일일 호출 한도 확인용, backend.py가 실행 전후 차이를 보여 준다)
API_CALLS = {"관세청": 0, "ECOS": 0}


# =============================================================================
# 관세청 수출
# =============================================================================
def fetch_regional_exports(start_ym: str, end_ym: str, regions: tuple[str, ...] | None = None) -> pd.DataFrame:
    """관세청 API에서 이천시, 청주시가 속한 시도의 HS 854232 월별 수출입 실적을 가공 없이 받는다.

    시도별로 CUSTOMS_MAX_MONTHS_PER_REQUEST개월씩 나눠 요청하고, 페이지가 나뉘면 끝까지 받는다.
    요청 수 = 시도 수 x 12개월 구간 수 (페이지가 나뉘지 않을 때).

    Args:
        start_ym: 조회 시작 월 "YYYY-MM".
        end_ym: 조회 끝 월 "YYYY-MM" (start_ym 이상).
        regions: 받을 지역 (기본: CUSTOMS_SIDO_CODES 전부). API 점검처럼 요청을 줄일 때만 넘긴다.

    Returns:
        raw_exports 표. 열은 관세청 응답 필드 이름 그대로(값은 문자열) + collected_at("YYYY-MM-DD", 실행일).
        시도 안의 다른 시군구 행도 그대로 있다. 응답에 행이 없으면 collected_at 열만 있는 0행 표.

    Raises:
        ValueError: "월 형식 오류: <값>", "시작월이 끝월보다 늦습니다: <start_ym> > <end_ym>"
        RuntimeError: "관세청 API 키가 없습니다", "관세청 API 호출 실패: <지역>, <원인>"
    """
    for value in (start_ym, end_ym):
        if not isinstance(value, str) or not YM_PATTERN.fullmatch(value):
            raise ValueError(f"월 형식 오류: {value}")
    if start_ym > end_ym:
        raise ValueError(f"시작월이 끝월보다 늦습니다: {start_ym} > {end_ym}")

    api_key = _get_api_key(CUSTOMS_API_KEY_ENV, "관세청 API")
    rows: list[dict[str, str]] = []
    requested: set[str] = set()
    for region, sido_code in CUSTOMS_SIDO_CODES.items():
        if sido_code in requested or (regions is not None and region not in regions):
            continue
        requested.add(sido_code)
        for chunk_start, chunk_end in _month_chunks(start_ym, end_ym):
            rows.extend(_fetch_customs_rows(api_key, region, sido_code, chunk_start, chunk_end))

    table = pd.DataFrame(rows)
    table[COLLECTED_AT_COLUMN] = date.today().strftime(DATE_FORMAT)
    return table


def _month_chunks(start_ym: str, end_ym: str) -> list[tuple[str, str]]:
    """조회 기간을 CUSTOMS_MAX_MONTHS_PER_REQUEST개월 이하 구간으로 나눈다.

    Returns:
        (구간 시작, 구간 끝) 목록. 값은 요청 변수 형식 "YYYYMM"이며 오래된 구간부터.
    """
    def to_index(ym: str) -> int:
        return int(ym[:4]) * MONTHS_PER_YEAR + int(ym[5:]) - 1

    def to_param(index: int) -> str:
        year, month_offset = divmod(index, MONTHS_PER_YEAR)
        return f"{year:04d}{month_offset + 1:02d}"

    start, end = to_index(start_ym), to_index(end_ym)
    return [
        (to_param(first), to_param(min(first + CUSTOMS_MAX_MONTHS_PER_REQUEST - 1, end)))
        for first in range(start, end + 1, CUSTOMS_MAX_MONTHS_PER_REQUEST)
    ]


def _fetch_customs_rows(
    api_key: str, region: str, sido_code: str, strt_yymm: str, end_yymm: str
) -> list[dict[str, str]]:
    """한 시도, 한 기간 구간의 item을 마지막 페이지까지 받아 모은다.

    totalCount가 없으면 페이지 변수를 쓰지 않는 응답으로 보고 첫 페이지에서 멈춘다.

    Returns:
        응답 순서대로 모은 item dict 목록 ({응답 필드 이름: 문자열 값}).

    Raises:
        RuntimeError: "관세청 API 호출 실패: <지역>, <원인>"
    """
    error_prefix = f"관세청 API 호출 실패: {region}, "
    rows: list[dict[str, str]] = []
    for page_no in range(1, CUSTOMS_MAX_PAGES + 1):
        params = {
            "serviceKey": api_key,
            "strtYymm": strt_yymm,
            "endYymm": end_yymm,
            "HsSgn": CUSTOMS_HS_CODE,
            "sidoCd": sido_code,
            "numOfRows": CUSTOMS_PAGE_SIZE,
            "pageNo": page_no,
        }
        response = _http_get(CUSTOMS_API_URL, params, error_prefix)
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError:
            raise RuntimeError(error_prefix + FORMAT_ERROR) from None

        page_rows, total_count = _parse_customs_page(root, error_prefix)
        rows.extend(page_rows)
        if total_count is None or not page_rows or len(rows) >= total_count:
            return rows
    raise RuntimeError(error_prefix + "페이지 수 초과")


def _parse_customs_page(root: ET.Element, error_prefix: str) -> tuple[list[dict[str, str]], int | None]:
    """관세청 XML 응답 한 페이지에서 item 목록과 전체 건수를 꺼낸다.

    Returns:
        (item dict 목록, totalCount 또는 None). 데이터 없음 결과 코드이면 ([], 0).

    Raises:
        RuntimeError: 오류 결과 코드, 인증키 오류 같은 게이트웨이 오류 응답, header가 없는 응답.
    """
    if root.tag == CUSTOMS_GATEWAY_ERROR_TAG:
        code = (root.findtext("./cmmMsgHeader/returnReasonCode") or "").strip()
        message = (root.findtext("./cmmMsgHeader/returnAuthMsg") or "").strip()
        raise RuntimeError(error_prefix + (f"{code} {message}".strip() or FORMAT_ERROR))

    result_code = (root.findtext("./header/resultCode") or "").strip()
    if not result_code:
        raise RuntimeError(error_prefix + FORMAT_ERROR)
    if result_code in CUSTOMS_NO_DATA_CODES:
        return [], 0
    if result_code not in CUSTOMS_SUCCESS_CODES:
        message = (root.findtext("./header/resultMsg") or "").strip()
        raise RuntimeError(error_prefix + f"{result_code} {message}".strip())

    items = [
        {child.tag: (child.text or "").strip() for child in item}
        for item in root.findall("./body/items/item")
    ]
    total_text = (root.findtext("./body/totalCount") or "").strip()
    return items, int(total_text) if total_text.isascii() and total_text.isdigit() else None


# =============================================================================
# ECOS 환율
# =============================================================================
def fetch_fx_rates(start_date: str, end_date: str) -> pd.DataFrame:
    """한국은행 ECOS API에서 일별 원/달러 매매기준율을 받는다.

    Args:
        start_date: 조회 시작일 "YYYY-MM-DD".
        end_date: 조회 끝일 "YYYY-MM-DD" (start_date 이상).

    Returns:
        fx 표 (date: str "YYYY-MM-DD", usdkrw: float64). date 오름차순, 같은 날짜는 마지막 값만 남긴다.
        주말, 공휴일은 행이 없고 자료가 없으면 dtype을 지정한 0행 표.

    Raises:
        ValueError: "날짜 형식 오류: <값>", "시작일이 끝일보다 늦습니다: <start_date> > <end_date>"
        RuntimeError: "ECOS API 키가 없습니다", "ECOS API 호출 실패: <원인>"
    """
    for value in (start_date, end_date):
        if not isinstance(value, str) or not DATE_PATTERN.fullmatch(value) or _to_date(value) is None:
            raise ValueError(f"날짜 형식 오류: {value}")
    if start_date > end_date:
        raise ValueError(f"시작일이 끝일보다 늦습니다: {start_date} > {end_date}")

    api_key = _get_api_key(ECOS_API_KEY_ENV, "ECOS API")
    rows: list[dict] = []
    first_row = 1
    while True:
        last_row = first_row + ECOS_PAGE_SIZE - 1
        url = (
            f"{ECOS_BASE_URL}/{api_key}/json/kr/{first_row}/{last_row}/"
            f"{ECOS_STAT_CODE}/{ECOS_CYCLE}/{start_date.replace('-', '')}/{end_date.replace('-', '')}/"
            f"{ECOS_ITEM_CODE}"
        )
        response = _http_get(url, None, "ECOS API 호출 실패: ")
        try:
            payload = response.json()
        except ValueError:
            raise RuntimeError(f"ECOS API 호출 실패: {FORMAT_ERROR}") from None

        page = _parse_ecos_page(payload)
        if page is None:
            break
        page_rows, total_count = page
        rows.extend(row for row in page_rows if isinstance(row, dict))
        if not page_rows or len(rows) >= total_count:
            break
        first_row += ECOS_PAGE_SIZE

    return _to_fx_table(rows)


def _parse_ecos_page(payload: object) -> tuple[list, int] | None:
    """ECOS JSON 응답 한 페이지에서 row 목록과 전체 행 수를 꺼낸다.

    Returns:
        (row 목록, list_total_count). 결과 코드가 INFO-200(데이터 없음)이면 None.

    Raises:
        RuntimeError: "ECOS API 호출 실패: <CODE> <MESSAGE>" 또는 응답 구조가 다를 때 "응답 형식 오류".
    """
    if not isinstance(payload, dict):
        raise RuntimeError(f"ECOS API 호출 실패: {FORMAT_ERROR}")

    # ECOS는 HTTP 200에도 RESULT 코드로 실패를 알린다(INFO-100 인증키 오류 등). INFO-200만 데이터 없음이다
    if "RESULT" in payload:
        result = payload["RESULT"]
        if not isinstance(result, dict) or "CODE" not in result:
            raise RuntimeError(f"ECOS API 호출 실패: {FORMAT_ERROR}")
        if result["CODE"] == ECOS_NO_DATA_CODE:
            return None
        raise RuntimeError(f"ECOS API 호출 실패: {result['CODE']} {result.get('MESSAGE', '')}".strip())

    statistic = payload.get("StatisticSearch")
    if not isinstance(statistic, dict):
        raise RuntimeError(f"ECOS API 호출 실패: {FORMAT_ERROR}")
    total_count = str(statistic.get("list_total_count", ""))
    page_rows = statistic.get("row")
    if not (total_count.isascii() and total_count.isdigit()) or not isinstance(page_rows, list):
        raise RuntimeError(f"ECOS API 호출 실패: {FORMAT_ERROR}")
    return page_rows, int(total_count)


def _to_fx_table(rows: list[dict]) -> pd.DataFrame:
    """ECOS row 목록을 fx 표로 바꾼다. 날짜나 값이 잘못됐거나 0 이하인 행은 뺀다.

    Returns:
        fx 표 (date 오름차순). 유효한 행이 없으면 dtype을 지정한 0행 표.
    """
    if not rows:
        return _empty_fx_table()

    dates = pd.to_datetime(
        pd.Series([row.get("TIME") for row in rows], dtype="object"), format="%Y%m%d", errors="coerce"
    )
    values = pd.to_numeric(pd.Series([row.get("DATA_VALUE") for row in rows], dtype="object"), errors="coerce")
    table = pd.DataFrame({"date": dates.dt.strftime(DATE_FORMAT), "usdkrw": values.astype("float64")})
    valid = dates.notna() & values.notna() & (values > 0)
    if not valid.any():
        return _empty_fx_table()
    return (
        table.loc[valid, list(FX_COLUMNS)]
        .drop_duplicates("date", keep="last")
        .sort_values("date")
        .reset_index(drop=True)
    )


def _empty_fx_table() -> pd.DataFrame:
    """dtype을 지정한 0행 fx 표를 만든다 (빈 표를 저장 표와 합쳐도 usdkrw가 object로 바뀌지 않게).

    Returns:
        열이 (date, usdkrw)인 0행 DataFrame.
    """
    return pd.DataFrame({"date": pd.Series(dtype=str), "usdkrw": pd.Series(dtype="float64")})


# =============================================================================
# 공통: API 키, HTTP 요청
# =============================================================================
def _get_api_key(env_name: str, api_name: str) -> str:
    """환경변수에서 API 키를 읽는다.

    Returns:
        앞뒤 공백을 지운 API 키.

    Raises:
        RuntimeError: "<api_name> 키가 없습니다" 키가 없거나 공백뿐인 경우.
    """
    api_key = (os.getenv(env_name) or "").strip()
    if not api_key:
        raise RuntimeError(f"{api_name} 키가 없습니다")
    return api_key


def _http_get(url: str, params: dict | None, error_prefix: str) -> requests.Response:
    """GET 요청을 보내고 HTTP 오류를 확인한다.

    requests 예외 문자열에는 키가 든 URL이 담기므로 메시지에는 예외 이름과 상태 코드만 쓴다.

    Returns:
        상태 코드가 정상인 requests.Response.

    Raises:
        RuntimeError: "<error_prefix><예외 클래스 이름>" 또는 "<error_prefix>HTTP <상태 코드>"
    """
    API_CALLS["관세청" if url.startswith(CUSTOMS_API_URL) else "ECOS"] += 1
    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SEC)
    except requests.RequestException as exc:
        raise RuntimeError(error_prefix + type(exc).__name__) from None
    if not response.ok:
        raise RuntimeError(error_prefix + f"HTTP {response.status_code}")
    return response


# =============================================================================
# 분기 확정 매출 (팀 작성 CSV)
# =============================================================================
def load_actuals(filepath: str) -> pd.DataFrame:
    """분기 확정 매출 CSV(data/actuals.csv)를 검증해 actuals 표로 읽는다.

    잘못된 행은 지우지 않고 ValueError로 알린다(사람이 고쳐야 하는 파일). 매출의 천 단위 쉼표는 지우고 읽는다.

    Args:
        filepath: CSV 경로. 열은 quarter, revenue_krw(원 단위), announced_date.

    Returns:
        actuals 표 (quarter: str, revenue_krw: float64, announced_date: str). quarter 오름차순.

    Raises:
        FileNotFoundError: 파일이 없을 때.
        ValueError: "필수 열 누락: <열>", "actuals.csv 형식 오류: <행 번호와 값>", "actuals.csv 분기 중복: <분기>",
            "actuals.csv 인코딩 오류: ..." (엑셀 기본 CSV인 cp949로 저장된 경우).
    """
    try:
        raw = pd.read_csv(filepath, encoding="utf-8-sig", dtype=str, keep_default_na=False, skip_blank_lines=False)
    except UnicodeDecodeError:
        raise ValueError(
            "actuals.csv 인코딩 오류: UTF-8로 저장해 주세요 (엑셀은 'CSV UTF-8(쉼표로 분리)'로 저장)"
        ) from None
    except pd.errors.EmptyDataError:
        raise ValueError(f"필수 열 누락: {', '.join(ACTUALS_COLUMNS)}") from None
    except pd.errors.ParserError:
        raise ValueError("actuals.csv 형식 오류: 열 개수가 맞지 않는 줄이 있습니다") from None

    raw.columns = [str(column).strip() for column in raw.columns]
    missing = [column for column in ACTUALS_COLUMNS if column not in raw.columns]
    if missing:
        raise ValueError(f"필수 열 누락: {', '.join(missing)}")

    errors: list[str] = []
    records: list[tuple[str, float, str]] = []
    for row_index, row in raw.loc[:, list(ACTUALS_COLUMNS)].iterrows():
        quarter, revenue_text, announced = (str(row[column]).strip() for column in ACTUALS_COLUMNS)
        if not (quarter or revenue_text or announced):
            continue
        line = f"{row_index + 2}행"  # 1행은 열 이름
        revenue = _to_float(revenue_text.replace(",", ""))
        if not QUARTER_PATTERN.fullmatch(quarter):
            errors.append(f"{line} quarter '{quarter}'")
        if revenue is None or revenue <= 0:
            errors.append(f"{line} revenue_krw '{revenue_text}'")
        if not DATE_PATTERN.fullmatch(announced) or _to_date(announced) is None:
            errors.append(f"{line} announced_date '{announced}'")
        records.append((quarter, revenue or 0.0, announced))
    if errors:
        raise ValueError("actuals.csv 형식 오류: " + "; ".join(errors))

    actuals = pd.DataFrame(records, columns=list(ACTUALS_COLUMNS)).astype(
        {"quarter": str, "revenue_krw": "float64", "announced_date": str}
    )
    duplicated = actuals.loc[actuals["quarter"].duplicated(), "quarter"].unique().tolist()
    if duplicated:
        raise ValueError(f"actuals.csv 분기 중복: {', '.join(duplicated)}")
    return actuals.sort_values("quarter").reset_index(drop=True)


def _to_float(text: str) -> float | None:
    """ASCII 숫자 문자열을 유한한 float로 바꾼다 (float()는 전각 숫자도 읽으므로 먼저 거른다).

    Returns:
        float 값. 숫자가 아니거나 NaN, 무한대이면 None.
    """
    if not text.isascii():
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _to_date(text: str) -> datetime | None:
    """"YYYY-MM-DD" 문자열이 달력에 있는 날짜인지 확인한다.

    Returns:
        datetime 값. 없는 날짜("2026-02-30")이면 None.
    """
    try:
        return datetime.strptime(text, DATE_FORMAT)
    except ValueError:
        return None
