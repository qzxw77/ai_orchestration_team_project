"""clean_exports 테스트.

T01~T06은 설계 문서 V1 파트 4의 테스트 케이스 명세를 그대로 옮긴 것이다.
X01~ 은 알트(ALT) 구현 가이드 1.2의 '반드시 지킬 것'과 공통 제약 조건을 검사하는 추가 테스트다.
모든 데이터는 가상 값이다(실데이터·PII 없음).
"""

import pandas as pd
import pytest

from preprocess import clean_exports

COLS = ["ym", "region", "hs_code", "export_usd", "collected_at"]


def _raw(rows: list[dict]) -> pd.DataFrame:
    """테스트용 원자료 표를 만든다. 기본값: hs_code 854232, collected_at 2026-09-15."""
    base = {"hs_code": "854232", "collected_at": "2026-09-15"}
    return pd.DataFrame([{**base, **r} for r in rows])


# ---------------------------------------------------------------- 설계 문서 T01~T06


def test_T01_normal_sort_and_ym_format():
    """[정상] 3행 → ym 오름차순, YYYYMM → "YYYY-MM", 열 5개."""
    raw = _raw([
        {"ym": 202608, "region": "이천시", "export_usd": 5.5e9},
        {"ym": 202607, "region": "청주시", "export_usd": 2.0e9},
        {"ym": 202607, "region": "이천시", "export_usd": 5.0e9},
    ])
    out = clean_exports(raw)
    assert list(out.columns) == COLS
    assert len(out) == 3
    assert out["ym"].tolist() == ["2026-07", "2026-07", "2026-08"]
    assert list(out.index) == [0, 1, 2]


def test_T02_duplicate_key_keeps_latest_collected():
    """[정상] 같은 키 2행 → collected_at이 최근인 정정치 1행만 남는다."""
    raw = _raw([
        {"ym": "2026-07", "region": "이천시", "export_usd": 5.0e9, "collected_at": "2026-08-15"},
        {"ym": "2026-07", "region": "이천시", "export_usd": 5.2e9, "collected_at": "2026-09-15"},
    ])
    out = clean_exports(raw)
    assert len(out) == 1
    assert out.loc[0, "export_usd"] == 5.2e9
    assert out.loc[0, "collected_at"] == "2026-09-15"


def test_T02b_duplicate_key_order_independent():
    """[정상] 정정치가 먼저 들어와도 최근 수집일 행이 남는다(입력 순서 무관)."""
    raw = _raw([
        {"ym": "2026-07", "region": "이천시", "export_usd": 5.2e9, "collected_at": "2026-09-15"},
        {"ym": "2026-07", "region": "이천시", "export_usd": 5.0e9, "collected_at": "2026-08-15"},
    ])
    out = clean_exports(raw)
    assert out["export_usd"].tolist() == [5.2e9]


def test_T03_empty_input_returns_5_columns():
    """[경계] 0행 빈 표 → 0행, 열 5개, 예외 없음."""
    out = clean_exports(pd.DataFrame(columns=COLS))
    assert len(out) == 0
    assert list(out.columns) == COLS


def test_T03b_empty_without_columns():
    """[경계] 열조차 없는 빈 표도 필수 열 검사보다 먼저 빈 표로 반환한다."""
    out = clean_exports(pd.DataFrame())
    assert len(out) == 0
    assert list(out.columns) == COLS


def test_T04_zero_kept_negative_removed():
    """[경계] 0은 유효값이라 남고, -1은 제거된다."""
    raw = _raw([
        {"ym": "2026-07", "region": "청주시", "export_usd": 0},
        {"ym": "2026-07", "region": "이천시", "export_usd": -1},
    ])
    out = clean_exports(raw)
    assert len(out) == 1
    assert out.loc[0, "region"] == "청주시"
    assert out.loc[0, "export_usd"] == 0.0


def test_T05_dirty_rows_removed_without_error():
    """[예외] 빈칸·"N/A"·없는 달·대상 외 지역은 예외 없이 제거된다."""
    raw = _raw([
        {"ym": "2026-07", "region": "이천시", "export_usd": 5.0e9},  # 정상
        {"ym": "2026-07", "region": "청주시", "export_usd": None},  # 빈칸
        {"ym": "2026-06", "region": "청주시", "export_usd": "N/A"},  # 숫자 아님
        {"ym": "2026-13", "region": "이천시", "export_usd": 1.0e9},  # 없는 달
        {"ym": "2026-07", "region": "용인시", "export_usd": 1.0e9},  # 대상 외 지역
    ])
    out = clean_exports(raw)
    assert len(out) == 1
    assert out.loc[0, "export_usd"] == 5.0e9


def test_T06_missing_column_raises():
    """[예외] export_usd 열이 없으면 ValueError, 메시지에 열 이름 포함."""
    raw = _raw([{"ym": "2026-07", "region": "이천시"}])
    with pytest.raises(ValueError, match="export_usd"):
        clean_exports(raw)


# ---------------------------------------------------------------- 구현 가이드 추가 검사


