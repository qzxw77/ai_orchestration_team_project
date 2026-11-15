# 11주차 화면(app.py) 공유 + 같이 정할 것들
---

## 1. 한눈에 보기

- `alt_backend_week11/` 폴더에 `app.py`를 두고, `import backend`로 통합 백엔드 함수를 불러 쓰는 구조예요.
- 사용자는 **확정 분기 매출 CSV(actuals) 하나만** 올려요. 수출과 환율은 `data/`에 저장된 파일을 읽기만 해요.
- 제 로컬(테스트용 가짜 수출·환율 데이터)에서 수동 검증 3종(정상 / cp949 / 컬럼 누락)은 모두 오류 없이 동작했어요.
- 화면 시안(HTML, 클릭해 볼 수 있어요)

### 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

`alt_backend_week11` 폴더에서 실행하고, 사이드바 `01 데이터 업로드`에 `samples/1_actuals_utf8.csv`를 끌어다 놓으면 돼요.

---

## 2. 화면 구성

| 사이드바 메뉴 | 내용 |
|---|---|
| 01 데이터 업로드 | 확정 매출 CSV 드래그 앤 드롭. 올리기 전에는 안내만 하고 `st.stop()` |
| 02 매출 전망 | 예상 매출과 범위, 수출 이상치, 반영 개월, 가이던스 일치, 차트 2개, 근거, 위험요인, 브리프, 사용한 데이터 표 |
| 03 리포트 이력 | "리포트 이력에 저장"으로 쌓은 목록 (세션 동안만 유지) |

- **사이드바 필터 = 보기 모드** (과제의 "사이드바 필터 1개 이상" 요구를 이걸로 충족해요)
  - **이번 분기 전망(기본):** 대상 분기를 `default_target_quarter()`로 자동 선택해요. 사용자가 분기를 고르지 않아요.
  - **지난 분기 검증:** 과거 분기를 골라 "우리 추정 vs 확정 매출"을 나란히 보여 줘요. 모델 신뢰도를 보여 주는 용도예요.
- **수출 차트:** 25개월로 고정했어요. 이상치 판정(`detect_anomaly`)에 쓰는 기간과 같아요.
- **빈자리(점선 카드):** 시장 컨센서스, 예상 괴리율, 직전 분기 대비 수출 증가율, 주가 영향 판단 3종, 추정 오차율. 데이터나 함수가 생기면 채울 자리예요.

---

## 3. 알아 두면 좋은 것

### app.py에는 pandas 가공이 없어요
과제 평가 항목("app.py에 pandas 가공 로직이 섞여 있지 않은가") 때문에 `app.py`는 pandas를 import하지 않아요. 그래서 **화면에 새 숫자나 표가 필요하면 backend 쪽에 함수를 하나 만들어 주셔야 해요.** app.py에서 직접 계산하면 감점 요인이 돼요.

### app.py가 기대고 있는 backend 함수들
아래 함수의 **이름, 인자, 반환 키를 바꾸면 화면이 깨져요.** 바꿀 일이 있으면 미리 말해 주세요.

| 함수 | 화면에서 쓰는 곳 |
|---|---|
| `data_loader.load_actuals(파일)` | 업로드 CSV 읽기, 검증 |
| `backend.run_forecast(...)` | 리포트 전체 (forecast, anomaly, consistency, guidance, facts, brief, exports, quarterly, anomaly_ym, transcript_file 키 사용) |
| `backend.default_target_quarter()` | 대상 분기 자동 선택 |
| `backend.list_target_quarters()` | 검증 모드의 분기 목록 |
| `backend.exports_chart_table()` | 최근 25개월 범위 |
| `backend.quarterly_display_table()`, `exports_display_table()` | 데이터 표 |
| `llm_module.build_brief_facts()` 결과 (`facts`) | 화면의 "117.7조 원", "+12.5%" 같은 표시 문자열 전부 |
| `llm_module.USE_MOCK`, `backend.DISCLAIMER`, `forecaster.FORECAST_STATUS_*` 등 상수 | 배지, 고지, 상태 분기 |

### session_state는 이렇게 써요
- `actuals`: 업로드한 표. 업로드 위젯이 없는 페이지로 가면 위젯 값이 지워져서 따로 보관해요.
- `report_history`: 저장한 리포트 목록.
- `upload_signature`, `upload_error`: 같은 파일을 rerun마다 다시 읽지 않는 용도.
- 예측 결과는 session_state 대신 `st.cache_data`로 캐시해요.

### 앱은 forecasts.csv에 쓰지 않아요
화면의 이력은 세션에만 쌓고, `run_forecast(..., save_history=False)`로 불러요. 화면에서 분기를 바꿀 때마다 `data/forecasts.csv`에 행이 쌓이는 걸 막으려고요. CLI(`python backend.py`)는 지금처럼 저장해요.

---

## 4. 같이 정해야 할 것

결정란은 회의 때 채우면 돼요.

### ① `run_forecast`에 인자 추가
- **문제:** 지금 `run_forecast`는 실적을 `data/actuals.csv` 경로에서만 읽어요. 그래서 **화면에서 올린 CSV가 계산에 안 들어가요.**
- **제안 (`backend.patch`, 기존 CLI 동작은 그대로):**
  - `actuals_df=None`: 넘기면 업로드한 표를 쓰고, 없으면 지금처럼 파일을 읽어요.
  - `save_history=True`: 화면은 `False`로 불러요.
  - 반환값에 `target_actual` 추가: 검증 모드에서 쓰는 대상 분기 확정 매출이에요.
