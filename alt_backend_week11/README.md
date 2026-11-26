# 알트(ALT) 11주차: 수출 CSV 업로드 대시보드

SK하이닉스 분기 매출 나우캐스팅 백엔드(10주차 통합본)에 Streamlit 화면을 입힌 프로토타입입니다. 관세청 시군구별 수출 CSV를 끌어다 놓으면 백엔드가 정제해서, 이천시와 청주시의 월별 수출 추이, 분기 매출 추정, 근거 표를 보여 줍니다.

## 실행 방법

모든 명령은 `alt_backend_week11` 폴더 안에서 실행합니다.

1. Python 3.10 이상에서 라이브러리를 설치합니다.
   ```bash
   pip install -r requirements.txt
   ```
2. `.env.example`을 `.env`로 복사하고 API 키를 넣습니다. `.env`는 커밋하지 않습니다. 키가 없어도 업로드, 차트, 표는 동작합니다.
3. 예측 숫자를 보려면 환율 자료(`data/fx.csv`)가 필요합니다. ECOS 키가 있으면 `python backend.py`를 한 번 실행해 받고, 없으면 팀에서 공유한 `fx.csv`를 `data/`에 넣습니다.
4. 앱을 실행합니다. `python app.py`가 아니라 `streamlit run`으로 실행해야 화면이 뜹니다.
   ```bash
   streamlit run app.py
   ```
