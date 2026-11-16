"""알트(ALT) 대시보드: 11주차 Streamlit 화면.

실행: week11 폴더 안에서 streamlit run app.py

이 파일은 처음부터 끝까지 돌아가는 골격이다. 네 구역 함수가 이미 최소한으로 동작하므로
각 담당자는 다른 사람의 구현을 기다리지 않고 자기 함수의 본문만 바꾸면 된다.
각 함수 docstring의 '계약'은 다른 구역이 믿고 쓰는 약속이라, 바꾸려면 팀과 먼저 합의한다.

[팀 규칙]
1. 자기 구역만 고친다: 자기 함수의 본문과 docstring, 그리고 자기 함수 바로 아래에 둘 _로 시작하는 보조 함수.
   def 줄(함수 이름, 매개변수)과 맨 아래 '실행 순서' 구역은 바꾸지 않는다.
2. 데이터 가공은 backend 함수 호출로만 한다. 이 파일에서 pandas를 import하지 않는다.
3. 맨 위 import 줄은 여럿이 고치면 충돌이 나므로, 새 import가 필요하면 팀 채팅에 먼저 말한다.
4. 위젯 key와 session_state 키는 자기 구역 접두어로 시작한다: upload_, forecast_, exports_, details_
   (같은 key가 두 번 그려지면 DuplicateWidgetID 오류가 난다)
"""

import streamlit as st

import backend

st.set_page_config(page_title="알트(ALT) 대시보드", layout="wide")
st.title("알트(ALT): SK하이닉스 분기 매출 나우캐스팅")
st.caption(backend.DISCLAIMER)


# =============================================================================
# A. 업로드와 입력 방어 (담당: 조현모)
# =============================================================================
def load_upload() -> dict:
    """수출 CSV를 받아 backend로 정제하고, 다른 구역이 쓸 업로드 결과를 돌려준다.

    계약 (B, C, D 구역이 이 모양을 믿고 개발한다):
        반환 dict
            key (tuple): (파일 이름, 파일 크기). 같은 파일인지 알아보는 값
            raw (DataFrame): backend.read_uploaded_csv 결과. 올린 원본 그대로(모든 값 문자열)
            imported (dict): backend.import_exports 결과. exports(DataFrame), raw_rows, clean_rows, added(int)
        업로드 전이거나 처리할 수 없는 파일이면 반환하지 않고 st.stop()으로 멈춘다.

    구현 메모:
        - session_state의 upload_key, upload_result에 마지막으로 처리한 파일의 key와 결과를 둔다.
          사이드바 필터를 움직이면 스크립트 전체가 다시 실행되는데, 그때마다 같은 CSV를 다시 정제하고
          data/exports.csv에 다시 저장하지 않기 위해서다. 새 파일(key가 다름)일 때만 정제, 저장한다.
        - 처리할 수 없는 파일은 backend가 ValueError로 알린다(필수 열 누락, 월이나 지역 형식 오류, 빈 파일,
          읽을 수 없는 인코딩, CSV 형식 오류). 그 파일은 저장되지 않으므로 원인과 고치는 방법을 보여 주고 멈춘다.
          그 밖의 예외는 코드 실수일 수 있어 잡지 않는다.
    """
    st.subheader("수출 자료 업로드")
    if "upload_key" not in st.session_state:  # 초기화 관용구: 세션에서 처음 한 번만 만든다
        st.session_state.upload_key = None
        st.session_state.upload_result = None

    uploaded = st.file_uploader(
        "시군구별 수출 CSV를 끌어다 놓으세요",
        type="csv",
        key="upload_file",
        help="관세청 시군구별 품목별 수출입실적 원자료(priodTitle, sggNm, expUsdAmt 열) 또는 "
        "같은 내용을 한글 열 이름(기간, 시군구, 수출금액)으로 담은 CSV. UTF-8과 cp949(엑셀 기본)를 읽습니다.",
    )
    if uploaded is None:
        st.info(
            "**이천시, 청주시의 메모리 반도체(HS 854232) 월별 수출 CSV를 올리면 분석이 시작됩니다.**\n\n"
            "| 필요한 열 | 관세청 원자료 이름 | 한글 이름 예 |\n"
            "|---|---|---|\n"
            "| 월 | priodTitle (예: 2026.08) | 기간, 년월 |\n"
            "| 지역 | sggNm (예: 경기도 이천시) | 시군구, 지역 |\n"
            "| 수출금액 | expUsdAmt (천 달러) | 수출금액, 수출금액(천달러) |\n\n"
            "품목 코드(hsSgn)와 수집일(collected_at)은 없어도 됩니다. "
            "예시 파일은 `samples/exports_normal.csv`이고, 원자료는 공공데이터포털의 "
            "'관세청_시군구별 품목별 수출입실적'에서 받을 수 있습니다."
        )
        st.stop()

    upload_key = (uploaded.name, uploaded.size)
    if st.session_state.upload_key != upload_key:  # 새 파일일 때만 정제하고 저장한다
        try:
            raw = backend.read_uploaded_csv(uploaded)  # UTF-8로 못 읽으면 seek(0) 후 cp949로 다시 읽는다
            imported = backend.import_exports(raw)
        except ValueError as exc:
            _show_upload_error(uploaded.name, exc)
            st.stop()
        st.session_state.upload_result = {"key": upload_key, "raw": raw, "imported": imported}
        st.session_state.upload_key = upload_key

    upload = st.session_state.upload_result
    imported = upload["imported"]
    if imported["clean_rows"] == 0:
        stored_note = (
            "아래 화면은 이전에 저장된 수출 자료로 그립니다."
            if len(imported["exports"]) > 0
            else "저장된 수출 자료도 없어 아래 지표와 차트가 비어 있을 수 있습니다."
        )
        st.warning(
            f"{uploaded.name}에는 이천시, 청주시의 메모리 반도체(HS 854232) 행이 없어 새로 반영된 자료가 없습니다. "
            + stored_note
        )
    else:
        st.caption(
            f"{uploaded.name}: {imported['raw_rows']:,}행 중 {imported['clean_rows']:,}행을 저장된 수출 자료에 반영했습니다."
        )
    return upload


