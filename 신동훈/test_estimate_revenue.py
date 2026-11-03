"""estimate_revenue 테스트 — ① 논리 설계의 테스트 케이스 표(T07~T11, A01~A04).

공통 입력 F는 설계 문서 파트 4를 따른다.
금액·비율 비교는 pytest.approx(rel=1e-6)로 한다.
"""
import math

import pandas as pd
import pytest

from forecaster import estimate_revenue

REL = 1e-6

FORECAST_KEYS = {
    "quarter",
    "estimate_krw",
    "lower_krw",
    "upper_krw",
    "qoq_change_pct",
    "ratio_used",
    "months_available",
    "status",
}
NUMERIC_KEYS = ["estimate_krw", "lower_krw", "upper_krw", "qoq_change_pct", "ratio_used"]


# ---------------------------------------------------------------------------
# 공통 입력 F — 테스트마다 새 DataFrame을 만들어 서로 영향을 주지 않게 한다
# ---------------------------------------------------------------------------
@pytest.fixture
def quarterly_f() -> pd.DataFrame:
    """공통 입력 F의 quarterly 표 (2025Q1~2026Q1)."""
    return pd.DataFrame(
        {
            "quarter": ["2025Q1", "2025Q2", "2025Q3", "2025Q4", "2026Q1"],
            "export_usd": [1.0e10, 1.0e10, 1.0e10, 1.0e10, 1.2e10],
            "months_available": [3, 3, 3, 3, 3],
            "fx_avg": [1400.0, 1400.0, 1400.0, 1400.0, 1450.0],
        }
    )


@pytest.fixture
def actuals_f() -> pd.DataFrame:
    """공통 입력 F의 actuals 표 (비율 1.4·1.5·1.5·1.6). announced_date는 가상 값."""
    return pd.DataFrame(
        {
            "quarter": ["2025Q1", "2025Q2", "2025Q3", "2025Q4"],
            "revenue_krw": [1.96e13, 2.10e13, 2.10e13, 2.24e13],
            "announced_date": ["2025-04-24", "2025-07-24", "2025-10-23", "2026-01-22"],
        }
    )


# ---------------------------------------------------------------------------
# 보조 검사 함수
# ---------------------------------------------------------------------------
def assert_forecast_keys(result: dict) -> None:
    """반환 dict가 항상 키 8개를 정확히 가지고, months_available이 int인지 확인한다."""
    assert set(result.keys()) == FORECAST_KEYS
    assert isinstance(result["months_available"], int)


def assert_numbers_none(result: dict) -> None:
    """숫자 값 5개가 모두 None인지 확인한다."""
    for key in NUMERIC_KEYS:
        assert result[key] is None, f"{key}는 None이어야 합니다: {result[key]!r}"


# ---------------------------------------------------------------------------
# 정상
# ---------------------------------------------------------------------------
def test_t07_full_quarter(quarterly_f, actuals_f):
    """T07 정상: 3개월 자료가 모두 있는 대상 분기 → 26.1조(24.36~27.84조)."""
    result = estimate_revenue(quarterly_f, actuals_f, "2026Q1")

    assert_forecast_keys(result)
    assert result["status"] == "ok"
    assert result["quarter"] == "2026Q1"
    assert result["estimate_krw"] == pytest.approx(2.61e13, rel=REL)
    assert result["lower_krw"] == pytest.approx(2.436e13, rel=REL)
    assert result["upper_krw"] == pytest.approx(2.784e13, rel=REL)
    assert result["ratio_used"] == pytest.approx(1.5, rel=REL)
    assert result["qoq_change_pct"] == pytest.approx((2.61e13 / 2.24e13 - 1) * 100, rel=REL)
    assert result["months_available"] == 3


def test_t08_partial_months_scaled(quarterly_f, actuals_f):
    """T08 정상: 2개월분 80억 달러 → 3개월분 120억 달러로 환산해 T07과 같은 금액."""
    target = quarterly_f["quarter"] == "2026Q1"
    quarterly_f.loc[target, "export_usd"] = 8.0e9
    quarterly_f.loc[target, "months_available"] = 2

    result = estimate_revenue(quarterly_f, actuals_f, "2026Q1")

    assert_forecast_keys(result)
    assert result["status"] == "ok"
    assert result["estimate_krw"] == pytest.approx(2.61e13, rel=REL)
    assert result["lower_krw"] == pytest.approx(2.436e13, rel=REL)
    assert result["upper_krw"] == pytest.approx(2.784e13, rel=REL)
    assert result["months_available"] == 2


