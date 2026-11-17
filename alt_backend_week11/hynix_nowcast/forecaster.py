"""[모듈 3] 분석 (숫자 계산 전담).

    estimate_revenue  분기 수출 x 과거 매출/수출 비율 -> 대상 분기 매출 범위
    detect_anomaly    최근 월 수출의 전년동월비 z-score -> 급증, 급감 판정
    compare_guidance  추정 방향과 컨콜 가이던스 방향 비교
    implied_quarter_consensus  연간(FY1) 컨센서스 - 발표된 실적 -> 대상 분기 컨센서스 (4분기 정확, 1~3분기 환산)
    compare_consensus          추정 매출과 분기 컨센서스의 괴리율, 상회/부합/하회 판정
    judge_price_impact         위치 판정과 리비전 -> 주가 영향 방향, 근거 충분도 -> 판단 신뢰도

입력 표와 dict는 바꾸지 않고, 결과 dict는 호출마다 새로 만들며 값은 파이썬 기본 타입만 쓴다.
"""

import math
import statistics
from datetime import date, timedelta

import pandas as pd

ALLOWED_REGIONS = ("이천시", "청주시")
MONTHS_PER_QUARTER = 3
RATIO_WINDOW = 4

FORECAST_STATUS_OK = "ok"
FORECAST_STATUS_NO_DATA = "no_data"
FORECAST_STATUS_INSUFFICIENT = "insufficient_history"

STD_EPSILON = 1e-9
YOY_LAG_MONTHS = 12
BASELINE_MONTHS = 12
REQUIRED_PAST_MONTHS = YOY_LAG_MONTHS + BASELINE_MONTHS
ANOMALY_REQUIRED_COLUMNS = ("ym", "region", "export_usd")
REASON_NORMAL = "정상"
REASON_SURGE = "급증"
REASON_DROP = "급감"
REASON_INSUFFICIENT = "데이터 부족"

DIRECTION_BAND_PCT = 2.0
INPUT_STATUS_OK = "ok"
DIRECTION_UP = "상승"
DIRECTION_FLAT = "보합"
DIRECTION_DOWN = "하락"
CONSISTENCY_MATCH = "일치"
CONSISTENCY_MISMATCH = "불일치"
CONSISTENCY_UNKNOWN = "판단불가"

# 컨센서스 비교와 주가 영향 판단 (설계서: 신동훈/consensus_price_impact_design.md)
KRW_PER_TRILLION = 1e12
QUARTERS_PER_YEAR = 4
CONSENSUS_STATUS_OK = "ok"
CONSENSUS_STATUS_NO_CONSENSUS = "no_consensus"
CONSENSUS_STATUS_NOT_READY = "not_ready"
CONSENSUS_STATUS_INVALID = "invalid"
METHOD_EXACT = "exact"
METHOD_ALLOCATED = "allocated"
ALLOCATION_METHODS = ("even", "prior_share", "const_growth")
COMPARISON_STATUS_OK = "ok"
COMPARISON_STATUS_UNAVAILABLE = "unavailable"
POSITION_ABOVE = "상회"
POSITION_INLINE = "부합"
POSITION_BELOW = "하회"
STRENGTH_STRONG = "강"
STRENGTH_WEAK = "약"
IMPACT_POSITIVE = "긍정"
IMPACT_NEUTRAL = "중립"
IMPACT_NEGATIVE = "부정"
IMPACT_UNKNOWN = "판단불가"

SURPRISE_BAND_PCT = 5.0
REVISION_BAND_PCT = 3.0
REVISION_LOOKBACK_DAYS = 30
FRESH_DAYS = 7
STALE_DAYS = 30
POST_ANNOUNCEMENT_DAYS = 5
SPREAD_FULL_PCT = 20.0
SPREAD_ZERO_PCT = 60.0
CONFIDENCE_MONTHS_MAX = 40.0
CONFIDENCE_STRENGTH_MAX = 30.0
CONFIDENCE_AGREEMENT_MAX = 15.0
CONFIDENCE_FRESH_MAX = 15.0
CONFIDENCE_FRESH_PARTIAL = 8.0
ALLOCATION_PENALTY = {1: 0.0, 2: 15.0, 3: 25.0, 4: 30.0}
MAX_REASONS = 3
GROWTH_SEARCH_STEPS = 200


