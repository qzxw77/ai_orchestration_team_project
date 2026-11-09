import os

import pandas as pd
import requests
from dotenv import load_dotenv


# .env의 값을 모듈을 불러올 때 한 번만 환경변수로 올린다.
# 함수 안에서 부르면 테스트가 지운 ECOS_API_KEY가 .env에서 다시 살아나 키 없음 검사를 할 수 없다
load_dotenv()

ECOS_BASE_URL = "https://ecos.bok.or.kr/api/StatisticSearch"
ECOS_STAT_CODE = "731Y001"  # 주요국 통화의 대원화환율
ECOS_ITEM_CODE = "0000001"  # 원/미국달러(매매기준율)
ECOS_CYCLE = "D"  # 일별
ECOS_PAGE_SIZE = 1000
ECOS_NO_DATA_CODE = "INFO-200"
REQUEST_TIMEOUT_SEC = 10
FX_COLUMNS = ("date", "usdkrw")

INPUT_DATE_FORMAT = "%Y-%m-%d"
ECOS_DATE_FORMAT = "%Y%m%d"
ECOS_API_KEY_ENV = "ECOS_API_KEY"
ECOS_FIRST_ROW = 1  # ECOS 행 번호는 1부터 센다

API_ERROR_PREFIX = "ECOS API 호출 실패"
FORMAT_ERROR_REASON = "응답 형식 오류"


def fetch_fx_rates(start_date: str, end_date: str) -> pd.DataFrame:
    """한국은행 ECOS에서 일별 원/달러 매매기준율을 조회해 fx 표로 돌려준다.

    검사 순서는 날짜 인자 -> API 키 -> ECOS 요청이며, 앞 단계에서 실패하면 ECOS를 부르지 않는다.

    Args:
        start_date: 조회 시작일. 달력에 있는 "YYYY-MM-DD" 문자열.
        end_date: 조회 종료일. 달력에 있는 "YYYY-MM-DD" 문자열이며 start_date와 같거나 늦어야 한다.

    Returns:
        열이 정확히 2개이고 순서가 (date, usdkrw)인 DataFrame.
            date: "YYYY-MM-DD" 문자열 (datetime, Timestamp가 아님)
            usdkrw: float, 1달러당 원, 0 초과
        date 오름차순, date 중복 없음(같은 date가 여러 번 오면 응답에서 나중 행), 행 번호 0부터.
        값이 없는 날(주말, 공휴일)은 채우지 않으며 행 자체가 없다.
        다음 경우에는 열 타입이 같은(date 문자열, usdkrw float) 0행 표를 돌려준다.
            첫 요청의 응답이 INFO-200(데이터 없음)
            받은 행 중 유효한 행(TIME이 달력 날짜이고 DATA_VALUE가 0 초과 숫자)이 없음
        나눠 받는 중에 INFO-200이 오면 그때까지 모은 행으로 표를 만든다.

    Raises:
        ValueError: "날짜 형식 오류: <값>" 날짜 인자가 "YYYY-MM-DD" 형식이나 달력 날짜가 아닌 경우.
        ValueError: "시작일이 끝일보다 늦습니다: <start_date> > <end_date>"
        RuntimeError: "ECOS API 키가 없습니다" 환경변수 ECOS_API_KEY가 없거나 공백뿐인 경우.
        RuntimeError: "ECOS API 호출 실패: <예외 클래스 이름>" 연결 오류, 시간 초과 등.
        RuntimeError: "ECOS API 호출 실패: HTTP <상태 코드>" HTTP 4xx, 5xx.
        RuntimeError: "ECOS API 호출 실패: <CODE> <MESSAGE>" INFO-200이 아닌 결과 코드.
        RuntimeError: "ECOS API 호출 실패: 응답 형식 오류" JSON이 아니거나 응답 구조가 명세와 다른 경우.
    """
    _validate_dates(start_date, end_date)
    api_key: str = _get_api_key()
    rows: list[dict] = _fetch_all_rows(api_key, start_date, end_date)
    return _to_fx_table(rows)


