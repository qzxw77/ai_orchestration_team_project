"""[모듈 2] 전처리.

    clean_exports       수출 원자료(관세청 응답, 업로드 CSV) -> exports 표
    upsert_records      저장 표와 새 표를 키 기준으로 합치기 (새 값 우선)
    aggregate_quarterly exports + fx -> 분기 집계(quarterly)

파일 입출력과 API 호출은 하지 않는다.
"""

import math
import re
from datetime import datetime

import pandas as pd

ALLOWED_REGIONS = ("이천시", "청주시")
TARGET_HS_CODE = "854232"
EXPORTS_COLUMNS = ("ym", "region", "hs_code", "export_usd", "collected_at")
EXPORTS_KEY_COLUMNS = ("ym", "region", "hs_code")
QUARTERLY_COLUMNS = ("quarter", "export_usd", "months_available", "fx_avg")

# 원자료 열 이름 후보. 표준 이름, 관세청 API 응답 필드, K-stat 내려받기 CSV 순으로 찾아 처음 찾은 열을 쓴다.
# 관세청 실제 응답(2026-11 확인): priodTitle "2026.08", sggNm "경기도 이천시", hsSgn "854232", expUsdAmt "3,650,354"
RAW_COLUMN_CANDIDATES = {
    "ym": ("ym", "priodTitle", "year", "yymm", "statYymm", "기간", "년월"),
    "region": ("region", "sggNm", "sgguNm", "sigunguNm", "시군구", "지역"),
    "hs_code": ("hs_code", "hsSgn", "hsCd", "hsCode", "품목코드", "HS코드"),
    "export_usd": ("export_usd", "expUsdAmt", "expDlr", "수출금액", "수출금액(달러)", "수출금액(천달러)"),
}
REQUIRED_RAW_COLUMNS = ("ym", "region", "export_usd")
# 금액 열 -> 달러 환산 배수 (목록에 없는 열은 달러로 본다).
# 관세청 expUsdAmt는 천 달러 단위다: 2026-08 이천시 3,650,354 = 36.5억 달러 (달러로 보면 365만 달러라 맞지 않음)
AMOUNT_MULTIPLIERS = {"expUsdAmt": 1000.0, "수출금액(천달러)": 1000.0}
# 청주시는 구 단위(상당구, 서원구, 흥덕구, 청원구)로 올 수 있어 모두 청주시로 합친다
REGION_PATTERNS = {
    "이천시": re.compile(r"이천"),
    "청주시": re.compile(r"청주|상당구|서원구|흥덕구|청원구"),
}
RAW_YM_PATTERN = re.compile(r"([0-9]{4})([^0-9]{0,3})([0-9]{1,2})[^0-9]*")
COLLECTED_AT_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


