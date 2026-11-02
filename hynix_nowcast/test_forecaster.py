import math
import pytest
from forecaster import compare_guidance


def F(status="ok", q=10.0):
    return {"status": status, "qoq_change_pct": q}


def G(status="ok", p="상승", d=None):
    return {"status": status, "price_outlook": p, "dram_bit_growth_pct": d}


@pytest.mark.parametrize(
    "forecast, guidance, expected",
    [
        (F(q=16.5), G(p="상승", d=10.0), ("일치", "상승", "상승")),
        (F(q=-5.0), G(p="상승", d=None), ("불일치", "하락", "상승")),
        (F(q=-5.0), G(p="하락", d=-3.0), ("일치", "하락", "하락")),
        (F(q=2.0), G(p="상승"), ("판단불가", "보합", "상승")),
        (F(q=-2.0), G(p="하락"), ("판단불가", "보합", "하락")),
        (F(q=10.0), G(p="상승", d=-5.0), ("판단불가", "상승", None)),
        (F(q=10.0), G(p="하락", d=5.0), ("판단불가", "상승", None)),
        (F(q=10.0), G(p="보합"), ("판단불가", "상승", None)),
        (F(q=10.0), G(p="언급없음"), ("판단불가", "상승", None)),
        (F(q=10.0), G(status="empty_input", p="NA"), ("판단불가", "상승", None)),
        (F(q=10.0), G(status="parse_error", p="NA"), ("판단불가", "상승", None)),
        (F(status="no_data", q=None), G(), ("판단불가", None, "상승")),
        (F(status="insufficient_history", q=None), G(), ("판단불가", None, "상승")),
        (F(q=None), G(), ("판단불가", None, "상승")),
        (F(q=float("nan")), G(), ("판단불가", None, "상승")),
        (F(q=True), G(), ("판단불가", None, "상승")),
    ],
)
def test_compare_guidance(forecast, guidance, expected):
    r = compare_guidance(forecast, guidance)
    assert (r["status"], r["forecast_direction"], r["guidance_direction"]) == expected
    assert set(r) == {"status", "forecast_direction", "guidance_direction"}


def test_input_not_mutated():
    f, g = F(q=5.0), G(d=3.0)
    f0, g0 = dict(f), dict(g)
    compare_guidance(f, g)
    assert f == f0 and g == g0


def test_bad_types_no_exception():
    assert compare_guidance(None, None)["status"] == "판단불가"
    assert compare_guidance({}, {})["status"] == "판단불가"