"""fetch_fx_rates 리팩터링 안전망 테스트 (기존 test_fetch_fx_rates.py 19개에 더해서)

리팩터링은 외부 동작을 바꾸지 않아야 한다. 기존 테스트가 확인하지 않는 동작
(오류 메시지 원문, 검사 순서, 코드 리딩 수정 1~3, 반복이 끝나는 조건)을 리팩터링 전 코드 기준으로 고정한다.
리팩터링 전에도, 후에도 모두 통과해야 한다. 실제 ECOS API를 부르지 않고, 환율 값은 가상의 더미 값이다.
"""

import pandas as pd
import pytest
import requests

import data_loader
from data_loader import fetch_fx_rates

TEST_KEY = "TESTKEY0123456789"
START, END = "2026-01-01", "2026-01-31"
FORMAT_ERROR = "ECOS API 호출 실패: 응답 형식 오류"
MAX_CALLS = 10  # 반복이 끝나지 않는 실수를 무한 루프 대신 실패로 드러내기 위한 상한


class FakeResponse:
    """requests.Response 대역. 코드가 쓰는 status_code, raise_for_status(), json()만 흉내 낸다."""

    def __init__(self, payload=None, status_code=200, bad_json=False):
        self.payload = payload
        self.status_code = status_code
        self.bad_json = bad_json

    def raise_for_status(self):
        if self.status_code >= 400:
            # 직접 만든 HTTPError라 .response가 None이다. 상태 코드는 응답 객체에서 읽어야 한다
            raise requests.HTTPError(f"{self.status_code} Error for url: /StatisticSearch/{TEST_KEY}/...")

    def json(self):
        if self.bad_json:
            raise ValueError("Expecting value")
        return self.payload


def _row(time, value):
    return {"STAT_CODE": "731Y001", "TIME": time, "DATA_VALUE": value}


def _ok(rows, total=None):
    return {"StatisticSearch": {"list_total_count": len(rows) if total is None else total, "row": rows}}


