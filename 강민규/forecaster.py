import math

import pandas as pd


ALLOWED_REGIONS = ("이천시", "청주시")
REQUIRED_COLUMNS = ("ym", "region", "export_usd")
STD_EPSILON = 1e-9

YOY_LAG_MONTHS = 12  # 전년 동월을 찾는 간격
BASELINE_MONTHS = 12  # 평소 범위(평균, 표준편차)를 계산할 직전 개월 수
REQUIRED_PAST_MONTHS = YOY_LAG_MONTHS + BASELINE_MONTHS  # 대상 월 앞으로 월 합계가 있어야 하는 개월 수

REASON_NORMAL = "정상"
REASON_SURGE = "급증"
REASON_DROP = "급감"
REASON_INSUFFICIENT = "데이터 부족"


def _is_valid_ym(value: object) -> bool:
    """값이 "YYYY-MM"(월 01~12) 형식의 문자열인지 확인한다.

    Args:
        value: 확인할 값. 어떤 타입이든 받는다.

    Returns:
        형식이 맞으면 True, 아니면 False.

    Raises:
        없음
    """
    # isdigit()는 "²" 같은 위첨자도 True라 int()에서 ValueError가 나므로 isdecimal()로 확인한다
    return (
        isinstance(value, str)
        and len(value) == 7
        and value[4] == "-"
        and value[:4].isdecimal()
        and value[5:].isdecimal()
        and 1 <= int(value[5:]) <= 12
    )


def _shift_ym(ym: str, months: int) -> str:
    """ym에서 months개월 뒤(음수면 앞)의 달을 "YYYY-MM"으로 돌려준다.

    Args:
        ym: 기준 월 ("YYYY-MM").
        months: 더할 개월 수 (예: -12는 12개월 전).

    Returns:
        이동한 달 ("YYYY-MM").

    Raises:
        없음 (형식이 확인된 ym만 받는다)
    """
    year = int(ym[:4])
    month = int(ym[5:])
    index = year * 12 + month - 1 + months
    shifted_year, shifted_month = divmod(index, 12)
    return f"{shifted_year:04d}-{shifted_month + 1:02d}"


def _insufficient_result(target_ym: str, yoy_pct: float | None = None) -> dict:
    """"데이터 부족" 결과 dict를 호출할 때마다 새로 만들어 돌려준다.

    모듈 수준 dict를 두고 고쳐 쓰면 앞 호출에서 채운 yoy_pct가 다음 호출 결과로 새므로 매번 새로 만든다.

    Args:
        target_ym: 결과의 ym에 그대로 넣을 대상 월.
        yoy_pct: 표준편차가 STD_EPSILON 미만일 때만 넘기는 대상 월의 전년동월비(%). 그 밖에는 None.

    Returns:
        ym, yoy_pct, z_score(None), is_anomaly(False), reason("데이터 부족")을 담은 새 dict.

    Raises:
        없음
    """
    return {
        "ym": target_ym,
        "yoy_pct": yoy_pct,
        "z_score": None,
        "is_anomaly": False,
        "reason": REASON_INSUFFICIENT,
    }


def _monthly_totals(exports_df: pd.DataFrame) -> dict[str, float]:
    """ALLOWED_REGIONS 지역이 모두 있는 달의 월 수출 합계를 만든다.

    잘못된 ym, 대상 외 지역, float()로 바꿀 수 없는 값, 결측, 음수, 무한대인 행은 건너뛰고,
    같은 달, 같은 지역 행이 여러 개면 더한다. exports_df는 읽기만 한다.

    Args:
        exports_df: REQUIRED_COLUMNS 열이 모두 있는 DataFrame.

    Returns:
        {"YYYY-MM": 월 합계(float)}. 한 지역이라도 없는 달은 들어 있지 않다.

    Raises:
        없음 (필수 열은 detect_anomaly가 먼저 확인하고, 바꿀 수 없는 값은 예외 없이 건너뛴다)
    """
    monthly_regions: dict[str, dict[str, float]] = {}

    # 벡터화(pd.to_numeric 등) 대신 행 단위로 도는 이유: float()의 변환 규칙("1_000", 전각 숫자, True)을 그대로 지키기 위해
    # 튜플로 열을 고르면 pandas가 튜플 전체를 열 이름 하나로 보므로 list로 바꿔 고른다
    rows = exports_df[list(REQUIRED_COLUMNS)].itertuples(index=False, name=None)
    for ym, region, export_usd in rows:
        if not _is_valid_ym(ym) or region not in ALLOWED_REGIONS:
            continue

        try:
            amount = float(export_usd)
        except (TypeError, ValueError, OverflowError):
            continue

        if not math.isfinite(amount) or amount < 0:
            continue

        regions = monthly_regions.setdefault(ym, {})
        regions[region] = regions.get(region, 0.0) + amount

    # 한 지역만 있는 달은 수집 누락일 가능성이 커서 합계가 실제보다 작게 잡혀 가짜 급감이 나온다.
    # 그래서 모든 지역이 있는 달만 합계를 만들고, 나머지는 월 합계가 없는 달로 본다
    return {
        ym: sum(regions[region] for region in ALLOWED_REGIONS)
        for ym, regions in monthly_regions.items()
        if all(region in regions for region in ALLOWED_REGIONS)
    }