_UPLOAD_ERROR_HINTS = {
    "필수 열 누락": "첫 줄의 열 이름에 월(priodTitle 또는 기간), 지역(sggNm 또는 시군구), "
    "수출금액(expUsdAmt 또는 수출금액)이 모두 있는지 확인해 주세요. 괄호 안 '원자료 열'이 이 파일에서 읽은 열입니다.",
    "월 형식 오류": "월 값은 2026.08, 2026-08, 202608처럼 연도 4자리와 월이 함께 있어야 합니다.",
    "지역 형식 오류": "지역 열에 '경기도 이천시', '충청북도 청주시'처럼 이천시나 청주시 행이 있는지 확인해 주세요.",
    "빈 파일": "파일이 비어 있습니다. 내려받기가 끝난 파일인지 확인해 주세요.",
    "인코딩 오류": "엑셀에서 '다른 이름으로 저장 > CSV UTF-8(쉼표로 분리)'로 다시 저장해 주세요.",
    "CSV 형식 오류": "쉼표로 구분된 CSV인지 확인해 주세요. 엑셀 파일(.xlsx)의 확장자만 바꾼 파일은 읽을 수 없습니다.",
}


def _show_upload_error(file_name: str, exc: ValueError) -> None:
    """처리할 수 없는 CSV의 원인 한 줄과 고치는 방법을 보여 준다 (backend 메시지 앞머리로 안내를 고른다)."""
    message = str(exc)
    hint = next(
        (text for prefix, text in _UPLOAD_ERROR_HINTS.items() if message.startswith(prefix)),
        "파일 내용과 형식을 확인해 주세요.",
    )
    st.error(f"**{file_name}** 파일을 처리하지 못했습니다.\n\n원인: {message}", icon="🚫")
    st.markdown(f"- 고치는 방법: {hint}\n- 이 파일의 내용은 저장하지 않았습니다. 고친 파일을 다시 올려 주세요.")


# =============================================================================
# B. 매출 예측 (담당: 신동훈)
# =============================================================================
def render_forecast(upload: dict) -> dict | None:
    """대상 분기를 고르게 하고 예측을 실행해 핵심 지표를 보여 준다.

    계약:
        upload: load_upload()의 반환값
        반환: backend.run_forecast의 결과 dict (D 구역이 브리프와 표에 쓴다). 예측을 실행하지 못했으면 None

    담당자가 할 일 (지금 본문은 임시 최소 구현):
        - 사이드바 selectbox(대상 분기): 목록은 backend.list_target_quarters(), 기본값은 backend.default_target_quarter()
        - st.metric 2개 이상: result["facts"]의 estimate, range, qoq, months 등 (이미 표시용 문자열)
        - result["status"]가 "ok"가 아니면 숫자 대신 result["brief"]의 안내 문장을 보여 준다
        - run_forecast의 ValueError, FileNotFoundError(actuals.csv 문제)는 st.error로 보여 주고 None을 돌려준다
        - (선택) 같은 분기, 같은 업로드면 다시 실행하지 않도록 session_state에 보관. 넣었다면 README 담당에게 이유를 알린다
    """
    result = backend.run_forecast(backend.default_target_quarter())
    st.metric("예상 매출", result["facts"]["estimate"])
    return result