5. 브라우저(기본 http://localhost:8501)가 열리면 `samples/exports_normal.csv`를 업로드 창에 끌어다 놓습니다.

## 올릴 수 있는 CSV

- 관세청 원자료 형식(`priodTitle`, `sggNm`, `hsSgn`, `expUsdAmt` 등) 또는 같은 내용을 한글 열 이름(`기간`, `시군구`, `품목코드`, `수출금액`)으로 담은 CSV
- 꼭 있어야 하는 열은 월, 지역, 수출금액 3개입니다. 품목코드 열이 없으면 HS 854232로 봅니다.
- UTF-8 파일과 엑셀 기본 CSV(cp949) 파일을 모두 읽습니다. UTF-8로 읽다 실패하면 `seek(0)`으로 처음으로 되돌린 뒤 cp949로 다시 읽습니다.
- 이천시, 청주시의 HS 854232 행만 반영하고, 다른 지역이나 품목 행은 원본 표에만 보입니다.
- 반영한 자료는 `data/exports.csv`에 합쳐 저장합니다. 같은 달이 이미 있으면 새 값으로 바뀝니다.
- 열이 빠지는 등 처리할 수 없는 파일은 저장하지 않고, 화면에 원인과 고치는 방법을 보여 줍니다.

## 화면 구성과 담당

| 구역 | app.py 함수 | 화면 | 담당 |
|---|---|---|---|
| A. 업로드와 입력 방어 | `load_upload()` | 업로드 창, 업로드 전 안내(필요한 열 표), 반영 결과 한 줄, 처리할 수 없는 CSV의 원인과 고치는 방법 | 조현모 |
| B. 매출 예측 | `render_forecast(upload)` | 사이드바 대상 분기 선택과 '최신 자료로 다시 예측' 버튼, 지표 4개(예상 매출, 예상 범위, 직전 분기 대비, 반영된 수출 개월), 이상치와 가이던스 판정 | 신동훈 |
| C. 수출 현황 | `render_exports(upload)` | 지표 4개(올린 행, 정제 후 반영된 행, 새로 추가된 행, 기존 행 갱신), 사이드바 차트 기간과 지역 선택, 이천시와 청주시 월별 선 그래프 | 신해성(차트), 조현모(업로드 지표) |
| D. 브리프와 상세 표 | `render_details(upload, result)` | 요약 브리프, 탭 4개(정제된 수출 자료, 분기 집계, 예측 이력, 올린 원본 CSV) | 이다현 |
| 골격과 통합 | 페이지 머리, 실행 순서 | 화면 골격, PR 머지, 문서 | 강민규 |

## 과제 요구사항 대응

| 요구사항 | 구현 위치 |
|---|---|
| `st.file_uploader`로 CSV 업로드, 업로드 전 안내 후 `st.stop()` | A `load_upload()` |
| cp949 파일도 오류 없이 처리 (seek(0) 재시도) | `backend.read_uploaded_csv`를 A에서 호출 |
| 데이터 가공은 backend 함수 호출로만 | app.py에 pandas import 없음 (아래 'UI와 백엔드의 분리') |
| 사이드바 필터 1개 이상, 즉시 반영 | 대상 분기(B), 차트 기간과 지역(C) |
| `st.metric` 2개 이상, 차트 1개 이상, `st.dataframe` 원본 표 | 지표 8개(B 4개, C 4개), 월별 선 그래프(C), '올린 원본 CSV' 탭(D) |
| `st.session_state` 사용과 설명 | 아래 'session_state 사용' |

## UI와 백엔드의 분리

`app.py`는 pandas를 import하지 않고, 입력을 받아 `backend.py`의 함수에 넘긴 뒤 돌려받은 결과를 그리기만 합니다. 정제, 분기 집계, 매출 추정은 `hynix_nowcast/` 모듈이 하고, 화면에 쓰는 표시용 문자열과 표도 backend가 만듭니다.

| app.py가 부르는 backend 함수 | 하는 일 |
|---|---|
| `read_uploaded_csv` | 업로드 파일을 UTF-8, 실패하면 cp949로 읽기 |
| `import_exports` | 정제해서 저장된 수출 자료와 합치고 저장. 이번 업로드에서 추가된 행과 기존 키를 갱신한 행 수를 반환 |
| `list_target_quarters`, `default_target_quarter` | 분기 선택 목록과 기본 분기 |
| `run_forecast` | 대상 분기 매출 추정, 이상치 판정, 브리프 |
| `exports_chart_table` | 이천시, 청주시 월별 수출 차트용 표(억 달러) |
| `exports_display_table`, `quarterly_display_table`, `history_display_table` | 화면 표시용 표 |

## session_state 사용

Streamlit은 사이드바 필터를 하나만 움직여도 `app.py` 전체를 처음부터 다시 실행하므로, 일반 변수만 쓰면 같은 CSV를 매번 다시 정제해 `data/exports.csv`에 저장하고 예측도 매번 다시 실행합니다(예측 이력 기록과, 키가 있으면 LLM 호출까지 반복). 그래서 처리한 업로드 결과와 예측 결과를 `st.session_state`에 보관하고, 새 파일이 올라오거나 분기를 바꿀 때만 다시 계산합니다. 모든 키는 `if "키" not in st.session_state:` 관용구로 세션에서 처음 한 번만 초기화합니다.

| 키 | 구역 | 담는 값 | 쓰는 이유 |
|---|---|---|---|
| `upload_key`, `upload_result` | A | 마지막으로 처리한 파일의 (이름, 크기)와 정제 결과 | 같은 파일이면 다시 정제, 저장하지 않음 |
| `forecast_cache_key`, `forecast_result` | B | 마지막으로 예측한 (업로드, 분기)와 예측 결과 | 같은 업로드, 같은 분기면 다시 예측하지 않음. data 폴더 파일을 바꿨을 때는 '최신 자료로 다시 예측' 버튼으로 새로 실행 |
| `exports_months`, `exports_regions` | C | 사이드바 차트 기간과 고른 지역 (위젯 key) | 처음 기본값을 정하고, 자료에 없는 지역이 선택에 남지 않게 정리 |

## 매출 추정 비율 규칙 (ratio_rule, 13주차 개선)

`estimate_revenue`는 "분기 수출 x 비율 x 환율"로 매출을 추정합니다. 비율 = (매출 / 환율) / 이천·청주 HS 854232 수출이고, 기준 분기 4개(`RATIO_WINDOW`)로 대상 분기에 쓸 비율을 정합니다.

| ratio_rule | 적용 비율 | 비고 |
|---|---|---|
| `avg` | 기준 분기 비율 4개의 평균 | 12주차까지의 방식 |
| `last` | 가장 최근 기준 분기의 비율 | |
| `drift` (기본값) | 최근 비율 x exp(기준 분기 사이 로그 비율 변화의 평균) | 비율 추세를 한 분기 연장 |

**바꾼 이유:** 비율이 2024~2025년 1.8~2.3에서 2026년 2.70 → 3.19 → 3.78로 계속 올라, 4개 분기 평균(`avg`)이 한두 분기씩 늦게 따라가며 2026년 추정이 매번 −34~−41% 낮았습니다.

**시점 기준 백테스트** (`python backtest_ratio_rule.py`, 샘플 수출 2024.01~2026.10, 각 달 수출은 다음 달 15일에 공개된다고 가정, 공개일 이전 환율·실적만 사용, 21개 시점):

| ratio_rule | MAPE | 편향(평균 오차) | 3개월 반영 시점 MAPE |
|---|---|---|---|
| avg | 20.6% | −14.9% | 18.2% |
| last | 14.7% | −12.3% | 11.9% |
| **drift** | **11.9%** | −10.1% | **8.6%** |

- 하한, 상한은 기준 비율 최솟값·최댓값과 적용 비율 중 최솟값·최댓값으로 정합니다(drift는 기준 비율 범위 밖으로 나갈 수 있음). `avg`에서는 예전과 같은 값입니다.
- **한계:** 독립 분기가 7개(2025Q1~2026Q3)뿐인 표본에서 고른 규칙이라 과최적화 위험이 있습니다. 비율 추세가 꺾인 2025Q3~Q4에는 drift 오차가 avg보다 컸습니다(3개월 반영 시점 −10.7%, −12.1%). 2026Q4 실적(2027년 1월 발표)으로 표본 밖 검증이 필요합니다.
- 예전 방식으로 되돌리려면 `forecaster.DEFAULT_RATIO_RULE = forecaster.RATIO_RULE_AVG`로 바꾸거나 `estimate_revenue(..., ratio_rule="avg")`로 부릅니다.
- `tests/test_ratio_rule.py`의 B02가 샘플 자료에서 drift MAPE < avg MAPE인지 확인해 정확도 후퇴를 막습니다.

## 검증, 과정 기록, 알려진 문제

- 수동 검증 기록(① 정상 CSV ② cp949 CSV ③ 컬럼 누락 CSV): manual_test_log.md
- AI 과정 기록: ai_log 폴더
- 보안 체크리스트: security_checklist.txt
- 테스트용 CSV: `samples/exports_normal.csv`(UTF-8), `samples/exports_cp949.csv`(cp949), `samples/missing_column.csv`(수출금액 열 삭제)

## alt_backend_week11 폴더 구성

| 경로 | 내용 |
|---|---|
| `app.py` | Streamlit 화면 (이번 주 작성) |
| `backend.py` | 백엔드 통합 파일. 10주차 `main.py`에서 이름만 바꿈 |
| `hynix_nowcast/` | 수집, 정제, 예측, LLM 모듈 |
| `prompts/` | LLM 프롬프트 |
| `data/` | `actuals.csv`, `transcripts/`. 실행하면 `exports.csv`, `fx.csv`, `forecasts.csv`, `raw_exports_last.csv`가 생기며 커밋하지 않음 |
| `samples/` | 수동 검증용 CSV |
| `backtest_ratio_rule.py` | ratio_rule별 시점 기준 백테스트 (MAPE 비교) |
| `requirements.txt` | 라이브러리 목록 (streamlit 포함) |
| `.env.example` | API 키 양식 (값은 비워 둠) |

---

## 백엔드 상세 (10주차 통합본)

아래는 10주차 백엔드 README입니다. 화면 없이 터미널에서 실행하는 방법과 데이터 규칙을 담고 있습니다.

관세청 수출 API와 한국은행 ECOS 환율 API 키만 넣으면 수집, 정제, 분기 집계, 매출 추정, 이상치 판정, 가이던스 비교, 브리프 작성까지 한 번에 실행됩니다.

### 파일 구성

| 경로 | 내용 |
|---|---|
| `backend.py` | 통합 실행(CLI)과 화면(app.py)이 `import backend`로 불러 쓸 단계 함수 |
| `hynix_nowcast/data_loader.py` | fetch_regional_exports(관세청), fetch_fx_rates(ECOS), load_actuals |
| `hynix_nowcast/preprocess.py` | clean_exports, upsert_records, aggregate_quarterly |
| `hynix_nowcast/forecaster.py` | estimate_revenue, detect_anomaly, compare_guidance |
| `hynix_nowcast/llm_module.py` | extract_guidance, generate_brief (LLM 호출은 `_call_llm` 한 곳) |
| `prompts/guidance_extraction.txt` | 컨콜 가이던스 추출 지시문 |
| `prompts/brief_generation.txt` | 개인투자자용 브리프 작성 지시문 |
| `data/actuals.csv` | 분기 확정 매출 (2024Q1~2026Q3) |
| `data/transcripts/` | 컨콜 정리 텍스트 `YYYYQn.txt` (선택, 작성법은 폴더 안 README) |
| `requirements.txt`, `.env.example` | 라이브러리 목록(pytest 포함), API 키 양식 |
| `pytest.ini` | 나중에 만들 테스트가 프로젝트 모듈을 바로 import하도록 경로 설정 |

### 백엔드 CLI 실행

1. Python 3.10 이상에서 `pip install -r requirements.txt`
2. `.env.example`을 `.env`로 복사하고 키를 넣습니다.
3. `python backend.py --check-api`로 키와 응답 형식을 먼저 확인하고(요청 2번), 문제가 없으면 `python backend.py`

| 명령 | 하는 일 | API 요청 수 |
|---|---|---|
| `python backend.py --check-api` | 키와 응답 형식만 확인 (관세청 경기도 2개월, ECOS 14일, 저장 안 함) | 관세청 1, ECOS 1 |
| `python backend.py` (첫 실행) | 2024-01부터 수출, 환율을 받은 뒤 두 지역 수출이 모두 있는 가장 최근 분기를 예측 | 관세청 6, ECOS 1 |
| `python backend.py` (두 번째부터) | 저장된 마지막 달의 3개월 전부터 이어 받고 예측 | 관세청 2, ECOS 1 |
| `python backend.py --no-refresh` | API 호출 없이 data/에 저장된 자료로만 예측 | 0 |
| `python backend.py --full-refresh` | 저장된 자료와 상관없이 2024-01부터 다시 수집 | 관세청 6, ECOS 1 |
| `python backend.py --quarter 2026Q3` | 대상 분기 지정 (다른 옵션과 같이 씀) | |
| `python backend.py --data-dir 다른폴더` | data 폴더 바꾸기 (환경변수 `ALT_DATA_DIR`도 가능) | |

- 관세청 요청 수 = 시도 2개(경기도, 충청북도) x 12개월 구간 수입니다. 실행이 끝나면 `API 호출: 관세청 n회, ECOS m회`가 출력됩니다.
- LLM은 키가 있을 때만 실행마다 최대 2번(브리프 1번, 컨콜 파일이 있으면 가이던스 1번) 부릅니다.
- 실행하면 `data/`에 exports.csv, fx.csv, forecasts.csv, raw_exports_last.csv(마지막으로 받은 관세청 원자료)가 생기고, 같은 날 다시 실행하면 그날 예측 이력은 덮어씁니다.
- 터미널 출력은 수출은 억 달러, 매출은 조 원, 환율은 소수 둘째 자리로 보여 줍니다. 계산과 CSV는 달러, 원 단위 숫자 그대로이고, 화면(app.py)에서도 `quarterly_display_table`, `history_display_table`, `exports_display_table`로 같은 표기를 쓸 수 있습니다.

| 키 | 받는 곳 | 없을 때 |
|---|---|---|
| `CUSTOMS_API_KEY` | 공공데이터포털 "관세청_시군구별 품목별 수출입실적" 활용신청 후 일반 인증키(Decoding) | 수출 갱신을 건너뛰고 경고 |
| `ECOS_API_KEY` | 한국은행 ECOS Open API 인증키 | 환율 갱신을 건너뛰고 경고 |
| `ANTHROPIC_API_KEY` | 13주차에 지급받는 키 | LLM은 mock으로 응답(문장 앞 `[MOCK]`) |

키가 있으면 실제 Claude API(`claude-sonnet-5-5`)를 부릅니다. 호출이 실패하면 `경고: LLM 호출 실패: ...`가 출력되고, 브리프는 정해진 문장 틀로, 가이던스는 parse_error로 이어집니다.

### 데이터 파일

- `data/actuals.csv`: SK하이닉스 실적발표(연결, K-IFRS)의 억 원 단위 매출을 원 단위로 옮겼습니다. 2024Q1부터 2025Q2까지의 공시일과 2024Q1부터 Q3까지의 매출은 DART 잠정실적 공시와 한 번 더 대조해 주세요. 새 분기 실적이 나오면 한 줄 추가합니다.
- `data/transcripts/`: 2026Q4를 예측할 때 `2026Q3.txt`(3분기 실적발표의 4분기 전망)를 읽습니다. 없으면 가이던스 비교만 "판단불가"가 됩니다.

### 관세청 응답 형식

- **실제 응답 필드:** priodTitle(기간), sggNm(시군구), hsSgn(HS 코드), korePrlstNm(품목명), expCnt, expUsdAmt(수출금액), impCnt, impUsdAmt, cmtrBlncAmt(무역수지). 이 중 priodTitle("2026.08"), sggNm("경기도 이천시"), hsSgn("854232"), expUsdAmt("3,650,354")를 씁니다.
- **금액 단위:** expUsdAmt는 천 달러 단위라 1,000배 해서 달러로 저장합니다(2026-08 이천시 3,650,354 = 36.5억 달러). 업로드 CSV의 금액 열 이름이 "수출금액(천달러)"여도 1,000배 합니다.
- **지역 표기:** "경기도 이천시"처럼 시도 이름이 붙어 와도 이천시, 청주시로 묶습니다. 청주시가 구 단위로 오면 구별 행을 더하고, 시 단위 행과 구 단위 행이 함께 오면 시 단위 행만 씁니다.
- **열이나 값을 못 읽으면:** `필수 열 누락: ... (원자료 열: ...)` 또는 `월 형식 오류: ... (값 예: ...)`처럼 실제 열 이름과 값 예시를 보여 주고 멈춥니다. 이때 `data/raw_exports_last.csv`에 받은 원자료가 남아 있으니 열어 보고 `preprocess.py`의 `RAW_COLUMN_CANDIDATES`나 `_parse_ym`을 고칩니다.
- **정제 규칙을 바꾼 뒤에는** `python backend.py --full-refresh`로 한 번 다시 받아야 저장된 예전 값과 섞이지 않습니다(이어 받기는 최근 몇 달만 바꿈).

### 11주차 변경

과제 제출물 이름(app.py, backend.py, requirements.txt)에 맞춰 main.py를 backend.py로 바꿨습니다. 함수와 동작은 같고, 명령만 `python main.py`에서 `python backend.py`로, import만 `import main`에서 `import backend`로 바뀝니다.