# ---------------------------------------------------------------------------
# 경계
# ---------------------------------------------------------------------------
def test_t09_insufficient_history(quarterly_f, actuals_f):
    """T09 경계: actuals의 2025Q1 삭제 → 기준 분기 3개 → insufficient_history."""
    actuals = actuals_f[actuals_f["quarter"] != "2025Q1"].reset_index(drop=True)

    result = estimate_revenue(quarterly_f, actuals, "2026Q1")

    assert_forecast_keys(result)
    assert result["status"] == "insufficient_history"
    assert result["quarter"] == "2026Q1"
    assert_numbers_none(result)
    assert result["months_available"] == 3


def test_t10_ignores_future_actuals(quarterly_f, actuals_f):
    """T10 경계: 대상 분기 실적(30.0조)이 있어도 결과가 T07과 완전히 같다."""
    expected = estimate_revenue(quarterly_f, actuals_f, "2026Q1")

    future_row = pd.DataFrame(
        {"quarter": ["2026Q1"], "revenue_krw": [3.0e13], "announced_date": ["2026-04-23"]}
    )
    actuals_with_future = pd.concat([actuals_f, future_row], ignore_index=True)

    result = estimate_revenue(quarterly_f, actuals_with_future, "2026Q1")

    assert result == expected


def test_a01_zero_months_available(quarterly_f, actuals_f):
    """A01 경계: 대상 분기 months_available 0 → no_data, months_available 0."""
    target = quarterly_f["quarter"] == "2026Q1"
    quarterly_f.loc[target, "export_usd"] = 0.0
    quarterly_f.loc[target, "months_available"] = 0

    result = estimate_revenue(quarterly_f, actuals_f, "2026Q1")

    assert_forecast_keys(result)
    assert result["status"] == "no_data"
    assert_numbers_none(result)
    assert result["months_available"] == 0


def test_a03_no_prev_quarter_actual(quarterly_f, actuals_f):
    """A03 경계: 직전 분기(2025Q4) 실적 없음 → 더 앞선 4개 분기로 계산, qoq는 None."""
    quarterly = pd.concat(
        [
            pd.DataFrame(
                {
                    "quarter": ["2024Q4"],
                    "export_usd": [1.0e10],
                    "months_available": [3],
                    "fx_avg": [1400.0],
                }
            ),
            quarterly_f,
        ],
        ignore_index=True,
    )
    actuals = pd.concat(
        [
            pd.DataFrame(
                {"quarter": ["2024Q4"], "revenue_krw": [2.10e13], "announced_date": ["2025-01-23"]}
            ),
            actuals_f[actuals_f["quarter"] != "2025Q4"],
        ],
        ignore_index=True,
    )

    result = estimate_revenue(quarterly, actuals, "2026Q1")

    # 기준 분기 = 2024Q4·2025Q1·2025Q2·2025Q3 (비율 1.5·1.4·1.5·1.5)
    assert_forecast_keys(result)
    assert result["status"] == "ok"
    assert result["ratio_used"] == pytest.approx(1.475, rel=REL)
    assert result["estimate_krw"] == pytest.approx(2.5665e13, rel=REL)
    assert result["lower_krw"] == pytest.approx(2.436e13, rel=REL)
    assert result["upper_krw"] == pytest.approx(2.61e13, rel=REL)
    assert result["qoq_change_pct"] is None
    assert result["months_available"] == 3


# ---------------------------------------------------------------------------
# 예외
# ---------------------------------------------------------------------------
def test_t11_no_target_row(quarterly_f, actuals_f):
    """T11 예외: quarterly에 대상 분기(2026Q2) 행 없음 → no_data, 예외 없음."""
    result = estimate_revenue(quarterly_f, actuals_f, "2026Q2")

    assert_forecast_keys(result)
    assert result["status"] == "no_data"
    assert result["quarter"] == "2026Q2"
    assert_numbers_none(result)
    assert result["months_available"] == 0


def test_a02_target_fx_missing(quarterly_f, actuals_f):
    """A02 예외: 대상 분기 fx_avg 결측 → no_data, months_available은 대상 행 값 유지."""
    quarterly_f.loc[quarterly_f["quarter"] == "2026Q1", "fx_avg"] = math.nan

    result = estimate_revenue(quarterly_f, actuals_f, "2026Q1")

    assert_forecast_keys(result)
    assert result["status"] == "no_data"
    assert_numbers_none(result)
    assert result["months_available"] == 3


def test_a04_revenue_nan_not_counted(quarterly_f, actuals_f):
    """A04 예외: 2025Q1 revenue_krw 결측 → 실적 없음으로 보고 기준 분기 3개 → insufficient_history."""
    actuals_f.loc[actuals_f["quarter"] == "2025Q1", "revenue_krw"] = math.nan

    result = estimate_revenue(quarterly_f, actuals_f, "2026Q1")

    assert_forecast_keys(result)
    assert result["status"] == "insufficient_history"
    assert_numbers_none(result)
    assert result["months_available"] == 3