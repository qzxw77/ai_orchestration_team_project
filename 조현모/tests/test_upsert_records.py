"""upsert_records 계약 테스트. 가상 데이터만 사용한다."""

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from preprocess import upsert_records


KEY = ["ym", "region", "hs_code"]


def test_new_row_replaces_old_record():
    old = pd.DataFrame([{"ym": "2026-03", "region": "이천시", "hs_code": "854232",
                         "export_usd": 100.0, "collected_at": "2026-04-01"}])
    new = old.assign(export_usd=300.0, collected_at="2026-04-03")
    result = upsert_records(old, new, KEY)
    assert len(result) == 1
    assert result.loc[0, "export_usd"] == 300.0
    assert result.loc[0, "collected_at"] == "2026-04-03"


def test_unmatched_old_and_new_rows_both_remain():
    old = pd.DataFrame([{"date": "2026-03-01", "usdkrw": 1400}])
    new = pd.DataFrame([{"date": "2026-03-02", "usdkrw": 1410}])
    result = upsert_records(old, new, ["date"])
    assert result.to_dict("records") == [
        {"date": "2026-03-01", "usdkrw": 1400},
        {"date": "2026-03-02", "usdkrw": 1410},
    ]


def test_empty_store_without_columns_accepts_new_rows():
    new = pd.DataFrame([{"quarter": "2026Q1", "as_of": "2026-04-01", "estimate_krw": 10}])
    assert_frame_equal(upsert_records(pd.DataFrame(), new, ["quarter", "as_of"]), new)


def test_empty_new_without_columns_preserves_old_rows():
    old = pd.DataFrame([{"date": "2026-03-01", "usdkrw": 1400}])
    assert_frame_equal(upsert_records(old, pd.DataFrame(), ["date"]), old)


def test_duplicate_within_new_rows_keeps_last():
    new = pd.DataFrame([{"date": "2026-03-01", "usdkrw": 1400},
                        {"date": "2026-03-01", "usdkrw": 1410}])
    result = upsert_records(pd.DataFrame(), new, ["date"])
    assert result.to_dict("records") == [{"date": "2026-03-01", "usdkrw": 1410}]


def test_duplicate_within_old_rows_keeps_last():
    old = pd.DataFrame([{"date": "2026-03-01", "usdkrw": 1400},
                        {"date": "2026-03-01", "usdkrw": 1410}])
    result = upsert_records(old, pd.DataFrame(), ["date"])
    assert result.to_dict("records") == [{"date": "2026-03-01", "usdkrw": 1410}]


@pytest.mark.parametrize("missing_from", ["store", "new"])
def test_missing_key_in_populated_input_raises(missing_from):
    valid = pd.DataFrame([{"date": "2026-03-01", "usdkrw": 1400}])
    invalid = valid.drop(columns="date")
    store, new = (invalid, valid) if missing_from == "store" else (valid, invalid)
    with pytest.raises(ValueError):
        upsert_records(store, new, ["date"])


def test_empty_key_list_raises():
    with pytest.raises(ValueError):
        upsert_records(pd.DataFrame(), pd.DataFrame(), [])


def test_composite_key_only_replaces_matching_combination():
    old = pd.DataFrame([{"ym": "2026-03", "region": "이천시", "hs_code": "854232", "export_usd": 100},
                        {"ym": "2026-03", "region": "청주시", "hs_code": "854232", "export_usd": 200}])
    new = pd.DataFrame([{"ym": "2026-03", "region": "이천시", "hs_code": "854232", "export_usd": 300}])
    result = upsert_records(old, new, KEY)
    assert len(result) == 2
    assert result.set_index("region").loc["이천시", "export_usd"] == 300
    assert result.set_index("region").loc["청주시", "export_usd"] == 200


def test_inputs_are_unchanged():
    old = pd.DataFrame([{"date": "2026-03-01", "usdkrw": 1400}])
    new = pd.DataFrame([{"date": "2026-03-01", "usdkrw": 1410}])
    old_copy, new_copy = old.copy(deep=True), new.copy(deep=True)
    upsert_records(old, new, ["date"])
    assert_frame_equal(old, old_copy)
    assert_frame_equal(new, new_copy)