# =============================================================================
# C. 수출 현황 (담당: 신해성)
# =============================================================================
def render_exports(upload: dict) -> None:
    """업로드 결과 지표와 이천시, 청주시 월별 수출 차트를 보여 준다.

    계약:
        upload: load_upload()의 반환값. 차트 자료는 upload["imported"]["exports"] (저장된 자료와 합친 전체 표)

    담당자가 할 일 (지금 본문은 임시 최소 구현):
        - st.metric 2개 이상: upload["imported"]의 raw_rows(올린 행), clean_rows(정제 후 남은 행), added(새로 늘어난 행)
        - 사이드바 slider(차트 기간, 개월): backend.exports_chart_table(exports, last_months=값)에 넘긴다
        - 사이드바 multiselect(지역): st.line_chart(표, y=고른 지역)으로 그릴 지역을 고른다
        - 차트 자료가 없거나 지역을 하나도 고르지 않았을 때 안내
    """
    st.line_chart(backend.exports_chart_table(upload["imported"]["exports"]))


# =============================================================================
# D. 브리프와 상세 표 (담당: 이다현)
# =============================================================================
def render_details(upload: dict, result: dict | None) -> None:
    """브리프와 원본, 정제, 분기 집계, 예측 이력 표를 보여 준다.

    계약:
        upload: load_upload()의 반환값
        result: render_forecast()의 반환값. None이면 예측에 딸린 부분(브리프, 분기 집계, 예측 이력)은 건너뛴다
    """
    st.subheader("브리프와 상세 자료")
    if result is None:
        st.info("예측을 실행하지 못해 브리프, 분기 집계, 예측 이력은 보여 줄 수 없습니다.")
    elif result["status"] == "ok":
        brief = result["brief"]
        with st.container(border=True):
            st.markdown(f"**{result['target_quarter']} 요약 브리프**")
            st.markdown(brief.replace("~", "\\~"))
            if brief.startswith("[MOCK]"):
                st.caption(
                    "[MOCK]은 ANTHROPIC_API_KEY가 없어 정해진 문장 틀로 만든 예시 문장이라는 표시입니다. "
                    "13주차에 실제 LLM 문장으로 바뀝니다."
                )

    tab_clean, tab_quarter, tab_history, tab_raw = st.tabs(["정제된 수출 자료", "분기 집계", "예측 이력", "올린 원본 CSV"])
    
    with tab_clean:
        st.caption("이천시, 청주시 HS 854232 월별 수출입니다. 저장돼 있던 자료와 이번 업로드를 합친 전체입니다.")
        st.dataframe(backend.exports_display_table(upload["imported"]["exports"]), hide_index=True)
        
    with tab_quarter:
        if result is None:
            st.info("예측 결과가 없어 분기 집계를 보여 줄 수 없습니다.")
        else:
            st.caption("두 지역 수출이 모두 있는 달만 더한 분기 합계와, 그 분기의 평균 환율입니다.")
            st.dataframe(backend.quarterly_display_table(result["quarterly"]), hide_index=True)
            
    with tab_history:
        if result is None:
            st.info("예측 결과가 없어 예측 이력을 보여 줄 수 없습니다.")
        else:
            st.caption(f"{result['target_quarter']} 예측을 언제 어떻게 했는지 보여 줍니다. 같은 날 다시 실행하면 그날 값은 덮어씁니다.")
            st.dataframe(backend.history_display_table(result["history"]), hide_index=True)
            
    with tab_raw:
        st.caption("올린 CSV를 가공하지 않고 그대로 보여 줍니다. 다른 지역, 다른 품목 행도 들어 있습니다.")
        st.dataframe(upload["raw"], column_config=_raw_column_labels(upload["raw"]), hide_index=True)


_RAW_LABELS = {
    "priodTitle": "기간",
    "sggNm": "시군구",
    "hsSgn": "HS 코드",
    "korePrlstNm": "품목명",
    "expCnt": "수출 건수",
    "expUsdAmt": "수출금액(천 달러)",
    "impCnt": "수입 건수",
    "impUsdAmt": "수입금액(천 달러)",
    "cmtrBlncAmt": "무역수지(천 달러)",
    "collected_at": "수집일",
}

def _raw_column_labels(raw: object) -> dict[str, str]:
    """원본 표의 열 중 알고 있는 관세청 열에만 '표시 이름 (원래 이름)'을 붙인다."""
    return {column: f"{label} ({column})" for column, label in _RAW_LABELS.items() if column in raw.columns}


# =============================================================================
# 실행 순서 (담당: 강민규). 각 구역 담당자는 이 아래를 고치지 않는다
# =============================================================================
upload = load_upload()
result = render_forecast(upload)
render_exports(upload)
render_details(upload, result)
