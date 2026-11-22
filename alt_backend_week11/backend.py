"""알트(ALT) SK하이닉스 분기 매출 나우캐스팅: 백엔드 통합 파일 (10주차의 main.py에서 이름만 바꿈).

    python backend.py                    수출, 환율을 API로 갱신(이어 받기)한 뒤 자료가 있는 가장 최근 분기를 예측
    python backend.py --check-api        요청 2번으로 키와 응답 형식만 확인 (저장 안 함)
    python backend.py --quarter 2026Q3   대상 분기 지정
    python backend.py --no-refresh       API를 부르지 않고 data/에 저장된 자료로만 예측
    python backend.py --full-refresh     저장된 자료와 상관없이 처음부터 다시 수집

필요한 것: .env의 CUSTOMS_API_KEY, ECOS_API_KEY (ANTHROPIC_API_KEY는 선택, 없으면 mock 응답), data/actuals.csv.
아래 단계 함수는 화면에 출력하지 않고 결과만 돌려주므로 Streamlit app.py가 `import backend`로 그대로 불러 쓴다.
    refresh_data, check_api, run_forecast, read_exports, read_uploaded_csv, import_exports,
    exports_chart_table, list_target_quarters, default_target_quarter
    quarterly_display_table, history_display_table, exports_display_table (표시용 표: 억 달러, 조 원 단위 문자열)
계산과 CSV는 원, 달러 단위 숫자 그대로 두고, 단위 변환과 자릿수 표시는 표시용 표와 출력에서만 한다.
"""

import argparse
import logging
import os
from datetime import date
from pathlib import Path

import pandas as pd

from hynix_nowcast import data_loader, forecaster, llm_module, preprocess

DEFAULT_DATA_DIR = Path(os.getenv("ALT_DATA_DIR") or Path(__file__).resolve().parent / "data")
# actuals.csv가 2024Q1부터라 그 전 수출, 환율은 계산에 쓰이지 않는다. 더 앞 분기를 볼 때만 앞당긴다
COLLECT_START_YM = "2024-01"
COLLECT_START_DATE = "2024-01-01"
# 저장된 자료가 있으면 마지막 달의 몇 개월 전부터 다시 받는다 (관세청이 매월 15일경 전월까지 자료를 정정함)
REFRESH_OVERLAP_MONTHS = 3
DEFAULT_ANOMALY_THRESHOLD = 2.0
CHART_MONTHS = 25
USD_PER_100M = 1e8
KRW_PER_TRILLION = 1e12
DISCLAIMER = "이 결과는 공개 통계로 계산한 참고용 추정치이며 투자 권유가 아닙니다."

EXPORTS_KEY_COLUMNS = list(preprocess.EXPORTS_KEY_COLUMNS)
FORECASTS_COLUMNS = (
    "quarter", "as_of", "estimate_krw", "lower_krw", "upper_krw",
    "qoq_change_pct", "ratio_used", "months_available", "status",
)
FORECASTS_FLOAT_COLUMNS = ("estimate_krw", "lower_krw", "upper_krw", "qoq_change_pct", "ratio_used")
# 숫자로 읽히면 "854232"와 854232가 다른 키가 되므로 문자열로 읽는다
STRING_COLUMNS = ("ym", "region", "hs_code", "date", "quarter", "as_of", "collected_at", "announced_date")


