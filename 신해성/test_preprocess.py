import pandas as pd
import pytest
from hynix_nowcast.preprocess import aggregate_quarterly


def test_aggregate_normal():
    # 정상 통합 및 두 지역 존재 테스트
    exports = pd.DataFrame({
        "ym": ["2026-01", "2026-01", "2026-02", "2026-02"],
        "region": ["이천시", "청주시", "이천시", "청주시"],
        "hs_code": ["854232", "854232", "854232", "854232"],
        "export_usd": [100.0, 50.0, 200.0, 50.0],
        "collected_at": ["2026-02-15", "2026-02-15", "2026-03-15", "2026-03-15"]
    })
    fx = pd.DataFrame({
        "date": ["2026-01-10", "2026-02-10"],
        "usdkrw": [1400.0, 1420.0]
    })
    result = aggregate_quarterly(exports, fx, lag_months=0)
    assert len(result) == 1
    assert result.loc[0, "quarter"] == "2026Q1"
    assert result.loc[0, "export_usd"] == 400.0
    assert result.loc[0, "months_available"] == 2


def test_lag_months_and_missing_region():
    # 경계: 한 지역만 있는 달 제외 및 lag_months 적용 테스트
    exports = pd.DataFrame({
        "ym": ["2025-12", "2025-12", "2026-01"],
        "region": ["이천시", "청주시", "이천시"],  # 2026-01은 청주시 누락
        "hs_code": ["854232", "854232", "854232"],
        "export_usd": [100.0, 100.0, 500.0],
        "collected_at": ["2026-01-15", "2026-01-15", "2026-02-15"]
    })
    fx = pd.DataFrame(columns=["date", "usdkrw"])
    result = aggregate_quarterly(exports, fx, lag_months=1)
    # 2025-12 + 1달 = 2026-01 (2026Q1로 귀속), 2026-01은 지역 누락으로 제외됨
    assert len(result) == 1
    assert result.loc[0, "quarter"] == "2026Q1"
    assert result.loc[0, "export_usd"] == 200.0
    assert result.loc[0, "months_available"] == 1


def test_empty_and_negative_lag():
    # 예외 및 빈 입력 테스트
    empty_df = pd.DataFrame(columns=["ym", "region", "hs_code", "export_usd", "collected_at"])
    fx = pd.DataFrame(columns=["date", "usdkrw"])
    
    res = aggregate_quarterly(empty_df, fx)
    assert res.empty
    assert list(res.columns) == ["quarter", "export_usd", "months_available", "fx_avg"]

    with pytest.raises(ValueError):
        aggregate_quarterly(empty_df, fx, lag_months=-1)
