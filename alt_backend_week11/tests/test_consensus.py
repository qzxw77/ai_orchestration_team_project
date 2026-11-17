"""컨센서스 비교와 주가 영향 판단 테스트 (설계서: 신동훈/consensus_price_impact_design.md 9장 C01~C19).

    load_consensus             consensus.csv 읽기와 형식 검사
    implied_quarter_consensus  연간 컨센서스 -> 분기 컨센서스 (4분기 정확, 1~3분기 환산)
    compare_consensus          괴리율과 상회/부합/하회 판정
    judge_price_impact         주가 영향 방향과 판단 신뢰도
    backend.consensus_facts    화면 표시용 문자열

공통 입력 G (단위 조 원): 2025년 실적 10, 15, 20, 25 / 2026년 실적 20, 25, 30, 발표일은 각 분기 다음 달 25일.
consensus: 2026-11-10 평균 105(최고 115, 최저 95), 2026-10-01 평균 100(최고 110, 최저 90).
"""

import copy
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

import backend
from hynix_nowcast import data_loader, forecaster

T = 1e12
CONSENSUS_HEADER = "as_of,fiscal_year,mean_krw,high_krw,low_krw,median_krw,source\n"


def _actuals(drop: tuple[str, ...] = ()) -> pd.DataFrame:
    rows = [
        ("2025Q1", 10, "2025-04-25"),
        ("2025Q2", 15, "2025-07-25"),
        ("2025Q3", 20, "2025-10-25"),
        ("2025Q4", 25, "2026-01-25"),
        ("2026Q1", 20, "2026-04-25"),
        ("2026Q2", 25, "2026-07-25"),
        ("2026Q3", 30, "2026-10-25"),
    ]
    return pd.DataFrame(
        [(q, v * T, d) for q, v, d in rows if q not in drop], columns=["quarter", "revenue_krw", "announced_date"]
    )