# =============================================================================
# 단계 함수 (화면 출력 없음)
# =============================================================================
def refresh_data(data_dir: Path = DEFAULT_DATA_DIR, today: date | None = None, full: bool = False) -> dict:
    """[데이터 갱신] ECOS 환율과 관세청 수출을 받아 저장 표와 합치고 data/에 저장한다.

    저장된 자료가 있으면 이어서 받는다: 수출은 마지막 달의 REFRESH_OVERLAP_MONTHS개월 전부터, 환율은 마지막 날부터.
    첫 실행이나 full=True면 COLLECT_START_YM, COLLECT_START_DATE부터 받는다.
    관세청 원자료는 정제 전에 data/raw_exports_last.csv로 저장해, 정제가 실패해도 받은 값을 열어 볼 수 있다.
    한쪽이 RuntimeError(키 없음, API 실패)로 실패하면 warnings에 남기고 다른 쪽을 계속한다.

    Args:
        data_dir: data 폴더 경로.
        today: 수집 끝 날짜. None이면 오늘.
        full: True면 저장된 자료와 상관없이 처음부터 다시 받는다.

    Returns:
        dict
            exports, fx (DataFrame): 갱신 후 표 (실패한 쪽은 저장돼 있던 표)
            exports_added, fx_added (int | None): 늘어난 행 수 (실패한 쪽은 None)
            exports_period, fx_period (str): 요청한 기간
            api_calls (dict[str, int]): 이번에 보낸 요청 수 {"관세청": n, "ECOS": m}
            warnings (list[str]): 화면에 보여 줄 경고 문장

    Raises:
        ValueError: 관세청 응답의 열이나 값 형식이 예상과 달라 정제할 수 없을 때. 수출은 저장하지 않는다(환율은 저장됨).
    """
    today = today or date.today()
    paths = _paths(data_dir)
    warnings: list[str] = []
    calls_before = dict(data_loader.API_CALLS)

    fx = _read_table(paths["fx"], data_loader.FX_COLUMNS, float_columns=("usdkrw",))
    fx_start = COLLECT_START_DATE if full or len(fx) == 0 else max(COLLECT_START_DATE, fx["date"].max())
    fx_start = min(fx_start, today.strftime("%Y-%m-%d"))
    fx_period = f"{fx_start}~{today:%Y-%m-%d}"
    fx_added = None
    try:
        new_fx = data_loader.fetch_fx_rates(fx_start, today.strftime("%Y-%m-%d"))
    except RuntimeError as exc:
        warnings.append(f"[환율] 수집 실패, 저장된 데이터로 진행합니다 ({exc})")
    else:
        before = len(fx)
        fx = preprocess.upsert_records(fx, new_fx, ["date"])
        _write_table(fx, paths["fx"])
        fx_added = len(fx) - before

    exports = read_exports(data_dir)
    exports_start = COLLECT_START_YM
    if not full and len(exports) > 0:
        exports_start = max(COLLECT_START_YM, _shift_ym(exports["ym"].max(), -REFRESH_OVERLAP_MONTHS))
    exports_period = f"{exports_start}~{today:%Y-%m}"
    exports_added = None
    try:
        raw_exports = data_loader.fetch_regional_exports(exports_start, today.strftime("%Y-%m"))
    except RuntimeError as exc:
        warnings.append(f"[수출] 수집 실패, 저장된 데이터로 진행합니다 ({exc})")
    else:
        _write_table(raw_exports, paths["raw_exports"])
        try:
            new_exports = preprocess.clean_exports(raw_exports)
        except ValueError as exc:
            raise ValueError(f"{exc} / 받은 원자료: {paths['raw_exports']}") from None
        before = len(exports)
        exports = preprocess.upsert_records(exports, new_exports, EXPORTS_KEY_COLUMNS)
        _write_table(exports, paths["exports"])
        exports_added = len(exports) - before

    return {
        "exports": exports,
        "fx": fx,
        "exports_added": exports_added,
        "fx_added": fx_added,
        "exports_period": exports_period,
        "fx_period": fx_period,
        "api_calls": {name: data_loader.API_CALLS[name] - calls_before[name] for name in calls_before},
        "warnings": warnings,
    }


def check_api(today: date | None = None) -> dict:
    """[API 점검] 요청 2번으로 키와 응답 형식만 확인한다. 아무것도 저장하지 않는다.

    관세청은 경기도(이천시) 한 시도의 최근 공표 2개월, ECOS는 최근 14일만 받는다.
    관세청 원자료를 clean_exports에 넣어 정제가 되는지도 함께 본다.

    Args:
        today: 기준일. None이면 오늘.

    Returns:
        dict
            customs_raw, customs_clean (DataFrame | None): 관세청 원자료와 정제 결과
            customs_error, fx_error (str | None): 실패 메시지
            fx (DataFrame | None): 환율
            api_calls (dict[str, int]): 보낸 요청 수
    """
    today = today or date.today()
    calls_before = dict(data_loader.API_CALLS)
    current_ym = today.strftime("%Y-%m")
    result: dict = {"customs_raw": None, "customs_clean": None, "customs_error": None, "fx": None, "fx_error": None}
    try:
        result["customs_raw"] = data_loader.fetch_regional_exports(
            _shift_ym(current_ym, -3), _shift_ym(current_ym, -2), regions=("이천시",)
        )
        result["customs_clean"] = preprocess.clean_exports(result["customs_raw"])
    except (RuntimeError, ValueError) as exc:
        result["customs_error"] = str(exc)
    try:
        start = date.fromordinal(today.toordinal() - 14)
        result["fx"] = data_loader.fetch_fx_rates(f"{start:%Y-%m-%d}", f"{today:%Y-%m-%d}")
    except (RuntimeError, ValueError) as exc:
        result["fx_error"] = str(exc)
    result["api_calls"] = {name: data_loader.API_CALLS[name] - calls_before[name] for name in calls_before}
    return result


