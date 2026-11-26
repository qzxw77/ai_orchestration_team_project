"""estimate_revenue의 ratio_rule 옵션 테스트.

    R01~R05  규칙별 계산식, 범위(하한 <= 중앙값 <= 상한), 잘못된 규칙명
    R06      미래 실적을 읽지 않음 (모든 규칙, auto의 채점 포함)
    R07~R09  auto: 과거 오차가 가장 작은 규칙 선택, 채점할 분기가 없으면 avg, 적용 규칙 기록
    B01~B03  시점 기준 백테스트: 기본값(auto)이 avg보다 정확한지(전체, OOS) 회귀 방지, IS/OOS 분할
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


def test_r02_default_is_auto():
    quarterly, actuals = _tables()
    assert forecaster.DEFAULT_RATIO_RULE == "auto"
    default = forecaster.estimate_revenue(quarterly, actuals, "2026Q1")
    auto = forecaster.estimate_revenue(quarterly, actuals, "2026Q1", ratio_rule="auto")
    assert default == auto


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


@pytest.mark.parametrize("rule", forecaster.RATIO_RULES)
def test_r06_ignores_future_actuals(rule):
    quarterly, actuals = _long_tables([2.0, 2.2, 2.4, 2.6, 2.8, 3.0])
    future = pd.concat(
        [actuals, pd.DataFrame({"quarter": ["2026Q3"], "revenue_krw": [9e15], "announced_date": ["2026-10-25"]})],
        ignore_index=True,
    )
    base = forecaster.estimate_revenue(quarterly, actuals, "2026Q3", ratio_rule=rule)
    with_future = forecaster.estimate_revenue(quarterly, future, "2026Q3", ratio_rule=rule)
    assert base == with_future


def _long_tables(ratios):
    """2025Q1부터 len(ratios)개 기준 분기 + 대상 분기(그 다음 분기, 3개월) 표."""
    quarters = [f"{2025 + i // 4}Q{i % 4 + 1}" for i in range(len(ratios) + 1)]
    quarterly = pd.DataFrame(
        {"quarter": quarters, "export_usd": [EXPORT] * len(quarters), "months_available": [3] * len(quarters),
         "fx_avg": [FX] * len(quarters)}
    )
    actuals = pd.DataFrame(
        {"quarter": quarters[:-1], "revenue_krw": [r * FX * EXPORT for r in ratios],
         "announced_date": ["2025-01-01"] * len(ratios)}
    )
    return quarterly, actuals


def test_r07_auto_picks_lowest_past_error():
    """비율이 일정한 비율로 오르면 drift가 과거 분기를 정확히 맞히므로 auto는 drift를 고른다."""
    ratios = [2.0 * 1.1 ** i for i in range(6)]
    quarterly, actuals = _long_tables(ratios)
    result = forecaster.estimate_revenue(quarterly, actuals, "2026Q3", ratio_rule="auto")
    assert result["ratio_rule"] == "drift"
    assert result["ratio_used"] == pytest.approx(ratios[-1] * 1.1)


def test_r08_auto_without_scored_quarter_uses_avg():
    """기준 분기가 RATIO_WINDOW개뿐이면 채점할 분기가 없어 avg를 쓴다."""
    quarterly, actuals = _tables()
    result = forecaster.estimate_revenue(quarterly, actuals, "2026Q1", ratio_rule="auto")
    assert result["ratio_rule"] == "avg"
    assert result["ratio_used"] == pytest.approx(sum(RATIOS) / 4)


@pytest.mark.parametrize("rule", forecaster.BASE_RATIO_RULES)
def test_r09_result_records_rule(rule):
    quarterly, actuals = _tables()
    assert forecaster.estimate_revenue(quarterly, actuals, "2026Q1", ratio_rule=rule)["ratio_rule"] == rule


@pytest.fixture(scope="module")
def backtest_inputs():
    return bt.load_inputs(Path(bt.ROOT) / "samples" / "exports_normal.csv")


def test_b01_backtest_uses_only_released_data(backtest_inputs):
    exports, fx, actuals = backtest_inputs
    table = bt.run_backtest(exports, fx, actuals, "drift")
    assert len(table) > 0
    assert (pd.to_datetime(table["release_date"]) > pd.to_datetime(table["month"] + "-01")).all()


@pytest.fixture(scope="module")
def backtest_tables(backtest_inputs):
    exports, fx, actuals = backtest_inputs
    return {rule: bt.run_backtest(exports, fx, actuals, rule) for rule in forecaster.RATIO_RULES}


def test_b02_default_beats_avg_on_sample(backtest_tables):
    """샘플 자료에서 기본값(auto)의 MAPE가 전체, OOS(2026~) 모두 avg보다 낮아야 한다 (회귀 방지)."""
    default = backtest_tables[forecaster.DEFAULT_RATIO_RULE]
    avg = backtest_tables["avg"]
    assert bt.summarize(default)["n"] == bt.summarize(avg)["n"] > 0
    assert bt.summarize(default)["mape_pct"] < bt.summarize(avg)["mape_pct"]
    assert bt.summarize(default, start_ym="2026-01")["mape_pct"] < bt.summarize(avg, start_ym="2026-01")["mape_pct"]


def test_b03_is_oos_split_picks_is_best(backtest_tables):
    split = bt.is_oos_split(backtest_tables, "2026-01", forecaster.BASE_RATIO_RULES)
    assert split["picked"] == min(split["is_mape"], key=split["is_mape"].get)
    assert split["picked_oos_mape"] == split["oos_mape"][split["picked"]]
