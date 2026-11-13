import xml.etree.ElementTree as ET

import pandas as pd
import pytest

import data_loader


def test_validate_months_rejects_invalid_values():
    with pytest.raises(ValueError, match="월 형식 오류"):
        data_loader._validate_months("2026-13", "2026-13")

    with pytest.raises(ValueError, match="시작월이 끝월보다 늦습니다"):
        data_loader._validate_months("2026-02", "2026-01")


def test_month_chunks_split_long_period():
    assert data_loader._month_chunks("2026-01", "2027-02") == [
        ("202601", "202612"),
        ("202701", "202702"),
    ]


def test_parse_customs_page_returns_rows_and_total_count():
    root = ET.fromstring(
        """
        <response>
          <header><resultCode>00</resultCode></header>
          <body>
            <totalCount>1</totalCount>
            <items>
              <item><region>이천시</region><amount>100</amount></item>
            </items>
          </body>
        </response>
        """
    )

    rows, total_count = data_loader._parse_customs_page(root, "이천시")

    assert rows == [{"region": "이천시", "amount": "100"}]
    assert total_count == 1


def test_parse_customs_page_handles_no_data():
    root = ET.fromstring(
        "<response><header><resultCode>03</resultCode></header></response>"
    )

    assert data_loader._parse_customs_page(root, "청주시") == ([], 0)


def test_fetch_regional_exports_uses_mocked_rows(monkeypatch):
    monkeypatch.setenv(data_loader.CUSTOMS_API_KEY_ENV, "test-key")
    calls = []

    def fake_fetch(api_key, region, sido_code, start_ym, end_ym):
        calls.append((api_key, region, sido_code, start_ym, end_ym))
        return [{"region": region, "amount": "100"}]

    monkeypatch.setattr(data_loader, "_fetch_customs_rows", fake_fetch)

    result = data_loader.fetch_regional_exports("2026-01", "2026-01")

    assert len(calls) == 2
    assert {call[1] for call in calls} == {"이천시", "청주시"}
    assert all(call[0] == "test-key" for call in calls)
    assert list(result.columns) == ["region", "amount", "collected_at"]
    assert len(result) == 2
    assert result["collected_at"].notna().all()


def test_to_raw_exports_table_preserves_fields():
    result = data_loader._to_raw_exports_table(
        [{"region": "이천시", "amount": "100"}], "2026-11-13"
    )

    pd.testing.assert_frame_equal(
        result,
        pd.DataFrame(
            {
                "region": ["이천시"],
                "amount": ["100"],
                "collected_at": ["2026-11-13"],
            }
        ),
    )


def test_validate_months_rejects_non_string():
    with pytest.raises(ValueError, match="월 형식 오류"):
        data_loader._validate_months(202601, "2026-01")


def test_validate_months_rejects_full_width_digits():
    with pytest.raises(ValueError, match="월 형식 오류"):
        data_loader._validate_months("２０２６-０１", "2026-01")


def test_get_customs_api_key_rejects_missing_key(monkeypatch):
    monkeypatch.delenv(data_loader.CUSTOMS_API_KEY_ENV, raising=False)

    with pytest.raises(RuntimeError, match="관세청 API 키가 없습니다"):
        data_loader._get_customs_api_key()


def test_get_customs_api_key_rejects_blank_key(monkeypatch):
    monkeypatch.setenv(data_loader.CUSTOMS_API_KEY_ENV, "  ")

    with pytest.raises(RuntimeError, match="관세청 API 키가 없습니다"):
        data_loader._get_customs_api_key()


def test_fetch_regional_exports_splits_each_region_into_12_month_chunks(monkeypatch):
    monkeypatch.setenv(data_loader.CUSTOMS_API_KEY_ENV, "test-key")
    calls = []

    def fake_fetch(api_key, region, sido_code, start_ym, end_ym):
        calls.append((api_key, region, sido_code, start_ym, end_ym))
        return []

    monkeypatch.setattr(data_loader, "_fetch_customs_rows", fake_fetch)

    result = data_loader.fetch_regional_exports("2026-01", "2027-02")

    assert result.empty
    assert len(calls) == 4
    assert [(call[1], call[2], call[3], call[4]) for call in calls] == [
        ("이천시", "41", "202601", "202612"),
        ("이천시", "41", "202701", "202702"),
        ("청주시", "43", "202601", "202612"),
        ("청주시", "43", "202701", "202702"),
    ]


