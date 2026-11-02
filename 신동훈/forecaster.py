import pandas as pd


RATIO_WINDOW = 4


def _quarter_index(quarter: str) -> int | None:
    """분기 문자열을 시간순 비교용 정수로 변환한다.

    Args:
        quarter: "YYYYQn" 형식의 분기 문자열.

    Returns:
        분기 순서를 나타내는 정수. 형식이 올바르지 않으면 None.

    Raises:
        없음
    """
    if not isinstance(quarter, str):
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
        "status": "no_data",
    }

    target_index = _quarter_index(target_quarter)
    if target_index is None:
        return result



    target_rows = quarterly_df[
        quarterly_df["quarter"] == target_quarter
    ]
    if target_rows.empty:
        return result

    target_row = target_rows.iloc[0]
    months_value = target_row["months_available"]
    if pd.isna(months_value):
        return result

    try:
        months_available = int(months_value)
    except (TypeError, ValueError, OverflowError):
        return result

    if months_available <= 0:
        return result

    result["months_available"] = months_available

    export_usd = target_row["export_usd"]
    fx_avg = target_row["fx_avg"]
    if pd.isna(export_usd) or pd.isna(fx_avg):
        return result

    try:
        export_usd = float(export_usd)
        fx_avg = float(fx_avg)
    except (TypeError, ValueError, OverflowError):
        return result

    quarterly_by_quarter = {}
    for row in quarterly_df.itertuples(index=False):
        row_values = row._asdict()
        quarter = row_values["quarter"]
        quarter_index = _quarter_index(quarter)
        if quarter_index is not None:
            quarterly_by_quarter[quarter] = row_values

    actuals_by_quarter = {}
    for row in actuals_df.itertuples(index=False):
        row_values = row._asdict()
        quarter = row_values["quarter"]
        quarter_index = _quarter_index(quarter)
        if quarter_index is not None:
            actuals_by_quarter[quarter] = row_values

    candidate_quarters = []
    for quarter in set(quarterly_by_quarter) & set(actuals_by_quarter):
        quarter_index = _quarter_index(quarter)
        if quarter_index is None or quarter_index >= target_index:
            continue

        quarterly_row = quarterly_by_quarter[quarter]
        actuals_row = actuals_by_quarter[quarter]
        revenue_krw = actuals_row["revenue_krw"]
        historical_export = quarterly_row["export_usd"]
        historical_fx = quarterly_row["fx_avg"]
        historical_months = quarterly_row["months_available"]

        if (
            pd.isna(revenue_krw)
            or pd.isna(historical_export)
            or pd.isna(historical_fx)
            or pd.isna(historical_months)
        ):
            continue

        try:
            historical_months = int(historical_months)
            revenue_krw = float(revenue_krw)
            historical_export = float(historical_export)
            historical_fx = float(historical_fx)
        except (TypeError, ValueError, OverflowError):
            continue

        if (
            historical_months != 3
            or historical_export <= 0
        ):
            continue

        candidate_quarters.append(
            (quarter_index, revenue_krw, historical_export, historical_fx)
        )

    if len(candidate_quarters) < RATIO_WINDOW:
        result["status"] = "insufficient_history"
        return result

    candidate_quarters.sort(key=lambda item: item[0])
    recent_quarters = candidate_quarters[-RATIO_WINDOW:]

    ratios = [
        (revenue_krw / historical_fx) / historical_export
        for _, revenue_krw, historical_export, historical_fx in recent_quarters
    ]

    estimated_export_usd = export_usd * 3.0 / months_available
    ratio_used = sum(ratios) / RATIO_WINDOW
    estimate_krw = estimated_export_usd * ratio_used * fx_avg
    lower_krw = estimated_export_usd * min(ratios) * fx_avg
    upper_krw = estimated_export_usd * max(ratios) * fx_avg

    previous_quarter = _prev_quarter(target_quarter)
    previous_revenue = None
    if previous_quarter is not None:
        previous_row = actuals_by_quarter.get(previous_quarter)
        if previous_row is not None:
            revenue_value = previous_row["revenue_krw"]
            if not pd.isna(revenue_value):
                try:
                    previous_revenue = float(revenue_value)
                except (TypeError, ValueError, OverflowError):
                    previous_revenue = None

    qoq_change_pct = None
    if previous_revenue is not None and previous_revenue != 0:
        qoq_change_pct = (estimate_krw / previous_revenue - 1.0) * 100.0

    return {
        "quarter": target_quarter,
        "estimate_krw": float(estimate_krw),
        "lower_krw": float(lower_krw),
        "upper_krw": float(upper_krw),
        "qoq_change_pct": (
            float(qoq_change_pct) if qoq_change_pct is not None else None
        ),
        "ratio_used": float(ratio_used),
        "months_available": months_available,
        "status": "ok",
    }