# =============================================================================
# clean_exports
# =============================================================================
def clean_exports(raw_df: pd.DataFrame) -> pd.DataFrame:
    """수출 원자료를 exports 표로 정제한다.

    열 이름을 RAW_COLUMN_CANDIDATES로 찾아 표준 이름으로 바꾸고, 금액은 AMOUNT_MULTIPLIERS로 달러로 환산한 뒤
    이천시, 청주시의 HS 854232 행만 남긴다. 같은 달, 같은 지역에 합계 행(시 단위, 6단위 품목)이 있으면 그 행을 쓰고,
    세부 행(구 단위, 10단위 품목)만 있으면 같은 수집일 안에서 더한다. 수집일이 다르면 가장 최근 수집일의 값을 남긴다.

    Args:
        raw_df: 수출 원자료. 월, 지역, 수출액 열이 있어야 하고 품목 코드와 collected_at 열은 없어도 된다
            (품목 코드가 없으면 854232로 본다).

    Returns:
        exports 표 (EXPORTS_COLUMNS 순서, ym/region/hs_code 오름차순). export_usd는 달러 float64,
        collected_at이 없거나 잘못된 행은 NaN. 남는 행이 없으면 dtype을 지정한 0행 표.

    Raises:
        ValueError: "필수 열 누락: <열>, ... (원자료 열: <열>, ...)" 행이 있는데 월, 지역, 수출액 열을 찾지 못한 경우.
        ValueError: "월 형식 오류: ...", "지역 형식 오류: ..." 열은 찾았지만 모든 행의 값을 읽지 못한 경우
            (형식이 예상과 달라 조용히 0행이 되지 않도록 값 예시와 함께 멈춘다).
    """
    if len(raw_df) == 0:
        return _empty_exports_table()

    raw = raw_df.rename(columns=lambda column: str(column).strip())
    source = {
        standard: next((name for name in candidates if name in raw.columns), None)
        for standard, candidates in RAW_COLUMN_CANDIDATES.items()
    }
    missing = [column for column in REQUIRED_RAW_COLUMNS if source[column] is None]
    if missing:
        found = ", ".join(raw.columns) or "없음"
        raise ValueError(f"필수 열 누락: {', '.join(missing)} (원자료 열: {found})")

    table = pd.DataFrame(
        {
            "ym": raw[source["ym"]].map(_parse_ym),
            "region": raw[source["region"]].map(_normalize_region),
            "hs_code": raw[source["hs_code"]].map(_normalize_hs_code) if source["hs_code"] else TARGET_HS_CODE,
            "export_usd": _parse_amounts(raw[source["export_usd"]])
            * AMOUNT_MULTIPLIERS.get(source["export_usd"], 1.0),
            "collected_at": raw["collected_at"].map(_parse_collected_at) if "collected_at" in raw.columns else "",
            "_subregion": raw[source["region"]].astype(str).str.strip().str.endswith("구"),
        },
        index=raw.index,
    )
    if table["ym"].isna().all():
        raise ValueError(f"월 형식 오류: {source['ym']} 열을 월로 읽을 수 없습니다 (값 예: {_samples(raw[source['ym']])})")
    if table["region"].isna().all():
        raise ValueError(
            f"지역 형식 오류: {source['region']} 열에서 이천시, 청주시를 찾지 못했습니다 "
            f"(값 예: {_samples(raw[source['region']])})"
        )
    valid = (
        table["ym"].notna()
        & table["region"].notna()
        & table["hs_code"].str.startswith(TARGET_HS_CODE)
        & table["export_usd"].map(lambda value: math.isfinite(value) and value >= 0)
    )
    table = table.loc[valid]
    if len(table) == 0:
        return _empty_exports_table()

    # 합계 행과 세부 행을 둘 다 더하면 두 번 세므로, 합계 행이 있는 달은 합계 행만 쓴다
    is_total = ~table["_subregion"] & (table["hs_code"] == TARGET_HS_CODE)
    has_total = is_total.groupby([table["ym"], table["region"], table["collected_at"]]).transform("any")
    table = table.loc[is_total | ~has_total].assign(hs_code=TARGET_HS_CODE)

    summed = table.groupby([*EXPORTS_KEY_COLUMNS, "collected_at"], as_index=False)["export_usd"].sum()
    latest = summed.sort_values("collected_at", kind="stable").drop_duplicates(
        list(EXPORTS_KEY_COLUMNS), keep="last"
    )
    latest["collected_at"] = latest["collected_at"].where(latest["collected_at"] != "")
    latest["export_usd"] = latest["export_usd"].astype("float64")
    return (
        latest.loc[:, list(EXPORTS_COLUMNS)]
        .sort_values(list(EXPORTS_KEY_COLUMNS), kind="stable")
        .reset_index(drop=True)
    )


def _empty_exports_table() -> pd.DataFrame:
    """dtype을 지정한 0행 exports 표를 만든다 (빈 표를 저장 표와 합쳐도 export_usd가 object로 바뀌지 않게).

    Returns:
        EXPORTS_COLUMNS 열의 0행 DataFrame (export_usd만 float64, 나머지는 문자열).
    """
    return pd.DataFrame(
        {column: pd.Series(dtype="float64" if column == "export_usd" else str) for column in EXPORTS_COLUMNS}
    )


