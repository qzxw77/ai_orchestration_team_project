"""fetch_fx_rates 테스트 (정상 2, 경계 2, 예외 4)

실제 ECOS API를 부르지 않는다. requests.get을 가짜 함수로 바꿔 끼우고,
API 키도 가짜 값(TEST_KEY)을 환경변수로 넣는다. 환율 값은 모두 가상의 더미 값이다.

가짜 응답 형식 (ECOS StatisticSearch JSON)
- 성공: {"StatisticSearch": {"list_total_count": N, "row": [{"TIME": "YYYYMMDD", "DATA_VALUE": "1445.0"}, ...]}}
- 결과 코드: {"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}}
요청 URL: {ECOS_BASE_URL}/{키}/json/kr/{시작 번호}/{끝 번호}/731Y001/D/{시작일 YYYYMMDD}/{끝일 YYYYMMDD}/0000001
"""

import traceback

import pandas as pd
import pytest
import requests

import data_loader
from data_loader import fetch_fx_rates

TEST_KEY = "TESTKEY0123456789"
START, END = "2026-01-01", "2026-01-31"


class FakeResponse:
    """requests.Response 대역. 코드가 쓰는 status_code, raise_for_status(), json()만 흉내 낸다."""

    def __init__(self, payload=None, status_code=200, url="", bad_json=False):
        self.payload = payload
        self.status_code = status_code
        self.url = url
        self.bad_json = bad_json

    def raise_for_status(self):
        if self.status_code >= 400:
            # 실제 requests처럼 예외 문자열에 요청 URL(= 키 포함)이 들어간다
            raise requests.HTTPError(f"{self.status_code} Server Error for url: {self.url}")

    def json(self):
        if self.bad_json:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self.payload


def _rows(*pairs):
    """(TIME, DATA_VALUE) 쌍을 ECOS row 목록으로 만든다. 실제 응답처럼 쓰지 않는 키도 섞는다."""
    return [{"STAT_CODE": "731Y001", "ITEM_NAME1": "원/미국달러(매매기준율)", "TIME": t, "DATA_VALUE": v}
            for t, v in pairs]


def _ok(rows, total=None):
    """성공 응답. total을 주지 않으면 rows 개수를 list_total_count로 쓴다."""
    return {"StatisticSearch": {"list_total_count": len(rows) if total is None else total, "row": rows}}


def _install(monkeypatch, calls, responder):
    """requests.get을 가짜로 바꾼다. responder(url)는 FakeResponse를 돌려주거나 예외를 낸다."""

    def fake_get(url, *args, **kwargs):
        calls.append({"url": url, "kwargs": kwargs})
        return responder(url)

    monkeypatch.setattr(data_loader.requests, "get", fake_get)


def _range_of(url):
    """요청 URL에서 (시작 번호, 끝 번호)를 꺼낸다."""
    parts = url.rstrip("/").split("/")
    return parts[-7], parts[-6]


@pytest.fixture
def calls(monkeypatch):
    """가짜 키를 넣고, requests.get 호출 기록을 담을 목록을 돌려준다."""
    monkeypatch.setenv("ECOS_API_KEY", TEST_KEY)
    return []


# ---------- 정상 ----------