def run_forecast(
    target_quarter: str,
    data_dir: Path = DEFAULT_DATA_DIR,
    today: date | None = None,
    threshold: float = DEFAULT_ANOMALY_THRESHOLD,
) -> dict:
    """[예측 실행] 저장된 자료로 대상 분기 매출을 추정하고 근거, 브리프를 만든 뒤 예측 이력에 저장한다.

    forecast의 status가 "no_data"면 이상치, 가이던스, 이력 저장 없이 안내 문장만 만든다.
    컨콜 텍스트는 data/transcripts/<직전 분기>.txt를 읽고, 없으면 가이던스는 empty_input(판단불가)이 된다.

    Args:
        target_quarter: 대상 분기 "YYYYQn".
        data_dir: data 폴더 경로.
        today: 예측 실행일(as_of). None이면 오늘.
        threshold: 이상치 판정 z-score 기준.

    Returns:
        dict
            target_quarter (str), as_of (str "YYYY-MM-DD"), status (str: forecast의 status)
            forecast, anomaly, guidance, consistency (dict, no_data면 anomaly 이하 None)
            brief (str), facts (dict[str, str]: 화면 표시용 숫자 문자열), anomaly_ym (str | None)
            transcript_file (str | None: 읽은 컨콜 파일 이름)
            exports, quarterly, actuals, history (DataFrame: 대상 분기의 예측 이력)

    Raises:
        ValueError: 분기 형식 오류, actuals.csv 형식 오류, 컨콜 파일 인코딩 오류.
        FileNotFoundError: data/actuals.csv가 없을 때.
    """
    _validate_quarter(target_quarter)
    as_of = (today or date.today()).strftime("%Y-%m-%d")
    paths = _paths(data_dir)

    actuals = data_loader.load_actuals(str(paths["actuals"]))
    exports = read_exports(data_dir)
    fx = _read_table(paths["fx"], data_loader.FX_COLUMNS, float_columns=("usdkrw",))
    quarterly = preprocess.aggregate_quarterly(exports, fx)
    forecast = forecaster.estimate_revenue(quarterly, actuals, target_quarter)

    result = {
        "target_quarter": target_quarter,
        "as_of": as_of,
        "status": forecast["status"],
        "forecast": forecast,
        "anomaly": None,
        "guidance": None,
        "consistency": None,
        "brief": "",
        "facts": llm_module.build_brief_facts(forecast, {}, {}),
        "anomaly_ym": None,
        "transcript_file": None,
        "exports": exports,
        "quarterly": quarterly,
        "actuals": actuals,
        "history": _quarter_history(_read_forecasts(paths["forecasts"]), target_quarter),
    }
    if forecast["status"] == forecaster.FORECAST_STATUS_NO_DATA:
        result["brief"] = llm_module.generate_brief(forecast, {}, {})  # LLM 없이 안내 문장을 돌려준다
        return result

    anomaly_ym = _latest_complete_ym(exports, target_quarter) or _quarter_months(target_quarter)[-1]
    anomaly = forecaster.detect_anomaly(exports, anomaly_ym, threshold)
    transcript_path = paths["transcripts"] / f"{_previous_quarter(target_quarter)}.txt"
    transcript_text = _read_transcript(transcript_path)
    guidance = llm_module.extract_guidance(transcript_text)
    consistency = forecaster.compare_guidance(forecast, guidance)

    result.update(
        anomaly=anomaly,
        guidance=guidance,
        consistency=consistency,
        brief=llm_module.generate_brief(forecast, anomaly, consistency),
        facts=llm_module.build_brief_facts(forecast, anomaly, consistency),
        anomaly_ym=anomaly_ym,
        transcript_file=transcript_path.name if transcript_text.strip() else None,
        history=_quarter_history(_save_forecast(paths["forecasts"], forecast, as_of), target_quarter),
    )
    return result


def read_exports(data_dir: Path = DEFAULT_DATA_DIR) -> pd.DataFrame:
    """저장된 exports 표(data/exports.csv)를 읽는다.

    Returns:
        exports 표. 파일이 없으면(첫 실행) dtype을 지정한 0행 표.
    """
    return _read_table(_paths(data_dir)["exports"], preprocess.EXPORTS_COLUMNS, float_columns=("export_usd",))