- 결정: ☐ 수용 ☐ 다른 방식 (                    )

### ② `load_actuals` cp949 정책 변경
- **바뀌는 점:** 예전(`b818268`)에는 "cp949면 UTF-8로 다시 저장하라"고 거부했는데, 과제가 cp949 업로드를 요구해서 **UTF-8 실패 → `seek(0)` → cp949로 다시 읽기**로 바꿔요.
- **같이 바뀌는 점:** 경로뿐 아니라 업로드 파일 객체도 받아요. 인코딩 테스트 7개(L15~L20)를 추가했어요.
- 결정: ☐ OK

### ③ 통합할 때 빠진 예전 수정
- **문제:** 통합 버전 `load_actuals`에서 `read_csv(index_col=False)`가 빠져서, 기존 테스트 L14(따옴표 없는 쉼표 매출)가 **TypeError로 실패해요.** 개인 폴더에서는 `2b9acaa`로 고쳤던 거예요.
- **조치:** ②의 patch에 같이 넣었어요. 통합 버전에 기존 테스트 27개 + 새 7개 = 34 passed(수정 전 5 failed).
- **부탁:** 다른 함수도 통합하면서 빠진 수정이 없는지, 각자 자기 테스트를 통합 버전에 한 번 돌려 봐 주세요.
- 결정: ☐ OK

### ④ 수출·환율 데이터 파일 관리 (API 키 있는 분)
- **문제:** 앱에는 "데이터 갱신" 버튼이 없어요(API 키 문제로 뺐어요). 그래서 `data/exports.csv`, `data/fx.csv`가 미리 있어야 해요. **지금 저장소에는 두 파일이 없어요.**
- **제안(A안):** 키가 있는 분이 매월 15일 이후 `python backend.py`를 한 번 실행하고 두 파일을 커밋해요. 그러면 다른 팀원과 평가자도 키 없이 앱을 돌릴 수 있어요. `.gitignore`에서 두 파일은 주석 처리돼 있어서 올라가요.
- **정할 것:** 담당자와 첫 생성 시점 (제출 캡처를 실제 데이터로 다시 찍어야 해서 빠를수록 좋아요).
- 결정: 담당 (        ) / 첫 생성 (        )

### ⑤ 빈자리 카드 담당
지금은 점선 카드로만 있어요. 누가 언제 만들지 정해야 해요.

| 항목 | 필요한 것 | 담당 |
|---|---|---|
| 시장 컨센서스, 예상 괴리율 | 컨센서스 데이터(예: `consensus.csv`: quarter, consensus_krw, source, as_of) + 괴리율 계산 함수 | |
| 직전 분기 대비 수출 증가율 | 분기 수출 QoQ 계산 함수 | |
| 추정 오차율 (검증 모드) | \|추정 − 확정\| ÷ 확정 계산 함수 | |
| 주가 영향 판단 (업종 점수, 방향, 신뢰도) | 산출 방식부터 정해야 함 | |

### ⑥ 설계 변경 반영 (전원)
- 설계문서 V1 범위 ⑥ "제외 1번"에 "주가 예측은 다루지 않는다"고 적혀 있는데, 주가 영향 판단을 추가하기로 했어요. **설계문서와 `docs/schema.md`에 반영이 필요해요.**
- 컨센서스를 넣게 되면 표, dict 스키마도 추가해야 해요.
- 결정: 수정 담당 (        )

### ⑦ 요약 브리프를 화면에 보여 줄지
- 원래 "자리만 두기"로 했는데, 그사이 통합 백엔드에 `generate_brief`가 생겨서 지금은 결과를 그대로 보여 줘요. 키가 없으면 `[MOCK]` 문장으로 나와요.
- 결정: ☐ 그대로 표시 ☐ 다시 빈자리로

### ⑧ (선택) 검증 모드의 수출 차트 기간
- 지금은 검증 모드에서도 "최근 25개월"을 보여 줘요. 고른 분기에 맞춰 자르려면 `exports_chart_table(..., end_ym=None)` 같은 인자가 필요해요.
- 결정: ☐ 지금대로 ☐ 인자 추가

### ⑨ 파일 위치, 의존성
- **추가될 파일:** `alt_backend_week11/app.py`, `alt_backend_week11/.streamlit/config.toml`(화이트 테마 고정, 키 없음), `alt_backend_week11/samples/*.csv`(수동 검증용 3종)
- **requirements:** `requirements.txt`에 `streamlit>=1.50` 추가. 1.50.0으로 테스트했고, 그보다 낮으면 `width="stretch"` 같은 인자가 없을 수 있어요.
- 결정: ☐ OK

---

## 5. 반영 순서 (합의 후)

1. 브랜치 생성
2. ②③ `load_actuals` 수정 + 인코딩 테스트 추가
3. ① `run_forecast` 수정 (합의된 형태로)
4. `app.py`, `config.toml`, `samples/`, `requirements.txt` 추가
5. ④ 실제 데이터 생성 후 수동 검증 캡처를 다시 찍고, README와 과정 기록 정리
6. PR 올리고 리뷰 요청