def test_normal_converts_sorts_and_builds_request(monkeypatch, calls):
    """정상 1: 날짜 역순 3행 -> date "YYYY-MM-DD" 오름차순, usdkrw float, 열 2개, 행 번호 0부터
    요청은 1번, URL에 키와 통계표/주기/기간/항목 코드가 들어가고 timeout을 준다"""
    rows = _rows(("20260106", "1452.25"), ("20260102", "1445.0"), ("20260105", "1450.5"))
    _install(monkeypatch, calls, lambda url: FakeResponse(_ok(rows), url=url))

    result = fetch_fx_rates(START, END)

    assert list(result.columns) == ["date", "usdkrw"]
    assert result["date"].tolist() == ["2026-01-02", "2026-01-05", "2026-01-06"]
    assert all(isinstance(d, str) for d in result["date"])
    assert result["usdkrw"].tolist() == pytest.approx([1445.0, 1450.5, 1452.25])
    assert pd.api.types.is_float_dtype(result["usdkrw"])
    assert result.index.tolist() == [0, 1, 2]

    assert len(calls) == 1
    url = calls[0]["url"]
    assert url.startswith("https://ecos.bok.or.kr/api/StatisticSearch/")
    assert f"/StatisticSearch/{TEST_KEY}/json/kr/1/" in url
    assert url.rstrip("/").endswith("/731Y001/D/20260101/20260131/0000001")
    assert calls[0]["kwargs"].get("timeout"), "requests.get에 timeout을 줘야 한다"


def test_normal_reads_all_pages(monkeypatch, calls):
    """정상 2: 한 번에 2행씩(ECOS_PAGE_SIZE=2) 받으면 전체 5행을 1~2, 3~4, 5~6 세 번에 나눠 모두 모은다"""
    monkeypatch.setattr(data_loader, "ECOS_PAGE_SIZE", 2)
    all_rows = _rows(
        ("20260102", "1445.0"),
        ("20260105", "1450.5"),
        ("20260106", "1452.25"),
        ("20260107", "1449.0"),
        ("20260108", "1447.75"),
    )

    def responder(url):
        start, end = (int(n) for n in _range_of(url))
        return FakeResponse(_ok(all_rows[start - 1:end], total=len(all_rows)), url=url)

    _install(monkeypatch, calls, responder)

    result = fetch_fx_rates(START, END)

    assert result["date"].tolist() == [
        "2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08",
    ]
    assert [_range_of(c["url"]) for c in calls] == [("1", "2"), ("3", "4"), ("5", "6")]


# ---------- 경계 ----------

def test_boundary_drops_bad_rows_and_keeps_last_duplicate(monkeypatch, calls):
    """경계 1: 값이 비었거나 숫자가 아니거나 0 이하인 행, 없는 날짜(20260230) 행은 지운다.
    같은 날짜가 두 번 오면 응답에서 나중에 온 행을 남긴다. 빠진 날(주말 등)을 채우지 않는다."""
    rows = _rows(
        ("20260102", "1445.0"),
        ("20260105", ""),        # 빈 값
        ("20260106", "-"),       # 숫자 아님
        ("20260107", None),      # null
        ("20260108", "0"),       # 0 이하
        ("20260112", "-3.5"),    # 0 이하
        ("20260230", "1450.0"),  # 달력에 없는 날짜
        ("20260109", "1451.0"),
        ("20260109", "1452.5"),  # 같은 날짜, 나중 값이 남는다
    )
    _install(monkeypatch, calls, lambda url: FakeResponse(_ok(rows), url=url))

    result = fetch_fx_rates(START, END)

    assert result["date"].tolist() == ["2026-01-02", "2026-01-09"]
    assert result["usdkrw"].tolist() == pytest.approx([1445.0, 1452.5])
    assert result.index.tolist() == [0, 1]


