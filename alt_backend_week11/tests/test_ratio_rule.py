"""estimate_revenue의 ratio_rule 옵션 테스트.

    R01~R05  규칙별 계산식, 범위(하한 <= 중앙값 <= 상한), 잘못된 규칙명
    R06      미래 실적을 읽지 않음 (drift도 대상 분기 이후 실적에 영향받지 않음)
    B01~B02  시점 기준 백테스트: drift가 avg보다 정확한지 회귀 방지
"""

import math
from pathlib import Path

import pandas as pd
import pytest

import backtest_ratio_rule as bt
from hynix_nowcast import forecaster

FX = 1000.0
EXPORT = 1_000_000_000.0
RATIOS = (2.0, 2.2, 2.6, 3.0)  # 기준 분기 4개의 (매출/환율)/수출 비율, 오래된 순


def _tables(ratios=RATIOS, target_months=3):
    quarters = ["2025Q1", "2025Q2", "2025Q3", "2025Q4"]
    quarterly = pd.DataFrame(
        {
            "quarter": quarters + ["2026Q1"],
            "export_usd": [EXPORT] * 4 + [EXPORT * target_months / 3],
            "months_available": [3, 3, 3, 3, target_months],
            "fx_avg": [FX] * 5,
        }
    )
    actuals = pd.DataFrame(
        {
            "quarter": quarters,
            "revenue_krw": [r * FX * EXPORT for r in ratios],
            "announced_date": ["2025-04-25", "2025-07-25", "2025-10-25", "2026-01-25"],
        }
    )
    return quarterly, actuals


@pytest.mark.parametrize(
    "rule, expected_ratio",
    [
        ("avg", sum(RATIOS) / 4),
        ("last", RATIOS[-1]),
        ("drift", RATIOS[-1] * math.exp(math.log(RATIOS[-1] / RATIOS[0]) / 3)),
    ],
)
def test_r01_rule_formula(rule, expected_ratio):
    quarterly, actuals = _tables()
    result = forecaster.estimate_revenue(quarterly, actuals, "2026Q1", ratio_rule=rule)
    assert result["status"] == "ok"
    assert result["ratio_used"] == pytest.approx(expected_ratio)
    assert result["estimate_krw"] == pytest.approx(EXPORT * expected_ratio * FX)


def test_r02_default_is_drift():
    quarterly, actuals = _tables()
    assert forecaster.DEFAULT_RATIO_RULE == "drift"
    default = forecaster.estimate_revenue(quarterly, actuals, "2026Q1")
    drift = forecaster.estimate_revenue(quarterly, actuals, "2026Q1", ratio_rule="drift")
    assert default == drift


@pytest.mark.parametrize("rule", forecaster.RATIO_RULES)
def test_r03_band_contains_estimate(rule):
    """drift는 기준 비율 최댓값보다 커질 수 있으므로 상한이 중앙값보다 작아지면 안 된다."""
    quarterly, actuals = _tables()
    result = forecaster.estimate_revenue(quarterly, actuals, "2026Q1", ratio_rule=rule)
    assert result["lower_krw"] <= result["estimate_krw"] <= result["upper_krw"]


def test_r04_avg_band_unchanged():
    """avg 규칙의 하한, 상한은 12주차 방식(기준 비율 최솟값, 최댓값)과 같다."""
    quarterly, actuals = _tables()
    result = forecaster.estimate_revenue(quarterly, actuals, "2026Q1", ratio_rule="avg")
    assert result["lower_krw"] == pytest.approx(EXPORT * min(RATIOS) * FX)
    assert result["upper_krw"] == pytest.approx(EXPORT * max(RATIOS) * FX)


def test_r05_unknown_rule_raises():
    quarterly, actuals = _tables()
    with pytest.raises(ValueError, match="ratio_rule"):
        forecaster.estimate_revenue(quarterly, actuals, "2026Q1", ratio_rule="dirft")


def test_r06_ignores_future_actuals():
    quarterly, actuals = _tables()
    future = pd.concat(
        [actuals, pd.DataFrame({"quarter": ["2026Q1"], "revenue_krw": [9e15], "announced_date": ["2026-04-25"]})],
        ignore_index=True,
    )
    base = forecaster.estimate_revenue(quarterly, actuals, "2026Q1", ratio_rule="drift")
    with_future = forecaster.estimate_revenue(quarterly, future, "2026Q1", ratio_rule="drift")
    assert base == with_future


@pytest.fixture(scope="module")
def backtest_inputs():
    return bt.load_inputs(Path(bt.ROOT) / "samples" / "exports_normal.csv")


def test_b01_backtest_uses_only_released_data(backtest_inputs):
    exports, fx, actuals = backtest_inputs
    table = bt.run_backtest(exports, fx, actuals, "drift")
    assert len(table) > 0
    assert (pd.to_datetime(table["release_date"]) > pd.to_datetime(table["month"] + "-01")).all()


def test_b02_drift_beats_avg_on_sample(backtest_inputs):
    """샘플 자료(2025.01~2026.09 공개 시점)에서 drift의 MAPE가 avg보다 낮아야 한다 (회귀 방지)."""
    exports, fx, actuals = backtest_inputs
    avg = bt.summarize(bt.run_backtest(exports, fx, actuals, "avg"))
    drift = bt.summarize(bt.run_backtest(exports, fx, actuals, "drift"))
    assert drift["n"] == avg["n"] > 0
    assert drift["mape_pct"] < avg["mape_pct"]
