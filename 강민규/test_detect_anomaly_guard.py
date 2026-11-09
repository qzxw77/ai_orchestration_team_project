"""detect_anomaly 리팩터링 안전망 테스트 (기존 test_detect_anomaly.py 6개에 더해서)

리팩터링은 외부 동작을 바꾸지 않아야 한다. 기존 테스트 6개가 확인하지 않는 동작을
리팩터링 전 코드 기준으로 고정한다. 리팩터링 전에도, 후에도 모두 통과해야 한다.
모든 금액은 가상의 더미 값 (실제 관세청 통계 아님)

공통 입력 A (test_detect_anomaly.py와 같음, 단위: 억 달러, 매달 이천시 62.5% + 청주시 37.5% 두 행)
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
KEYS = {"ym", "yoy_pct", "z_score", "is_anomaly", "reason"}
INSUFFICIENT = {"yoy_pct": None, "z_score": None, "is_anomaly": False, "reason": "데이터 부족"}


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


def _extra_row(ym, region, export_usd):
    return {"ym": ym, "region": region, "hs_code": "854232", "export_usd": export_usd, "collected_at": "2026-10-15"}


# ---------- 판정 규칙 ----------

def test_guard_sharp_drop():
    """대상 월 64 -> 16, 전년동월비 -75%, z = -3.0 -> 급감 (기존 테스트에는 급감이 없다)"""
    result = detect_anomaly(_make_exports(_totals_a(16)), TARGET)
    assert result["yoy_pct"] == pytest.approx(-75.0)
    assert result["z_score"] == pytest.approx(-3.0)
    assert result["is_anomaly"] is True
    assert result["reason"] == "급감"


def test_guard_z_equal_to_threshold_is_normal():
    """대상 월 64 -> 96, 전년동월비 +50%, z가 정확히 2.0 -> threshold(2.0)와 같으므로 정상
    계산식이나 합산 순서가 바뀌면 z가 2.0에서 끝자리만큼 벗어나 결과가 뒤집힐 수 있다"""
    result = detect_anomaly(_make_exports(_totals_a(96)), TARGET)
    assert result["z_score"] == 2.0
    assert result["is_anomaly"] is False
    assert result["reason"] == "정상"


def test_guard_calculation_order_is_kept():
    """평균과 표본 표준편차를 지금 식(합 / 개수, 제곱합 / (개수 - 1), math.sqrt) 그대로 계산해야 하는 이유를 고정한다.
    이 데이터는 지금 식으로 z = -2.8559676606421838인데, pandas std나 statistics.stdev로 바꾸면
    -2.855967660642184로 끝자리가 달라진다. threshold를 지금 z의 절댓값으로 주면 지금 식은 |z| == threshold라 정상,
    바꾼 식은 |z| > threshold라 급감이 된다 (경계 판정이 뒤집힘)"""
    totals = [90, 90, 60, 80, 64, 72, 90, 90, 100, 60, 90, 64,
              90, 90, 64, 60, 72, 80, 90, 72, 100, 60, 100, 64, 60]
    exports = _make_exports(dict(zip(_months_from_2024_09(25), totals)))

    result = detect_anomaly(exports, TARGET, threshold=2.8559676606421838)

    assert result["z_score"] == -2.8559676606421838
    assert result["reason"] == "정상"


def test_guard_threshold_argument_is_used():
    """z = 1.0이어도 threshold=0.5를 넘기면 급증 (threshold를 2.0으로 고정해 버리면 실패)"""
    result = detect_anomaly(_make_exports(_totals_a(80)), TARGET, threshold=0.5)
    assert result["is_anomaly"] is True
    assert result["reason"] == "급증"


# ---------- 두 지역 규칙 (9주차 수정 1의 회귀 테스트) ----------

def test_guard_one_region_month_counts_as_missing():
    """2025-09에 청주시 행만 빠지면 그 달은 월 합계가 없는 달 -> 25개월이 안 되므로 데이터 부족"""
    exports = _make_exports(_totals_a(80))
    exports = exports[~((exports["ym"] == "2025-09") & (exports["region"] == "청주시"))]
    assert detect_anomaly(exports, TARGET) == {"ym": TARGET, **INSUFFICIENT}


def test_guard_region_absent_everywhere():
    """표 전체에 청주시가 한 행도 없으면 데이터 부족 (KeyError 같은 예외 없이)"""
    exports = _make_exports(_totals_a(80))
    exports = exports[exports["region"] == "이천시"]
    assert detect_anomaly(exports, TARGET) == {"ym": TARGET, **INSUFFICIENT}


# ---------- 지저분한 행, 값 표기 ----------

def test_guard_dirty_rows_are_skipped():
    """대상 외 지역, 잘못된 ym, 숫자 아님, 결측, 음수, 무한대 행은 건너뛰어 결과가 깨끗한 표와 같다"""
    clean = _make_exports(_totals_a(80))
    dirty = pd.concat([clean, pd.DataFrame([
        _extra_row(TARGET, "용인시", 9e12),
        _extra_row("2026-13", "이천시", 9e12),
        _extra_row(TARGET, "이천시", "N/A"),
        _extra_row(TARGET, "이천시", float("nan")),
        _extra_row(TARGET, "이천시", -5e9),
        _extra_row(TARGET, "청주시", float("inf")),
    ])], ignore_index=True)
    assert detect_anomaly(dirty, TARGET) == detect_anomaly(clean, TARGET)


@pytest.mark.parametrize("variant", ["numeric_strings", "split_rows"])
def test_guard_value_forms_give_same_result(variant):
    """export_usd가 숫자 문자열이거나, 같은 달/지역이 두 행으로 나뉘어 있어도 결과가 같다 (같은 달/지역은 더한다)"""
    clean = _make_exports(_totals_a(80))
    if variant == "numeric_strings":
        exports = clean.assign(export_usd=clean["export_usd"].astype(str))
    else:
        half = clean.assign(export_usd=clean["export_usd"] / 2)
        exports = pd.concat([half, half], ignore_index=True)
    assert detect_anomaly(exports, TARGET) == detect_anomaly(clean, TARGET)


# ---------- 입력 오류, 호출 오류 ----------

@pytest.mark.parametrize(
    "exports",
    [
        _make_exports(_totals_a(80)).iloc[0:0],                          # 빈 표
        _make_exports(_totals_a(80)).drop(columns="export_usd"),         # 필수 열 없음
        None,                                                            # DataFrame이 아님
    ],
    ids=["empty", "missing_column", "not_dataframe"],
)
def test_guard_invalid_inputs_return_default(exports):
    """빈 표, 필수 열(ym, region, export_usd) 누락, DataFrame이 아닌 입력 -> 예외 없이 데이터 부족"""
    assert detect_anomaly(exports, TARGET) == {"ym": TARGET, **INSUFFICIENT}


def test_guard_non_numeric_threshold_raises_type_error():
    """숫자가 아닌 threshold는 호출 실수이므로 TypeError (docstring Raises에 적힌 동작).
    try/except로 감싸거나 float()로 바꿔 넘어가면 실패"""
    with pytest.raises(TypeError):
        detect_anomaly(_make_exports(_totals_a(80)), TARGET, threshold="2")


# ---------- 반환 형식, 상태 ----------

def test_guard_return_types_and_input_unchanged():
    """반환 dict는 키 5개, yoy_pct와 z_score는 파이썬 float(numpy.float64 아님), is_anomaly는 bool.
    입력 표는 바뀌지 않는다 (export_usd를 숫자 문자열로 넣어, 입력 열을 숫자로 바꿔 쓰는 실수도 드러나게 한다)"""
    clean = _make_exports(_totals_a(80))
    exports = clean.assign(export_usd=clean["export_usd"].astype(str))
    before = exports.copy(deep=True)

    result = detect_anomaly(exports, TARGET)

    assert set(result) == KEYS
    assert type(result["yoy_pct"]) is float
    assert type(result["z_score"]) is float
    assert type(result["is_anomaly"]) is bool
    pd.testing.assert_frame_equal(exports, before)


def test_guard_insufficient_results_do_not_share_state():
    """yoy_pct만 채운 '데이터 부족'(표준편차 0)을 돌려준 뒤 다른 호출의 '데이터 부족'에 yoy_pct가 남지 않는다
    (기본값 dict를 모듈 상수로 빼서 고쳐 쓰면 9주차 가변 기본값 문제처럼 값이 다음 호출로 샌다)"""
    flat = dict(zip(_months_from_2024_09(25), [100] * 12 + [110] * 12 + [121]))
    first = detect_anomaly(_make_exports(flat), TARGET)
    assert first["yoy_pct"] == pytest.approx(10.0)

    second = detect_anomaly(_make_exports(_totals_a(80)), "2026-13")
    assert second == {"ym": "2026-13", **INSUFFICIENT}
    # 두 결과가 같은 dict 객체를 나눠 쓰면, 두 번째 호출이 앞서 돌려준 결과까지 바꿔 버린다
    assert first is not second
    assert first["yoy_pct"] == pytest.approx(10.0)
