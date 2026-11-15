"""알트(ALT) SK하이닉스 분기 매출 나우캐스트: Streamlit 화면 (11주차).

실행: alt_backend_week11 폴더에서  streamlit run app.py

이 파일은 화면 구성과 표시만 맡는다. 데이터 읽기, 검증, 정제, 집계, 매출 추정, 이상치 판정, 가이던스 비교,
화면용 단위 변환(조 원, 억 달러 문자열)은 모두 backend.py와 hynix_nowcast 모듈 함수가 한다.
수출(data/exports.csv)과 환율(data/fx.csv)은 담당자가 매월 `python backend.py`로 갱신해 커밋한 파일을 읽기만 한다.
"""

from datetime import datetime
from pathlib import Path

import altair as alt
import streamlit as st

import backend
from hynix_nowcast import data_loader, forecaster, llm_module

# --- 화면 상수 -------------------------------------------------------------------------------
PAGE_UPLOAD = "데이터 업로드"
PAGE_REPORT = "매출 전망"
PAGE_HISTORY = "리포트 이력"
PAGES = (PAGE_UPLOAD, PAGE_REPORT, PAGE_HISTORY)
PAGE_NUMBERS = {PAGE_UPLOAD: "01", PAGE_REPORT: "02", PAGE_HISTORY: "03"}

MODE_NOW = "이번 분기 전망"
MODE_CHECK = "지난 분기 검증"

# session_state 키
KEY_ACTUALS = "actuals"  # load_actuals 결과(DataFrame). 업로드 위젯이 없는 페이지에서도 써야 해서 보관
KEY_ACTUALS_NAME = "actuals_file_name"
KEY_UPLOAD_SIGNATURE = "upload_signature"  # 마지막으로 읽은 파일 (이름, 크기): 같은 파일을 rerun마다 다시 읽지 않음
KEY_UPLOAD_ERROR = "upload_error"  # 마지막 업로드의 오류 문장 (없으면 "")
KEY_HISTORY = "report_history"  # 이번 세션에 저장한 리포트 목록(list[dict])
KEY_PAGE = "page"  # 사이드바 메뉴 라디오 위젯 값
KEY_MODE = "view_mode"  # 보기 모드 라디오 위젯 값
KEY_CHECK_QUARTER = "check_quarter"  # 검증할 분기 selectbox 위젯 값

COLOR_ICHEON = "#2563EB"
COLOR_CHEONGJU = "#93C5FD"
COLOR_ACTUAL_BAR = "#94A3B8"
COLOR_ESTIMATE = "#0E8A6B"
COLOR_CHECK_POINT = "#E8484B"
UNAVAILABLE = "확인 불가"  # build_brief_facts가 값이 없을 때 넣는 문자열
REQUIRED_COLUMNS_TEXT = ", ".join(data_loader.ACTUALS_COLUMNS)

RISKS = (
    ("지역 수출 ≠ 기업 연결 매출", "중국 공장·해외 생산분은 과거 비율에만 간접 반영됩니다."),
    ("관세청 수치 정정 가능", "전월 수출이 정정되면 다음 갱신 때 추정치가 바뀔 수 있습니다."),
    ("매출 증가 ≠ 이익 증가", "가격·제품 구성·비용은 별도로 확인해야 합니다."),
)

