"""ratio_rule별 시점 기준(point-in-time) 백테스트.

각 달 m의 수출이 m+1월 RELEASE_DAY일에 공개된다고 보고, 그날까지 알 수 있던 자료만으로
그 달이 속한 분기의 매출을 estimate_revenue로 추정한 뒤 확정 실적과 비교한다.
    - 수출: ym <= m 인 달만 사용
    - 환율: 공개일 이전 날짜만 사용 (대상 분기 평균 환율도 그날까지의 평균)
    - 실적: announced_date가 공개일보다 앞선 분기만 사용

실행 (alt_backend_week11 폴더에서):
    python backtest_ratio_rule.py                  # samples/exports_normal.csv, data/fx.csv, data/actuals.csv
    python backtest_ratio_rule.py --exports data/exports.csv
"""

import argparse
from pathlib import Path

import pandas as pd

from hynix_nowcast import forecaster, preprocess

ROOT = Path(__file__).resolve().parent
RELEASE_DAY = 15  # 가정: 관세청 월간 수출은 다음 달 중순 이후 사용 가능 (실제 공개일과 다를 수 있음)


def _quarter_of(period: pd.Period) -> str:
    return f"{period.year}Q{(period.month - 1) // 3 + 1}"


def run_backtest(exports: pd.DataFrame, fx: pd.DataFrame, actuals: pd.DataFrame, ratio_rule: str) -> pd.DataFrame:
    """ratio_rule 하나에 대해 달마다 시점 기준 추정치와 실적을 비교한 표를 돌려준다.

    Args:
        exports: clean_exports 결과 (ym, region, hs_code, export_usd, ...).
        fx: date(datetime), usdkrw.
        actuals: quarter, revenue_krw, announced_date(datetime).
        ratio_rule: forecaster.RATIO_RULES 중 하나.

    Returns:
        month, release_date, quarter, months_available, estimate_krw, actual_krw, error_pct 열의 표.
        실적이 아직 없는 분기는 actual_krw, error_pct가 NaN이다.
    """
    rows = []
    months = sorted(exports["ym"].unique())
    actual_by_quarter = actuals.set_index("quarter")["revenue_krw"]
    for ym in months:
        period = pd.Period(ym, freq="M")
        next_month = period + 1
        release = pd.Timestamp(next_month.year, next_month.month, RELEASE_DAY)
        quarter = _quarter_of(period)
        quarterly = preprocess.aggregate_quarterly(exports.loc[exports["ym"] <= ym], fx.loc[fx["date"] < release])
        known = actuals.loc[actuals["announced_date"] < release, ["quarter", "revenue_krw"]]
        forecast = forecaster.estimate_revenue(quarterly, known, quarter, ratio_rule=ratio_rule)
        if forecast["status"] != forecaster.FORECAST_STATUS_OK:
            continue
        actual = actual_by_quarter.get(quarter)
        rows.append(
            {
                "month": ym,
                "release_date": release.date().isoformat(),
                "quarter": quarter,
                "months_available": forecast["months_available"],
                "estimate_krw": forecast["estimate_krw"],
                "actual_krw": actual,
                "error_pct": (forecast["estimate_krw"] / actual - 1) * 100 if actual else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def summarize(table: pd.DataFrame) -> dict:
    """백테스트 표를 MAPE, 평균 오차(편향), 3개월 반영 시점 MAPE로 요약한다."""
    done = table.dropna(subset=["error_pct"])
    full = done.loc[done["months_available"] == forecaster.MONTHS_PER_QUARTER]
    return {
        "n": len(done),
        "mape_pct": done["error_pct"].abs().mean(),
        "bias_pct": done["error_pct"].mean(),
        "mape_full_quarter_pct": full["error_pct"].abs().mean(),
    }


def load_inputs(exports_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    raw = pd.read_csv(exports_path, dtype=str, keep_default_na=False)
    exports = preprocess.clean_exports(raw) if "priodTitle" in raw.columns else raw.astype({"export_usd": float})
    fx = pd.read_csv(ROOT / "data" / "fx.csv", parse_dates=["date"])
    actuals = pd.read_csv(ROOT / "data" / "actuals.csv", parse_dates=["announced_date"])
    return exports, fx, actuals


def main() -> None:
    parser = argparse.ArgumentParser(description="ratio_rule별 시점 기준 백테스트")
    parser.add_argument("--exports", type=Path, default=ROOT / "samples" / "exports_normal.csv")
    args = parser.parse_args()
    exports, fx, actuals = load_inputs(args.exports)
    print(f"수출 {exports['ym'].min()}~{exports['ym'].max()}, 공개일 가정: 다음 달 {RELEASE_DAY}일")
    print(f"{'ratio_rule':10s} {'n':>3s} {'MAPE':>7s} {'편향':>7s} {'3개월 MAPE':>10s}")
    for rule in forecaster.RATIO_RULES:
        s = summarize(run_backtest(exports, fx, actuals, rule))
        mark = "  <- 기본값" if rule == forecaster.DEFAULT_RATIO_RULE else ""
        print(f"{rule:10s} {s['n']:3d} {s['mape_pct']:6.1f}% {s['bias_pct']:6.1f}% {s['mape_full_quarter_pct']:9.1f}%{mark}")


if __name__ == "__main__":
    main()
