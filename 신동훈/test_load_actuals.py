"""load_actuals 테스트 (L01~L12).

구현 가이드 1.1절 권장 항목(정상 파일, 필수 열 누락, quarter 형식 오류, 분기 중복)에 경계·예외 케이스를 더했다.
각 테스트는 pytest의 tmp_path에 CSV를 직접 써서 사용한다(저장소에 파일을 남기지 않음).
매출값은 공통입력 G의 더미 값이다.

"""

import pandas as pd
import pytest

from data_loader import load_actuals

# 공통 파일 G: 일부러 정렬하지 않았고, 2025Q4 매출은 천 단위 쉼표 표기
HEADER = "quarter,revenue_krw,announced_date"
ROW_Q1 = "2025Q1,19600000000000,2025-04-24"
G = "\n".join([
    HEADER,
    "2025Q3,21000000000000,2025-10-23",
    ROW_Q1,
    '2025Q4,"22,400,000,000,000",2026-01-22',
    "2025Q2,21000000000000,2025-07-24",
]) + "\n"

EXPECTED_COLUMNS = ["quarter", "revenue_krw", "announced_date"]
EXPECTED_QUARTERS = ["2025Q1", "2025Q2", "2025Q3", "2025Q4"]
EXPECTED_REVENUES = [1.96e13, 2.1e13, 2.1e13, 2.24e13]
EXPECTED_DATES = ["2025-04-24", "2025-07-24", "2025-10-23", "2026-01-22"]


def _write(tmp_path, text: str, encoding: str = "utf-8") -> str:
    """tmp_path에 actuals.csv를 쓰고 경로 문자열을 돌려준다."""
    path = tmp_path / "actuals.csv"
    path.write_text(text, encoding=encoding)
    return str(path)


def _g_with_q1_row(new_row: str) -> str:
    """G에서 2025Q1 행만 new_row로 바꾼 CSV 내용을 돌려준다."""
    return G.replace(ROW_Q1, new_row)


# ---------------------------------------------------------------- 정상

def test_L01_normal_file(tmp_path):
    """L01 정상: 열 순서·정렬·타입·index·결측 없음."""
    df = load_actuals(_write(tmp_path, G))

    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == EXPECTED_COLUMNS
    assert len(df) == 4
    assert list(df.index) == [0, 1, 2, 3]

    assert df["quarter"].tolist() == EXPECTED_QUARTERS
    assert df["revenue_krw"].tolist() == pytest.approx(EXPECTED_REVENUES, rel=1e-6)
    assert df["announced_date"].tolist() == EXPECTED_DATES

    assert str(df["revenue_krw"].dtype) == "float64"
    assert all(isinstance(v, str) for v in df["quarter"])
    assert all(isinstance(v, str) for v in df["announced_date"])
    assert not df.isna().any().any()


def test_L02_messy_but_valid_file(tmp_path):
    """L02 정상: BOM·앞뒤 공백·memo 열·쉼표·지수 표기가 섞여도 L01과 같은 표."""
    messy = "\n".join([
        " quarter ,revenue_krw , announced_date,memo",
        " 2025Q3 ,2.1E+13,2025-10-23,",
        '2025Q1,"19,600,000,000,000", 2025-04-24 ,잠정치 대조 완료',
        "2025Q4,22400000000000,2026-01-22,",
        "2025Q2, 21000000000000 ,2025-07-24,",
    ]) + "\n"
    expected = load_actuals(_write(tmp_path, G))

    messy_dir = tmp_path / "messy"
    messy_dir.mkdir()
    df = load_actuals(_write(messy_dir, messy, encoding="utf-8-sig"))

    pd.testing.assert_frame_equal(df, expected)


# ---------------------------------------------------------------- 경계

def test_L03_header_only_returns_empty_table(tmp_path):
    """L03 경계: 열 이름 줄만 있으면 예외 없이 열 3개짜리 빈 표."""
    df = load_actuals(_write(tmp_path, HEADER + "\n"))

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 0
    assert list(df.columns) == EXPECTED_COLUMNS


def test_L04_blank_row_is_ignored(tmp_path):
    """L04 경계: 세 칸이 모두 빈 ',,' 줄은 무시한다."""
    with_blank = G.replace(ROW_Q1, ROW_Q1 + "\n,,")
    expected = load_actuals(_write(tmp_path, G))

    blank_dir = tmp_path / "blank"
    blank_dir.mkdir()
    df = load_actuals(_write(blank_dir, with_blank))

    pd.testing.assert_frame_equal(df, expected)


