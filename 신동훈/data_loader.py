import math
import re
from datetime import datetime

import pandas as pd


ACTUALS_COLUMNS = ("quarter", "revenue_krw", "announced_date")
CSV_ENCODING = "utf-8-sig"
QUARTER_PATTERN = r"^[0-9]{4}Q[1-4]$"
DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
DATE_FORMAT = "%Y-%m-%d"


def load_actuals(filepath: str) -> pd.DataFrame:
    """분기 확정 매출 CSV를 검증하고 표준 actuals 표로 반환한다.

    Args:
        filepath: 실적 CSV 파일 경로.

    Returns:
        quarter, revenue_krw, announced_date 열을 갖는 검증된 DataFrame.

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때 발생한다.
        ValueError: CSV의 열 또는 데이터 형식이 올바르지 않거나, UTF-8로 읽을 수 없을 때 발생한다.
    """
    try:
        raw = pd.read_csv(
            filepath,
            encoding=CSV_ENCODING,
            dtype=str,
            keep_default_na=False,
            skip_blank_lines=False,
            index_col=False,
        )

    except UnicodeDecodeError:
       # 엑셀 "CSV(쉼표로 분리)" 저장 파일은 cp949라 UTF-8로 읽을 수 없다.
        # 그대로 두면 "'utf-8' codec can't decode ..."만 보여 무엇을 고칠지 알 수 없으므로 안내 문장으로 바꾼다
        raise ValueError(
           "actuals.csv 인코딩 오류: UTF-8로 저장해 주세요 (엑셀은 'CSV UTF-8(쉼표로 분리)'로 저장)"
       ) from None

    except pd.errors.EmptyDataError as exc:
        raise ValueError("필수 열 누락: quarter, revenue_krw, announced_date") from exc

    except pd.errors.ParserError as exc:
         raise ValueError(
             f"actuals.csv 형식 오류: 열 개수가 맞지 않는 줄이 있습니다 ({exc})"
         ) from exc

    raw.columns = [str(column).strip() for column in raw.columns]

    duplicated_columns = sorted(set(raw.columns[raw.columns.duplicated()])) 
    if duplicated_columns:
        raise ValueError(f"actuals.csv 열 이름 중복: {', '.join(duplicated_columns)}")

    missing_columns = [
        column for column in ACTUALS_COLUMNS if column not in raw.columns
    ]
    if missing_columns:
        raise ValueError(f"필수 열 누락: {', '.join(missing_columns)}")

    actuals = raw.loc[:, ACTUALS_COLUMNS].copy()
    actuals = actuals.map(lambda value: str(value).strip())

    non_empty = ~actuals.eq("").all(axis=1)
    actuals = actuals.loc[non_empty].copy()

    if actuals.empty:
        return actuals.astype({"revenue_krw": "float64"}).reset_index(drop=True)

    errors: list[str] = []
    revenues: list[float] = []

    for row_index, row in actuals.iterrows():
        line_number = int(row_index) + 2
        quarter = row["quarter"]
        revenue_text = row["revenue_krw"]
        announced_date = row["announced_date"]

        if re.fullmatch(QUARTER_PATTERN, quarter) is None:
            errors.append(f"{line_number}행 quarter '{quarter}'")

        try:
            revenue = float(revenue_text.replace(",", ""))
        except ValueError:
            revenue = math.nan

        revenues.append(revenue)

        if pd.isna(revenue) or not math.isfinite(revenue) or revenue <= 0:
            errors.append(f"{line_number}행 revenue_krw '{revenue_text}'")

        if re.fullmatch(DATE_PATTERN, announced_date) is None:
            errors.append(f"{line_number}행 announced_date '{announced_date}'")
        else:
            try:
                datetime.strptime(announced_date, DATE_FORMAT)
            except ValueError:
                errors.append(f"{line_number}행 announced_date '{announced_date}'")

    if errors:
        raise ValueError("actuals.csv 형식 오류: " + "; ".join(errors))

    duplicate_quarters = actuals.loc[
        actuals["quarter"].duplicated(), "quarter"
    ].drop_duplicates()
    if not duplicate_quarters.empty:
        raise ValueError(
            "actuals.csv 분기 중복: " + ", ".join(duplicate_quarters.tolist())
        )

    actuals["revenue_krw"] = revenues
    actuals = actuals.sort_values("quarter").reset_index(drop=True)

    return actuals.loc[:, ACTUALS_COLUMNS]