def read_uploaded_csv(source: object) -> pd.DataFrame:
    """올린 CSV(경로 또는 st.file_uploader 파일 객체)를 모든 열 문자열로 읽는다.

    UTF-8(BOM 포함)로 읽을 수 없으면 처음으로 되돌아가 cp949(엑셀 기본 CSV)로 다시 읽는다.

    Returns:
        모든 값이 문자열인 원자료 표 (빈칸은 "").

    Raises:
        ValueError: 원인만 담은 한국어 메시지로 바꿔 낸다(고치는 방법은 화면이 붙인다. 원래 예외는 __cause__).
            "빈 파일: ..." 내용이 없는 파일
            "인코딩 오류: ..." UTF-8, cp949 모두로 읽을 수 없는 파일 (UTF-16 등)
            "CSV 형식 오류: ..." 쉼표 구분이 맞지 않는 파일
    """
    try:
        try:
            return pd.read_csv(source, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        except UnicodeDecodeError:
            if hasattr(source, "seek"):
                source.seek(0)
            return pd.read_csv(source, dtype=str, keep_default_na=False, encoding="cp949")
    except pd.errors.EmptyDataError as exc:
        raise ValueError("빈 파일: 파일에 내용이 없습니다.") from exc
    except UnicodeDecodeError as exc:
        raise ValueError("인코딩 오류: UTF-8과 cp949(엑셀 기본 CSV)로 모두 읽을 수 없습니다 (UTF-16 등).") from exc
    except pd.errors.ParserError as exc:
        raise ValueError(f"CSV 형식 오류: 쉼표로 구분된 표로 읽을 수 없습니다 ({exc})") from exc


def import_exports(raw_df: pd.DataFrame, data_dir: Path = DEFAULT_DATA_DIR, today: date | None = None) -> dict:
    """[CSV로 갱신] 올린 수출 원자료(K-stat 등)를 정제해 저장된 exports 표와 합치고 저장한다.

    collected_at 열이 없으면 정제 후 올린 날짜로 채운다(오류 메시지에는 올린 열만 나온다).

    Args:
        raw_df: read_uploaded_csv 결과. 바꾸지 않는다.
        data_dir: data 폴더 경로.
        today: collected_at으로 쓸 날짜. None이면 오늘.

    Returns:
        dict
            exports (DataFrame): 저장한 exports 표
            raw_rows, clean_rows (int): 올린 행 수, 정제 후 남은 행 수
            added (int): 저장 표에서 늘어난 행 수
            updated (int): 이번 업로드의 정제된 키 중 기존 저장 표와 겹쳐 교체한 행 수

    Raises:
        ValueError: "필수 열 누락: ..." (clean_exports). 저장하지 않는다.
    """
    # collected_at은 정제한 뒤에 채운다. 정제 전에 열을 붙이면 '필수 열 누락' 메시지의 '원자료 열'에
    # 사용자가 올리지 않은 collected_at이 섞여 나온다. 열이 없을 때 clean_exports는 모든 행을 같은 수집일로 보므로
    # 정제 결과(중복 처리 포함)는 정제 전에 채우던 때와 같다.
    new_exports = preprocess.clean_exports(raw_df)
    if data_loader.COLLECTED_AT_COLUMN not in {str(column).strip() for column in raw_df.columns}:
        new_exports[data_loader.COLLECTED_AT_COLUMN] = (today or date.today()).strftime("%Y-%m-%d")
    stored = read_exports(data_dir)
    stored_keys = stored[EXPORTS_KEY_COLUMNS].drop_duplicates()
    new_keys = new_exports[EXPORTS_KEY_COLUMNS].drop_duplicates()
    updated = len(new_keys.merge(stored_keys, on=EXPORTS_KEY_COLUMNS, how="inner"))
    exports = preprocess.upsert_records(stored, new_exports, EXPORTS_KEY_COLUMNS)
    _write_table(exports, _paths(data_dir)["exports"])
    return {
        "exports": exports,
        "raw_rows": len(raw_df),
        "clean_rows": len(new_exports),
        "added": len(exports) - len(stored),
        "updated": updated,
    }


def exports_chart_table(exports: pd.DataFrame, last_months: int = CHART_MONTHS) -> pd.DataFrame:
    """이천, 청주 월별 수출 차트용 표를 만든다.

    Returns:
        index가 ym, 열이 지역, 값이 억 달러인 표 (최근 last_months개월). 자료가 없으면 0행.
    """
    target = exports.loc[exports["region"].isin(preprocess.ALLOWED_REGIONS)]
    table = target.pivot_table(index="ym", columns="region", values="export_usd", aggfunc="sum")
    return (table / USD_PER_100M).sort_index().tail(last_months)


def list_target_quarters(data_dir: Path = DEFAULT_DATA_DIR, today: date | None = None) -> list[str]:
    """대상 분기 선택 목록을 만든다: 진행 중인 분기 + 수출 자료가 있는 분기.

    Returns:
        "YYYYQn" 목록 (최근 분기부터).
    """
    quarters = {_quarter_of(ym) for ym in read_exports(data_dir)["ym"].dropna()}
    quarters.add(_quarter_of((today or date.today()).strftime("%Y-%m")))
    return sorted(quarters, reverse=True)


def quarterly_display_table(quarterly: pd.DataFrame) -> pd.DataFrame:
    """분기 집계 표를 읽기 쉬운 단위의 문자열 표로 바꾼다 (화면 표시용, 계산과 저장에는 쓰지 않는다).

    Returns:
        열이 분기, 수출(억 달러), 반영 개월, 평균 환율(원)인 새 DataFrame. 값이 없으면 "-".
    """
    return pd.DataFrame(
        {
            "분기": quarterly["quarter"],
            "수출(억 달러)": quarterly["export_usd"].map(lambda value: _number_text(value / USD_PER_100M, 1)),
            "반영 개월": quarterly["months_available"],
            "평균 환율(원)": quarterly["fx_avg"].map(lambda value: _number_text(value, 2)),
        }
    )


def history_display_table(history: pd.DataFrame) -> pd.DataFrame:
    """예측 이력 표를 읽기 쉬운 단위의 문자열 표로 바꾼다 (화면 표시용, forecasts.csv는 원 단위 그대로).

    Returns:
        열이 분기, 실행일, 예상 매출, 하한, 상한(조 원), 직전 분기 대비, 적용 비율, 반영 개월, 상태인 새 DataFrame.
    """
    def trillion(value: object) -> str:
        return _number_text(value / KRW_PER_TRILLION, 1) if isinstance(value, (int, float)) else "-"

    return pd.DataFrame(
        {
            "분기": history["quarter"],
            "실행일": history["as_of"],
            "예상 매출(조 원)": history["estimate_krw"].map(trillion),
            "하한(조 원)": history["lower_krw"].map(trillion),
            "상한(조 원)": history["upper_krw"].map(trillion),
            "직전 분기 대비": history["qoq_change_pct"].map(_pct_text),
            "적용 비율": history["ratio_used"].map(lambda value: _number_text(value, 2)),
            "반영 개월": history["months_available"],
            "상태": history["status"],
        }
    )


def exports_display_table(exports: pd.DataFrame) -> pd.DataFrame:
    """exports 표를 읽기 쉬운 단위의 문자열 표로 바꾼다 (화면 표시용).

    Returns:
        열이 월, 지역, 수출(억 달러), 수집일인 새 DataFrame.
    """
    return pd.DataFrame(
        {
            "월": exports["ym"],
            "지역": exports["region"],
            "수출(억 달러)": exports["export_usd"].map(lambda value: _number_text(value / USD_PER_100M, 2)),
            "수집일": exports["collected_at"].fillna("-"),
        }
    )


def default_target_quarter(data_dir: Path = DEFAULT_DATA_DIR, today: date | None = None) -> str:
    """기본 대상 분기를 고른다: 두 지역 수출이 모두 있는 가장 최근 달의 분기.

    진행 중인 분기는 첫 달 자료가 공표되는 15일 무렵까지 자료가 0개월이라 바로 고르면 no_data가 된다.

    Returns:
        "YYYYQn". 저장된 자료가 없으면 진행 중인 분기.
    """
    complete = _complete_months(read_exports(data_dir))
    if complete:
        return _quarter_of(complete[-1])
    return _quarter_of((today or date.today()).strftime("%Y-%m"))


# =============================================================================
# 내부 도우미: 파일
# =============================================================================
def _paths(data_dir: Path) -> dict[str, Path]:
    """data 폴더 안의 고정 경로를 모은다.

    Returns:
        {"exports", "fx", "actuals", "forecasts", "transcripts"} -> Path.
    """
    data_dir = Path(data_dir)
    return {
        "exports": data_dir / "exports.csv",
        "fx": data_dir / "fx.csv",
        "actuals": data_dir / "actuals.csv",
        "forecasts": data_dir / "forecasts.csv",
        "transcripts": data_dir / "transcripts",
        "raw_exports": data_dir / "raw_exports_last.csv",
    }


def _read_table(
    path: Path, columns: tuple[str, ...], float_columns: tuple[str, ...] = (), int_columns: tuple[str, ...] = ()
) -> pd.DataFrame:
    """저장된 CSV를 읽는다. 문자열 키 열은 문자열로 읽는다.

    Returns:
        DataFrame. 파일이 없으면 columns 열의 0행 표(float_columns는 float64, int_columns는 int64, 나머지 문자열).
    """
    if not path.exists():
        return pd.DataFrame(
            {
                column: pd.Series(
                    dtype="float64" if column in float_columns else "int64" if column in int_columns else str
                )
                for column in columns
            }
        )
    return pd.read_csv(path, dtype={column: str for column in STRING_COLUMNS}, encoding="utf-8-sig")


def _write_table(table: pd.DataFrame, path: Path) -> None:
    """표를 UTF-8, index 없이 저장한다. 폴더가 없으면 만든다.

    Returns:
        None.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(path, index=False, encoding="utf-8")


def _read_forecasts(path: Path) -> pd.DataFrame:
    """예측 이력(data/forecasts.csv)을 읽는다.

    Returns:
        forecasts 표. 없으면 0행 표.
    """
    return _read_table(path, FORECASTS_COLUMNS, FORECASTS_FLOAT_COLUMNS, ("months_available",))


def _save_forecast(path: Path, forecast: dict, as_of: str) -> pd.DataFrame:
    """forecast에 as_of를 붙인 1행을 예측 이력에 합쳐 저장한다 (키 quarter + as_of, 같은 날 다시 실행하면 덮어씀).

    Returns:
        저장한 전체 예측 이력 표.
    """
    new_row = pd.DataFrame([{**forecast, "as_of": as_of}], columns=list(FORECASTS_COLUMNS))
    # None이 든 dict로 만든 행은 숫자 열이 object가 되므로 float64로 맞춘다
    new_row = new_row.astype({column: "float64" for column in FORECASTS_FLOAT_COLUMNS})
    forecasts = preprocess.upsert_records(_read_forecasts(path), new_row, ["quarter", "as_of"])
    forecasts = forecasts.loc[:, list(FORECASTS_COLUMNS)]
    _write_table(forecasts, path)
    return forecasts


def _quarter_history(forecasts: pd.DataFrame, quarter: str) -> pd.DataFrame:
    """예측 이력에서 대상 분기 행만 고른다.

    Returns:
        as_of 오름차순 표.
    """
    history = forecasts.loc[forecasts["quarter"] == quarter]
    return history.sort_values("as_of", kind="stable").reset_index(drop=True)


def _read_transcript(path: Path) -> str:
    """컨콜 텍스트를 읽는다.

    Returns:
        파일 내용. 파일이 없으면 "".

    Raises:
        ValueError: "컨콜 파일 인코딩 오류: <파일 이름> ..." UTF-8로 읽을 수 없을 때.
    """
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError(f"컨콜 파일 인코딩 오류: {path.name} (UTF-8로 저장해 주세요)") from None


# =============================================================================
# 내부 도우미: 분기, 월
# =============================================================================
def _validate_quarter(quarter: str) -> None:
    """대상 분기가 ASCII "YYYYQn"(n은 1~4)인지 검사한다.

    Returns:
        None.

    Raises:
        ValueError: "분기 형식 오류: <값>"
    """
    if (
        not isinstance(quarter, str)
        or len(quarter) != 6
        or not quarter.isascii()
        or not quarter[:4].isdigit()
        or quarter[4] != "Q"
        or quarter[5] not in "1234"
    ):
        raise ValueError(f"분기 형식 오류: {quarter}")


def _shift_ym(ym: str, months: int) -> str:
    """월에서 months개월 이동한 달을 구한다 (음수면 앞으로).

    Returns:
        "YYYY-MM".
    """
    year, month_offset = divmod(int(ym[:4]) * 12 + int(ym[5:7]) - 1 + months, 12)
    return f"{year:04d}-{month_offset + 1:02d}"


def _quarter_of(ym: str) -> str:
    """월이 속한 분기를 구한다 ("2026-11" -> "2026Q4").

    Returns:
        "YYYYQn".
    """
    return f"{ym[:4]}Q{(int(ym[5:7]) - 1) // 3 + 1}"


def _previous_quarter(quarter: str) -> str:
    """직전 분기를 구한다 (컨콜 파일 이름: 2026Q4 예측에는 2026Q3 실적발표의 전망을 쓴다).

    Returns:
        "YYYYQn".
    """
    year, number = int(quarter[:4]), int(quarter[5])
    return f"{year - 1}Q4" if number == 1 else f"{year}Q{number - 1}"


def _quarter_months(quarter: str) -> tuple[str, str, str]:
    """분기에 속한 세 달을 구한다 ("2026Q4" -> 2026-10, 2026-11, 2026-12).

    Returns:
        "YYYY-MM" 세 개.
    """
    first = (int(quarter[5]) - 1) * 3 + 1
    return tuple(f"{quarter[:4]}-{first + offset:02d}" for offset in range(3))


def _complete_months(exports: pd.DataFrame) -> list[str]:
    """두 지역 수출이 모두 있는 달을 고른다 (분기 집계, 이상치 판정과 같은 기준).

    Returns:
        "YYYY-MM" 오름차순 목록.
    """
    target = exports.loc[exports["region"].isin(preprocess.ALLOWED_REGIONS)]
    counts = target.groupby("ym")["region"].nunique()
    return sorted(counts.index[counts == len(preprocess.ALLOWED_REGIONS)])


def _latest_complete_ym(exports: pd.DataFrame, quarter: str) -> str | None:
    """대상 분기 안에서 두 지역 수출이 모두 있는 가장 최근 달을 고른다 (이상치 판정 대상 월).

    Returns:
        "YYYY-MM" 또는 None.
    """
    months = [ym for ym in _complete_months(exports) if ym in _quarter_months(quarter)]
    return months[-1] if months else None


# =============================================================================
# CLI
# =============================================================================
def _number_text(value: object, digits: int) -> str:
    """숫자를 천 단위 쉼표와 소수 digits자리로 표시한다 (지수 표기 1.06e+10 대신 십진수).

    Returns:
        "1,450.98" 같은 문자열. 숫자가 아니거나 NaN이면 "-".
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)) or pd.isna(value):
        return "-"
    return f"{value:,.{digits}f}"