CSS = """
<style>
.block-container {padding-top: 3rem; max-width: 1180px;}
.alt-logo b {font-size: 1.9rem; font-weight: 800; letter-spacing: -0.01em; line-height: 1;}
.alt-logo small {display: block; font-size: 0.62rem; letter-spacing: 0.1em; color: #667085; font-weight: 700;}
.alt-company {background: #fff; border: 1px solid #E3E6EC; border-radius: 10px; padding: 10px 14px; margin: 14px 0 6px;}
.alt-company b {display: block; font-size: 0.95rem;}
.alt-company span {font-size: 0.75rem; color: #667085;}
.alt-status {background: #fff; border: 1px solid #E3E6EC; border-radius: 10px; padding: 12px 14px; font-size: 0.8rem;}
.alt-status h4 {margin: 0 0 6px; font-size: 0.85rem;}
.alt-status .row {display: flex; justify-content: space-between; gap: 8px; color: #667085; margin: 4px 0;}
.alt-status .row b {color: #1E2533;}
.alt-status .row b.wait {color: #C2410C;}
.alt-status .note {font-size: 0.7rem; color: #667085; border-top: 1px solid #E3E6EC; margin-top: 8px; padding-top: 6px;}
.alt-hero {background: #14294A; color: #fff; border-radius: 14px; padding: 22px 26px; margin-bottom: 14px;}
.alt-hero .eyebrow {color: #93B4E8; font-size: 0.78rem; font-weight: 700; letter-spacing: 0.08em;}
.alt-hero h1 {color: #fff; font-size: 1.7rem; margin: 6px 0 4px; padding: 0;}
.alt-hero .meta {color: #C9D4E6; font-size: 0.9rem;}
.alt-badge {display: inline-block; font-size: 0.72rem; font-weight: 700; border-radius: 999px; padding: 2px 10px; margin-left: 8px; vertical-align: middle;}
.alt-badge.mock {background: #2E4468; color: #fff;}
.alt-badge.check {background: #F5B841; color: #4A3305;}
.alt-concl {background: #E7EEFC; border-radius: 12px; padding: 14px 18px; margin-bottom: 6px;}
.alt-concl.check {background: #FEF4DC;}
.alt-concl small {color: #2563EB; font-weight: 700;}
.alt-concl.check small {color: #4A3305;}
.alt-concl div {font-size: 1.15rem; font-weight: 700; margin-top: 2px;}
.alt-ph {border: 1.5px dashed #B4BAC5; border-radius: 12px; padding: 12px 16px; min-height: 112px;
         background: repeating-linear-gradient(135deg, #fff 0 10px, #F6F7F9 10px 20px);}
.alt-ph .t {font-size: 0.85rem; color: #667085;}
.alt-ph .pill {font-size: 0.66rem; font-weight: 700; background: #E3E6EC; color: #667085; border-radius: 999px; padding: 2px 8px; margin-left: 6px;}
.alt-ph .v {font-size: 1.9rem; font-weight: 700; color: #B4BAC5; margin: 2px 0;}
.alt-ph .c {font-size: 0.75rem; color: #8A93A3;}
div[data-testid="stMetric"] {background: #fff; border: 1px solid #E3E6EC; border-radius: 12px; padding: 12px 16px;}
</style>
"""


# --- session_state 초기화 -------------------------------------------------------------------
def init_session_state() -> None:
    """앱이 처음 실행될 때 한 번만 기본값을 넣는다 (rerun 때는 기존 값을 유지)."""
    if KEY_ACTUALS not in st.session_state:
        st.session_state[KEY_ACTUALS] = None
    if KEY_ACTUALS_NAME not in st.session_state:
        st.session_state[KEY_ACTUALS_NAME] = ""
    if KEY_UPLOAD_SIGNATURE not in st.session_state:
        st.session_state[KEY_UPLOAD_SIGNATURE] = None
    if KEY_UPLOAD_ERROR not in st.session_state:
        st.session_state[KEY_UPLOAD_ERROR] = ""
    if KEY_HISTORY not in st.session_state:
        st.session_state[KEY_HISTORY] = []
    if KEY_PAGE not in st.session_state:
        st.session_state[KEY_PAGE] = PAGE_UPLOAD


def go_to(page: str) -> None:
    """버튼 콜백: 다음 rerun에서 사이드바 메뉴가 page를 가리키게 한다."""
    st.session_state[KEY_PAGE] = page


# --- 데이터 접근 (모두 backend 함수 호출) ------------------------------------------------------
def data_file_date(file_name: str) -> str:
    """data/ 파일의 마지막 수정일(= 담당자가 API로 갱신한 날). 파일이 없으면 "파일 없음"."""
    path = Path(backend.DEFAULT_DATA_DIR) / file_name
    if not path.exists():
        return "파일 없음"
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")


def data_version() -> tuple:
    """수출, 환율, 컨콜 파일이 바뀌면 캐시를 새로 계산하도록 수정 시각을 묶는다."""
    data_dir = Path(backend.DEFAULT_DATA_DIR)
    paths = [data_dir / "exports.csv", data_dir / "fx.csv", data_dir / "transcripts"]
    return tuple(path.stat().st_mtime if path.exists() else 0.0 for path in paths)


