"""SK하이닉스 분기 매출 나우캐스팅 전처리 함수 (aggregate_quarterly)."""

import math

import pandas as pd


ALLOWED_REGIONS: tuple[str, ...] = ("이천시", "청주시")
QUARTERLY_COLUMNS: tuple[str, ...] = (
    "quarter",
    "export_usd",
    "months_available",
    "fx_avg",
)


def _get_shifted_quarter(ym: str, lag_months: int) -> str:
    """월에 시차를 적용한 뒤 해당 분기를 반환한다.

    Args:
        ym: ``YYYY-MM`` 형식의 월.
        lag_months: 더할 개월 수.

    Returns:
        시차가 적용된 분기 문자열(``YYYYQn``).
    """
    shifted_month = pd.Period(ym, freq="M") + lag_months
    return f"{shifted_month.year}Q{shifted_month.quarter}"


def _empty_quarterly_table() -> pd.DataFrame:
    """분기 집계 결과의 빈 표를 생성한다.

    Returns:
        ``quarter``, ``export_usd``, ``months_available``, ``fx_avg`` 열을
        표준 순서와 타입으로 가진 0행 DataFrame.

    Raises:
        없음.
    """
    return pd.DataFrame(
        {
            "quarter": pd.Series(dtype=str),
            "export_usd": pd.Series(dtype="float64"),
            "months_available": pd.Series(dtype="int64"),
            "fx_avg": pd.Series(dtype="float64"),
        }
    )


def aggregate_quarterly(
    exports_df: pd.DataFrame, fx_df: pd.DataFrame, lag_months: int = 0
) -> pd.DataFrame:
    """월별 수출과 일별 환율 자료를 분기별로 집계한다.

    Args:
        exports_df: ``ym``, ``region``, ``hs_code``, ``export_usd``,
            ``collected_at`` 열을 포함하는 월별 수출 표.
        fx_df: ``date``와 ``usdkrw`` 열을 포함하는 일별 환율 표.
        lag_months: 수출액을 뒤로 이월할 개월 수. 환율에는 적용하지 않는다.

    Returns:
        ``quarter``(str), ``export_usd``(float), ``months_available``(int),
        ``fx_avg``(float) 열을 표준 순서로 가진 분기별 집계 표.
        `hs_code`가 ``"854232"``가 아닌 행, 결측 행, 대상 지역이 아닌 행은
        집계에서 제외한다. 환율은 결측값, 0 이하, 양·음의 무한대를 제외하고
        평균을 계산한다.

    Raises:
        ValueError: ``lag_months``가 0보다 작은 경우.
    """
    if lag_months < 0:
        raise ValueError("lag_months는 0 이상이어야 합니다")
    if len(exports_df) == 0:
        return _empty_quarterly_table()

    exports = exports_df.copy()
    target_exports = exports[
        exports["region"].isin(ALLOWED_REGIONS)
        & exports["hs_code"].eq("854232")
    ].copy()

    region_counts = target_exports.groupby("ym")["region"].nunique()
    complete_months = region_counts[region_counts == len(ALLOWED_REGIONS)].index
    complete_exports = target_exports[
        target_exports["ym"].isin(complete_months)
    ].copy()

    if len(complete_exports) == 0:
        return _empty_quarterly_table()

    complete_exports["quarter"] = complete_exports["ym"].map(
        lambda ym: _get_shifted_quarter(ym, lag_months)
    )
    export_quarterly = (
        complete_exports.groupby("quarter", as_index=False)
        .agg(
            export_usd=("export_usd", "sum"),
            months_available=("ym", "nunique"),
        )
        .sort_values("quarter")
    )

    fx = fx_df.copy()
    if len(fx) == 0:
        fx_quarterly = pd.DataFrame(
            {"quarter": pd.Series(dtype=str), "fx_avg": pd.Series(dtype="float64")}
        )
    else:
        numeric_usdkrw = pd.to_numeric(fx["usdkrw"], errors="coerce")
        valid_fx = (
            numeric_usdkrw.notna()
            & numeric_usdkrw.map(math.isfinite)
            & numeric_usdkrw.gt(0)
        )
        fx = fx.loc[valid_fx].copy()
        fx["usdkrw"] = numeric_usdkrw.loc[valid_fx]
        if len(fx) == 0:
            fx_quarterly = pd.DataFrame(
                {"quarter": pd.Series(dtype=str), "fx_avg": pd.Series(dtype="float64")}
            )
        else:
            fx["quarter"] = pd.to_datetime(fx["date"]).dt.to_period("Q").astype(str)
            fx_quarterly = fx.groupby("quarter", as_index=False).agg(
                fx_avg=("usdkrw", "mean")
            )

    result = export_quarterly.merge(fx_quarterly, on="quarter", how="left")
    return result.loc[:, list(QUARTERLY_COLUMNS)].reset_index(drop=True)