def _print_table(table: pd.DataFrame) -> None:
    """표를 index 없이 출력한다. 한글 열 이름 폭을 맞추고, 행이 없으면 안내 문장을 출력한다.

    Returns:
        None.
    """
    if len(table) == 0:
        print("  (자료 없음)")
        return
    with pd.option_context("display.unicode.east_asian_width", True, "display.width", 200):
        print(table.to_string(index=False))


def _krw_text(value: object) -> str:
    """원 단위 금액을 조 원으로 표시한다.

    Returns:
        "26.1조 원" 또는 값이 없으면 "-".
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)) or pd.isna(value):
        return "-"
    return f"{value / KRW_PER_TRILLION:.1f}조 원"


def _pct_text(value: object) -> str:
    """퍼센트 값을 부호와 함께 표시한다.

    Returns:
        "+10.0%" 또는 값이 없으면 "-".
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)) or pd.isna(value):
        return "-"
    return f"{value:+.1f}%"


def _print_refresh(refresh: dict) -> None:
    """refresh_data 결과를 출력한다.

    Returns:
        None.
    """
    print("[데이터 갱신]")
    for label, key in (("수출", "exports"), ("환율", "fx")):
        added = refresh[f"{key}_added"]
        state = "실패" if added is None else f"{added:+d}행"
        print(f"  {label}: 요청 {refresh[f'{key}_period']}, {state}, 저장된 행 {len(refresh[key])}개")
    calls = refresh["api_calls"]
    print(f"  API 호출: 관세청 {calls['관세청']}회, ECOS {calls['ECOS']}회")
    for warning in refresh["warnings"]:
        print(f"  경고: {warning}")


