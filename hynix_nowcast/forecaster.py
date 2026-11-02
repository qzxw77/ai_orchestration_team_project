import math

# 방향 판정 경계값 (%): 전분기 대비 변화율이 ±2.0% 이내이면 "보합"으로 판정한다.
DIRECTION_BAND_PCT = 2.0


def _is_valid_number(value: object) -> bool:
    """입력값이 불리언(bool)이 아닌 유효한 실수 또는 정수인지 확인한다.

    Args:
        value: 검사할 임의의 값.

    Returns:
        bool: 불리언이 아니며 NaN이나 무한대가 아닌 유효한 숫자이면 True, 아니면 False.

    Raises:
        없음.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value)


def compare_guidance(forecast: dict, guidance: dict) -> dict:
    """추정 매출의 전분기 대비 방향이 컨콜 가이던스가 가리키는 방향과 같은지 판정한다.

    Args:
        forecast: estimate_revenue 함수가 반환한 매출 추정 결과 dict.
            (필수 참조 키: "status", "qoq_change_pct")
        guidance: extract_guidance 함수가 반환한 컨퍼런스콜 가이던스 dict.
            (필수 참조 키: "status", "price_outlook", "dram_bit_growth_pct")

    Returns:
        dict: 방향 비교 결과를 담은 consistency 형식의 새 dict.
            - "status": "일치", "불일치", "판단불가" 중 하나 (str)
            - "forecast_direction": "상승", "보합", "하락" 또는 None (str | None)
            - "guidance_direction": "상승", "하락" 또는 None (str | None)

    Raises:
        없음. 입력 누락이나 비정상 값이 들어와도 예외를 내지 않고 "판단불가"로 반환한다.
    """
    # 1) 추정치의 방향 판정
    forecast_direction: str | None = None
    if isinstance(forecast, dict) and forecast.get("status") == "ok":
        q = forecast.get("qoq_change_pct")
        if _is_valid_number(q):
            if q > DIRECTION_BAND_PCT:
                forecast_direction = "상승"
            elif q < -DIRECTION_BAND_PCT:
                forecast_direction = "하락"
            else:
                forecast_direction = "보합"

    # 2) 가이던스의 방향 판정 (D램 기준, 매출 = 가격 × 출하량)
    guidance_direction: str | None = None
    if isinstance(guidance, dict) and guidance.get("status") == "ok":
        p = guidance.get("price_outlook")
        d = guidance.get("dram_bit_growth_pct")
        if p == "상승" and (d is None or (_is_valid_number(d) and d >= 0)):
            guidance_direction = "상승"
        elif p == "하락" and (d is None or (_is_valid_number(d) and d <= 0)):
            guidance_direction = "하락"
        else:
            guidance_direction = None

    # 3) 최종 일치 여부 판정
    if (
        forecast_direction is None
        or guidance_direction is None
        or forecast_direction == "보합"
    ):
        status = "판단불가"
    elif forecast_direction == guidance_direction:
        status = "일치"
    else:
        status = "불일치"

    return {
        "status": status,
        "forecast_direction": forecast_direction,
        "guidance_direction": guidance_direction,
    }