# =============================================================================
# estimate_revenue
# =============================================================================
def estimate_revenue(quarterly_df: pd.DataFrame, actuals_df: pd.DataFrame, target_quarter: str) -> dict:
    """대상 분기 매출을 과거 분기의 (매출/환율)/수출 비율로 추정한다.

    기준 분기는 대상 분기보다 앞서고, 실적이 있고, 3개월 자료가 모두 있고, 수출과 환율이 0보다 큰 분기 중
    가장 최근 RATIO_WINDOW개다. 분기 수출 추정 = 대상 분기 수출 x 3 / 반영 개월 수이고,
    중앙값, 하한, 상한 = 분기 수출 추정 x (비율 평균, 최솟값, 최댓값) x 대상 분기 평균 환율이다.
    대상 분기와 그 뒤의 실적은 읽지 않는다.

    Args:
        quarterly_df: aggregate_quarterly 결과.
        actuals_df: load_actuals 결과.
        target_quarter: 대상 분기 "YYYYQn".

    Returns:
        forecast dict
            quarter (str), estimate_krw, lower_krw, upper_krw (float | None, 원),
            qoq_change_pct (float | None, 직전 분기 실적 대비 %), ratio_used (float | None),
            months_available (int, 0~3), status ("ok", "no_data", "insufficient_history").
        status가 "ok"가 아니면 숫자 키 5개는 None이다.

    Raises:
        KeyError: 표에 필요한 열이 없을 때 (앞 단계 계약 위반이라 그대로 올린다).
    """
    result = {
        "quarter": target_quarter,
        "estimate_krw": None,
        "lower_krw": None,
        "upper_krw": None,
        "qoq_change_pct": None,
        "ratio_used": None,
        "months_available": 0,
        "status": FORECAST_STATUS_NO_DATA,
    }
    if _quarter_index(target_quarter) is None:
        return result

    target_rows = quarterly_df.loc[quarterly_df["quarter"] == target_quarter]
    if len(target_rows) == 0 or pd.isna(target_rows["months_available"].iloc[0]):
        return result
    target = target_rows.iloc[0]
    months_available = int(target["months_available"])
    if months_available <= 0:
        return result
    result["months_available"] = months_available
    if pd.isna(target["export_usd"]) or pd.isna(target["fx_avg"]):
        return result

    actuals = actuals_df.loc[actuals_df["revenue_krw"].notna(), ["quarter", "revenue_krw"]]
    merged = quarterly_df.merge(actuals, on="quarter", how="inner")
    base = merged.loc[
        (merged["quarter"] < target_quarter)
        & (merged["months_available"] == MONTHS_PER_QUARTER)
        & (merged["export_usd"] > 0)
        & (merged["fx_avg"] > 0)
    ].sort_values("quarter")
    if len(base) < RATIO_WINDOW:
        result["status"] = FORECAST_STATUS_INSUFFICIENT
        return result

    recent = base.tail(RATIO_WINDOW)
    ratios = ((recent["revenue_krw"] / recent["fx_avg"]) / recent["export_usd"]).tolist()
    quarter_export_usd = float(target["export_usd"]) * MONTHS_PER_QUARTER / months_available
    fx_avg = float(target["fx_avg"])
    ratio_used = sum(ratios) / len(ratios)
    estimate_krw = quarter_export_usd * ratio_used * fx_avg

    previous = actuals.loc[actuals["quarter"] == _previous_quarter(target_quarter), "revenue_krw"]
    qoq_change_pct = None
    if len(previous) > 0 and float(previous.iloc[0]) != 0:
        qoq_change_pct = float((estimate_krw / float(previous.iloc[0]) - 1.0) * 100.0)

    result.update(
        estimate_krw=float(estimate_krw),
        lower_krw=float(quarter_export_usd * min(ratios) * fx_avg),
        upper_krw=float(quarter_export_usd * max(ratios) * fx_avg),
        qoq_change_pct=qoq_change_pct,
        ratio_used=float(ratio_used),
        status=FORECAST_STATUS_OK,
    )
    return result


def _quarter_index(quarter: object) -> int | None:
    """"YYYYQn" 분기를 시간순 비교용 정수(연 x 4 + n - 1)로 바꾼다.

    Returns:
        정수. ASCII "YYYYQn" 형식이 아니면 None.
    """
    if (
        not isinstance(quarter, str)
        or len(quarter) != 6
        or not quarter.isascii()
        or not quarter[:4].isdigit()
        or quarter[4] != "Q"
        or quarter[5] not in "1234"
    ):
        return None
    return int(quarter[:4]) * 4 + int(quarter[5]) - 1


def _previous_quarter(quarter: str) -> str:
    """직전 분기를 구한다 (2026Q1 -> 2025Q4).

    Returns:
        "YYYYQn" 문자열. quarter는 형식 검사를 통과한 값이어야 한다.
    """
    year, offset = divmod(_quarter_index(quarter) - 1, 4)
    return f"{year:04d}Q{offset + 1}"