def _print_check(check: dict) -> None:
    """check_api 결과를 출력한다.

    Returns:
        None.
    """
    print("[API 점검] 저장하지 않음")
    raw = check["customs_raw"]
    if raw is not None:
        print(f"  관세청 원자료: {len(raw)}행, 열 {list(raw.columns)}")
        print(raw.head(5).to_string(index=False))
    if check["customs_error"]:
        print(f"  관세청 실패: {check['customs_error']}")
    elif check["customs_clean"] is not None:
        print(f"  정제 결과 (이천시만 요청): {len(check['customs_clean'])}행")
        _print_table(exports_display_table(check["customs_clean"]))
    if check["fx_error"]:
        print(f"  ECOS 실패: {check['fx_error']}")
    elif check["fx"] is not None:
        last = check["fx"].tail(1).to_dict("records")
        print(f"  ECOS 환율: {len(check['fx'])}행, 마지막 {last[0] if last else '없음'}")
    calls = check["api_calls"]
    print(f"  API 호출: 관세청 {calls['관세청']}회, ECOS {calls['ECOS']}회")


def _print_report(result: dict) -> None:
    """run_forecast 결과를 출력한다.

    Returns:
        None.
    """
    forecast, facts = result["forecast"], result["facts"]
    print(f"\n==== {result['target_quarter']} 예측 (실행일 {result['as_of']}, status {result['status']}) ====")
    print("[분기 집계] 최근 5개 분기")
    _print_table(quarterly_display_table(result["quarterly"].tail(5)))
    if result["status"] != forecaster.FORECAST_STATUS_OK:
        print(f"\n[안내] {result['brief']}")
        print(f"[고지] {DISCLAIMER}")
        return

    print(
        f"\n[예상 매출] {_krw_text(forecast['estimate_krw'])} (범위 {facts['range']}), "
        f"직전 분기 대비 {facts['qoq']}"
    )
    print(f"[근거] 반영 수출 {facts['months']}, 적용 비율 {facts['ratio']}")
    anomaly = result["anomaly"]
    z_text = "-" if anomaly["z_score"] is None else f"{anomaly['z_score']:.2f}"
    print(f"[이상치] {anomaly['ym']}: {anomaly['reason']} (전년동월비 {facts['export_yoy']}, z {z_text})")
    guidance = result["guidance"]
    print(
        f"[가이던스] {result['transcript_file'] or '컨콜 파일 없음'}: status {guidance['status']}, "
        f"가격 {guidance['price_outlook']}, D램 출하 {_pct_text(guidance['dram_bit_growth_pct'])}, "
        f"낸드 출하 {_pct_text(guidance['nand_bit_growth_pct'])}"
    )
    consistency = result["consistency"]
    print(
        f"[일치 여부] {consistency['status']} "
        f"(예측 {consistency['forecast_direction'] or '없음'}, 가이던스 {consistency['guidance_direction'] or '없음'})"
    )
    print(f"[브리프] {result['brief']}")
    print("[예측 이력]")
    _print_table(history_display_table(result["history"]))
    print(f"[고지] {DISCLAIMER}")


