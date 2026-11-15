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

    담당자가 할 일 (지금 본문은 임시 최소 구현):
        - 업로드 전: 어떤 CSV를 올리면 되는지 st.info로 안내한 뒤 st.stop()
        - cp949 파일: backend.read_uploaded_csv의 seek(0) 재시도로 읽히는지 확인
        - 잘못된 파일(필수 열 누락, 월이나 지역 형식 오류, 빈 파일): ValueError를 잡아 st.error로 안내하고 st.stop()
        - session_state: 같은 파일이면 다시 정제, 저장하지 않게 한다 (지금은 위젯을 만질 때마다 다시 함)
        - 정제 후 남은 행이 0개면 st.warning으로 안내
        - (backend) 필수 열 누락 메시지의 '원자료 열'에 올리지 않은 collected_at이 섞여 나오는 문제
    """
    uploaded = st.file_uploader("시군구별 수출 CSV를 끌어다 놓으세요", type="csv", key="upload_file")
    if uploaded is None:
        st.stop()
    raw = backend.read_uploaded_csv(uploaded)
    return {"key": (uploaded.name, uploaded.size), "raw": raw, "imported": backend.import_exports(raw)}


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

    담당자가 할 일 (지금 본문은 임시 최소 구현):
        - 브리프: result["brief"]. ANTHROPIC_API_KEY가 없으면 문장 앞에 [MOCK]이 붙는다는 것도 안내
        - st.dataframe 원본 표: upload["raw"] (과제 필수 항목)
        - 정제 표: backend.exports_display_table(upload["imported"]["exports"])
        - 분기 집계와 예측 이력: backend.quarterly_display_table(result["quarterly"]),
          backend.history_display_table(result["history"])
        - st.tabs나 st.expander로 화면 정리
    """
    st.dataframe(upload["raw"])


# =============================================================================
# 실행 순서 (담당: 강민규). 각 구역 담당자는 이 아래를 고치지 않는다
# =============================================================================
upload = load_upload()
result = render_forecast(upload)
render_exports(upload)
render_details(upload, result)