# =============================================================================
# detect_anomaly
# =============================================================================
def detect_anomaly(exports_df: pd.DataFrame, target_ym: str, threshold: float = 2.0) -> dict:
    """대상 월 수출의 전년동월비가 평소 범위를 벗어났는지 z-score로 판정한다.

    두 지역이 모두 있는 달만 월 합계를 만들고, 대상 월과 직전 12개월의 전년동월비를 구한다.
    직전 12개월 전년동월비의 평균과 표본 표준편차로 대상 월의 z-score를 계산해 |z| > threshold이면 이상치다.

    Args:
        exports_df: exports 표 (ym, region, export_usd 열 사용).
        target_ym: 판정 대상 월 "YYYY-MM".
        threshold: 이상치 기준 z-score 절댓값 (같으면 정상).

    Returns:
        anomaly dict
            ym (str: target_ym 그대로), yoy_pct (float | None, %), z_score (float | None),
            is_anomaly (bool), reason ("정상", "급증", "급감", "데이터 부족").
        "데이터 부족": target_ym 형식 오류, 표가 아니거나 0행이거나 열 누락, 대상 월과 앞 24개월 중 월 합계가 없는 달,
        12개월 전 합계가 0, 직전 12개월 전년동월비의 표준편차가 STD_EPSILON 미만(이때만 yoy_pct를 채운다).

    Raises:
        TypeError: threshold가 숫자가 아닐 때 (호출 실수라 그대로 올린다).
    """
    if not _is_valid_ym(target_ym):
        return _insufficient_anomaly(target_ym)
    if not isinstance(exports_df, pd.DataFrame) or len(exports_df) == 0:
        return _insufficient_anomaly(target_ym)
    if not set(ANOMALY_REQUIRED_COLUMNS).issubset(exports_df.columns):
        return _insufficient_anomaly(target_ym)

    yoy_values = _yoy_values(_monthly_totals(exports_df), target_ym)
    if yoy_values is None:
        return _insufficient_anomaly(target_ym)

    yoy_pct = float(yoy_values[-1])
    baseline = yoy_values[:-1]
    # 경계(|z| == threshold) 판정이 흔들리지 않도록 합 / 개수, 제곱합 / (개수 - 1) 식을 그대로 쓴다
    mean = sum(baseline) / len(baseline)
    std = math.sqrt(sum((value - mean) ** 2 for value in baseline) / (len(baseline) - 1))
    if std < STD_EPSILON:
        return _insufficient_anomaly(target_ym, yoy_pct)

    z_score = float((yoy_pct - mean) / std)
    is_anomaly = abs(z_score) > threshold
    if not is_anomaly:
        reason = REASON_NORMAL
    else:
        reason = REASON_SURGE if z_score > 0 else REASON_DROP
    return {"ym": target_ym, "yoy_pct": yoy_pct, "z_score": z_score, "is_anomaly": is_anomaly, "reason": reason}


def _is_valid_ym(value: object) -> bool:
    """값이 ASCII "YYYY-MM"(월 01~12)인지 확인한다.

    Returns:
        형식이 맞으면 True.
    """
    return (
        isinstance(value, str)
        and len(value) == 7
        and value.isascii()
        and value[4] == "-"
        and value[:4].isdigit()
        and value[5:].isdigit()
        and 1 <= int(value[5:]) <= 12
    )


def _shift_ym(ym: str, months: int) -> str:
    """ym에서 months개월 이동한 달을 구한다 (음수면 앞으로).

    Returns:
        "YYYY-MM" 문자열.
    """
    year, month_offset = divmod(int(ym[:4]) * 12 + int(ym[5:]) - 1 + months, 12)
    return f"{year:04d}-{month_offset + 1:02d}"


def _insufficient_anomaly(target_ym: str, yoy_pct: float | None = None) -> dict:
    """"데이터 부족" 결과를 새 dict로 만든다.

    Returns:
        z_score None, is_anomaly False, reason "데이터 부족"인 anomaly dict.
    """
    return {"ym": target_ym, "yoy_pct": yoy_pct, "z_score": None, "is_anomaly": False, "reason": REASON_INSUFFICIENT}


def _monthly_totals(exports_df: pd.DataFrame) -> dict[str, float]:
    """ALLOWED_REGIONS가 모두 있는 달의 월 수출 합계를 만든다.

    잘못된 ym, 대상 외 지역, 숫자로 바꿀 수 없는 값, 결측, 음수, 무한대인 행은 건너뛰고 같은 달, 같은 지역은 더한다.

    Returns:
        {"YYYY-MM": 월 합계}. 한 지역이라도 없는 달은 들어 있지 않다.
    """
    by_month: dict[str, dict[str, float]] = {}
    for ym, region, export_usd in exports_df[list(ANOMALY_REQUIRED_COLUMNS)].itertuples(index=False, name=None):
        if not _is_valid_ym(ym) or region not in ALLOWED_REGIONS:
            continue
        try:
            amount = float(export_usd)
        except (TypeError, ValueError, OverflowError):
            continue
        if not math.isfinite(amount) or amount < 0:
            continue
        regions = by_month.setdefault(ym, {})
        regions[region] = regions.get(region, 0.0) + amount

    return {
        ym: sum(regions.values())
        for ym, regions in by_month.items()
        if all(region in regions for region in ALLOWED_REGIONS)
    }


