"""A구역(업로드와 입력 방어)이 기대는 backend 함수 테스트 (담당: 조현모).

    read_uploaded_csv  올린 CSV를 문자열 표로 읽기 (UTF-8 -> cp949 재시도, 읽을 수 없으면 한국어 ValueError)
    import_exports     정제 후 저장 표와 합쳐 저장 (collected_at이 없으면 올린 날짜로 채움)

data_dir는 모두 tmp_path로 넘겨 실제 data/exports.csv를 건드리지 않는다.
"""

import io
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

import backend

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "exports_normal.csv"
TODAY = date(2026, 11, 16)


@pytest.fixture
def sample_raw() -> pd.DataFrame:
    return pd.read_csv(SAMPLE, dtype=str, keep_default_na=False)


def _csv_bytes(table: pd.DataFrame, encoding: str = "utf-8") -> io.BytesIO:
    return io.BytesIO(table.to_csv(index=False).encode(encoding, errors="replace"))


# =============================================================================
# import_exports: 필수 열 누락 메시지
# =============================================================================
def test_missing_column_message_lists_only_uploaded_columns(sample_raw, tmp_path):
    """collected_at 없이 올린 CSV의 '원자료 열'에 backend가 붙인 collected_at이 섞이지 않아야 한다."""
    raw = sample_raw.drop(columns=["collected_at", "expUsdAmt"])

    with pytest.raises(ValueError) as excinfo:
        backend.import_exports(raw, data_dir=tmp_path, today=TODAY)

    message = str(excinfo.value)
    assert message.startswith("필수 열 누락: export_usd")
    found = message.split("(원자료 열: ", 1)[1].rstrip(")").split(", ")
    assert found == list(raw.columns)
    assert "collected_at" not in found
    assert not (tmp_path / "exports.csv").exists()  # 실패한 파일은 저장하지 않는다


def test_missing_column_message_keeps_uploaded_collected_at(sample_raw, tmp_path):
    """사용자가 collected_at을 직접 올렸다면 그 열은 메시지에 그대로 나와야 한다."""
    raw = sample_raw.drop(columns=["expUsdAmt"])

    with pytest.raises(ValueError, match=r"원자료 열: .*collected_at"):
        backend.import_exports(raw, data_dir=tmp_path, today=TODAY)


# =============================================================================
# import_exports: 고친 뒤에도 정제, 저장 결과가 그대로인지
# =============================================================================
def test_without_collected_at_fills_upload_date(sample_raw, tmp_path):
    raw = sample_raw.drop(columns=["collected_at"])

    result = backend.import_exports(raw, data_dir=tmp_path, today=TODAY)

    exports = result["exports"]
    assert (result["raw_rows"], result["clean_rows"], result["added"]) == (953, 68, 68)
    assert list(exports.columns) == ["ym", "region", "hs_code", "export_usd", "collected_at"]
    assert set(exports["collected_at"]) == {"2026-11-16"}
    assert set(exports["region"]) == {"이천시", "청주시"}
    assert exports["export_usd"].dtype == "float64"
    saved = backend.read_exports(tmp_path)
    assert len(saved) == 68 and set(saved["collected_at"]) == {"2026-11-16"}


def test_same_upload_twice_adds_nothing(sample_raw, tmp_path):
    first = backend.import_exports(sample_raw, data_dir=tmp_path, today=TODAY)
    second = backend.import_exports(sample_raw, data_dir=tmp_path, today=TODAY)

    assert (first["added"], first["updated"]) == (68, 0)
    assert (second["added"], second["updated"]) == (0, 68)
    assert len(second["exports"]) == 68


def test_header_only_csv_returns_zero_clean_rows(sample_raw, tmp_path):
    """열 이름만 있는 파일은 오류가 아니라 0행 (화면에서는 st.warning으로 알린다)."""
    raw = backend.read_uploaded_csv(_csv_bytes(sample_raw.head(0)))

    result = backend.import_exports(raw, data_dir=tmp_path, today=TODAY)

    assert (result["raw_rows"], result["clean_rows"], result["added"], result["updated"]) == (0, 0, 0, 0)


# =============================================================================
# read_uploaded_csv: 인코딩과 읽을 수 없는 파일
# =============================================================================
def test_cp949_file_reads_same_as_utf8(sample_raw):
    utf8 = backend.read_uploaded_csv(_csv_bytes(sample_raw, "utf-8"))
    cp949 = backend.read_uploaded_csv(_csv_bytes(sample_raw, "cp949"))

    pd.testing.assert_frame_equal(utf8, cp949)
    assert "경기도 이천시" in set(cp949["sggNm"])


def test_empty_file_raises_korean_value_error():
    with pytest.raises(ValueError, match="빈 파일"):
        backend.read_uploaded_csv(io.BytesIO(b""))


def test_utf16_file_raises_korean_value_error(sample_raw):
    with pytest.raises(ValueError, match="인코딩"):
        backend.read_uploaded_csv(_csv_bytes(sample_raw.head(5), "utf-16"))


def test_unreadable_errors_are_still_value_error_subclasses(sample_raw):
    """app.py는 except ValueError만 잡으므로, 바꾼 메시지도 ValueError여야 한다."""
    for payload in (b"", sample_raw.head(5).to_csv(index=False).encode("utf-16")):
        with pytest.raises(ValueError):
            backend.read_uploaded_csv(io.BytesIO(payload))


def test_upload_with_existing_and_new_month_counts_both(tmp_path):
    first = pd.DataFrame([
        {"ym": "2026-09", "region": "이천시", "hs_code": "854232", "export_usd": "100", "collected_at": "2026-10-01"},
        {"ym": "2026-09", "region": "청주시", "hs_code": "854232", "export_usd": "200", "collected_at": "2026-10-01"},
    ])
    second = pd.DataFrame([
        {"ym": "2026-09", "region": "이천시", "hs_code": "854232", "export_usd": "300", "collected_at": "2026-11-01"},
        {"ym": "2026-10", "region": "청주시", "hs_code": "854232", "export_usd": "400", "collected_at": "2026-11-01"},
    ])

    backend.import_exports(first, data_dir=tmp_path, today=TODAY)
    result = backend.import_exports(second, data_dir=tmp_path, today=TODAY)

    assert (result["clean_rows"], result["added"], result["updated"]) == (2, 1, 1)
    assert len(result["exports"]) == 3
    replaced = result["exports"].loc[
        (result["exports"]["ym"] == "2026-09") & (result["exports"]["region"] == "이천시"),
        "export_usd",
    ]
    assert replaced.tolist() == [300.0]


def test_exports_chart_long_returns_recent_month_region_values():
    exports = pd.DataFrame([
        {"ym": "2026-08", "region": "이천시", "export_usd": 100_000_000.0},
        {"ym": "2026-09", "region": "이천시", "export_usd": 123_456_789.0},
        {"ym": "2026-09", "region": "청주시", "export_usd": 200_000_000.0},
        {"ym": "2026-09", "region": "용인시", "export_usd": 300_000_000.0},
    ])

    chart = backend.exports_chart_long(exports, last_months=1)

    assert list(chart.columns) == ["ym", "region", "export_100m_usd"]
    assert chart["ym"].tolist() == ["2026-09", "2026-09"]
    assert chart["region"].tolist() == ["이천시", "청주시"]
    assert chart["export_100m_usd"].tolist() == [1.23456789, 2.0]
