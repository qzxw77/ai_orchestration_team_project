import math
from typing import Any

import pandas as pd


ALLOWED_REGIONS = ("이천시", "청주시")
STD_EPSILON = 1e-9


def _is_valid_ym(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 7
        and value[4] == "-"
        and value[:4].isdigit()
        and value[5:].isdigit()
        and 1 <= int(value[5:]) <= 12
    )


def _shift_ym(ym: str, months: int) -> str:
    year = int(ym[:4])
    month = int(ym[5:])
    index = year * 12 + month - 1 + months
    shifted_year, shifted_month = divmod(index, 12)
    return f"{shifted_year:04d}-{shifted_month + 1:02d}"


def detect_anomaly(
    exports_df: pd.DataFrame,
    target_ym: str,
    threshold: float = 2.0,
) -> dict:
    """대상 월 수출의 전년 동월 대비 증가율 이상 여부를 판정한다.

    Args:
        exports_df: 지역별 월 수출 데이터프레임.
        target_ym: 판정 대상 월(YYYY-MM).
        threshold: 이상치 판정에 사용할 절댓값 기준 z-score.

    Returns:
        ym, yoy_pct, z_score, is_anomaly, reason을 담은 딕셔너리.

    Raises:
        없음
    """
    default = {
        "ym": target_ym,
        "yoy_pct": None,
        "z_score": None,
        "is_anomaly": False,
        "reason": "데이터 부족",
    }

    try:
        if not _is_valid_ym(target_ym):
            return default

        threshold_value = float(threshold)
        if not math.isfinite(threshold_value):
            return default

        if not isinstance(exports_df, pd.DataFrame) or exports_df.empty:
            return default

        required_columns = {"ym", "region", "export_usd"}
        if not required_columns.issubset(exports_df.columns):
            return default

        working = exports_df.copy()
        monthly_regions: dict[str, dict[str, float]] = {}

        for row in working[["ym", "region", "export_usd"]].itertuples(
            index=False,
            name=None,
        ):
            ym, region, export_usd = row

            if not _is_valid_ym(ym) or region not in ALLOWED_REGIONS:
                continue

            try:
                amount = float(export_usd)
            except (TypeError, ValueError, OverflowError):
                continue

            if not math.isfinite(amount) or amount < 0:
                continue

            monthly_regions.setdefault(
                ym,
                {"이천시": 0.0, "청주시": 0.0},
            )[region] += amount

        monthly_totals = {
            ym: regions["이천시"] + regions["청주시"]
            for ym, regions in monthly_regions.items()
            if all(region in regions for region in ALLOWED_REGIONS)
        }

        required_months = {
            _shift_ym(target_ym, offset)
            for offset in range(-24, 1)
        }
        if not required_months.issubset(monthly_totals):
            return default

        yoy_values: list[float] = []
        for offset in range(-12, 1):
            ym = _shift_ym(target_ym, offset)
            previous_ym = _shift_ym(ym, -12)
            previous_total = monthly_totals[previous_ym]

            if previous_total == 0:
                return default

            yoy_values.append(
                (monthly_totals[ym] / previous_total - 1.0) * 100.0
            )

        yoy_pct = float(yoy_values[-1])
        mean = sum(yoy_values[:-1]) / 12.0
        variance = sum(
            (value - mean) ** 2 for value in yoy_values[:-1]
        ) / 11.0
        standard_deviation = math.sqrt(variance)

        if standard_deviation < STD_EPSILON:
            default["yoy_pct"] = yoy_pct
            return default

        z_score = float((yoy_pct - mean) / standard_deviation)
        is_anomaly = abs(z_score) > threshold_value

        if not is_anomaly:
            reason = "정상"
        elif z_score > 0:
            reason = "급증"
        else:
            reason = "급감"

        return {
            "ym": target_ym,
            "yoy_pct": yoy_pct,
            "z_score": z_score,
            "is_anomaly": bool(is_anomaly),
            "reason": reason,
        }
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
        return default