def _yoy_values(monthly_totals: dict[str, float], target_ym: str) -> list[float] | None:
    """대상 월과 직전 BASELINE_MONTHS개월의 전년동월비(%)를 구한다.

    Returns:
        오래된 달부터 13개 값의 list (마지막이 대상 월). 필요한 25개월 중 빈 달이 있거나 비교할 합계가 0이면 None.
    """
    required = {_shift_ym(target_ym, offset) for offset in range(-REQUIRED_PAST_MONTHS, 1)}
    if not required.issubset(monthly_totals):
        return None

    values: list[float] = []
    for offset in range(-BASELINE_MONTHS, 1):
        ym = _shift_ym(target_ym, offset)
        previous = monthly_totals[_shift_ym(ym, -YOY_LAG_MONTHS)]
        if previous == 0:
            return None
        values.append((monthly_totals[ym] / previous - 1.0) * 100.0)
    return values


# =============================================================================
# compare_guidance
# =============================================================================
def compare_guidance(forecast: dict, guidance: dict) -> dict:
    """추정 매출의 전분기 대비 방향과 컨콜 가이던스(D램 기준) 방향이 같은지 판정한다.

    예측 방향: qoq_change_pct가 +2 초과면 "상승", -2 미만이면 "하락", 그 사이면 "보합".
    가이던스 방향: price_outlook "상승"이고 D램 출하 증가율이 없거나 0 이상이면 "상승", "하락"이고 없거나 0 이하이면 "하락".

    Args:
        forecast: estimate_revenue 결과 (status, qoq_change_pct 사용).
        guidance: extract_guidance 결과 (status, price_outlook, dram_bit_growth_pct 사용).

    Returns:
        consistency dict
            status ("일치", "불일치", "판단불가"), forecast_direction ("상승", "보합", "하락", None),
            guidance_direction ("상승", "하락", None).
        한쪽 방향이 없거나 예측이 "보합"이면 "판단불가"다.

    Raises:
        없음. dict가 아니거나 키가 없거나 숫자 자리에 bool, NaN이 와도 "판단불가"로 돌려준다.
    """
    forecast_direction = None
    if isinstance(forecast, dict) and forecast.get("status") == INPUT_STATUS_OK:
        change = forecast.get("qoq_change_pct")
        if _is_valid_number(change):
            if change > DIRECTION_BAND_PCT:
                forecast_direction = DIRECTION_UP
            elif change < -DIRECTION_BAND_PCT:
                forecast_direction = DIRECTION_DOWN
            else:
                forecast_direction = DIRECTION_FLAT

    guidance_direction = None
    if isinstance(guidance, dict) and guidance.get("status") == INPUT_STATUS_OK:
        outlook = guidance.get("price_outlook")
        dram_growth = guidance.get("dram_bit_growth_pct")
        if outlook == DIRECTION_UP and (dram_growth is None or (_is_valid_number(dram_growth) and dram_growth >= 0)):
            guidance_direction = DIRECTION_UP
        elif outlook == DIRECTION_DOWN and (
            dram_growth is None or (_is_valid_number(dram_growth) and dram_growth <= 0)
        ):
            guidance_direction = DIRECTION_DOWN

    if forecast_direction is None or guidance_direction is None or forecast_direction == DIRECTION_FLAT:
        status = CONSISTENCY_UNKNOWN
    elif forecast_direction == guidance_direction:
        status = CONSISTENCY_MATCH
    else:
        status = CONSISTENCY_MISMATCH
    return {"status": status, "forecast_direction": forecast_direction, "guidance_direction": guidance_direction}


def _is_valid_number(value: object) -> bool:
    """bool이 아닌 유한한 int, float인지 확인한다.

    Returns:
        유효한 숫자면 True.
    """
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