def _yoy_values(monthly_totals: dict[str, float], target_ym: str) -> list[float] | None:
    """대상 월과 직전 BASELINE_MONTHS개월의 전년 동월 대비 증가율(%)을 구한다.

    Args:
        monthly_totals: _monthly_totals가 만든 {"YYYY-MM": 월 합계}.
        target_ym: 대상 월 ("YYYY-MM", 형식이 확인된 값).

    Returns:
        전년동월비 BASELINE_MONTHS + 1개(지금은 13개)를 오래된 달부터 담은 list. 마지막 값이 대상 월이다.
        대상 월과 그 앞 REQUIRED_PAST_MONTHS개월 중 월 합계가 없는 달이 있거나,
        비교할 YOY_LAG_MONTHS개월 전 합계가 0이면 None.

    Raises:
        없음
    """
    required_months = {
        _shift_ym(target_ym, offset)
        for offset in range(-REQUIRED_PAST_MONTHS, 1)
    }
    if not required_months.issubset(monthly_totals):
        return None

    yoy_values: list[float] = []
    for offset in range(-BASELINE_MONTHS, 1):
        ym = _shift_ym(target_ym, offset)
        previous_total = monthly_totals[_shift_ym(ym, -YOY_LAG_MONTHS)]

        if previous_total == 0:
            return None

        yoy_values.append((monthly_totals[ym] / previous_total - 1.0) * 100.0)

    return yoy_values


def _mean_and_sample_std(values: list[float]) -> tuple[float, float]:
    """값 목록의 평균과 표본 표준편차(개수 - 1로 나눔)를 구한다.

    Args:
        values: 평균과 표준편차를 구할 값 (2개 이상).

    Returns:
        (평균, 표본 표준편차).

    Raises:
        ZeroDivisionError: values가 2개 미만일 때 (detect_anomaly는 항상 BASELINE_MONTHS개를 넘긴다).
    """
    # statistics나 pandas의 mean, std로 바꾸면 끝자리가 달라져 |z| == threshold 경계 판정이 뒤집힐 수 있어
    # 합 / 개수, 제곱합 / (개수 - 1), math.sqrt 식을 그대로 쓴다
    count = len(values)
    mean = sum(values) / count
    variance = sum((value - mean) ** 2 for value in values) / (count - 1)
    return mean, math.sqrt(variance)


def _classify(z_score: float, threshold: float) -> tuple[bool, str]:
    """z-score와 threshold로 이상치 여부와 사유를 정한다.

    Args:
        z_score: 대상 월의 z-score.
        threshold: 이상치 판정 기준인 z-score 절댓값.

    Returns:
        (is_anomaly, reason). |z_score| > threshold가 아니면 (False, "정상"),
        넘으면서 z_score가 양수면 (True, "급증"), 아니면 (True, "급감").

    Raises:
        TypeError: threshold가 숫자가 아니어서 abs(z_score)와 비교할 수 없을 때. 호출 실수이므로 잡지 않는다.
    """
    # 이상치는 기준을 "넘는" 경우로 정했으므로 |z|가 threshold와 정확히 같으면 정상이다 (>=가 아니라 >)
    is_anomaly = abs(z_score) > threshold
    if not is_anomaly:
        return False, REASON_NORMAL
    if z_score > 0:
        return True, REASON_SURGE
    return True, REASON_DROP