@st.cache_data(show_spinner="리포트를 계산하는 중입니다...")
def run_report(target_quarter: str, _actuals, upload_signature: tuple, version: tuple) -> dict:
    """backend.run_forecast 결과를 캐시한다.

    Streamlit은 위젯을 건드릴 때마다 스크립트 전체를 다시 실행하므로, 같은 분기와 같은 파일이면 다시 계산하지 않는다.
    _actuals는 해시하지 않고(밑줄), 업로드 파일 (이름, 크기)와 data 파일 수정 시각을 캐시 키로 쓴다.
    forecasts.csv에는 저장하지 않는다(save_history=False). 화면의 이력은 session_state에 따로 쌓는다.
    """
    return backend.run_forecast(target_quarter, actuals_df=_actuals, save_history=False)


# --- 공통 표시 도우미 -------------------------------------------------------------------------
def shown(text: str) -> str:
    """facts의 "확인 불가"를 화면에서는 "—"로 보여 준다."""
    return "—" if text in (UNAVAILABLE, "-", "", None) else text


def placeholder_card(title: str, value: str, caption: str, pill: str = "연결 예정") -> None:
    """아직 데이터나 backend 함수가 없는 지표의 빈자리 카드 (컨센서스, 주가 판단 등)."""
    st.markdown(
        f'<div class="alt-ph"><div class="t">{title}<span class="pill">{pill}</span></div>'
        f'<div class="v">{value}</div><div class="c">{caption}</div></div>',
        unsafe_allow_html=True,
    )


def render_consensus(consensus: dict | None = None) -> None:
    """시장 컨센서스, 예상 괴리율 자리. consensus가 생기면 값만 넘기면 된다 (괴리율 계산은 backend에서)."""
    if consensus is None:
        placeholder_card("시장 컨센서스", "—", "동일 분기 · 연결 매출 기준")
        st.write("")
        placeholder_card("예상 괴리율", "—", "(예상 매출 ÷ 컨센서스 − 1) × 100")
        return
    st.metric("시장 컨센서스", consensus["consensus_text"])
    st.metric("예상 괴리율", consensus["gap_text"])


# --- 사이드바 -------------------------------------------------------------------------------
def render_sidebar() -> tuple[str, str]:
    """로고, 메뉴, 보기 모드(필터), 데이터 반영 현황을 그리고 (선택한 페이지, 대상 분기)를 돌려준다."""
    actuals = st.session_state[KEY_ACTUALS]
    loaded = actuals is not None
    auto_quarter = backend.default_target_quarter()

    with st.sidebar:
        st.markdown(
            '<div class="alt-logo"><b>ALT</b><small>EARNINGS INTELLIGENCE</small></div>'
            '<div class="alt-company"><b>SK하이닉스</b><span>000660 · KOSPI</span></div>',
            unsafe_allow_html=True,
        )

        page = st.radio(
            "워크스페이스",
            PAGES,
            key=KEY_PAGE,
            format_func=lambda name: f"{PAGE_NUMBERS[name]}  {name}",
        )

        st.divider()
        mode = st.radio(
            "보기 모드",
            (MODE_NOW, MODE_CHECK),
            key=KEY_MODE,
            disabled=not loaded,
            captions=("자동으로 고른 진행 중인 분기", "추정과 확정 매출 비교"),
            help="CSV를 업로드하면 선택할 수 있습니다. 바꾸면 매출 전망 화면이 바로 바뀝니다.",
        )

        target_quarter = auto_quarter
        if mode == MODE_NOW or not loaded:
            st.info(f"대상 분기 **{auto_quarter}** (자동 선택)\n\n두 지역 수출이 모두 공표된 가장 최근 달의 분기입니다.")
        else:
            # 자동 선택 분기보다 앞선 분기만 검증 대상 (문자열 비교 = 시간 순서, schema 1.1)
            past_quarters = [quarter for quarter in backend.list_target_quarters() if quarter < auto_quarter]
            if past_quarters:
                target_quarter = st.selectbox("검증할 분기", past_quarters, key=KEY_CHECK_QUARTER)
            else:
                st.warning("검증할 과거 분기가 없습니다.")

        st.markdown(
            '<div class="alt-status"><h4>데이터 반영 현황</h4>'
            f'<div class="row"><span>확정 매출</span>'
            f'{f"<b>{len(actuals)}개 분기</b>" if loaded else "<b class=wait>업로드 대기</b>"}</div>'
            f'<div class="row"><span>수출 데이터 갱신</span><b>{data_file_date("exports.csv")}</b></div>'
            f'<div class="row"><span>환율 데이터 갱신</span><b>{data_file_date("fx.csv")}</b></div>'
            '<div class="note">확정 매출: 업로드 CSV · 수출·환율: data/ 저장 자료(매월 API 갱신)</div></div>',
            unsafe_allow_html=True,
        )
        st.caption("ALT / MVP · SK하이닉스 분기 매출 나우캐스트")

    return page, target_quarter