# =============================================================================
# implied_quarter_consensus
# =============================================================================
def implied_quarter_consensus(
    consensus_df: pd.DataFrame, actuals_df: pd.DataFrame, target_quarter: str, as_of: str
) -> dict:
    """예측 실행일까지 공개된 FY1 연간 컨센서스에서 발표된 실적을 빼고 대상 분기 몫을 구한다.

    남은 컨센서스 R = FY1 평균 - 대상 연도에 발표된 분기 실적 합, 남은 분기 수 k = 5 - 분기 번호.
    k = 1(4분기)이면 R이 곧 분기 컨센서스다(exact). k >= 2이면 균등 분할, 전년 분기 비중, 일정 성장 세 방법으로
    나눈 값의 중앙값을 중심값, 최솟값~최댓값을 범위로 쓴다(allocated).
    컨센서스 기준일과 실적 발표일이 as_of보다 늦은 자료는 읽지 않는다(미래 정보 금지).

    Args:
        consensus_df: load_consensus 결과.
        actuals_df: load_actuals 결과 (quarter, revenue_krw, announced_date 사용).
        target_quarter: 대상 분기 "YYYYQn".
        as_of: 예측 실행일 "YYYY-MM-DD".

    Returns:
        consensus dict
            status ("ok", "no_consensus", "not_ready", "invalid"), quarter, consensus_as_of, fiscal_year,
            annual_mean_krw, annual_high_krw, annual_low_krw, ytd_actual_krw, remaining_quarters, method,
            methods ({"even", "prior_share", "const_growth": float | None}), center_krw, band_low_krw, band_high_krw,
            dist_low_krw, dist_high_krw, revision_pct, revision_base_krw, revision_base_as_of,
            days_since_consensus, days_after_announcement.
        "not_ready": 직전 분기 실적이 as_of까지 발표되지 않았거나 대상 연도의 앞선 분기 실적이 빠짐.
        "invalid": 분기나 as_of 형식 오류, 또는 R <= 0. status가 "ok"가 아니면 금액, 비율 키는 None이다.
    """
    quarter_index = _quarter_index(target_quarter)
    as_of_date = _to_date(as_of)
    result = _empty_consensus(target_quarter)
    if quarter_index is None or as_of_date is None:
        result["status"] = CONSENSUS_STATUS_INVALID
        return result
    year, number = divmod(quarter_index, QUARTERS_PER_YEAR)
    number += 1
    result["fiscal_year"] = year
    result["remaining_quarters"] = QUARTERS_PER_YEAR + 1 - number

    actuals = _announced_actuals(actuals_df, as_of)
    previous = _previous_quarter(target_quarter)
    ytd_quarters = [f"{year:04d}Q{q}" for q in range(1, number)]
    if previous not in actuals or any(quarter not in actuals for quarter in ytd_quarters):
        result["status"] = CONSENSUS_STATUS_NOT_READY
        return result

    candidates = consensus_df.loc[
        (consensus_df["fiscal_year"] == year) & (consensus_df["as_of"] <= as_of)
    ].sort_values("as_of")
    if len(candidates) == 0:
        result["status"] = CONSENSUS_STATUS_NO_CONSENSUS
        return result
    row = candidates.iloc[-1]

    ytd = float(sum(actuals[quarter][0] for quarter in ytd_quarters))
    remaining = float(row["mean_krw"]) - ytd
    if remaining <= 0:
        result["status"] = CONSENSUS_STATUS_INVALID
        return result

    k = result["remaining_quarters"]
    if k == 1:
        methods = {name: remaining for name in ALLOCATION_METHODS}
        center = band_low = band_high = remaining
        dist_low, dist_high = float(row["low_krw"]) - ytd, float(row["high_krw"]) - ytd
        method = METHOD_EXACT
    else:
        methods = {
            "even": remaining / k,
            "prior_share": _prior_share(actuals, year, number, remaining),
            "const_growth": _const_growth(actuals[previous][0], remaining, k),
        }
        values = [value for value in methods.values() if value is not None]
        center = float(statistics.median(values))
        band_low, band_high = min(values), max(values)
        dist_low, dist_high = band_low, band_high
        method = METHOD_ALLOCATED

    consensus_date = _to_date(row["as_of"])
    revision_rows = candidates.loc[
        candidates["as_of"] <= (consensus_date - timedelta(days=REVISION_LOOKBACK_DAYS)).isoformat()
    ]
    revision_pct = revision_base = revision_base_as_of = None
    if len(revision_rows) > 0:
        base_row = revision_rows.iloc[-1]
        revision_base = float(base_row["mean_krw"])
        revision_base_as_of = str(base_row["as_of"])
        revision_pct = (float(row["mean_krw"]) / revision_base - 1.0) * 100.0

    result.update(
        status=CONSENSUS_STATUS_OK,
        consensus_as_of=str(row["as_of"]),
        annual_mean_krw=float(row["mean_krw"]),
        annual_high_krw=float(row["high_krw"]),
        annual_low_krw=float(row["low_krw"]),
        ytd_actual_krw=ytd,
        method=method,
        methods={name: (float(value) if value is not None else None) for name, value in methods.items()},
        center_krw=float(center),
        band_low_krw=float(band_low),
        band_high_krw=float(band_high),
        dist_low_krw=float(dist_low),
        dist_high_krw=float(dist_high),
        revision_pct=revision_pct,
        revision_base_krw=revision_base,
        revision_base_as_of=revision_base_as_of,
        days_since_consensus=(as_of_date - consensus_date).days,
        days_after_announcement=(consensus_date - _to_date(actuals[previous][1])).days,
    )
    return result