def _samples(values: pd.Series, count: int = 3) -> str:
    """오류 메시지에 넣을 값 예시를 만든다.

    Returns:
        서로 다른 값 앞에서부터 count개를 쉼표로 이은 문자열.
    """
    return ", ".join(f"'{value}'" for value in values.astype(str).drop_duplicates().head(count))


def _parse_ym(value: object) -> str | None:
    """원자료의 월 값("2026-09", "202609", "2026.09", "2026년 9월" 등)을 "YYYY-MM"으로 바꾼다.

    Returns:
        "YYYY-MM" 문자열. 월로 읽을 수 없으면(합계 행 등) None.
    """
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        value = str(int(value)) if float(value).is_integer() else str(value)
    if not isinstance(value, str):
        return None
    match = RAW_YM_PATTERN.fullmatch(value.strip())
    if match is None:
        return None
    year, separator, month_text = match.groups()
    # 엑셀이 "2026.10"을 숫자 2026.1로 바꿔 저장한 경우다. 1~9월은 "2026.01"처럼 두 자리로 남는다
    if separator == "." and month_text == "1":
        month_text = "10"
    month = int(month_text)
    if not 1 <= month <= 12:
        return None
    return f"{year}-{month:02d}"


def _normalize_region(value: object) -> str | None:
    """지역 표기("경기도 이천시", "청주시 흥덕구" 등)를 ALLOWED_REGIONS 이름으로 바꾼다.

    Returns:
        "이천시" 또는 "청주시". 그 밖의 지역이면 None.
    """
    if not isinstance(value, str):
        return None
    for region, pattern in REGION_PATTERNS.items():
        if pattern.search(value):
            return region
    return None


