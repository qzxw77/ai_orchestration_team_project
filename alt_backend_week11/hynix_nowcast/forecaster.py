"""[모듈 3] 분석 (숫자 계산 전담).

    estimate_revenue  분기 수출 x 과거 매출/수출 비율(ratio_rule로 계산 방식 선택) -> 대상 분기 매출 범위
    detect_anomaly    최근 월 수출의 전년동월비 z-score -> 급증, 급감 판정
    compare_guidance  추정 방향과 컨콜 가이던스 방향 비교

입력 표와 dict는 바꾸지 않고, 결과 dict는 호출마다 새로 만들며 값은 파이썬 기본 타입만 쓴다.
"""

import math

import pandas as pd

ALLOWED_REGIONS = ("이천시", "청주시")
MONTHS_PER_QUARTER = 3
RATIO_WINDOW = 4
# 기준 분기 비율로 대상 분기 비율을 정하는 규칙. 기본값 drift의 근거는 backtest_ratio_rule.py와 README 참고
RATIO_RULE_AVG = "avg"      # 기준 분기 비율의 평균 (12주차까지의 방식)
RATIO_RULE_LAST = "last"    # 가장 최근 기준 분기의 비율
RATIO_RULE_DRIFT = "drift"  # 가장 최근 비율 x exp(기준 분기 사이 로그 비율 변화의 평균): 비율 추세를 한 분기 연장
RATIO_RULE_AUTO = "auto"    # 대상 분기 이전의 발표된 분기들로 위 3개 규칙을 채점해 오차가 가장 작은 규칙 사용
BASE_RATIO_RULES = (RATIO_RULE_AVG, RATIO_RULE_LAST, RATIO_RULE_DRIFT)  # 동점이면 앞쪽(보수적인 규칙)을 고른다
RATIO_RULES = BASE_RATIO_RULES + (RATIO_RULE_AUTO,)
DEFAULT_RATIO_RULE = RATIO_RULE_AUTO

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


