"""10주차 전처리 경계 계약과 빈 스키마 회귀 테스트."""

import pandas as pd
import pytest

from preprocess import clean_exports, upsert_records


def test_upsert_rejects_row_with_no_columns():
    """pandas .empty가 참이어도 행이 있으면 키 누락을 검출한다."""
    old = pd.DataFrame(index=[0])
    new = pd.DataFrame([{"date": "2026-03-01", "usdkrw": 1400}])
    with pytest.raises(ValueError):
        upsert_records(old, new, ["date"])


def test_clean_exports_to_upsert_keeps_new_correction():
    """정제 출력이 저장 갱신 함수의 입력 계약을 만족한다."""
    raw = pd.DataFrame([
        {"ym": "202603", "region": "이천시", "hs_code": "854232",
         "export_usd": "300", "collected_at": "2026-04-03"},
    ])
    stored = pd.DataFrame([
        {"ym": "2026-03", "region": "이천시", "hs_code": "854232",
         "export_usd": 100.0, "collected_at": "2026-04-01"},
    ])
    cleaned = clean_exports(raw)
    result = upsert_records(stored, cleaned, ["ym", "region", "hs_code"])
    assert result.to_dict("records") == [
        {"ym": "2026-03", "region": "이천시", "hs_code": "854232",
         "export_usd": 300.0, "collected_at": "2026-04-03"},
    ]


def test_clean_exports_to_upsert_propagates_missing_column():
    """필수 열 누락은 정제 경계에서 명시적 ValueError로 전파한다."""
    raw = pd.DataFrame([
        {"ym": "202603", "region": "이천시", "export_usd": "300",
         "collected_at": "2026-04-03"},
    ])
    with pytest.raises(ValueError, match="hs_code"):
        cleaned = clean_exports(raw)
        upsert_records(pd.DataFrame(), cleaned, ["ym", "region", "hs_code"])
