"""detect_anomaly 테스트 (정상 2, 경계 2, 예외 2)
모든 금액은 가상의 더미 값 (실제 관세청 통계 아님)

공통 입력 A (단위: 억 달러, 매달 이천시 62.5% + 청주시 37.5% 두 행)
- 2024-09 ~ 2025-08: 매달 64
- 2025-09 ~ 2026-08: 64, 88, 40, 80, 48, 88, 40, 64, 64, 64, 64, 64
- 2026-09 (대상 월): 테스트마다 다름
직전 12개월 전년동월비 평균 0, 표본 표준편차 25
대상 월 전년동월비 = (대상 월 합계 / 64 - 1) * 100, z = 전년동월비 / 25
"""

import pandas as pd
import pytest

from forecaster import detect_anomaly

TARGET = "2026-09"


def _make_exports(totals: dict) -> pd.DataFrame:
    """월 합계(억 달러)를 이천시 62.5%, 청주시 37.5% 두 행으로 나눠 exports 표를 만든다."""
    rows = []
    for ym, total in totals.items():
        for region, share in (("이천시", 0.625), ("청주시", 0.375)):
            rows.append({
                "ym": ym,
                "region": region,
                "hs_code": "854232",
                "export_usd": total * share * 1e8,
                "collected_at": "2026-10-15",
            })
    return pd.DataFrame(rows)


def _months_from_2024_09(count: int) -> list[str]:
    """2024-09부터 count개월의 "YYYY-MM" 목록"""
    result = []
    for i in range(count):
        year, month = 2024 + (8 + i) // 12, (8 + i) % 12 + 1
        result.append(f"{year:04d}-{month:02d}")
    return result


def _totals_a(target_total: float) -> dict:
    """공통 입력 A의 월 합계 25개월, 대상 월(2026-09) 합계만 바꿔 쓴다."""
    values = [64] * 12 + [64, 88, 40, 80, 48, 88, 40, 64, 64, 64, 64, 64] + [target_total]
    return dict(zip(_months_from_2024_09(25), values))


INSUFFICIENT = {"yoy_pct": None, "z_score": None, "is_anomaly": False, "reason": "데이터 부족"}


# ---------- 정상 ----------

def test_normal_within_range():
    """정상 1: 대상 월 64 -> 80, 전년동월비 +25%, z = 1.0 -> 정상"""
    result = detect_anomaly(_make_exports(_totals_a(80)), TARGET)
    assert result["ym"] == TARGET
    assert result["yoy_pct"] == pytest.approx(25.0)
    assert result["z_score"] == pytest.approx(1.0)
    assert result["is_anomaly"] is False
    assert result["reason"] == "정상"


def test_normal_surge():
    """정상 2: 대상 월 64 -> 128, 전년동월비 +100%, z = 4.0 -> 급증"""
    result = detect_anomaly(_make_exports(_totals_a(128)), TARGET)
    assert result["yoy_pct"] == pytest.approx(100.0)
    assert result["z_score"] == pytest.approx(4.0)
    assert result["is_anomaly"] is True
    assert result["reason"] == "급증"


# ---------- 경계 ----------

def test_boundary_24_months_is_insufficient():
    """경계 1: 25개월이 필요한데 가장 오래된 달(2024-09)이 없어 24개월이면 데이터 부족"""
    totals = _totals_a(80)
    del totals["2024-09"]
    result = detect_anomaly(_make_exports(totals), TARGET)
    assert result == {"ym": TARGET, **INSUFFICIENT}


def test_boundary_zero_std_is_insufficient():
    """경계 2: 전년동월비 13개가 모두 10%로 같으면 표준편차 0 -> 데이터 부족

    기준 해 100, 직전 12개월 110, 대상 월 121
    pandas std()는 이때 0이 아니라 약 1.9e-15를 돌려주므로 '== 0' 비교로는 통과하지 못한다.
    yoy_pct는 채우고 z_score는 None으로 둔다.
    """
    totals = dict(zip(_months_from_2024_09(25), [100] * 12 + [110] * 12 + [121]))
    result = detect_anomaly(_make_exports(totals), TARGET)
    assert result["yoy_pct"] == pytest.approx(10.0)
    assert result["z_score"] is None
    assert result["is_anomaly"] is False
    assert result["reason"] == "데이터 부족"


# ---------- 예외 ----------

def test_exception_invalid_target_ym():
    """예외 1: target_ym이 존재하지 않는 달("2026-13")이면 예외 없이 데이터 부족"""
    result = detect_anomaly(_make_exports(_totals_a(80)), "2026-13")
    assert result == {"ym": "2026-13", **INSUFFICIENT}


def test_exception_zero_total_twelve_months_before():
    """예외 2: 2025-03 합계가 0이면 2026-03 전년동월비를 0으로 나누게 되므로
    예외(ZeroDivisionError)나 inf 없이 데이터 부족"""
    totals = _totals_a(80)
    totals["2025-03"] = 0
    result = detect_anomaly(_make_exports(totals), TARGET)
    assert result == {"ym": TARGET, **INSUFFICIENT}