def test_fetch_regional_exports_deduplicates_same_sido(monkeypatch):
    monkeypatch.setenv(data_loader.CUSTOMS_API_KEY_ENV, "test-key")
    calls = []
    monkeypatch.setattr(
        data_loader,
        "CUSTOMS_REGION_SIDO_CODES",
        {"이천시": "41", "청주시": "41"},
    )

    def fake_fetch(api_key, region, sido_code, start_ym, end_ym):
        calls.append((region, sido_code))
        return []

    monkeypatch.setattr(data_loader, "_fetch_customs_rows", fake_fetch)

    data_loader.fetch_regional_exports("2026-01", "2026-01")

    assert calls == [("이천시", "41")]


def test_request_customs_xml_passes_expected_url_and_parameters(monkeypatch):
    captured = {}

    class FakeResponse:
        content = b"<response />"
        status_code = 200

        def raise_for_status(self):
            return None

    def fake_get(url, params, timeout):
        captured.update(url=url, params=params, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr(data_loader.requests, "get", fake_get)

    root = data_loader._request_customs_xml(
        {
            "serviceKey": "decoded-key",
            "strtYymm": "202601",
            "endYymm": "202612",
            "HsSgn": "854232",
            "sidoCd": "41",
        },
        "이천시",
    )

    assert root.tag == "response"
    assert captured == {
        "url": data_loader.CUSTOMS_API_URL,
        "params": {
            "serviceKey": "decoded-key",
            "strtYymm": "202601",
            "endYymm": "202612",
            "HsSgn": "854232",
            "sidoCd": "41",
        },
        "timeout": data_loader.CUSTOMS_REQUEST_TIMEOUT_SEC,
    }


def test_request_customs_xml_hides_request_exception_details(monkeypatch):
    def fake_get(*args, **kwargs):
        raise data_loader.requests.RequestException("secret-key in URL")

    monkeypatch.setattr(data_loader.requests, "get", fake_get)

    with pytest.raises(RuntimeError) as exc_info:
        data_loader._request_customs_xml({}, "이천시")

    assert str(exc_info.value) == "관세청 API 호출 실패: 이천시, RequestException"
    assert "secret-key" not in str(exc_info.value)


def test_request_customs_xml_reports_http_status_without_url(monkeypatch):
    class FakeResponse:
        content = b""
        status_code = 403

        def raise_for_status(self):
            raise data_loader.requests.HTTPError("https://example.test?serviceKey=secret")

    monkeypatch.setattr(
        data_loader.requests, "get", lambda *args, **kwargs: FakeResponse()
    )

    with pytest.raises(RuntimeError) as exc_info:
        data_loader._request_customs_xml({}, "청주시")

    assert str(exc_info.value) == "관세청 API 호출 실패: 청주시, HTTP 403"
    assert "secret" not in str(exc_info.value)


def test_request_customs_xml_rejects_non_xml_response(monkeypatch):
    class FakeResponse:
        content = b"not xml"
        status_code = 200

        def raise_for_status(self):
            return None

    monkeypatch.setattr(
        data_loader.requests, "get", lambda *args, **kwargs: FakeResponse()
    )

    with pytest.raises(RuntimeError, match="응답 형식 오류"):
        data_loader._request_customs_xml({}, "이천시")


def test_parse_customs_page_reports_api_error_code():
    root = ET.fromstring(
        """
        <response>
          <header><resultCode>30</resultCode><resultMsg>Unauthorized</resultMsg></header>
        </response>
        """
    )

    with pytest.raises(RuntimeError, match="관세청 API 호출 실패: 이천시, 30 Unauthorized"):
        data_loader._parse_customs_page(root, "이천시")


def test_fetch_customs_rows_requests_next_page_until_total_count(monkeypatch):
    calls = []
    responses = [
        (
            [{"year": "2026"}],
            2,
        ),
        (
            [{"year": "2027"}],
            2,
        ),
    ]

    def fake_request(params, region):
        calls.append(params.copy())
        return ET.Element("response")

    monkeypatch.setattr(data_loader, "_request_customs_xml", fake_request)
    monkeypatch.setattr(data_loader, "_parse_customs_page", lambda root, region: responses.pop(0))

    rows = data_loader._fetch_customs_rows(
        "decoded-key", "이천시", "41", "202601", "202612"
    )

    assert rows == [{"year": "2026"}, {"year": "2027"}]
    assert [call["pageNo"] for call in calls] == [1, 2]
    assert all(call["serviceKey"] == "decoded-key" for call in calls)