def test_X01_input_not_modified():
    """[제약] 입력 DataFrame을 직접 수정하지 않는다."""
    raw = _raw([
        {"ym": 202608, "region": "경기도 이천시", "export_usd": "5,500"},
        {"ym": 202607, "region": "용인시", "export_usd": 1},
    ])
    before = raw.copy(deep=True)
    clean_exports(raw)
    pd.testing.assert_frame_equal(raw, before)


def test_X02_output_types():
    """[자료구조] ym·region·hs_code·collected_at은 문자열, export_usd는 float."""
    raw = _raw([{"ym": 202607, "region": "이천시", "export_usd": 5}])
    out = clean_exports(raw)
    row = out.iloc[0]
    assert isinstance(row["ym"], str)
    assert isinstance(row["region"], str)
    assert isinstance(row["hs_code"], str)
    assert isinstance(row["collected_at"], str)
    assert isinstance(row["export_usd"], float)


def test_X03_region_name_map():
    """[정상] "경기도 이천시"처럼 긴 이름은 REGION_NAME_MAP으로 표준 이름이 된다."""
    raw = _raw([
        {"ym": "2026-07", "region": "경기도 이천시", "export_usd": 1.0},
        {"ym": "2026-07", "region": " 충청북도 청주시 ", "export_usd": 2.0},
    ])
    out = clean_exports(raw)
    assert sorted(out["region"]) == ["이천시", "청주시"]


def test_X04_ym_float_and_dot_formats():
    """[경계] CSV에서 float로 읽힌 202607.0, "2026.07"도 "2026-07"이 된다."""
    raw = _raw([
        {"ym": 202607.0, "region": "이천시", "export_usd": 1.0},
        {"ym": "2026.08", "region": "이천시", "export_usd": 1.0},
    ])
    out = clean_exports(raw)
    assert out["ym"].tolist() == ["2026-07", "2026-08"]


def test_X05_ambiguous_ym_removed():
    """[예외] "20267"(5자리), "2026-7"처럼 애매한 연월은 결측 처리돼 제거된다."""
    raw = _raw([
        {"ym": "20267", "region": "이천시", "export_usd": 1.0},
        {"ym": "2026-7", "region": "이천시", "export_usd": 1.0},
        {"ym": "abc", "region": "이천시", "export_usd": 1.0},
    ])
    assert len(clean_exports(raw)) == 0


def test_X06_hs_code_string_kept():
    """[자료구조] 숫자 hs_code도 문자열로 바뀌고, 앞자리 0 문자열은 그대로 유지된다."""
    raw = _raw([
        {"ym": "2026-07", "region": "이천시", "export_usd": 1.0, "hs_code": 854232},
        {"ym": "2026-07", "region": "청주시", "export_usd": 1.0, "hs_code": "085423"},
    ])
    out = clean_exports(raw)
    assert sorted(out["hs_code"]) == ["085423", "854232"]


def test_X07_blank_collected_at_is_oldest():
    """[경계] collected_at이 빈 행은 가장 오래된 것으로 본다."""
    raw = _raw([
        {"ym": "2026-07", "region": "이천시", "export_usd": 5.2e9, "collected_at": "2026-08-15"},
        {"ym": "2026-07", "region": "이천시", "export_usd": 9.9e9, "collected_at": None},
    ])
    out = clean_exports(raw)
    assert out["export_usd"].tolist() == [5.2e9]


def test_X08_comma_and_inf_amounts():
    """[경계] "5,000,000"은 숫자로, 무한대는 결측으로 처리한다."""
    raw = _raw([
        {"ym": "2026-07", "region": "이천시", "export_usd": "5,000,000"},
        {"ym": "2026-08", "region": "이천시", "export_usd": float("inf")},
    ])
    out = clean_exports(raw)
    assert out["export_usd"].tolist() == [5_000_000.0]


def test_X09_missing_month_not_filled():
    """[제약] 빠진 달(2026-08)을 0으로 채우지 않는다."""
    raw = _raw([
        {"ym": "2026-07", "region": "이천시", "export_usd": 1.0},
        {"ym": "2026-09", "region": "이천시", "export_usd": 1.0},
    ])
    assert clean_exports(raw)["ym"].tolist() == ["2026-07", "2026-09"]


def test_X10_multiple_missing_columns_listed():
    """[예외] 여러 열이 없으면 메시지에 모두 적는다."""
    raw = pd.DataFrame([{"region": "이천시", "hs_code": "854232"}])
    with pytest.raises(ValueError) as e:
        clean_exports(raw)
    for col in ["ym", "export_usd", "collected_at"]:
        assert col in str(e.value)


def test_X11_all_rows_dirty_returns_empty_schema():
    """[경계] 정제 후 남은 행이 없어도 열 5개 빈 표를 돌려준다."""
    raw = _raw([{"ym": "2026-07", "region": "용인시", "export_usd": 1.0}])
    out = clean_exports(raw)
    assert len(out) == 0
    assert list(out.columns) == COLS