# =============================================================================
# estimate_revenue
# =============================================================================
def estimate_revenue(
    quarterly_df: pd.DataFrame,
    actuals_df: pd.DataFrame,
    target_quarter: str,
    ratio_rule: str = DEFAULT_RATIO_RULE,
) -> dict:
    """대상 분기 매출을 과거 분기의 (매출/환율)/수출 비율로 추정한다.

    기준 분기는 대상 분기보다 앞서고, 실적이 있고, 3개월 자료가 모두 있고, 수출과 환율이 0보다 큰 분기 중
    가장 최근 RATIO_WINDOW개다. 분기 수출 추정 = 대상 분기 수출 x 3 / 반영 개월 수이고,
    중앙값 = 분기 수출 추정 x 적용 비율 x 대상 분기 평균 환율이고, 적용 비율은 ratio_rule로 정한다.
        avg   기준 분기 비율의 평균
        last  가장 최근 기준 분기의 비율
        drift 가장 최근 비율 x exp(기준 분기 사이 로그 비율 변화의 평균)
        auto  대상 분기보다 앞선 기준 분기 각각을 "그 앞 RATIO_WINDOW개 분기로 추정"해 보고,
              절대 오차 평균이 가장 작은 규칙(avg, last, drift 중)을 쓴다 (기본값).
              채점할 분기가 없으면 avg를 쓴다. 대상 분기와 그 뒤의 실적은 채점에도 쓰지 않는다.
    하한, 상한 = 분기 수출 추정 x (기준 비율과 적용 비율 중 최솟값, 최댓값) x 대상 분기 평균 환율이다.
    (drift는 기준 비율 범위 밖으로 나갈 수 있어 적용 비율도 범위에 넣는다. avg에서는 예전과 같은 값이다.)
    대상 분기와 그 뒤의 실적은 읽지 않는다.

    Args:
        quarterly_df: aggregate_quarterly 결과.
        actuals_df: load_actuals 결과.
        target_quarter: 대상 분기 "YYYYQn".
        ratio_rule: RATIO_RULES 중 하나 (기본 DEFAULT_RATIO_RULE).

    Returns:
        forecast dict
            quarter (str), estimate_krw, lower_krw, upper_krw (float | None, 원),
            qoq_change_pct (float | None, 직전 분기 실적 대비 %), ratio_used (float | None),
            months_available (int, 0~3), status ("ok", "no_data", "insufficient_history"),
            ratio_rule (str, 실제로 적용한 규칙. auto이면 고른 규칙 이름).
        status가 "ok"가 아니면 숫자 키 5개는 None이다.

    Raises:
        KeyError: 표에 필요한 열이 없을 때 (앞 단계 계약 위반이라 그대로 올린다).
        ValueError: ratio_rule이 RATIO_RULES에 없을 때 (호출 코드의 오타라 조용히 넘기지 않는다).
    """
    if ratio_rule not in RATIO_RULES:
        raise ValueError(f"ratio_rule은 {RATIO_RULES} 중 하나여야 합니다: {ratio_rule!r}")
    result = {
        "quarter": target_quarter,
        "estimate_krw": None,
        "lower_krw": None,
        "upper_krw": None,
        "qoq_change_pct": None,
        "ratio_used": None,
        "months_available": 0,
        "status": FORECAST_STATUS_NO_DATA,
        "ratio_rule": ratio_rule,
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
    applied_rule = _select_ratio_rule(base) if ratio_rule == RATIO_RULE_AUTO else ratio_rule
    ratio_used = _apply_ratio_rule(ratios, applied_rule)
    band = [min(ratios), max(ratios), ratio_used]
    estimate_krw = quarter_export_usd * ratio_used * fx_avg

    previous = actuals.loc[actuals["quarter"] == _previous_quarter(target_quarter), "revenue_krw"]
    qoq_change_pct = None
    if len(previous) > 0 and float(previous.iloc[0]) != 0:
        qoq_change_pct = float((estimate_krw / float(previous.iloc[0]) - 1.0) * 100.0)

    result.update(
        estimate_krw=float(estimate_krw),
        lower_krw=float(quarter_export_usd * min(band) * fx_avg),
        upper_krw=float(quarter_export_usd * max(band) * fx_avg),
        qoq_change_pct=qoq_change_pct,
        ratio_used=float(ratio_used),
        status=FORECAST_STATUS_OK,
        ratio_rule=applied_rule,
    )
    return result


def _select_ratio_rule(base: pd.DataFrame) -> str:
    """기준 분기 후보 표(시간순)로 BASE_RATIO_RULES를 채점해 절대 오차 평균이 가장 작은 규칙을 고른다.

    채점 대상은 base의 각 분기 b 중 b보다 앞선 분기가 RATIO_WINDOW개 이상 있는 분기이고,
    b의 3개월 수출과 그 앞 RATIO_WINDOW개 분기의 비율로 b의 매출을 추정해 b의 실적과 비교한다.

    Args:
        base: estimate_revenue가 고른 기준 분기 후보 (quarter, export_usd, fx_avg, revenue_krw, 오름차순).

    Returns:
        고른 규칙 이름. 채점할 분기가 없으면 RATIO_RULE_AVG.
    """
    all_ratios = ((base["revenue_krw"] / base["fx_avg"]) / base["export_usd"]).tolist()
    errors: dict[str, list[float]] = {rule: [] for rule in BASE_RATIO_RULES}
    for index in range(RATIO_WINDOW, len(all_ratios)):
        window = all_ratios[index - RATIO_WINDOW:index]
        for rule in BASE_RATIO_RULES:
            # 같은 분기의 수출, 환율을 쓰므로 매출 추정 오차 = 비율 추정 오차
            errors[rule].append(abs(_apply_ratio_rule(window, rule) / all_ratios[index] - 1.0))
    if not errors[RATIO_RULE_AVG]:
        return RATIO_RULE_AVG
    return min(BASE_RATIO_RULES, key=lambda rule: sum(errors[rule]) / len(errors[rule]))


def _apply_ratio_rule(ratios: list[float], ratio_rule: str) -> float:
    """기준 분기 비율(오래된 분기 -> 최근 분기 순)로 대상 분기에 쓸 비율을 정한다.

    Args:
        ratios: 0보다 큰 비율 목록 (기준 분기 조건에서 매출, 환율, 수출이 모두 양수라 비율도 양수다).
        ratio_rule: BASE_RATIO_RULES 중 하나 (auto는 _select_ratio_rule로 먼저 바꾼다).

    Returns:
        적용 비율.
    """
    if ratio_rule == RATIO_RULE_LAST:
        return ratios[-1]
    if ratio_rule == RATIO_RULE_DRIFT:
        log_changes = [math.log(after / before) for before, after in zip(ratios, ratios[1:])]
        if not log_changes:  # RATIO_WINDOW가 1이면 변화율을 구할 수 없어 최근 비율을 그대로 쓴다
            return ratios[-1]
        return ratios[-1] * math.exp(sum(log_changes) / len(log_changes))
    return sum(ratios) / len(ratios)


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