# --- 01 데이터 업로드 ---------------------------------------------------------------------------
def page_upload() -> None:
    st.title("데이터 업로드")
    st.caption("팀이 DART 공시로 작성한 확정 분기 매출 CSV를 올리면 매출 전망을 볼 수 있습니다. 수출·환율은 저장소 data/ 파일을 사용합니다.")

    uploaded = st.file_uploader(
        "확정 분기 매출 CSV를 여기로 끌어다 놓으세요",
        type="csv",
        help=f"필수 열: {REQUIRED_COLUMNS_TEXT} · UTF-8 또는 cp949(엑셀 기본 저장)",
    )

    if uploaded is not None:
        signature = (uploaded.name, uploaded.size)
        if st.session_state[KEY_UPLOAD_SIGNATURE] != signature:
            # 새 파일일 때만 읽는다. cp949 재시도(seek(0) 후 다시 읽기)와 형식 검증은 load_actuals가 한다
            st.session_state[KEY_UPLOAD_SIGNATURE] = signature
            try:
                actuals = data_loader.load_actuals(uploaded)
            except ValueError as exc:
                st.session_state[KEY_ACTUALS] = None
                st.session_state[KEY_ACTUALS_NAME] = ""
                st.session_state[KEY_UPLOAD_ERROR] = str(exc)
            else:
                st.session_state[KEY_ACTUALS] = actuals
                st.session_state[KEY_ACTUALS_NAME] = uploaded.name
                st.session_state[KEY_UPLOAD_ERROR] = ""
            # 사이드바는 이 함수보다 먼저 그려졌으므로, 바뀐 업로드 상태로 화면 전체를 한 번 다시 그린다
            st.rerun()
        if st.session_state[KEY_UPLOAD_ERROR]:
            st.error(f"**파일을 읽을 수 없습니다.** {st.session_state[KEY_UPLOAD_ERROR]}")
            st.caption(f"파일을 고친 뒤 다시 올려 주세요. 필수 열: {REQUIRED_COLUMNS_TEXT}")
            st.stop()

    actuals = st.session_state[KEY_ACTUALS]
    if actuals is None:
        st.info("아직 업로드된 파일이 없습니다. 확정 분기 매출 CSV를 올리면 다음 단계로 진행할 수 있습니다.")
        cols = st.columns(3)
        cols[0].markdown("**quarter**  \n분기, \"YYYYQn\" (예: 2026Q3)")
        cols[1].markdown("**revenue_krw**  \n연결 기준 3개월 매출, 원 단위")
        cols[2].markdown("**announced_date**  \n잠정실적 공시일, \"YYYY-MM-DD\"")
        st.stop()

    st.success(f"업로드 완료: **{st.session_state[KEY_ACTUALS_NAME]}** · {len(actuals)}개 분기 실적을 읽었습니다.")
    st.dataframe(actuals, hide_index=True)
    left, right = st.columns([1, 4])
    left.button("매출 전망 보기 →", type="primary", on_click=go_to, args=(PAGE_REPORT,))
    right.button("업로드한 파일 지우기", on_click=clear_upload)


