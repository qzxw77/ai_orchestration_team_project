"""[모듈 2] 전처리: 수출 원자료 정제 (알트 ALT · SK하이닉스 분기 매출 나우캐스팅).

조현모 담당 clean_exports와 그 내부 도우미만 있다. 파일 입출력·외부 API 호출을 하지 않는다.
"""

from datetime import datetime
import math

import pandas as pd


RAW_COLUMN_MAP: dict[str, str] = {}
REGION_NAME_MAP: dict[str, str] = {
    "경기도 이천시": "이천시",
    "충청북도 청주시": "청주시",
}
ALLOWED_REGIONS: tuple[str, ...] = ("이천시", "청주시")
YM_FORMATS: tuple[str, ...] = ("%Y-%m", "%Y%m", "%Y.%m", "%Y/%m")
COLLECTED_AT_FORMAT: str = "%Y-%m-%d"

_EXPORT_COLUMNS: list[str] = [
    "ym",
    "region",
    "hs_code",
    "export_usd",
    "collected_at",
]


def _parse_ym(value: object) -> str | None:
    """연월 값을 엄격히 검증해 YYYY-MM 문자열로 변환한다.

    Args:
        value: 정수, 정수형 실수 또는 지원 형식의 연월 값.

    Returns:
        유효한 연월의 YYYY-MM 문자열. 변환할 수 없으면 None.
    """
    if pd.isna(value) or isinstance(value, bool):
        return None

    if isinstance(value, int):
        text = str(value)
    elif isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            return None
        text = str(int(value))
    else:
        text = str(value).strip()

    for fmt in YM_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        # 다시 같은 형식으로 썼을 때 원래 글자와 같아야 인정한다("20267", "2026-7" 같은 애매한 값 차단)
        if parsed.strftime(fmt) == text:
            return parsed.strftime("%Y-%m")

    return None

    return None


def _parse_collected_at(value: object) -> str | None:
    """수집일을 YYYY-MM-DD 문자열로 바꾼다.

    Args:
        value: 수집일 값.

    Returns:
        유효한 수집일 문자열. 비어 있거나 유효하지 않으면 None.
    """
    if pd.isna(value):
        return None

    parsed = pd.to_datetime(value, format=COLLECTED_AT_FORMAT, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.strftime("%Y-%m-%d")


def _normalize_region(value: object) -> str | None:
    """지역 이름의 공백을 지우고 REGION_NAME_MAP으로 표준 이름으로 바꾼다.

    Args:
        value: 지역 이름 값.

    Returns:
        표준 지역 이름. 결측이면 None.
    """
    if pd.isna(value):
        return None
    name = str(value).strip()
    return REGION_NAME_MAP.get(name, name)


def _normalize_hs_code(value: object) -> str | None:
    """HS 코드를 문자열로 정규화한다.

    Args:
        value: HS 코드 값.

    Returns:
        정규화한 문자열. 결측 또는 빈 문자열이면 None.
    """
    if pd.isna(value):
        return None
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        text = str(int(value))
    else:
        text = str(value).strip()
    return text or None


def clean_exports(raw_df: pd.DataFrame) -> pd.DataFrame:
    """관세청 수출 원자료를 정제해 exports 표를 반환한다.

    지저분한 행(결측·숫자 아님·없는 달·음수·대상 외 지역)은 예외 없이 제거하고 export_usd = 0은 남긴다.
    키(ym, region, hs_code)가 같으면 collected_at이 가장 최근인 1행만 남긴다(빈 수집일은 가장 오래된 것).
    빠진 달을 0으로 채우거나 합계를 계산하지 않는다.

    Args:
        raw_df: 연월, 지역, HS 코드, 수출액, 수집일을 포함한 원자료.

    Returns:
        지정된 다섯 열만 가진 정제된 수출 표.

    Raises:
        ValueError: 비어 있지 않은 입력에 필수 열이 누락된 경우.
    """
    if raw_df.empty:
        return pd.DataFrame(columns=_EXPORT_COLUMNS)

    result = raw_df.copy()
    rename_map = {
        source: target
        for source, target in RAW_COLUMN_MAP.items()
        if source in result.columns and target not in result.columns
    }
    result = result.rename(columns=rename_map)

    missing = [column for column in _EXPORT_COLUMNS if column not in result.columns]
    if missing:
        raise ValueError(f"필수 열 누락: {', '.join(missing)}")

    result["ym"] = result["ym"].map(_parse_ym)
    result["region"] = result["region"].map(_normalize_region)
    result["hs_code"] = result["hs_code"].map(_normalize_hs_code)

    amounts = pd.to_numeric(
        result["export_usd"].astype("string").str.replace(",", "", regex=False),
        errors="coerce",
    )
    result["export_usd"] = amounts.where(
        amounts.map(lambda value: pd.notna(value) and math.isfinite(value))
    )
    result["collected_at"] = result["collected_at"].map(_parse_collected_at)

    valid_rows = (
        result["ym"].notna()
        & result["export_usd"].notna()
        & result["export_usd"].ge(0)
        & result["region"].isin(ALLOWED_REGIONS)
    )
    result = result.loc[valid_rows].copy()

    if result.empty:
        return pd.DataFrame(columns=_EXPORT_COLUMNS)

    result["_collected_sort"] = result["collected_at"].fillna("")
    result = result.sort_values("_collected_sort", kind="stable")
    result = result.drop_duplicates(
        subset=["ym", "region", "hs_code"],
        keep="last",
    )
    result["export_usd"] = result["export_usd"].astype(float)

    return (
        result.loc[:, _EXPORT_COLUMNS]
        .sort_values(["ym", "region", "hs_code"], kind="stable")
        .reset_index(drop=True)
    )