def main() -> None:
    """CLI 진입점: (선택) 데이터 갱신 -> 예측 실행 -> 결과 출력.

    RuntimeError(수집 실패)는 경고 후 저장된 데이터로 진행하고, ValueError와 FileNotFoundError는 메시지를 보여 주고 멈춘다.

    Returns:
        None.
    """
    parser = argparse.ArgumentParser(description="알트(ALT) SK하이닉스 분기 매출 나우캐스팅")
    parser.add_argument("--quarter", help="대상 분기 YYYYQn (생략하면 자료가 있는 가장 최근 분기)")
    parser.add_argument("--no-refresh", action="store_true", help="API를 부르지 않고 저장된 자료로만 예측")
    parser.add_argument("--full-refresh", action="store_true", help="저장된 자료와 상관없이 처음부터 다시 수집")
    parser.add_argument("--check-api", action="store_true", help="요청 2번으로 키와 응답 형식만 확인 (저장 안 함)")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, help="data 폴더 경로")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="  경고: %(message)s")

    if args.check_api:
        _print_check(check_api())
        return
    try:
        if not args.no_refresh:
            _print_refresh(refresh_data(args.data_dir, full=args.full_refresh))
        target_quarter = args.quarter or default_target_quarter(args.data_dir)
        mode = "mock (ANTHROPIC_API_KEY 없음)" if llm_module.USE_MOCK else llm_module.CLAUDE_MODEL_NAME
        print(f"\n[LLM] {mode}")
        _print_report(run_forecast(target_quarter, args.data_dir))
    except (ValueError, FileNotFoundError) as exc:
        print(f"\n[중단] {exc}")


if __name__ == "__main__":
    main()