def clear_upload() -> None:
    """버튼 콜백: 업로드한 확정 매출을 세션에서 지운다 (다시 업로드 전 상태로)."""
    st.session_state[KEY_ACTUALS] = None
    st.session_state[KEY_ACTUALS_NAME] = ""
    st.session_state[KEY_UPLOAD_SIGNATURE] = None
    st.session_state[KEY_UPLOAD_ERROR] = ""


# --- 02 매출 전망 -------------------------------------------------------------------------------
def save_report(row: dict) -> None:
    """버튼 콜백: 같은 분기, 같은 날, 같은 모드면 덮어쓰고 아니면 이력에 추가한다."""
    history = st.session_state[KEY_HISTORY]
    keys = ("분기", "실행일", "보기 모드")
    for index, saved in enumerate(history):
        if all(saved[key] == row[key] for key in keys):
            history[index] = row
            st.toast("같은 날 같은 분기 리포트를 덮어썼습니다.")
            return
    history.append(row)
    st.toast("리포트 이력에 저장했습니다. 사이드바 ‘리포트 이력’에서 확인하세요.")


def revenue_chart(actuals, forecast: dict, target_quarter: str, target_actual: dict | None):
    """분기 확정 매출 막대 + 대상 분기 추정(막대와 범위) + (검증 모드) 확정 매출 점.

    원 → 조 원 변환은 pandas가 아니라 차트 표시 설정(Vega transform_calculate)에서만 한다.
    """
    to_trillion = "datum.revenue_krw / 1e12"
    actual_bars = (
        alt.Chart(actuals)
        .transform_filter(f"datum.quarter < '{target_quarter}'")
        .transform_calculate(trillion=to_trillion)
        .mark_bar(color=COLOR_ACTUAL_BAR, cornerRadiusTopLeft=2, cornerRadiusTopRight=2)
        .encode(
            x=alt.X("quarter:N", title=None, sort="ascending", axis=alt.Axis(labelAngle=-45)),
            y=alt.Y("trillion:Q", title="조 원"),
            tooltip=[alt.Tooltip("quarter:N", title="분기"), alt.Tooltip("trillion:Q", title="확정 매출(조 원)", format=".1f")],
        )
    )
    layers = [actual_bars]
    if forecast["status"] == forecaster.FORECAST_STATUS_OK:
        estimate = alt.Data(values=[{
            "quarter": target_quarter,
            "estimate_krw": forecast["estimate_krw"],
            "lower_krw": forecast["lower_krw"],
            "upper_krw": forecast["upper_krw"],
        }])
        base = alt.Chart(estimate).transform_calculate(
            est="datum.estimate_krw / 1e12", low="datum.lower_krw / 1e12", high="datum.upper_krw / 1e12"
        )
        layers += [
            base.mark_bar(color=COLOR_ESTIMATE, opacity=0.9).encode(
                x=alt.X("quarter:N", sort="ascending"), y="est:Q",
                tooltip=[alt.Tooltip("est:Q", title="추정(조 원)", format=".1f"),
                         alt.Tooltip("low:Q", title="하한", format=".1f"), alt.Tooltip("high:Q", title="상한", format=".1f")],
            ),
            base.mark_rule(color="#1E2533", strokeWidth=1.5).encode(x=alt.X("quarter:N", sort="ascending"), y="low:Q", y2="high:Q"),
        ]
    if target_actual is not None:
        point = alt.Data(values=[{"quarter": target_quarter, "revenue_krw": target_actual["revenue_krw"]}])
        layers.append(
            alt.Chart(point).transform_calculate(trillion=to_trillion)
            .mark_point(color=COLOR_CHECK_POINT, filled=True, size=110)
            .encode(x=alt.X("quarter:N", sort="ascending"), y="trillion:Q",
                    tooltip=[alt.Tooltip("trillion:Q", title="확정 매출(조 원)", format=".1f")])
        )
    return alt.layer(*layers).properties(height=300)