# ---------------------------------------------------------------- 예외

@pytest.mark.parametrize(
    "content, missing",
    [
        ("quarter,announced_date\n2025Q1,2025-04-24\n", ["revenue_krw"]),
        ("revenue_krw\n19600000000000\n", ["quarter", "announced_date"]),
    ],
    ids=["no_revenue_krw", "no_quarter_and_date"],
)
def test_L05_missing_required_columns(tmp_path, content, missing):
    """L05 예외: 필수 열이 없으면 ValueError, 없는 열 이름을 모두 알린다."""
    with pytest.raises(ValueError) as exc_info:
        load_actuals(_write(tmp_path, content))

    message = str(exc_info.value)
    assert "필수 열 누락" in message
    for col in missing:
        assert col in message


def test_L06_zero_byte_file(tmp_path):
    """L06 예외: 0바이트 파일은 EmptyDataError가 아니라 ValueError(필수 열 누락)."""
    with pytest.raises(ValueError) as exc_info:
        load_actuals(_write(tmp_path, ""))

    assert "필수 열 누락" in str(exc_info.value)


@pytest.mark.parametrize("bad_quarter", ["2025-Q1", "2025Q5", "25Q1", "2025q1"])
def test_L07_invalid_quarter(tmp_path, bad_quarter):
    """L07 예외: quarter가 YYYYQn(n=1~4)이 아니면 ValueError, 원래 값을 보여준다."""
    content = _g_with_q1_row(f"{bad_quarter},19600000000000,2025-04-24")

    with pytest.raises(ValueError) as exc_info:
        load_actuals(_write(tmp_path, content))

    message = str(exc_info.value)
    assert "형식 오류" in message
    assert bad_quarter in message


@pytest.mark.parametrize(
    "bad_revenue",
    ["N/A", "", "0", "-1", "inf", "abc"],
    ids=["NA", "blank", "zero", "negative", "inf", "text"],
)
def test_L08_invalid_revenue(tmp_path, bad_revenue):
    """L08 예외: 매출이 숫자가 아니거나 0 이하이거나 유한하지 않으면 ValueError."""
    content = _g_with_q1_row(f"2025Q1,{bad_revenue},2025-04-24")

    with pytest.raises(ValueError) as exc_info:
        load_actuals(_write(tmp_path, content))

    message = str(exc_info.value)
    assert "형식 오류" in message
    assert "revenue_krw" in message


@pytest.mark.parametrize(
    "bad_date",
    ["2025/04/24", "2025-4-24", "2025-02-30", ""],
    ids=["slash", "one_digit_month", "not_a_real_date", "blank"],
)
def test_L09_invalid_announced_date(tmp_path, bad_date):
    """L09 예외: 날짜가 YYYY-MM-DD 모양이 아니거나 달력에 없으면 ValueError."""
    content = _g_with_q1_row(f"2025Q1,19600000000000,{bad_date}")

    with pytest.raises(ValueError) as exc_info:
        load_actuals(_write(tmp_path, content))

    message = str(exc_info.value)
    assert "형식 오류" in message
    assert "announced_date" in message


def test_L10_duplicate_quarter(tmp_path):
    """L10 예외: 같은 quarter가 두 번 이상이면 ValueError(분기 중복)."""
    content = G + "2025Q1,19700000000000,2025-04-25\n"

    with pytest.raises(ValueError) as exc_info:
        load_actuals(_write(tmp_path, content))

    message = str(exc_info.value)
    assert "분기 중복" in message
    assert "2025Q1" in message


def test_L11_all_format_errors_reported_at_once(tmp_path):
    """L11 예외: 형식 오류가 여러 행이면 한 번의 ValueError에 줄 번호를 모두 담는다."""
    content = "\n".join([
        HEADER,                                # 1행
        "2025Q1,19600000000000,2025-04-24",    # 2행 정상
        "2025-Q2,21000000000000,2025-07-24",   # 3행 quarter 오류
        "2025Q3,21000000000000,2025-10-23",    # 4행 정상
        "2025Q4,N/A,2026-01-22",               # 5행 revenue_krw 오류
    ]) + "\n"

    with pytest.raises(ValueError) as exc_info:
        load_actuals(_write(tmp_path, content))

    message = str(exc_info.value)
    assert "형식 오류" in message
    assert "3행" in message
    assert "5행" in message


def test_L12_file_not_found(tmp_path):
    """L12 예외: 없는 경로면 FileNotFoundError가 그대로 난다."""
    with pytest.raises(FileNotFoundError):
        load_actuals(str(tmp_path / "없음.csv"))