def _empty_consensus(target_quarter: str) -> dict:
    """금액, 비율 키가 모두 None인 consensus dict를 새로 만든다.

    Returns:
        status "no_consensus"인 consensus dict.
    """
    return {
        "status": CONSENSUS_STATUS_NO_CONSENSUS,
        "quarter": target_quarter,
        "consensus_as_of": None,
        "fiscal_year": None,
        "annual_mean_krw": None,
        "annual_high_krw": None,
        "annual_low_krw": None,
        "ytd_actual_krw": None,
        "remaining_quarters": None,
        "method": None,
        "methods": {name: None for name in ALLOCATION_METHODS},
        "center_krw": None,
        "band_low_krw": None,
        "band_high_krw": None,
        "dist_low_krw": None,
        "dist_high_krw": None,
        "revision_pct": None,
        "revision_base_krw": None,
        "revision_base_as_of": None,
        "days_since_consensus": None,
        "days_after_announcement": None,
    }


def _to_date(value: object) -> date | None:
    """"YYYY-MM-DD" 문자열을 date로 바꾼다.

    Returns:
        date. 형식이 다르거나 달력에 없는 날짜면 None.
    """
    if not isinstance(value, str) or len(value) != 10 or not value.isascii():
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _announced_actuals(actuals_df: pd.DataFrame, as_of: str) -> dict[str, tuple[float, str]]:
    """as_of까지 발표된 분기 실적만 모은다.

    Returns:
        {"YYYYQn": (revenue_krw, announced_date)}. 매출이 없거나 0 이하인 행은 뺀다.
    """
    announced: dict[str, tuple[float, str]] = {}
    for quarter, revenue, announced_date in actuals_df[["quarter", "revenue_krw", "announced_date"]].itertuples(
        index=False, name=None
    ):
        if not isinstance(announced_date, str) or announced_date > as_of or pd.isna(revenue) or revenue <= 0:
            continue
        announced[str(quarter)] = (float(revenue), announced_date)
    return announced


def _prior_share(actuals: dict[str, tuple[float, str]], year: int, number: int, remaining: float) -> float | None:
    """전년 분기 비중으로 남은 컨센서스 중 대상 분기 몫을 구한다.

    Returns:
        remaining x 전년 대상 분기 실적 / 전년 대상~4분기 실적 합. 전년 실적이 하나라도 없으면 None.
    """
    prior = [actuals.get(f"{year - 1:04d}Q{q}") for q in range(1, QUARTERS_PER_YEAR + 1)]
    if any(item is None for item in prior):
        return None
    rest = sum(item[0] for item in prior[number - 1 :])
    return remaining * prior[number - 1][0] / rest if rest > 0 else None


def _const_growth(base: float, remaining: float, k: int) -> float | None:
    """직전 분기 실적 base에서 매 분기 같은 배수 x로 늘어 k개 분기 합이 remaining이 되는 x를 구한다.

    base x (x + x^2 + ... + x^k) = remaining 을 이분법으로 푼다 (좌변이 x > 0에서 단조 증가해 해가 하나).

    Returns:
        대상 분기 몫 base x x. base가 0 이하이면 None.
    """
    if base <= 0:
        return None

    def total(x: float) -> float:
        return base * sum(x**power for power in range(1, k + 1))

    low, high = 0.0, 1.0
    while total(high) < remaining:
        high *= 2.0
    for _ in range(GROWTH_SEARCH_STEPS):
        middle = (low + high) / 2.0
        if total(middle) < remaining:
            low = middle
        else:
            high = middle
    return base * (low + high) / 2.0