def _validate_dates(start_date: str, end_date: str) -> None:
    """날짜 인자 두 개를 검사한다.

    두 값의 형식 검사를 먼저 모두 끝내고, 그다음 두 값의 달력 날짜 검사, 그다음 시작일 > 끝일 검사를 한다.
    이 순서가 바뀌면 오류 메시지에 나오는 값이 바뀐다.

    Args:
        start_date: 조회 시작일 ("YYYY-MM-DD").
        end_date: 조회 종료일 ("YYYY-MM-DD").

    Returns:
        None. 문제가 없으면 아무것도 돌려주지 않는다.

    Raises:
        ValueError: 형식이나 달력 날짜가 틀리면 "날짜 형식 오류: <값>",
            시작일이 끝일보다 늦으면 "시작일이 끝일보다 늦습니다: <start_date> > <end_date>".
    """
    # 형식: 10글자, ASCII, 5번째와 8번째 글자가 "-"
    # (자리 수를 따로 보지 않으면 "2026-1-01"처럼 한 자리 월도 날짜로 읽힐 수 있다)
    for value in (start_date, end_date):
        if (
            not isinstance(value, str)
            or len(value) != 10
            # 전각 숫자("２０２６")는 pd.to_datetime이 날짜로 읽어 버리므로 ASCII로 한정한다
            or not value.isascii()
            or value[4] != "-"
            or value[7] != "-"
        ):
            raise ValueError(f"날짜 형식 오류: {value}")

    # 달력: "2026-13-01", "2026-02-30"처럼 형식은 맞지만 없는 날짜를 걸러 낸다
    for value in (start_date, end_date):
        if pd.isna(pd.to_datetime(value, format=INPUT_DATE_FORMAT, errors="coerce")):
            raise ValueError(f"날짜 형식 오류: {value}")

    # 형식을 통과한 "YYYY-MM-DD" 문자열은 사전순과 날짜순이 같다
    if start_date > end_date:
        raise ValueError(f"시작일이 끝일보다 늦습니다: {start_date} > {end_date}")


def _get_api_key() -> str:
    """환경변수에서 ECOS API 키를 읽는다.

    검사는 앞뒤 공백을 뺀 값으로 하고, 돌려주는 값은 환경변수에 적힌 원래 값이다.

    Args:
        없음.

    Returns:
        ECOS API 키 문자열.

    Raises:
        RuntimeError: "ECOS API 키가 없습니다" 키가 없거나 공백뿐인 경우.
    """
    api_key: str | None = os.getenv(ECOS_API_KEY_ENV)
    if not api_key or not api_key.strip():
        raise RuntimeError("ECOS API 키가 없습니다")
    return api_key


def _fetch_all_rows(api_key: str, start_date: str, end_date: str) -> list[dict]:
    """기간 전체 행을 ECOS_PAGE_SIZE행씩 나눠 요청해 모은다.

    이번 응답의 row가 0개이거나, 모은 행 수가 list_total_count 이상이거나, INFO-200이 오면 멈춘다.
    dict가 아닌 row는 건너뛰며, 모은 행 수는 건너뛴 뒤의 개수로 센다.

    Args:
        api_key: ECOS API 키. _build_url에 넘기기만 하고 다른 곳에 쓰지 않는다.
        start_date: 검사를 통과한 조회 시작일 ("YYYY-MM-DD").
        end_date: 검사를 통과한 조회 종료일 ("YYYY-MM-DD").

    Returns:
        응답 순서대로 모은 row dict 목록. 첫 요청이 INFO-200이면 빈 목록.

    Raises:
        RuntimeError: ECOS 호출이 실패했거나 응답 형식이 틀린 경우 (_request_json, _parse_page에서 발생).
    """
    rows: list[dict] = []
    start_number: int = ECOS_FIRST_ROW

    while True:
        end_number: int = start_number + ECOS_PAGE_SIZE - 1
        url: str = _build_url(api_key, start_number, end_number, start_date, end_date)
        page: tuple[list, int] | None = _parse_page(_request_json(url))
        if page is None:
            break

        page_rows, total_count = page
        rows.extend(row for row in page_rows if isinstance(row, dict))

        if not page_rows or len(rows) >= total_count:
            break

        start_number += ECOS_PAGE_SIZE

    return rows