NO_DATA = {"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}}


@pytest.fixture
def fake_ecos(monkeypatch):
    """가짜 키를 넣고 requests.get을 바꿔 끼운다. responder(호출 번호)가 응답을 정한다. 호출 기록을 돌려준다."""
    monkeypatch.setenv("ECOS_API_KEY", TEST_KEY)
    calls = []

    def install(responder):
        def fake_get(url, *args, **kwargs):
            calls.append({"url": url, "kwargs": kwargs})
            if len(calls) > MAX_CALLS:
                raise AssertionError("요청이 끝나지 않는다 (반복 종료 조건이 바뀜)")
            return responder(len(calls))

        monkeypatch.setattr(data_loader.requests, "get", fake_get)
        return calls

    return install


# ---------- 오류 메시지 원문 (main이 화면에 그대로 보여 줌) ----------

def _raise(exc_type):
    def responder(n):
        raise exc_type(f"failed: /StatisticSearch/{TEST_KEY}/json/kr/1/1000/...")
    return responder


@pytest.mark.parametrize(
    "responder, expected",
    [
        (_raise(requests.ConnectionError), "ECOS API 호출 실패: ConnectionError"),
        (_raise(requests.Timeout), "ECOS API 호출 실패: Timeout"),
        (lambda n: FakeResponse(status_code=404), "ECOS API 호출 실패: HTTP 404"),
        (lambda n: FakeResponse({"RESULT": {"CODE": "INFO-100", "MESSAGE": "인증키가 유효하지 않습니다."}}),
         "ECOS API 호출 실패: INFO-100 인증키가 유효하지 않습니다."),
        (lambda n: FakeResponse(bad_json=True), FORMAT_ERROR),
    ],
    ids=["connection", "timeout", "http404", "result_code", "not_json"],
)
def test_guard_api_error_messages_exact(fake_ecos, responder, expected):
    """호출 실패 메시지는 글자 하나까지 그대로 (메시지를 상수나 도우미로 옮기다 바뀌는 것을 막는다)"""
    fake_ecos(responder)
    with pytest.raises(RuntimeError) as excinfo:
        fetch_fx_rates(START, END)
    assert str(excinfo.value) == expected


@pytest.mark.parametrize(
    "payload",
    [
        {"RESULT": "오류"},                                                  # RESULT가 dict가 아님
        {"RESULT": {"MESSAGE": "코드 없음"}},                                 # CODE 없음
        [1, 2, 3],                                                          # 응답이 dict가 아님
        {"StatisticSearch": {"list_total_count": 1, "row": "x"}},           # row가 목록이 아님
        {"StatisticSearch": {"list_total_count": True, "row": []}},
        {"StatisticSearch": {"list_total_count": -1, "row": []}},
        {"StatisticSearch": {"list_total_count": "abc", "row": []}},
        {"StatisticSearch": {"list_total_count": 1.5, "row": []}},
        {"StatisticSearch": {"list_total_count": "-1", "row": []}},
    ],
    ids=["result_not_dict", "result_no_code", "payload_list", "row_not_list",
         "total_true", "total_negative", "total_text", "total_float", "total_negative_text"],
)
def test_guard_malformed_responses(fake_ecos, payload):
    """망가진 응답은 모두 "응답 형식 오류" (수정 3 이후에도 True, 음수, 문자, 소수는 그대로 오류)"""
    fake_ecos(lambda n: FakeResponse(payload))
    with pytest.raises(RuntimeError) as excinfo:
        fetch_fx_rates(START, END)
    assert str(excinfo.value) == FORMAT_ERROR


# ---------- 코드 리딩 수정 1~3 회귀 ----------

def test_guard_numeric_string_total_count_with_paging(fake_ecos, monkeypatch):
    """수정 3: list_total_count가 숫자 문자열 "5"여도 정상. 2행씩 받아 1~2, 3~4, 5~6 세 번 요청해 5행을 모은다
    (문자열과 숫자를 그대로 비교하면 TypeError가 나므로 int로 바꾼 값으로 비교해야 한다)"""
    monkeypatch.setattr(data_loader, "ECOS_PAGE_SIZE", 2)
    rows = [_row(f"2026010{d}", f"14{d}0.0") for d in range(2, 7)]
    calls = fake_ecos(lambda n: FakeResponse(_ok(rows[(n - 1) * 2:n * 2], total="5")))

    result = fetch_fx_rates(START, END)

    assert len(result) == 5
    assert len(calls) == 3


def test_guard_empty_tables_have_same_dtypes_as_normal(fake_ecos):
    """수정 2: INFO-200 빈 표, 값이 모두 무효라 생긴 빈 표, 정상 표의 열 타입이 같다.
    정상 표와 빈 표를 이어 붙여도 usdkrw는 float로 남는다"""
    responses = iter([
        FakeResponse(_ok([_row("20260102", "1445.0")])),
        FakeResponse(NO_DATA),
        FakeResponse(_ok([_row("20260102", "-")])),
    ])
    fake_ecos(lambda n: next(responses))

    normal = fetch_fx_rates(START, END)
    no_data = fetch_fx_rates(START, END)
    all_invalid = fetch_fx_rates(START, END)

    assert len(no_data) == 0 and len(all_invalid) == 0
    assert list(no_data.columns) == ["date", "usdkrw"]
    assert no_data.dtypes.equals(normal.dtypes)
    assert all_invalid.dtypes.equals(normal.dtypes)
    assert pd.api.types.is_float_dtype(pd.concat([normal, no_data], ignore_index=True)["usdkrw"])


@pytest.mark.parametrize(
    "start, end, expected",
    [
        ("2026-13-01", "2026-12-31", "날짜 형식 오류: 2026-13-01"),
        ("2026-02-01", "2026-01-31", "시작일이 끝일보다 늦습니다: 2026-02-01 > 2026-01-31"),
        # 두 값의 자리 수, ASCII, "-" 검사를 먼저 하고 달력 검사는 그다음 -> 끝일의 형식 오류가 먼저 걸린다
        ("2026-13-01", "2026/01/31", "날짜 형식 오류: 2026/01/31"),
        # 수정 1: 전각 숫자 날짜
        ("2026-01-01", "２０２６-01-31", "날짜 형식 오류: ２０２６-01-31"),
    ],
    ids=["calendar", "start_after_end", "format_checked_first", "fullwidth_digits"],
)
def test_guard_date_error_messages_and_order(fake_ecos, start, end, expected):
    """날짜 오류 메시지 원문과 검사 순서. ECOS는 부르지 않는다"""
    calls = fake_ecos(lambda n: FakeResponse(_ok([])))
    with pytest.raises(ValueError) as excinfo:
        fetch_fx_rates(start, end)
    assert str(excinfo.value) == expected
    assert calls == []


# ---------- 검사 순서, 경계 ----------

def test_guard_dates_checked_before_api_key(fake_ecos, monkeypatch):
    """날짜 인자 -> API 키 순서: 키가 없어도 날짜가 틀리면 ValueError가 먼저 난다"""
    fake_ecos(lambda n: FakeResponse(_ok([])))
    monkeypatch.delenv("ECOS_API_KEY", raising=False)
    with pytest.raises(ValueError):
        fetch_fx_rates("2026-13-01", "2026-12-31")


def test_guard_same_start_and_end_is_allowed(fake_ecos):
    """시작일과 끝일이 같으면 오류가 아니다 (시작일 > 끝일일 때만 ValueError)"""
    calls = fake_ecos(lambda n: FakeResponse(_ok([_row("20260102", "1445.0")])))
    result = fetch_fx_rates("2026-01-02", "2026-01-02")
    assert result["date"].tolist() == ["2026-01-02"]
    assert calls[0]["url"].rstrip("/").endswith("/20260102/20260102/0000001")


@pytest.mark.parametrize("second_page", ["no_data", "empty_rows"])
def test_guard_paging_stops_early(fake_ecos, monkeypatch, second_page):
    """list_total_count는 5인데 두 번째 요청이 INFO-200이거나 빈 목록이면 거기서 멈추고 모은 2행을 돌려준다"""
    monkeypatch.setattr(data_loader, "ECOS_PAGE_SIZE", 2)
    first = FakeResponse(_ok([_row("20260102", "1445.0"), _row("20260105", "1450.5")], total=5))
    second = FakeResponse(NO_DATA if second_page == "no_data" else _ok([], total=5))
    calls = fake_ecos(lambda n: first if n == 1 else second)

    result = fetch_fx_rates(START, END)

    assert result["date"].tolist() == ["2026-01-02", "2026-01-05"]
    assert len(calls) == 2


def test_guard_every_page_request_uses_same_settings(fake_ecos, monkeypatch):
    """모든 페이지 요청에 REQUEST_TIMEOUT_SEC를 주고, 기간과 통계 코드는 페이지마다 같다"""
    monkeypatch.setattr(data_loader, "ECOS_PAGE_SIZE", 1)
    rows = [_row("20260102", "1445.0"), _row("20260105", "1450.5")]
    calls = fake_ecos(lambda n: FakeResponse(_ok(rows[n - 1:n], total=2)))

    fetch_fx_rates(START, END)

    assert len(calls) == 2
    for call in calls:
        assert call["kwargs"].get("timeout") == data_loader.REQUEST_TIMEOUT_SEC
        assert call["url"].rstrip("/").endswith("/731Y001/D/20260101/20260131/0000001")


def test_guard_non_dict_rows_are_skipped(fake_ecos):
    """row 목록 안에 dict가 아닌 값이 섞여 있으면 그 값만 건너뛴다"""
    fake_ecos(lambda n: FakeResponse(_ok([_row("20260102", "1445.0"), "깨진 행", None], total=3))
              if n == 1 else FakeResponse(NO_DATA))
    result = fetch_fx_rates(START, END)
    assert result["date"].tolist() == ["2026-01-02"]