# =============================================================================
# compare_consensus
# =============================================================================
def compare_consensus(forecast: dict, consensus: dict) -> dict:
    """우리 추정 매출과 분기 컨센서스의 괴리율, 위치(상회, 부합, 하회), 분포 안 위치를 판정한다.

    exact(4분기): 하한 > 컨센서스면 상회(강), 상한 < 컨센서스면 하회(강), 괴리율 >= +5%면 상회(약),
    <= -5%면 하회(약), 그 외 부합. allocated(1~3분기): 같은 순서로 환산 범위(band)와 비교한다.

    Args:
        forecast: estimate_revenue 결과.
        consensus: implied_quarter_consensus 결과.

    Returns:
        comparison dict
            status ("ok", "unavailable"), surprise_pct (float | None), position ("상회", "부합", "하회", None),
            strength ("강", "약", None), dist_position_pct (float | None, 0~100).
    """
    result = {
        "status": COMPARISON_STATUS_UNAVAILABLE,
        "surprise_pct": None,
        "position": None,
        "strength": None,
        "dist_position_pct": None,
    }
    if not _is_ok(forecast, FORECAST_STATUS_OK) or not _is_ok(consensus, CONSENSUS_STATUS_OK):
        return result
    estimate, lower, upper = (forecast.get(key) for key in ("estimate_krw", "lower_krw", "upper_krw"))
    center = consensus.get("center_krw")
    if not all(_is_valid_number(value) for value in (estimate, lower, upper, center)) or center <= 0:
        return result

    surprise = (estimate / center - 1.0) * 100.0
    if consensus.get("method") == METHOD_EXACT:
        reference_low = reference_high = center
        above_weak, below_weak = surprise >= SURPRISE_BAND_PCT, surprise <= -SURPRISE_BAND_PCT
    else:
        reference_low, reference_high = consensus["band_low_krw"], consensus["band_high_krw"]
        above_weak, below_weak = estimate > reference_high, estimate < reference_low

    if lower > reference_high:
        position, strength = POSITION_ABOVE, STRENGTH_STRONG
    elif upper < reference_low:
        position, strength = POSITION_BELOW, STRENGTH_STRONG
    elif above_weak:
        position, strength = POSITION_ABOVE, STRENGTH_WEAK
    elif below_weak:
        position, strength = POSITION_BELOW, STRENGTH_WEAK
    else:
        position, strength = POSITION_INLINE, None

    dist_low, dist_high = consensus.get("dist_low_krw"), consensus.get("dist_high_krw")
    dist_position = None
    if _is_valid_number(dist_low) and _is_valid_number(dist_high) and dist_high > dist_low:
        dist_position = min(max((estimate - dist_low) / (dist_high - dist_low) * 100.0, 0.0), 100.0)

    result.update(
        status=COMPARISON_STATUS_OK,
        surprise_pct=float(surprise),
        position=position,
        strength=strength,
        dist_position_pct=dist_position,
    )
    return result


def _is_ok(value: object, ok_status: str) -> bool:
    """dict이고 status가 ok_status인지 확인한다.

    Returns:
        조건을 만족하면 True.
    """
    return isinstance(value, dict) and value.get("status") == ok_status


# =============================================================================
# judge_price_impact
# =============================================================================
def judge_price_impact(forecast: dict, consensus: dict, comparison: dict) -> dict:
    """위치 판정과 컨센서스 리비전으로 주가 영향 방향을, 근거 충분도로 판단 신뢰도를 정한다.

    방향: 상회 -> 긍정, 하회 -> 부정, 부합이면 리비전 >= +3% 긍정, <= -3% 부정, 그 외 중립.
    신뢰도(0~100): 수출 반영 개월(40) + 신호 강도(30) + 컨센서스 합의도(15) + 최신성(15) - 환산 감점.
    신뢰도는 근거 데이터가 얼마나 충분한지 나타내는 점수이며 주가가 오를 확률이 아니다.

    Args:
        forecast: estimate_revenue 결과.
        consensus: implied_quarter_consensus 결과.
        comparison: compare_consensus 결과.

    Returns:
        price_impact dict
            direction ("긍정", "중립", "부정", "판단불가"), confidence (int 0~100 | None),
            confidence_parts ({"months", "strength", "agreement", "freshness", "allocation_penalty"} | None),
            reasons (list[str], 최대 3개).
    """
    if not _is_ok(comparison, COMPARISON_STATUS_OK):
        return {
            "direction": IMPACT_UNKNOWN,
            "confidence": None,
            "confidence_parts": None,
            "reasons": [_unknown_reason(forecast, consensus)],
        }

    position = comparison["position"]
    revision = consensus.get("revision_pct")
    if position == POSITION_ABOVE:
        direction = IMPACT_POSITIVE
    elif position == POSITION_BELOW:
        direction = IMPACT_NEGATIVE
    elif _is_valid_number(revision) and revision >= REVISION_BAND_PCT:
        direction = IMPACT_POSITIVE
    elif _is_valid_number(revision) and revision <= -REVISION_BAND_PCT:
        direction = IMPACT_NEGATIVE
    else:
        direction = IMPACT_NEUTRAL

    parts = _confidence_parts(forecast, consensus, comparison)
    raw = parts["months"] + parts["strength"] + parts["agreement"] + parts["freshness"] - parts["allocation_penalty"]
    confidence = int(round(min(max(raw, 0.0), 100.0)))
    return {
        "direction": direction,
        "confidence": confidence,
        "confidence_parts": {key: round(value, 1) for key, value in parts.items()},
        "reasons": _impact_reasons(forecast, consensus, comparison),
    }