def _build_url(
    api_key: str, start_number: int, end_number: int, start_date: str, end_date: str
) -> str:
    """ECOS StatisticSearch 요청 URL을 만든다.

    돌려주는 URL에는 API 키가 들어 있으므로 오류 메시지, 로그, print에 쓰지 않는다.

    Args:
        api_key: ECOS API 키 (URL 경로에 들어간다).
        start_number: 요청 범위의 시작 행 번호 (1부터 센다).
        end_number: 요청 범위의 끝 행 번호.
        start_date: 조회 시작일 ("YYYY-MM-DD").
        end_date: 조회 종료일 ("YYYY-MM-DD").

    Returns:
        아래 형식의 URL 문자열.
        {ECOS_BASE_URL}/{키}/json/kr/{시작 번호}/{끝 번호}/{통계 코드}/{주기}/{시작일 YYYYMMDD}/{끝일 YYYYMMDD}/{항목 코드}

    Raises:
        없음.
    """
    return (
        f"{ECOS_BASE_URL}/{api_key}/json/kr/{start_number}/{end_number}/"
        f"{ECOS_STAT_CODE}/{ECOS_CYCLE}/"
        f"{start_date.replace('-', '')}/{end_date.replace('-', '')}/"
        f"{ECOS_ITEM_CODE}"
    )


def _request_json(url: str) -> object:
    """URL로 GET 요청을 보내고 응답 본문을 JSON으로 해석한다.

    url에는 API 키가 들어 있으므로 오류 메시지에는 예외 클래스 이름이나 상태 코드만 쓴다.

    Args:
        url: _build_url이 만든 요청 URL (API 키 포함).

    Returns:
        json()이 돌려준 값. dict가 아닐 수도 있으므로 구조 검사는 _parse_page가 한다.

    Raises:
        RuntimeError: "ECOS API 호출 실패: <예외 클래스 이름>" requests.get의 예외(연결 오류, 시간 초과 등).
        RuntimeError: "ECOS API 호출 실패: HTTP <상태 코드>" raise_for_status()의 HTTPError.
        RuntimeError: "ECOS API 호출 실패: 응답 형식 오류" 본문이 JSON이 아닌 경우.
    """
    # requests 예외의 str(e)에는 키가 든 요청 URL이 담긴다.
    # from None으로 원래 예외가 traceback에 함께 찍히지 않게 하고, 메시지에도 str(e)를 넣지 않는다
    try:
        response: requests.Response = requests.get(url, timeout=REQUEST_TIMEOUT_SEC)
    except requests.RequestException as exc:
        raise _api_error(type(exc).__name__) from None

    try:
        response.raise_for_status()
    except requests.HTTPError:
        # HTTPError.response는 None일 수 있으므로 상태 코드는 지역 변수 response에서 읽는다
        raise _api_error(f"HTTP {response.status_code}") from None

    try:
        return response.json()
    except ValueError:
        raise _api_error(FORMAT_ERROR_REASON) from None


def _parse_page(payload: object) -> tuple[list, int] | None:
    """ECOS 응답 한 페이지를 검사하고 row 목록과 전체 행 수를 꺼낸다.

    Args:
        payload: _request_json이 돌려준 JSON 값.

    Returns:
        (이번 요청의 row 목록, list_total_count를 int로 바꾼 값).
        row 목록에는 dict가 아닌 값이 섞여 있을 수 있다 (거르는 것은 _fetch_all_rows).
        결과 코드가 INFO-200(데이터 없음)이면 None.

    Raises:
        RuntimeError: "ECOS API 호출 실패: <CODE> <MESSAGE>" INFO-200이 아닌 결과 코드.
        RuntimeError: "ECOS API 호출 실패: 응답 형식 오류" 응답이 dict가 아님, RESULT가 dict가 아니거나
            CODE 없음, StatisticSearch, list_total_count, row 중 하나라도 없음, row가 목록이 아님,
            list_total_count가 0 이상의 정수 표기(숫자 또는 숫자 문자열)가 아님.
    """
    if not isinstance(payload, dict):
        raise _api_error(FORMAT_ERROR_REASON) from None

    if "RESULT" in payload:
        result = payload["RESULT"]
        if not isinstance(result, dict) or "CODE" not in result:
            raise _api_error(FORMAT_ERROR_REASON) from None

        code = result["CODE"]
        # ECOS는 HTTP 200에도 결과 코드로 실패를 알리고, INFO-100(인증키 오류)처럼 INFO로 시작하는 실패도 있다.
        # 그래서 INFO-200만 데이터 없음으로 보고 나머지는 모두 실패로 올린다
        if code == ECOS_NO_DATA_CODE:
            return None

        message = result.get("MESSAGE", "")
        raise _api_error(f"{code} {message}") from None

    statistic = payload.get("StatisticSearch")
    if (
        not isinstance(statistic, dict)
        or "list_total_count" not in statistic
        or "row" not in statistic
    ):
        raise _api_error(FORMAT_ERROR_REASON) from None

    total_count = statistic["list_total_count"]
    page_rows = statistic["row"]
    # 명세는 list_total_count 키가 있는지만 정하고 값 타입은 정하지 않으므로 숫자 문자열("1234")도 받는다.
    # str()로 바꿔 0 이상의 정수 표기인지 보므로 True, -1, "abc", 1.5는 응답 형식 오류다
    if not str(total_count).isdecimal() or not isinstance(page_rows, list):
        raise _api_error(FORMAT_ERROR_REASON) from None

    return page_rows, int(total_count)