def test_boundary_no_data_returns_empty_table(monkeypatch, calls):
    """경계 2: 기간 안에 값이 없어 ECOS가 INFO-200을 주면 예외 없이 열 2개짜리 0행 표"""
    payload = {"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}}
    _install(monkeypatch, calls, lambda url: FakeResponse(payload, url=url))

    result = fetch_fx_rates("2026-01-03", "2026-01-04")

    assert list(result.columns) == ["date", "usdkrw"]
    assert len(result) == 0


# ---------- 예외 ----------

@pytest.mark.parametrize("key", [None, "   "], ids=["no_key", "blank_key"])
def test_exception_missing_api_key(monkeypatch, key):
    """예외 1: ECOS_API_KEY가 없거나 공백뿐이면 RuntimeError, ECOS를 부르지 않는다"""
    calls = []
    _install(monkeypatch, calls, lambda url: FakeResponse(_ok([]), url=url))
    if key is None:
        monkeypatch.delenv("ECOS_API_KEY", raising=False)
    else:
        monkeypatch.setenv("ECOS_API_KEY", key)

    with pytest.raises(RuntimeError, match="ECOS API 키가 없습니다"):
        fetch_fx_rates(START, END)
    assert calls == []


@pytest.mark.parametrize("failure", ["connection", "timeout", "http500"])
def test_exception_request_failure_hides_key(monkeypatch, calls, failure):
    """예외 2: 연결 오류, 시간 초과, HTTP 500 -> "ECOS API 호출 실패"로 시작하는 RuntimeError
    requests 예외 문자열에는 키가 든 URL이 들어 있으므로, 오류 메시지와 traceback 어디에도 키가 나오면 안 된다"""

    def responder(url):
        if failure == "connection":
            raise requests.ConnectionError(f"Max retries exceeded with url: {url}")
        if failure == "timeout":
            raise requests.Timeout(f"Read timed out. (url: {url})")
        return FakeResponse(status_code=500, url=url)

    _install(monkeypatch, calls, responder)

    with pytest.raises(RuntimeError) as excinfo:
        fetch_fx_rates(START, END)

    message = str(excinfo.value)
    assert message.startswith("ECOS API 호출 실패")
    if failure == "http500":
        assert "500" in message
    shown = "".join(traceback.format_exception(excinfo.value))
    assert TEST_KEY not in shown, "오류 메시지나 traceback에 API 키가 노출됨"


@pytest.mark.parametrize(
    "response, expected",
    [
        (FakeResponse({"RESULT": {"CODE": "INFO-100", "MESSAGE": "인증키가 유효하지 않습니다."}}), "INFO-100"),
        (FakeResponse({"RESULT": {"CODE": "ERROR-602", "MESSAGE": "과도한 OpenAPI호출로 이용이 제한되었습니다."}}),
         "ERROR-602"),
        (FakeResponse({"unexpected": {}}), "응답 형식"),
        (FakeResponse(bad_json=True), "응답 형식"),
    ],
    ids=["info100_not_no_data", "error602", "unknown_shape", "not_json"],
)
def test_exception_result_code_or_bad_response(monkeypatch, calls, response, expected):
    """예외 3: INFO-200이 아닌 결과 코드(INFO로 시작해도 오류일 수 있음)는 RuntimeError,
    StatisticSearch도 RESULT도 없거나 JSON이 아닌 응답도 RuntimeError"""
    _install(monkeypatch, calls, lambda url: response)

    with pytest.raises(RuntimeError) as excinfo:
        fetch_fx_rates(START, END)

    assert str(excinfo.value).startswith("ECOS API 호출 실패")
    assert expected in str(excinfo.value)


@pytest.mark.parametrize(
    "start, end",
    [
        ("2026-13-01", "2026-12-31"),  # 없는 달
        ("2026-02-30", "2026-03-31"),  # 없는 날
        ("2026/01/01", "2026-01-31"),  # 구분자가 다름
        ("20260101", "20260131"),      # ECOS 형식을 그대로 넣음
        ("2026-1-01", "2026-01-31"),   # 두 자리가 아님 (strptime만 쓰면 통과해 버린다)
        ("2026-02-01", "2026-01-31"),  # 시작일이 끝일보다 뒤
    ],
)
def test_exception_invalid_dates(monkeypatch, calls, start, end):
    """예외 4: 날짜 인자가 "YYYY-MM-DD" 실제 날짜가 아니거나 시작일 > 끝일이면 ValueError, ECOS를 부르지 않는다"""
    _install(monkeypatch, calls, lambda url: FakeResponse(_ok([]), url=url))

    with pytest.raises(ValueError):
        fetch_fx_rates(start, end)
    assert calls == []