def _normalize_hs_code(value: object) -> str:
    """품목 코드에서 ASCII 숫자만 남긴다("8542.32" -> "854232", 숫자로 읽힌 854232.0 -> "854232").

    Returns:
        숫자 문자열. 결측이면 "".
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return "".join(character for character in text if character in "0123456789")


def _parse_amounts(values: pd.Series) -> pd.Series:
    """금액 열을 숫자로 바꾼다. 천 단위 쉼표는 지우고, 숫자가 아니면 NaN으로 둔다.

    Returns:
        float64 Series (입력과 같은 index).
    """
    text = values.map(lambda value: str(value).replace(",", "").strip() if isinstance(value, str) else value)
    return pd.to_numeric(text, errors="coerce").astype("float64")


def _parse_collected_at(value: object) -> str:
    """수집일을 "YYYY-MM-DD"로 검사한다.

    Returns:
        정상 날짜면 그대로, 아니면 "" (가장 오래된 수집으로 본다).
    """
    if not isinstance(value, str) or not COLLECTED_AT_PATTERN.fullmatch(value.strip()):
        return ""
    try:
        datetime.strptime(value.strip(), "%Y-%m-%d")
    except ValueError:
        return ""
    return value.strip()


# =============================================================================
# upsert_records
# =============================================================================
def upsert_records(store_df: pd.DataFrame, new_df: pd.DataFrame, key_cols: list[str]) -> pd.DataFrame:
    """저장 표와 새 표를 합친다. 같은 키가 있으면 새 표의 행을 남긴다.

    Args:
        store_df: 저장된 표.
        new_df: 새로 받은 표 (store_df와 같은 열).
        key_cols: 중복을 판정할 키 열 (예: ["ym", "region", "hs_code"]).

    Returns:
        키마다 한 행만 남긴 새 표 (key_cols 오름차순, 행 번호 0부터). 입력 표는 바꾸지 않는다.

    Raises:
        ValueError: "key_cols는 비어 있을 수 없습니다.", "<store_df 또는 new_df>에 키 열이 없습니다: <열>, ..."
    """
    if not key_cols:
        raise ValueError("key_cols는 비어 있을 수 없습니다.")
    for name, table in (("store_df", store_df), ("new_df", new_df)):
        missing = [column for column in key_cols if column not in table.columns]
        if len(table) > 0 and missing:
            raise ValueError(f"{name}에 키 열이 없습니다: {', '.join(missing)}")

    frames = [table for table in (store_df, new_df) if len(table) > 0]
    if not frames:
        return store_df.copy()
    combined = pd.concat(frames, ignore_index=True) if len(frames) == 2 else frames[0].copy()
    return (
        combined.drop_duplicates(subset=key_cols, keep="last")
        .sort_values(key_cols, kind="stable")
        .reset_index(drop=True)
    )


# =============================================================================
# aggregate_quarterly
# =============================================================================
def aggregate_quarterly(exports_df: pd.DataFrame, fx_df: pd.DataFrame, lag_months: int = 0) -> pd.DataFrame:
    """월별 수출과 일별 환율을 분기 단위로 집계한다.

    두 지역이 모두 있는 달만 수출 합계에 넣는다(한 지역만 있으면 합계가 작게 잡혀 가짜 급감이 나온다).
    lag_months는 수출에만 적용하고, fx_avg는 그 분기 실제 날짜들의 평균이다.

    Args:
        exports_df: exports 표.
        fx_df: fx 표.
        lag_months: 수출 월을 몇 개월 뒤 분기로 넘길지 (0 이상, 기본 0).

    Returns:
        quarterly 표 (quarter: str, export_usd: float64, months_available: int64 1~3, fx_avg: float64).
        quarter 오름차순. 수출 자료가 없는 분기는 행이 없고, 환율이 없는 분기의 fx_avg는 NaN.

    Raises:
        ValueError: "lag_months는 0 이상이어야 합니다"
    """
    if lag_months < 0:
        raise ValueError("lag_months는 0 이상이어야 합니다")
    if len(exports_df) == 0:
        return _empty_quarterly_table()

    target = exports_df.loc[exports_df["region"].isin(ALLOWED_REGIONS)]
    region_counts = target.groupby("ym")["region"].nunique()
    complete_months = region_counts.index[region_counts == len(ALLOWED_REGIONS)]
    complete = target.loc[target["ym"].isin(complete_months)]
    if len(complete) == 0:
        return _empty_quarterly_table()

    shifted = complete.assign(quarter=complete["ym"].map(lambda ym: _shifted_quarter(ym, lag_months)))
    exports_quarterly = shifted.groupby("quarter", as_index=False).agg(
        export_usd=("export_usd", "sum"), months_available=("ym", "nunique")
    )

    if len(fx_df) == 0:
        fx_quarterly = pd.DataFrame({"quarter": pd.Series(dtype=str), "fx_avg": pd.Series(dtype="float64")})
    else:
        fx_quarter = pd.to_datetime(fx_df["date"], errors="coerce").dt.to_period("Q").astype(str)
        fx_quarterly = (
            fx_df.assign(quarter=fx_quarter)
            .groupby("quarter", as_index=False)
            .agg(fx_avg=("usdkrw", "mean"))
        )

    result = exports_quarterly.merge(fx_quarterly, on="quarter", how="left")
    return result.astype({"export_usd": "float64", "months_available": "int64", "fx_avg": "float64"}).loc[
        :, list(QUARTERLY_COLUMNS)
    ].reset_index(drop=True)


def _shifted_quarter(ym: str, lag_months: int) -> str:
    """월에 lag_months를 더한 달이 속한 분기를 구한다.

    Returns:
        "YYYYQn" 문자열.
    """
    shifted = pd.Period(ym, freq="M") + lag_months
    return f"{shifted.year}Q{shifted.quarter}"


def _empty_quarterly_table() -> pd.DataFrame:
    """dtype을 지정한 0행 quarterly 표를 만든다.

    Returns:
        QUARTERLY_COLUMNS 열의 0행 DataFrame.
    """
    return pd.DataFrame(
        {
            "quarter": pd.Series(dtype=str),
            "export_usd": pd.Series(dtype="float64"),
            "months_available": pd.Series(dtype="int64"),
            "fx_avg": pd.Series(dtype="float64"),
        }
    )
