# 알트(ALT) 백엔드: SK하이닉스 분기 매출 나우캐스팅

관세청 수출 API와 한국은행 ECOS 환율 API 키만 넣으면 수집, 정제, 분기 집계, 매출 추정, 이상치 판정, 가이던스 비교, 브리프 작성까지 한 번에 실행됩니다.

## 파일 구성

| 경로 | 내용 |
|---|---|
| `main.py` | 통합 실행(CLI)과 화면(app.py)이 그대로 import할 단계 함수 |
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

## 실행

1. Python 3.10 이상에서 `pip install -r requirements.txt`
2. `.env.example`을 `.env`로 복사하고 키를 넣습니다.
3. `python main.py --check-api`로 키와 응답 형식을 먼저 확인하고(요청 2번), 문제가 없으면 `python main.py`

| 명령 | 하는 일 | API 요청 수 |
|---|---|---|
| `python main.py --check-api` | 키와 응답 형식만 확인 (관세청 경기도 2개월, ECOS 14일, 저장 안 함) | 관세청 1, ECOS 1 |
| `python main.py` (첫 실행) | 2024-01부터 수출, 환율을 받은 뒤 두 지역 수출이 모두 있는 가장 최근 분기를 예측 | 관세청 6, ECOS 1 |
| `python main.py` (두 번째부터) | 저장된 마지막 달의 3개월 전부터 이어 받고 예측 | 관세청 2, ECOS 1 |
| `python main.py --no-refresh` | API 호출 없이 data/에 저장된 자료로만 예측 | 0 |
| `python main.py --full-refresh` | 저장된 자료와 상관없이 2024-01부터 다시 수집 | 관세청 6, ECOS 1 |
| `python main.py --quarter 2026Q3` | 대상 분기 지정 (다른 옵션과 같이 씀) | |
| `python main.py --data-dir 다른폴더` | data 폴더 바꾸기 (환경변수 `ALT_DATA_DIR`도 가능) | |

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

## 데이터 파일

- `data/actuals.csv`: SK하이닉스 실적발표(연결, K-IFRS)의 억 원 단위 매출을 원 단위로 옮겼습니다. 2024Q1~2025Q2의 공시일과 2024Q1~Q3 매출은 DART 잠정실적 공시와 한 번 더 대조해 주세요. 새 분기 실적이 나오면 한 줄 추가합니다.
- `data/transcripts/`: 2026Q4를 예측할 때 `2026Q3.txt`(3분기 실적발표의 4분기 전망)를 읽습니다. 없으면 가이던스 비교만 "판단불가"가 됩니다.

## 관세청 응답 형식

- **실제 응답 필드:** priodTitle(기간), sggNm(시군구), hsSgn(HS 코드), korePrlstNm(품목명), expCnt, expUsdAmt(수출금액), impCnt, impUsdAmt, cmtrBlncAmt(무역수지). 이 중 priodTitle("2026.08"), sggNm("경기도 이천시"), hsSgn("854232"), expUsdAmt("3,650,354")를 씁니다.
- **금액 단위:** expUsdAmt는 천 달러 단위라 1,000배 해서 달러로 저장합니다(2026-08 이천시 3,650,354 = 36.5억 달러). 업로드 CSV의 금액 열 이름이 "수출금액(천달러)"여도 1,000배 합니다.
- **지역 표기:** "경기도 이천시"처럼 시도 이름이 붙어 와도 이천시, 청주시로 묶습니다. 청주시가 구 단위로 오면 구별 행을 더하고, 시 단위 행과 구 단위 행이 함께 오면 시 단위 행만 씁니다.
- **열이나 값을 못 읽으면:** `필수 열 누락: ... (원자료 열: ...)` 또는 `월 형식 오류: ... (값 예: ...)`처럼 실제 열 이름과 값 예시를 보여 주고 멈춥니다. 이때 `data/raw_exports_last.csv`에 받은 원자료가 남아 있으니 열어 보고 `preprocess.py`의 `RAW_COLUMN_CANDIDATES`나 `_parse_ym`을 고칩니다.
- **정제 규칙을 바꾼 뒤에는** `python main.py --full-refresh`로 한 번 다시 받아야 저장된 예전 값과 섞이지 않습니다(이어 받기는 최근 몇 달만 바꿈).

## 나중에 파트별로 테스트할 때

모듈끼리 서로 import하지 않고, 파일 읽기와 쓰기는 main.py와 load_actuals만 하므로 함수 단위로 따로 테스트할 수 있습니다.
`tests/` 폴더에 `test_*.py`를 만들고 프로젝트 루트에서 `pytest`를 실행합니다(pytest.ini가 루트를 import 경로에 넣어 둠).

| 대상 | 방법 |
|---|---|
| fetch_regional_exports, fetch_fx_rates | `monkeypatch`로 `requests.get`을 가짜 응답으로 바꾸고 환경변수에 가짜 키를 넣음 |
| load_actuals | `tmp_path`에 CSV를 써서 읽음 |
| preprocess, forecaster 함수 | DataFrame, dict만 넣고 결과의 열, dtype, 정렬, 키를 확인 (API, 파일 필요 없음) |
| extract_guidance, generate_brief | 키 없이 실행하면 mock. 응답을 고정하려면 `monkeypatch`로 `llm_module._call_llm`을 바꿈 |
| main 단계 함수 | `tmp_path`를 data_dir로 넘기고 `requests.get`을 바꿈 |

## 조원 코드에서 바뀐 점

- 1차 통합 점검의 문제 15개를 모두 반영했습니다. 결정을 기다리던 6번(청주시 구 단위)은 구별 행을 합치도록, 7번(금액 단위)은 열 이름으로 환산하도록, hs_code는 854232만 남기도록 정했습니다(10단위 세부 코드는 6단위 행이 없을 때만 더함).
- clean_exports: 필수 열은 월, 지역, 수출액 3개이고 품목 코드, collected_at은 없어도 됩니다. 엑셀이 "2026.10"을 2026.1로 바꿔 저장한 월도 10월로 읽습니다.
- LLM: Sonnet 5.5에 맞춰 temperature를 빼고, thinking 블록을 건너뛰고 text 블록만 읽으며, 응답 앞뒤에 설명이 붙어도 JSON을 꺼냅니다. 키 유무로 mock과 실제 호출을 자동 전환하고 프롬프트는 prompts/로 분리했습니다.
- main: 데모 코드를 빼고, 기본 대상 분기를 자료가 있는 가장 최근 분기로 바꿨습니다.
- schema.md와 다른 부분(clean_exports 필수 열, 오류 메시지의 원자료 열 표시, USE_MOCK 자동 전환)은 팀 문서에도 반영해 주세요.