def detect_anomaly(
    exports_df: pd.DataFrame,
    target_ym: str,
    threshold: float = 2.0,
) -> dict:
    """대상 월 수출의 전년 동월 대비 증가율이 평소 범위를 벗어났는지 판정한다.

    ALLOWED_REGIONS 지역이 모두 있는 달만 월 합계를 만들고, 대상 월과 직전 12개월의 전년동월비를 구한다.
    직전 12개월 전년동월비의 평균과 표본 표준편차로 대상 월의 z-score를 계산해
    |z| > threshold이면 이상치로 본다.

    Args:
        exports_df: 지역별 월 수출 표. 아래 필수 열(REQUIRED_COLUMNS)이 있어야 하고 다른 열은 무시한다.
            ym (str): 수출 월, "YYYY-MM".
            region (str): 지역 이름. ALLOWED_REGIONS("이천시", "청주시")만 쓴다.
            export_usd (float 또는 float()로 바꿀 수 있는 값): 수출액(달러), 0 이상의 유한한 값.
            조건에 맞지 않는 행(잘못된 ym, 대상 외 지역, 숫자로 바꿀 수 없는 값, 결측, 음수, 무한대)은 건너뛰고,
            같은 달, 같은 지역 행이 여러 개면 더한다. 표는 수정하지 않는다.
        target_ym: 판정 대상 월, "YYYY-MM" (월은 01~12).
        threshold: 이상치 판정 기준인 z-score 절댓값 (int 또는 float, 기본값 2.0).
            |z_score|가 threshold보다 클 때만 이상치이고, 같으면 정상이다.

    Returns:
        아래 키 5개를 가진 새 dict (호출마다 새로 만든다).
            ym: 받은 target_ym 그대로.
            yoy_pct (float | None): 대상 월의 전년 동월 대비 증가율(%).
            z_score (float | None): 직전 12개월 전년동월비의 평균과 표본 표준편차로 계산한 대상 월의 z-score.
            is_anomaly (bool): |z_score| > threshold이면 True.
            reason (str): "정상", "급증", "급감", "데이터 부족" 중 하나.
        아래 경우에는 reason이 "데이터 부족"이고 z_score는 None, is_anomaly는 False다.
            - target_ym이 "YYYY-MM" 형식이 아님
            - exports_df가 DataFrame이 아님, 빈 표, 필수 열 누락
            - 대상 월과 그 앞 24개월(모두 25개월) 중 월 합계가 없는 달이 있음
            - 비교할 12개월 전 월 합계가 0
            - 직전 12개월 전년동월비의 표준편차가 STD_EPSILON 미만
        yoy_pct는 표준편차가 STD_EPSILON 미만인 경우에만 채우고, 나머지 "데이터 부족"에서는 None이다.

    Raises:
        TypeError: threshold가 숫자가 아니어서 |z|와 비교할 수 없을 때 (예: "2").
            자료 문제가 아니라 호출 실수이므로 "데이터 부족"으로 바꾸지 않고 그대로 올린다.
            z를 계산하기 전에 "데이터 부족"으로 끝나는 경우에는 threshold를 쓰지 않으므로 나지 않는다.
    """
    if not _is_valid_ym(target_ym):
        return _insufficient_result(target_ym)

    if not isinstance(exports_df, pd.DataFrame) or exports_df.empty:
        return _insufficient_result(target_ym)

    if not set(REQUIRED_COLUMNS).issubset(exports_df.columns):
        return _insufficient_result(target_ym)

    yoy_values = _yoy_values(_monthly_totals(exports_df), target_ym)
    if yoy_values is None:
        return _insufficient_result(target_ym)

    yoy_pct = float(yoy_values[-1])
    mean, standard_deviation = _mean_and_sample_std(yoy_values[:-1])

    # 평소 증가율이 거의 일정하면 표준편차가 0에 가까워 z가 터무니없이 커진다(0이면 나눗셈 오류).
    # 부동소수 오차로 정확히 0이 아닌 아주 작은 값이 나올 수 있어 == 0 대신 STD_EPSILON과 비교한다
    if standard_deviation < STD_EPSILON:
        return _insufficient_result(target_ym, yoy_pct)

    z_score = float((yoy_pct - mean) / standard_deviation)
    is_anomaly, reason = _classify(z_score, threshold)

    return {
        "ym": target_ym,
        "yoy_pct": yoy_pct,
        "z_score": z_score,
        "is_anomaly": is_anomaly,
        "reason": reason,
    }