def exports_chart(exports, start_ym: str):
    """이천·청주 월별 수출 쌓은 막대 (start_ym부터 = backend.exports_chart_table과 같은 최근 25개월).

    달러 → 억 달러 변환과 같은 달, 같은 지역 합계는 차트 표시 설정(Vega)에서만 한다.
    """
    return (
        alt.Chart(exports)
        .transform_filter(f"datum.ym >= '{start_ym}'")
        .transform_calculate(eok="datum.export_usd / 1e8")
        .mark_bar()
        .encode(
            x=alt.X("ym:O", title=None, axis=alt.Axis(labelAngle=-45)),
            y=alt.Y("sum(eok):Q", title="억 달러"),
            color=alt.Color("region:N", title=None, sort=["이천시", "청주시"],
                            scale=alt.Scale(domain=["이천시", "청주시"], range=[COLOR_ICHEON, COLOR_CHEONGJU]),
                            legend=alt.Legend(orient="top")),
            order=alt.Order("region:N", sort="ascending"),
            tooltip=[alt.Tooltip("ym:O", title="월"), alt.Tooltip("region:N", title="지역"),
                     alt.Tooltip("sum(eok):Q", title="수출(억 달러)", format=".1f")],
        )
        .properties(height=300)
    )


def page_report(target_quarter: str) -> None:
    actuals = st.session_state[KEY_ACTUALS]
    if actuals is None:
        st.title(PAGE_REPORT)
        st.info("먼저 확정 분기 매출 CSV를 업로드해 주세요. ‘데이터 업로드’에서 파일을 올리면 이 화면에 리포트가 표시됩니다.")
        st.button("데이터 업로드로 이동", on_click=go_to, args=(PAGE_UPLOAD,))
        st.stop()

    check_mode = st.session_state.get(KEY_MODE) == MODE_CHECK and target_quarter != backend.default_target_quarter()
    try:
        result = run_report(target_quarter, actuals, st.session_state[KEY_UPLOAD_SIGNATURE], data_version())
    except (ValueError, FileNotFoundError) as exc:
        st.error(f"리포트를 만들 수 없습니다: {exc}")
        st.stop()

    forecast, facts = result["forecast"], result["facts"]
    anomaly, consistency, guidance = result["anomaly"] or {}, result["consistency"] or {}, result["guidance"] or {}
    is_ok = forecast["status"] == forecaster.FORECAST_STATUS_OK
    year, number = target_quarter[:4], target_quarter[-1]
    months = forecast["months_available"]

    # 헤더
    badges = '<span class="alt-badge mock">MOCK 모드 · LLM 가짜 응답</span>' if llm_module.USE_MOCK else ""
    if check_mode:
        badges = '<span class="alt-badge check">지난 분기 검증</span>' + badges
    sub = "사후 검증" if check_mode else "자동 선택"
    st.markdown(
        f'<div class="alt-hero"><div class="eyebrow">ALT / EARNINGS INTELLIGENCE</div>'
        f'<h1>실적 전망 및 주가 영향 리포트{badges}</h1>'
        f'<div class="meta">SK하이닉스 | {year}년 {number}분기 ({sub}) | 기준일 {result["as_of"]} | '
        f'수출 반영 {months}/3개월{f" (최근 {result["anomaly_ym"]})" if result["anomaly_ym"] else ""}</div></div>',
        unsafe_allow_html=True,
    )

    # 핵심 결론 + 저장 버튼
    left, right = st.columns([5, 1.3], vertical_alignment="center")
    with left:
        if check_mode and result["target_actual"] is not None:
            text = f'추정 {shown(facts["estimate"])} (범위 {shown(facts["range"])}) · 확정 {result["target_actual"]["revenue_text"]}'
            st.markdown(f'<div class="alt-concl check"><small>검증 요약</small><div>{text}</div></div>', unsafe_allow_html=True)
        elif is_ok:
            direction = consistency.get("forecast_direction") or "방향 판단 불가"
            status = consistency.get("status", forecaster.CONSISTENCY_UNKNOWN)
            guide = "비교 판단불가 (컨콜 자료 없음)" if status == forecaster.CONSISTENCY_UNKNOWN else status
            text = f"매출 전분기 대비 {direction} 전망 · 컨콜 가이던스와 {guide}"
            st.markdown(f'<div class="alt-concl"><small>핵심 결론</small><div>{text}</div></div>', unsafe_allow_html=True)
        else:
            st.warning(result["brief"])  # no_data, insufficient_history 안내 문장 (generate_brief가 만듦)
    with right:
        row = {
            "분기": target_quarter, "실행일": result["as_of"], "보기 모드": MODE_CHECK if check_mode else MODE_NOW,
            "예상 매출": facts["estimate"], "예상 범위": facts["range"], "직전 분기 대비": facts["qoq"],
            "반영 개월": f"{months}/3", "이상치": facts["anomaly"], "가이던스": facts["consistency"],
            "상태": forecast["status"],
        }
        st.button("리포트 이력에 저장", on_click=save_report, args=(row,), width="stretch")

    # 검증 모드: 추정 vs 확정
    if check_mode:
        st.subheader("추정 vs 확정 매출")
        st.caption("현재 저장된 자료로 다시 계산한 값입니다. 대상 분기와 그 이후 실적은 계산에 쓰지 않습니다.")
        c1, c2, c3 = st.columns(3)
        c1.metric("우리 추정 (중앙값)", shown(facts["estimate"]), help=f"범위 {shown(facts['range'])}")
        if result["target_actual"] is not None:
            c2.metric("확정 매출 (업로드 CSV)", result["target_actual"]["revenue_text"],
                      help=f"잠정실적 공시일 {result['target_actual']['announced_date']}")
        else:
            c2.info(f"업로드한 CSV에 {target_quarter} 확정 매출이 없습니다.")
        with c3:
            placeholder_card("추정 오차율", "— %", "|추정 − 확정| ÷ 확정 · backend 함수 추가 후 표시")

    # 매출 전망 지표: 왼쪽 우리 추정, 오른쪽 컨센서스 자리
    st.subheader("매출 전망 지표")
    ours, market = st.columns(2)
    with ours:
        st.metric("예상 매출 (중앙값)", shown(facts["estimate"]),
                  delta=f'{facts["qoq"]} 전분기 대비' if shown(facts["qoq"]) != "—" else None,
                  help="수출 × 과거 4개 분기 매출/수출 비율 × 환율")
        st.metric("예상 범위 (하한 ~ 상한)", shown(facts["range"]), help="기준 분기 비율의 최솟값 ~ 최댓값 적용")
    with market:
        render_consensus(None)

    # 수출 신호 지표
    st.subheader("수출 신호 지표")
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        placeholder_card("수출 증가율 · 직전 분기 대비", "—", "backend 함수 추가 후 표시", pill="준비 중")
    z_score = anomaly.get("z_score")
    s2.metric("수출 이상치 판정", shown(facts["anomaly"]),
              delta=f'{facts["export_yoy"]} 전년 동월 대비' if shown(facts["export_yoy"]) != "—" else None,
              help=f"판정 월 {result['anomaly_ym']} · z = {z_score:.2f} (기준 ±{backend.DEFAULT_ANOMALY_THRESHOLD})"
              if isinstance(z_score, float) else "판정에 필요한 25개월 자료가 부족합니다")
    s3.metric("반영된 수출 개월", f"{months} / 3",
              help="남은 달은 공표 전이라 3개월로 환산해 추정합니다" if months < 3 else "3개월 수출이 모두 반영됐습니다")
    s4.metric("가이던스 일치 여부", shown(facts["consistency"]),
              help=f'예측 {consistency.get("forecast_direction") or "-"} · 가이던스 {consistency.get("guidance_direction") or "-"} (D램 기준)')

    # 주가 영향 판단 자리
    st.subheader("주가 영향 판단")
    p1, p2, p3 = st.columns(3)
    with p1:
        placeholder_card("업종 펀더멘털 점수", "— / 100", "메모리 가격·수요·재고 지표 가중 합산 (예정)", pill="준비 중")
    with p2:
        placeholder_card("주가 영향 방향", "—", "긍정 / 중립 / 부정 (예정)", pill="준비 중")
    with p3:
        placeholder_card("판단 신뢰도", "— %", "신뢰도 점수이며 주가 상승 확률이 아님 (예정)", pill="준비 중")

    # 차트
    st.subheader("차트")
    chart_left, chart_right = st.columns([1.25, 1])
    with chart_left:
        st.markdown("**이천·청주 월별 메모리 수출 추이**")
        recent = backend.exports_chart_table(result["exports"])  # 최근 25개월 (index = ym)
        if len(recent) == 0:
            st.info("저장된 수출 자료가 없습니다. 담당자가 `python backend.py`로 data/exports.csv를 만들어야 합니다.")
        else:
            st.altair_chart(exports_chart(result["exports"], recent.index[0]), use_container_width=True)
            st.caption("HS 854232 · 최근 25개월 = 이상치 판정에 쓰는 기간(대상 월 + 직전 24개월)")
    with chart_right:
        st.markdown("**분기 매출 추이와 대상 분기 추정**")
        st.altair_chart(revenue_chart(actuals, forecast, target_quarter, result["target_actual"] if check_mode else None),
                        use_container_width=True)
        st.caption("회색: 확정 매출(업로드 CSV) · 초록: 추정과 범위" + (" · 빨간 점: 확정 매출" if check_mode else ""))

    # 근거와 위험요인
    st.subheader("판단 근거와 위험요인")
    basis_col, risk_col = st.columns(2)
    with basis_col, st.container(border=True):
        st.markdown("**추정 근거**")
        price = guidance.get("price_outlook", "NA")
        transcript = result["transcript_file"] or "없음"
        st.markdown(
            f"- 적용 비율 **{shown(facts['ratio'])}** (최근 4개 분기 달러 매출 ÷ 수출 평균)\n"
            f"- 대상 분기 수출 **{shown(facts['months'])}** 반영" + (" → 3개월로 환산\n" if months < 3 else "\n") +
            f"- 이천·청주 수출 전년 동월 대비 **{shown(facts['export_yoy'])}** ({shown(facts['anomaly'])})\n"
            f"- 직전 분기 컨콜 가격 전망 **{price}** (파일: {transcript})"
        )
    with risk_col, st.container(border=True):
        st.markdown("**주요 위험요인**")
        st.markdown("\n".join(f"- **{title}**: {detail}" for title, detail in RISKS))

    with st.container(border=True):
        st.markdown("**요약 브리프**")
        st.write(result["brief"] if is_ok else "추정 결과가 없어 브리프를 만들지 않았습니다.")
        if llm_module.USE_MOCK:
            st.caption("[MOCK] 표시는 실제 LLM이 아닌 가짜 응답이라는 뜻입니다 (ANTHROPIC_API_KEY 없음).")

    # 데이터 원본
    st.subheader("분석에 사용한 데이터")
    tab_actuals, tab_quarterly, tab_exports = st.tabs(["업로드한 확정 매출", "분기 집계", "월별 수출"])
    with tab_actuals:
        st.dataframe(actuals, hide_index=True)
    with tab_quarterly:
        st.dataframe(backend.quarterly_display_table(result["quarterly"]), hide_index=True)
    with tab_exports:
        st.dataframe(backend.exports_display_table(result["exports"]), hide_index=True)

    st.info(f"**{backend.DISCLAIMER}** 주가 영향 판단은 상승이나 수익을 보장하지 않습니다.")


# --- 03 리포트 이력 -----------------------------------------------------------------------------
def clear_history() -> None:
    st.session_state[KEY_HISTORY] = []


def page_history() -> None:
    st.title(PAGE_HISTORY)
    st.caption("‘매출 전망’에서 저장한 리포트가 이 세션 동안 쌓입니다. 같은 분기·같은 날·같은 모드는 덮어씁니다.")
    history = st.session_state[KEY_HISTORY]
    if not history:
        st.info("저장된 리포트가 없습니다. ‘매출 전망’ 화면의 ‘리포트 이력에 저장’을 눌러 주세요.")
        if st.session_state[KEY_ACTUALS] is not None:
            st.button("매출 전망으로 이동", on_click=go_to, args=(PAGE_REPORT,))
        return
    st.dataframe(history, hide_index=True)
    st.button("이력 비우기", on_click=clear_history)


# --- 진입점 -----------------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="ALT 매출 전망", layout="wide", initial_sidebar_state="expanded")
    st.markdown(CSS, unsafe_allow_html=True)
    init_session_state()
    page, target_quarter = render_sidebar()
    if page == PAGE_UPLOAD:
        page_upload()
    elif page == PAGE_REPORT:
        page_report(target_quarter)
    else:
        page_history()


main()