def _consensus(rows: list[tuple[str, int, float, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [(as_of, year, mean * T, high * T, low * T, mean * T, "FnGuide") for as_of, year, mean, high, low in rows],
        columns=list(data_loader.CONSENSUS_COLUMNS),
    ).astype({"fiscal_year": "int64"})


@pytest.fixture
def consensus_g() -> pd.DataFrame:
    return _consensus([("2026-10-01", 2026, 100, 110, 90), ("2026-11-10", 2026, 105, 115, 95)])


def _forecast(estimate: float, lower: float, upper: float, months: int = 3, status: str = "ok") -> dict:
    return {
        "quarter": "2026Q4",
        "estimate_krw": estimate * T,
        "lower_krw": lower * T,
        "upper_krw": upper * T,
        "qoq_change_pct": None,
        "ratio_used": 1.5,
        "months_available": months,
        "status": status,
    }


def _exact_consensus(center: float, dist_low: float, dist_high: float, **overrides) -> dict:
    result = forecaster._empty_consensus("2026Q4")
    result.update(
        status="ok",
        method="exact",
        remaining_quarters=1,
        center_krw=center * T,
        band_low_krw=center * T,
        band_high_krw=center * T,
        dist_low_krw=dist_low * T,
        dist_high_krw=dist_high * T,
        revision_pct=None,
        days_since_consensus=3,
        days_after_announcement=14,
    )
    result.update(overrides)
    return result


# =============================================================================
# load_consensus
# =============================================================================
def test_c01_load_consensus_normal(tmp_path: Path):
    path = tmp_path / "consensus.csv"
    path.write_text(
        CONSENSUS_HEADER
        + "2026-11-11,2026,\"363,041,268,000,000\",383602000000000,337589000000000,364027500000000,FnGuide\n"
        + "2026-11-10,2026,363041268000000,383602000000000,337589000000000,364027500000000,FnGuide\n",
        encoding="utf-8",
    )
    table = data_loader.load_consensus(str(path))
    assert len(table) == 2
    assert table["as_of"].tolist() == ["2026-11-10", "2026-11-11"]
    assert table["fiscal_year"].dtype == "int64"
    assert table["mean_krw"].dtype == "float64"
    assert table["mean_krw"].iloc[1] == pytest.approx(363.041268 * T)


def test_c02_load_consensus_missing_column(tmp_path: Path):
    path = tmp_path / "consensus.csv"
    path.write_text("as_of,fiscal_year,high_krw,low_krw,median_krw,source\n", encoding="utf-8")
    with pytest.raises(ValueError, match="필수 열 누락: mean_krw"):
        data_loader.load_consensus(str(path))


def test_load_consensus_rejects_mean_outside_high_low(tmp_path: Path):
    path = tmp_path / "consensus.csv"
    path.write_text(CONSENSUS_HEADER + "2026-11-11,2026,500,400,300,350,FnGuide\n", encoding="utf-8")
    with pytest.raises(ValueError, match="consensus.csv 형식 오류: 2행 low_krw <= mean_krw <= high_krw 아님"):
        data_loader.load_consensus(str(path))


def test_load_consensus_rejects_duplicate_date(tmp_path: Path):
    path = tmp_path / "consensus.csv"
    row = "2026-11-11,2026,350,400,300,350,FnGuide\n"
    path.write_text(CONSENSUS_HEADER + row + row, encoding="utf-8")
    with pytest.raises(ValueError, match="consensus.csv 날짜 중복: 2026-11-11"):
        data_loader.load_consensus(str(path))


def test_team_consensus_file_is_valid():
    """커밋된 data/consensus.csv가 형식 검사를 통과하고 FY1이 4분기 발표일에 다음 해로 넘어가야 한다."""
    data_dir = Path(__file__).resolve().parent.parent / "data"
    table = data_loader.load_consensus(str(data_dir / "consensus.csv"))
    actuals = data_loader.load_actuals(str(data_dir / "actuals.csv"))
    first_day = table.groupby("fiscal_year")["as_of"].min()
    for quarter, announced in actuals.loc[actuals["quarter"].str.endswith("Q4"), ["quarter", "announced_date"]].values:
        next_year = int(quarter[:4]) + 1
        if next_year in first_day.index:
            assert first_day[next_year] == announced


# =============================================================================
# implied_quarter_consensus
# =============================================================================
def test_c03_q4_exact(consensus_g):
    result = forecaster.implied_quarter_consensus(consensus_g, _actuals(), "2026Q4", "2026-11-17")
    assert result["status"] == "ok"
    assert result["method"] == "exact"
    assert result["center_krw"] == pytest.approx(30 * T)
    assert (result["dist_low_krw"], result["dist_high_krw"]) == (pytest.approx(20 * T), pytest.approx(40 * T))
    assert (result["band_low_krw"], result["band_high_krw"]) == (pytest.approx(30 * T), pytest.approx(30 * T))
    assert result["ytd_actual_krw"] == pytest.approx(75 * T)
    assert result["days_since_consensus"] == 7
    assert result["days_after_announcement"] == 16


def test_c04_q3_allocated_three_methods():
    consensus = _consensus([("2026-07-30", 2026, 105, 115, 95)])
    result = forecaster.implied_quarter_consensus(consensus, _actuals(), "2026Q3", "2026-08-01")
    assert result["status"] == "ok"
    assert result["method"] == "allocated"
    assert result["remaining_quarters"] == 2
    methods = result["methods"]
    assert methods["even"] == pytest.approx(30 * T, rel=1e-6)
    assert methods["prior_share"] == pytest.approx(60 * 20 / 45 * T, rel=1e-6)
    assert methods["const_growth"] == pytest.approx(28.197051 * T, rel=1e-6)
    assert result["center_krw"] == pytest.approx(28.197051 * T, rel=1e-6)
    assert result["band_low_krw"] == pytest.approx(26.666667 * T, rel=1e-6)
    assert result["band_high_krw"] == pytest.approx(30 * T, rel=1e-6)
    assert (result["dist_low_krw"], result["dist_high_krw"]) == (result["band_low_krw"], result["band_high_krw"])


def test_c05_prior_year_missing_uses_two_methods():
    consensus = _consensus([("2026-07-30", 2026, 105, 115, 95)])
    result = forecaster.implied_quarter_consensus(consensus, _actuals(drop=("2025Q2",)), "2026Q3", "2026-08-01")
    assert result["methods"]["prior_share"] is None
    assert result["center_krw"] == pytest.approx((30 + 28.197051) / 2 * T, rel=1e-6)


def test_c06_future_consensus_is_not_used(consensus_g):
    result = forecaster.implied_quarter_consensus(consensus_g, _actuals(), "2026Q4", "2026-11-05")
    assert result["consensus_as_of"] == "2026-10-01"
    assert result["center_krw"] == pytest.approx(25 * T)


def test_c07_previous_quarter_not_announced(consensus_g):
    result = forecaster.implied_quarter_consensus(consensus_g, _actuals(), "2026Q4", "2026-10-20")
    assert result["status"] == "not_ready"
    assert result["center_krw"] is None


def test_c08_no_consensus_for_target_year():
    consensus = _consensus([("2026-11-10", 2025, 105, 115, 95)])
    result = forecaster.implied_quarter_consensus(consensus, _actuals(), "2026Q4", "2026-11-17")
    assert result["status"] == "no_consensus"


def test_c09_remaining_not_positive():
    consensus = _consensus([("2026-11-10", 2026, 70, 80, 60)])
    result = forecaster.implied_quarter_consensus(consensus, _actuals(), "2026Q4", "2026-11-17")
    assert result["status"] == "invalid"
    assert result["center_krw"] is None


def test_c10_revision_against_30_days_earlier(consensus_g):
    result = forecaster.implied_quarter_consensus(consensus_g, _actuals(), "2026Q4", "2026-11-17")
    assert result["revision_pct"] == pytest.approx(5.0)
    assert result["revision_base_as_of"] == "2026-10-01"
    assert result["revision_base_krw"] == pytest.approx(100 * T)


def test_q1_target_uses_previous_year_q4_as_growth_base():
    consensus = _consensus([("2026-02-01", 2026, 100, 110, 90)])
    result = forecaster.implied_quarter_consensus(consensus, _actuals(), "2026Q1", "2026-02-02")
    assert result["status"] == "ok"
    assert result["remaining_quarters"] == 4
    assert result["ytd_actual_krw"] == 0
    assert result["methods"]["even"] == pytest.approx(25 * T)
    assert result["methods"]["prior_share"] == pytest.approx(100 * 10 / 70 * T)
    base = 25 * T  # 2025Q4 실적
    x = result["methods"]["const_growth"] / base
    assert base * (x + x**2 + x**3 + x**4) == pytest.approx(100 * T, rel=1e-6)


# =============================================================================
# compare_consensus
# =============================================================================
def test_c11_lower_above_consensus_is_strong_beat():
    result = forecaster.compare_consensus(_forecast(33, 31, 35), _exact_consensus(30, 20, 40))
    assert (result["status"], result["position"], result["strength"]) == ("ok", "상회", "강")
    assert result["surprise_pct"] == pytest.approx(10.0)
    assert result["dist_position_pct"] == pytest.approx(65.0)


def test_c12_surprise_exactly_band_is_weak_beat():
    result = forecaster.compare_consensus(_forecast(31.5, 29, 34), _exact_consensus(30, 20, 40))
    assert result["surprise_pct"] == pytest.approx(5.0)
    assert (result["position"], result["strength"]) == ("상회", "약")


def test_upper_below_consensus_is_strong_miss():
    result = forecaster.compare_consensus(_forecast(26, 24, 28), _exact_consensus(30, 20, 40))
    assert (result["position"], result["strength"]) == ("하회", "강")


def test_c13_allocated_inside_band_is_inline():
    consensus = _exact_consensus(28.197051, 26.666667, 30)
    consensus.update(method="allocated", remaining_quarters=2, band_low_krw=26.666667 * T, band_high_krw=30 * T)
    result = forecaster.compare_consensus(_forecast(29, 27, 31), consensus)
    assert (result["position"], result["strength"]) == ("부합", None)


def test_c14_forecast_without_estimate_is_unavailable():
    forecast = _forecast(30, 28, 32, status="no_data")
    result = forecaster.compare_consensus(forecast, _exact_consensus(30, 20, 40))
    assert result == {
        "status": "unavailable",
        "surprise_pct": None,
        "position": None,
        "strength": None,
        "dist_position_pct": None,
    }


# =============================================================================
# judge_price_impact
# =============================================================================
def test_c15_inline_with_revision_at_band_is_positive():
    forecast = _forecast(30.3, 28, 33)
    consensus = _exact_consensus(30, 20, 40, revision_pct=3.0)
    comparison = forecaster.compare_consensus(forecast, consensus)
    assert comparison["position"] == "부합"
    assert forecaster.judge_price_impact(forecast, consensus, comparison)["direction"] == "긍정"


def test_c16_design_example_2026q4():
    """설계서 6.6: 추정 128.4조(119.2~137.9조), 수출 2개월, 컨센서스 2026-11-11 기준 -> 긍정, 57점."""
    ytd = 52.5763 + 79.3187 + 104.6155
    consensus = _exact_consensus(
        363.041268 - ytd,
        337.589 - ytd,
        383.602 - ytd,
        revision_pct=(363.041268 / 342.2870758 - 1) * 100,
        days_since_consensus=6,
        days_after_announcement=14,
    )
    forecast = _forecast(128.4, 119.2, 137.9, months=2)
    comparison = forecaster.compare_consensus(forecast, consensus)
    impact = forecaster.judge_price_impact(forecast, consensus, comparison)
    assert comparison["position"] == "부합"
    assert comparison["surprise_pct"] == pytest.approx(1.477, abs=1e-3)
    assert impact["direction"] == "긍정"
    assert impact["confidence"] == 57
    assert impact["confidence_parts"] == {
        "months": 26.7,
        "strength": 6.1,
        "agreement": 8.9,
        "freshness": 15.0,
        "allocation_penalty": 0.0,
    }


def test_c17_right_after_announcement_has_no_freshness():
    forecast = _forecast(30.3, 28, 33)
    consensus = _exact_consensus(30, 20, 40, days_after_announcement=2)
    comparison = forecaster.compare_consensus(forecast, consensus)
    assert forecaster.judge_price_impact(forecast, consensus, comparison)["confidence_parts"]["freshness"] == 0.0


def test_c18_unavailable_comparison_is_unknown():
    forecast = _forecast(30, 28, 32, status="no_data")
    consensus = _exact_consensus(30, 20, 40)
    comparison = forecaster.compare_consensus(forecast, consensus)
    impact = forecaster.judge_price_impact(forecast, consensus, comparison)
    assert impact["direction"] == "판단불가"
    assert impact["confidence"] is None
    assert impact["reasons"] == ["매출 추정치가 없어 컨센서스와 비교할 수 없습니다."]


def test_allocation_penalty_lowers_confidence():
    forecast = _forecast(29, 27, 31)
    consensus = _exact_consensus(28.197051, 26.666667, 30)
    consensus.update(method="allocated", remaining_quarters=3, band_low_krw=26.666667 * T, band_high_krw=30 * T)
    comparison = forecaster.compare_consensus(forecast, consensus)
    impact = forecaster.judge_price_impact(forecast, consensus, comparison)
    assert impact["confidence_parts"]["allocation_penalty"] == 25.0
    assert "근사값" in impact["reasons"][-1]


def test_c19_inputs_are_not_modified(consensus_g):
    actuals = _actuals()
    consensus_before, actuals_before = consensus_g.copy(), actuals.copy()
    implied = forecaster.implied_quarter_consensus(consensus_g, actuals, "2026Q4", "2026-11-17")
    pd.testing.assert_frame_equal(consensus_g, consensus_before)
    pd.testing.assert_frame_equal(actuals, actuals_before)

    forecast = _forecast(33, 31, 35)
    forecast_before, implied_before = copy.deepcopy(forecast), copy.deepcopy(implied)
    comparison = forecaster.compare_consensus(forecast, implied)
    comparison_before = copy.deepcopy(comparison)
    forecaster.judge_price_impact(forecast, implied, comparison)
    assert (forecast, implied, comparison) == (forecast_before, implied_before, comparison_before)


# =============================================================================
# backend: run_forecast 연결과 표시용 문자열
# =============================================================================
def test_run_forecast_without_consensus_file(tmp_path: Path):
    _actuals().to_csv(tmp_path / "actuals.csv", index=False)
    result = backend.run_forecast("2026Q4", data_dir=tmp_path, today=date(2026, 11, 17))
    assert result["consensus"]["status"] == "no_consensus"
    assert result["price_impact"]["direction"] == "판단불가"
    assert result["consensus_facts"]["consensus_value"] == "—"
    assert "data/consensus.csv" in result["consensus_facts"]["consensus_note"]


def test_consensus_facts_text_for_exact_quarter(consensus_g):
    consensus = forecaster.implied_quarter_consensus(consensus_g, _actuals(), "2026Q4", "2026-11-17")
    forecast = _forecast(33, 31, 35)
    comparison = forecaster.compare_consensus(forecast, consensus)
    facts = backend.consensus_facts(consensus, comparison, forecaster.judge_price_impact(forecast, consensus, comparison))
    assert set(facts) == set(backend.CONSENSUS_FACT_KEYS)
    assert facts["consensus_value"] == "30.0조 원"
    assert facts["consensus_note"] == "연간 105.0조 − 1~3Q 실적 75.0조 · 기준일 2026-11-10"
    assert (facts["surprise_value"], facts["surprise_note"]) == ("+10.0%", "상회(강)")
    assert facts["dist_value"] == "65%"
    assert facts["revision_value"] == "+5.0%"
    assert facts["direction_value"] == "긍정"
    assert facts["confidence_value"].endswith("점")