def _confidence_parts(forecast: dict, consensus: dict, comparison: dict) -> dict[str, float]:
    """판단 신뢰도의 구성 요소 다섯 개를 계산한다.

    Returns:
        {"months", "strength", "agreement", "freshness", "allocation_penalty": float}.
    """
    months = forecast.get("months_available")
    months_score = CONFIDENCE_MONTHS_MAX * min(max(months, 0), MONTHS_PER_QUARTER) / MONTHS_PER_QUARTER if (
        isinstance(months, int) and not isinstance(months, bool)
    ) else 0.0

    estimate, lower, upper = forecast["estimate_krw"], forecast["lower_krw"], forecast["upper_krw"]
    center = consensus["center_krw"]
    half_width_pct = (upper - lower) / 2.0 / estimate * 100.0 if estimate > 0 else 0.0
    if center < lower or center > upper or half_width_pct <= 0:
        strength = CONFIDENCE_STRENGTH_MAX
    else:
        strength = CONFIDENCE_STRENGTH_MAX * min(abs(comparison["surprise_pct"]) / half_width_pct, 1.0)

    spread = (consensus["dist_high_krw"] - consensus["dist_low_krw"]) / center * 100.0
    if spread <= SPREAD_FULL_PCT:
        agreement = CONFIDENCE_AGREEMENT_MAX
    elif spread >= SPREAD_ZERO_PCT:
        agreement = 0.0
    else:
        agreement = CONFIDENCE_AGREEMENT_MAX * (SPREAD_ZERO_PCT - spread) / (SPREAD_ZERO_PCT - SPREAD_FULL_PCT)

    after, since = consensus.get("days_after_announcement"), consensus.get("days_since_consensus")
    if not isinstance(after, int) or not isinstance(since, int) or after < POST_ANNOUNCEMENT_DAYS:
        freshness = 0.0
    elif since <= FRESH_DAYS:
        freshness = CONFIDENCE_FRESH_MAX
    elif since <= STALE_DAYS:
        freshness = CONFIDENCE_FRESH_PARTIAL
    else:
        freshness = 0.0

    penalty = ALLOCATION_PENALTY.get(consensus.get("remaining_quarters"), max(ALLOCATION_PENALTY.values()))
    return {
        "months": float(months_score),
        "strength": float(strength),
        "agreement": float(agreement),
        "freshness": float(freshness),
        "allocation_penalty": float(penalty),
    }


def _trillion(value: float) -> str:
    """원 단위 금액을 "126.5조" 형식으로 바꾼다.

    Returns:
        조 단위 소수 첫째 자리 문자열.
    """
    return f"{value / KRW_PER_TRILLION:.1f}조"


def _impact_reasons(forecast: dict, consensus: dict, comparison: dict) -> list[str]:
    """판단 근거 문장(괴리율, 리비전, 환산 근사)을 만든다.

    Returns:
        최대 MAX_REASONS개의 문장 list.
    """
    surprise = comparison["surprise_pct"]
    position = comparison["position"]
    label = position if comparison["strength"] is None else f"{position}({comparison['strength']})"
    gap = f"{abs(surprise):.1f}% {'높아' if surprise >= 0 else '낮아'}"
    reasons = [
        f"추정치 {_trillion(forecast['estimate_krw'])} 원이 분기 컨센서스 {_trillion(consensus['center_krw'])} 원보다 "
        f"{gap} {label} 판정입니다."
    ]
    revision = consensus.get("revision_pct")
    if _is_valid_number(revision):
        trend = "상향" if revision > 0 else "하향" if revision < 0 else "변화 없음"
        reasons.append(f"연간 컨센서스가 최근 {REVISION_LOOKBACK_DAYS}일 동안 {revision:+.1f}% {trend}되었습니다.")
    if consensus.get("method") == METHOD_ALLOCATED:
        reasons.append(
            "분기 컨센서스는 연간 컨센서스를 남은 분기에 나눈 근사값이라 환산 범위로 판정했습니다."
        )
    return reasons[:MAX_REASONS]


def _unknown_reason(forecast: dict, consensus: dict) -> str:
    """판단불가 사유 한 문장을 만든다.

    Returns:
        사유 문장.
    """
    if not _is_ok(forecast, FORECAST_STATUS_OK):
        return "매출 추정치가 없어 컨센서스와 비교할 수 없습니다."
    status = consensus.get("status") if isinstance(consensus, dict) else None
    if status == CONSENSUS_STATUS_NOT_READY:
        return "직전 분기 실적이 아직 발표되지 않아 분기 컨센서스를 구할 수 없습니다."
    if status == CONSENSUS_STATUS_INVALID:
        return "연간 컨센서스가 이미 발표된 실적 합보다 작아 분기 컨센서스를 구할 수 없습니다."
    return "대상 연도의 컨센서스 자료가 없습니다 (data/consensus.csv)."