def _api_error(reason: str) -> RuntimeError:
    """ECOS 호출 실패 예외 객체를 만든다. raise _api_error(...) from None 으로 쓴다.

    Args:
        reason: 실패 원인. 예외 클래스 이름, "HTTP <상태 코드>", "<CODE> <MESSAGE>", FORMAT_ERROR_REASON 중 하나.
            URL, API 키, str(e)는 넣지 않는다.

    Returns:
        메시지가 "ECOS API 호출 실패: <reason>"인 RuntimeError.

    Raises:
        없음. 예외를 만들어 돌려줄 뿐 발생시키지 않는다.
    """
    return RuntimeError(f"{API_ERROR_PREFIX}: {reason}")


def _to_fx_table(rows: list[dict]) -> pd.DataFrame:
    """모은 row를 fx 표로 바꾼다.

    TIME("YYYYMMDD")은 "YYYY-MM-DD" 문자열로, DATA_VALUE는 숫자로 바꾸고, 바꿀 수 없으면 결측으로 둔다.
    date나 usdkrw가 결측이거나 usdkrw가 0 이하인 행은 빼고, 같은 date는 나중 행만 남긴 뒤 date 오름차순으로 정렬한다.

    Args:
        rows: _fetch_all_rows가 모은 row dict 목록 (응답 순서).

    Returns:
        fetch_fx_rates의 Returns와 같은 fx 표. rows가 비었거나 유효한 행이 없으면 0행 표.

    Raises:
        없음.
    """
    if not rows:
        return _empty_fx_table()

    date_column, value_column = FX_COLUMNS
    dates: pd.Series = pd.to_datetime(
        pd.Series([row.get("TIME") for row in rows], dtype="object"),
        format=ECOS_DATE_FORMAT,
        errors="coerce",
    )
    values: pd.Series = pd.to_numeric(
        pd.Series([row.get("DATA_VALUE") for row in rows], dtype="object"),
        errors="coerce",
    )

    table: pd.DataFrame = pd.DataFrame(
        {
            date_column: dates.dt.strftime(INPUT_DATE_FORMAT),
            value_column: values.astype(float),
        }
    )
    valid: pd.Series = dates.notna() & values.notna() & values.gt(0)

    return (
        table.loc[valid, list(FX_COLUMNS)]
        .drop_duplicates(date_column, keep="last")
        .sort_values(date_column)
        .reset_index(drop=True)
    )


def _empty_fx_table() -> pd.DataFrame:
    """열 타입을 지정한 0행 fx 표를 만든다.

    Args:
        없음.

    Returns:
        열이 (date, usdkrw)이고 date는 문자열, usdkrw는 float 타입인 0행 DataFrame.

    Raises:
        없음.
    """
    date_column, value_column = FX_COLUMNS
    # 열 이름만 준 빈 표는 두 열이 모두 object라, 저장 표와 이어 붙이면(upsert_records) usdkrw 열 전체가
    # object로 바뀐다. 그래서 정상 표와 같은 타입을 지정한다
    return pd.DataFrame(
        {date_column: pd.Series(dtype=str), value_column: pd.Series(dtype=float)}
    )