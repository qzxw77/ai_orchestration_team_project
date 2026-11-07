# [수정 1] 날짜 인자 검사에 ASCII 확인 추가: 전각 숫자("２０２６-01-31")가 형식 검사를 통과하던 문제
# [수정 2] INFO-200(데이터 없음)일 때 돌려주는 빈 표의 열 타입을 정상 표와 같게(date 문자열, usdkrw float) 맞춤
# [수정 3] list_total_count가 int일 때만 받던 명세 밖 검사를 숫자 문자열도 받도록 고침

import os

import pandas as pd
import requests
from dotenv import load_dotenv


load_dotenv()

ECOS_BASE_URL = "https://ecos.bok.or.kr/api/StatisticSearch"
ECOS_STAT_CODE = "731Y001"
ECOS_ITEM_CODE = "0000001"
ECOS_CYCLE = "D"
ECOS_PAGE_SIZE = 1000
ECOS_NO_DATA_CODE = "INFO-200"
REQUEST_TIMEOUT_SEC = 10
FX_COLUMNS = ("date", "usdkrw")


def fetch_fx_rates(start_date: str, end_date: str) -> pd.DataFrame:
    """한국은행 ECOS에서 일별 원/달러 매매기준율을 조회한다.

    Args:
        start_date: 조회 시작일("YYYY-MM-DD").
        end_date: 조회 종료일("YYYY-MM-DD").

    Returns:
        date와 usdkrw 열을 가진 환율 DataFrame.

    Raises:
        ValueError: 날짜 형식이 잘못되었거나 시작일이 종료일보다 늦은 경우.
        RuntimeError: API 키가 없거나 ECOS API 호출에 실패한 경우.
    """
    for value in (start_date, end_date):
        if (
            not isinstance(value, str)
            or len(value) != 10
            or not value.isascii()  # [수정 1] 전각 숫자는 pd.to_datetime이 날짜로 읽어 버리므로 여기서 막는다
            or value[4] != "-"
            or value[7] != "-"
        ):
            raise ValueError(f"날짜 형식 오류: {value}")

    parsed_dates = pd.to_datetime(
        [start_date, end_date],
        format="%Y-%m-%d",
        errors="coerce",
    )
    if parsed_dates.isna().any():
        invalid_value = start_date if pd.isna(parsed_dates[0]) else end_date
        raise ValueError(f"날짜 형식 오류: {invalid_value}")

    if start_date > end_date:
        raise ValueError(f"시작일이 끝일보다 늦습니다: {start_date} > {end_date}")

    api_key = os.getenv("ECOS_API_KEY")
    if not api_key or not api_key.strip():
        raise RuntimeError("ECOS API 키가 없습니다")

    start_number = 1
    rows = []

    while True:
        end_number = start_number + ECOS_PAGE_SIZE - 1
        url = (
            f"{ECOS_BASE_URL}/{api_key}/json/kr/{start_number}/{end_number}/"
            f"{ECOS_STAT_CODE}/{ECOS_CYCLE}/"
            f"{start_date.replace('-', '')}/{end_date.replace('-', '')}/"
            f"{ECOS_ITEM_CODE}"
        )

        response = None
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT_SEC)
            response.raise_for_status()
        except requests.RequestException as exc:
            if response is not None and response.status_code >= 400:
                reason = f"HTTP {response.status_code}"
            else:
                reason = type(exc).__name__
            raise RuntimeError(f"ECOS API 호출 실패: {reason}") from None

        try:
            payload = response.json()
        except ValueError:
            raise RuntimeError("ECOS API 호출 실패: 응답 형식 오류") from None

        if not isinstance(payload, dict):
            raise RuntimeError("ECOS API 호출 실패: 응답 형식 오류")

        if "RESULT" in payload:
            result = payload["RESULT"]
            if not isinstance(result, dict) or "CODE" not in result:
                raise RuntimeError("ECOS API 호출 실패: 응답 형식 오류")

            code = result["CODE"]
            if code == ECOS_NO_DATA_CODE:
                break

            message = result.get("MESSAGE", "")
            raise RuntimeError(f"ECOS API 호출 실패: {code} {message}")

        statistic = payload.get("StatisticSearch")
        if (
            not isinstance(statistic, dict)
            or "list_total_count" not in statistic
            or "row" not in statistic
        ):
            raise RuntimeError("ECOS API 호출 실패: 응답 형식 오류")

        total_count = statistic["list_total_count"]
        page_rows = statistic["row"]
        # [수정 3] int 타입만 받던 검사를 숫자 문자열("1234")도 받도록 바꿈 (명세는 키가 있는지만 요구)
        # str()로 바꿔 0 이상의 정수 표기인지 확인하므로 True, -1, "abc", 1.5는 여전히 응답 형식 오류
        if not str(total_count).isdecimal() or not isinstance(page_rows, list):
            raise RuntimeError("ECOS API 호출 실패: 응답 형식 오류")
        total_count = int(total_count)

        rows.extend(row for row in page_rows if isinstance(row, dict))

        if not page_rows or len(rows) >= total_count:
            break

        start_number += ECOS_PAGE_SIZE

    if not rows:
        # [수정 2] 열 이름만 준 빈 표는 두 열이 모두 object라 usdkrw가 float이 아니다.
        # 저장 표와 이어 붙이면(upsert_records) usdkrw 열 전체가 object로 바뀌므로 타입을 지정한다
        return pd.DataFrame(
            {"date": pd.Series(dtype=str), "usdkrw": pd.Series(dtype=float)}
        )

    dates = pd.to_datetime(
        pd.Series([row.get("TIME") for row in rows], dtype="object"),
        format="%Y%m%d",
        errors="coerce",
    )
    values = pd.to_numeric(
        pd.Series([row.get("DATA_VALUE") for row in rows], dtype="object"),
        errors="coerce",
    )

    result = pd.DataFrame(
        {
            "date": dates.dt.strftime("%Y-%m-%d"),
            "usdkrw": values.astype(float),
        }
    )
    valid = dates.notna() & values.notna() & values.gt(0)

    return (
        result.loc[valid, list(FX_COLUMNS)]
        .drop_duplicates("date", keep="last")
        .sort_values("date")
        .reset_index(drop=True)
    )