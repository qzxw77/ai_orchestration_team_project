import pandas as pd


RATIO_WINDOW = 4
MONTHS_PER_QUARTER = 3
FORECAST_STATUS_OK = "ok"
FORECAST_STATUS_NO_DATA = "no_data"
FORECAST_STATUS_INSUFFICIENT = "insufficient_history"

def _quarter_index(quarter: str) -> int | None:
    """분기 문자열을 시간순 비교용 정수로 변환한다.

    Args:
        quarter: "YYYYQn" 형식의 분기 문자열.

    Returns:
        분기 순서를 나타내는 정수. 형식이 올바르지 않으면 None.

    Raises:
        없음
    """
    # 전각 숫자("２０２６Q4")는 isdecimal()을 통과하므로 ASCII로 한정한다 (schema.md 1.1)
    if not isinstance(quarter, str) or not quarter.isascii():
        return None
    if len(quarter) != 6 or quarter[4] != "Q":
        return None
    if not quarter[:4].isdecimal() or not quarter[5:].isdecimal():
        return None

    year = int(quarter[:4])
    quarter_number = int(quarter[5:])
    if quarter_number not in (1, 2, 3, 4):
        return None

    return year * 4 + quarter_number - 1


def _prev_quarter(quarter: str) -> str | None:
    """주어진 분기의 바로 이전 분기를 반환한다.

    Args:
        quarter: "YYYYQn" 형식의 분기 문자열.

    Returns:
        바로 이전 분기 문자열. 형식이 올바르지 않으면 None.

    Raises:
        없음
    """
    quarter_index = _quarter_index(quarter)
    if quarter_index is None:
        return None

    year, quarter_offset = divmod(quarter_index - 1, 4)
    return f"{year:04d}Q{quarter_offset + 1}"


def estimate_revenue(
    quarterly_df: pd.DataFrame,
    actuals_df: pd.DataFrame,
    target_quarter: str,
) -> dict:
    """과거 분기별 달러 매출 대비 수출 비율로 대상 분기 매출을 추정한다.

    Args:
        quarterly_df: 분기별 수출·환율 집계 데이터프레임.
        actuals_df: 분기 확정 매출 데이터프레임.
        target_quarter: 매출을 추정할 대상 분기("YYYYQn").

    Returns:
        대상 분기, 추정 매출 범위, 전분기 대비 증감률, 사용 비율,
        가용 월 수, 처리 상태를 담은 딕셔너리.

    Raises:
        없음
    """
    result = {
        "quarter": target_quarter,
        "estimate_krw": None,
        "lower_krw": None,
        "upper_krw": None,
        "qoq_change_pct": None,
        "ratio_used": None,
        "months_available": 0,
        "status": FORECAST_STATUS_NO_DATA,
    }

    if _quarter_index(target_quarter) is None:
        return result

    # 1) 대상 분기 행 확인 → 없거나 자료가 0개월이거나 환율이 없으면 no_data
    target_rows = quarterly_df[quarterly_df["quarter"] == target_quarter]
    if target_rows.empty:
        return result

    target_row = target_rows.iloc[0]
    if pd.isna(target_row["months_available"]):
        return result
    months_available = int(target_row["months_available"])
    if months_available <= 0:
        return result

    result["months_available"] = months_available

    if pd.isna(target_row["export_usd"]) or pd.isna(target_row["fx_avg"]):
        return result
    export_usd = float(target_row["export_usd"])
    fx_avg = float(target_row["fx_avg"])

    # 2) 기준 분기: 대상 분기보다 앞서고, 실적이 있고, 3개월 자료·수출>0·환율>0인 분기
    actuals = actuals_df.loc[actuals_df["revenue_krw"].notna(), ["quarter", "revenue_krw"]]
    merged = quarterly_df.merge(actuals, on="quarter", how="inner")
    base = merged[
        (merged["quarter"] < target_quarter)
        & (merged["months_available"] == MONTHS_PER_QUARTER)
        & (merged["export_usd"] > 0)
        & (merged["fx_avg"] > 0)
    ].sort_values("quarter")

    if len(base) < RATIO_WINDOW:
        result["status"] = FORECAST_STATUS_INSUFFICIENT
        return result

    # 3) 가장 최근 기준 분기 4개의 비율 → 중앙값·하한·상한
    recent = base.tail(RATIO_WINDOW)
    ratios = ((recent["revenue_krw"] / recent["fx_avg"]) / recent["export_usd"]).tolist()

    estimated_export_usd = export_usd * MONTHS_PER_QUARTER / months_available
    ratio_used = sum(ratios) / len(ratios)
    estimate_krw = estimated_export_usd * ratio_used * fx_avg
    lower_krw = estimated_export_usd * min(ratios) * fx_avg
    upper_krw = estimated_export_usd * max(ratios) * fx_avg

    # 4) 직전 분기 실적이 있으면 전분기 대비 증감률
    previous = actuals[actuals["quarter"] == _prev_quarter(target_quarter)]
    qoq_change_pct = None
    if not previous.empty and previous["revenue_krw"].iloc[0] != 0:
        previous_revenue = float(previous["revenue_krw"].iloc[0])
        qoq_change_pct = (estimate_krw / previous_revenue - 1.0) * 100.0

    return {
        "quarter": target_quarter,
        "estimate_krw": float(estimate_krw),
        "lower_krw": float(lower_krw),
        "upper_krw": float(upper_krw),
        "qoq_change_pct": qoq_change_pct,
        "ratio_used": float(ratio_used),
        "months_available": months_available,
        "status": FORECAST_STATUS_OK,
    }