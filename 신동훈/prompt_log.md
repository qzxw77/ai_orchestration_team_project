# 표준 6단계 사이클

## 1. 논리 설계

### <구현할 함수 시그니처>

```python
import pandas as pd

RATIO_WINDOW = 4  # 비율 계산에 쓰는 기준 분기 수

def estimate_revenue(quarterly_df: pd.DataFrame, actuals_df: pd.DataFrame,
                     target_quarter: str) -> dict:
```

### <책임>

대상 분기 수출에 과거 4개 분기의 '달러 매출 ÷ 수출' 비율을 적용해 매출 중앙값과 범위(하한~상한)를 추정한다.

### <입력 명세>

#### quarterly_df — 분기별 수출·환율 집계 표 (`aggregate_quarterly`의 출력)

| 열 | 타입 | 규칙 |
|---|---|---|
| quarter | str | "YYYYQn", 키(중복 없음) |
| export_usd | float | 분기 수출 합계(달러) |
| months_available | int | 0~3, 수출 자료가 있는 달 수 |
| fx_avg | float | 분기 평균 원/달러 환율, 결측(NaN) 가능 |

- 대상 분기보다 뒤의 분기 행이 들어 있을 수 있다.
- 예: `quarter="2025Q4", export_usd=1.0e10, months_available=3, fx_avg=1400.0`

#### actuals_df — 분기 확정 매출 표 (`load_actuals`의 출력)

| 열 | 타입 | 규칙 |
|---|---|---|
| quarter | str | "YYYYQn", 키(중복 없음) |
| revenue_krw | float | 원, 연결 기준 분기 매출 |
| announced_date | str | "YYYY-MM-DD", 계산에 쓰지 않음 |

- 대상 분기와 그 이후 분기의 실적이 들어 있을 수 있다(읽지 않는다).
- 예: `quarter="2025Q4", revenue_krw=2.24e13, announced_date="2026-01-29"`

#### target_quarter

- str, "YYYYQn" (예: `"2026Q1"`)

### <출력 명세 — forecast dict (항상 키 8개)>

| 키 | 타입 | 의미 |
|---|---|---|
| quarter | str | target_quarter 그대로 |
| estimate_krw | float 또는 None | 매출 중앙값(원) |
| lower_krw | float 또는 None | 매출 하한(원) |
| upper_krw | float 또는 None | 매출 상한(원) |
| qoq_change_pct | float 또는 None | 직전 분기 실적 대비 증감률(%) |
| ratio_used | float 또는 None | 기준 분기 4개 비율의 평균 |
| months_available | int | 대상 행의 값, 대상 행이 없으면 0 |
| status | str | "ok", "no_data", "insufficient_history" 중 하나 |

### <처리 순서 (Pseudocode)>

```text
함수 estimate_revenue — 입력: quarterly 표, actuals 표, 대상 분기 / 출력: forecast dict
    대상 행 = quarterly_df에서 quarter == target_quarter인 행
    IF 대상 행이 없거나 months_available이 0이거나 fx_avg가 결측이면
        RETURN forecast dict(status="no_data", months_available=대상 행의 값(없으면 0),
                             나머지 숫자 값은 모두 None)
    기준 분기 = target_quarter보다 앞선 분기 중 아래 조건을 모두 만족하는 분기
        (actuals에 실적 있음, months_available = 3, export_usd > 0, fx_avg 있음)
    # 대상 분기와 그 이후의 실적은 읽지 않는다: 미래 정보 누수 방지
    IF 기준 분기가 RATIO_WINDOW(=4)개 미만이면
        RETURN forecast dict(status="insufficient_history", months_available=대상 행의 값,
                             나머지 숫자 값은 모두 None)
    비율 목록 = 빈 목록
    FOR 가장 최근 기준 분기 4개 각각 반복
        비율 목록에 (revenue_krw ÷ fx_avg) ÷ export_usd를 추가한다
    분기 수출 추정 = 대상 행의 export_usd × 3 ÷ months_available
    중앙값 = 분기 수출 추정 × 비율 평균 × 대상 행의 fx_avg
    하한   = 분기 수출 추정 × 비율 최솟값 × 대상 행의 fx_avg
    상한   = 분기 수출 추정 × 비율 최댓값 × 대상 행의 fx_avg
    직전 분기 = target_quarter 바로 앞 분기 (예: 2026Q1 → 2025Q4)
    IF actuals에 직전 분기 실적이 있으면
        qoq_change_pct = (중앙값 ÷ 직전 분기 revenue_krw − 1) × 100
    ELSE
        qoq_change_pct = None
    RETURN forecast dict(quarter=target_quarter, estimate_krw=중앙값, lower_krw=하한,
                         upper_krw=상한, qoq_change_pct, ratio_used=비율 평균,
                         months_available=대상 행의 값, status="ok")
```

### <예외·경계 방침>

| 상황 | status | months_available | 숫자 값 5개 |
|---|---|---|---|
| quarterly_df에 대상 분기 행 없음 | no_data | 0 | 모두 None |
| 대상 행 months_available = 0 | no_data | 0 | 모두 None |
| 대상 행 fx_avg 결측 | no_data | 대상 행의 값 | 모두 None |
| 기준 분기 4개 미만 | insufficient_history | 대상 행의 값 | 모두 None |
| 대상 행 months_available = 1~2 | ok | 대상 행의 값 | 3개월분으로 환산해 계산 |
| 직전 분기 실적 없음 | ok | 대상 행의 값 | qoq_change_pct만 None |
| actuals에 대상 분기·이후 실적 있음 | 영향 없음 | — | 읽지 않음 |

- 예외를 발생시키지 않는다. 자료 부족은 status로만 알린다.
- 숫자 값 5개 = estimate_krw, lower_krw, upper_krw, qoq_change_pct, ratio_used

### <고정 규칙 · 구체화한 규칙>

**반드시 지킬 것**

- 입력은 quarterly 표와 actuals 표뿐이다.
- 대상 분기와 그 이후의 실적을 읽지 않는다.
- 금액은 원 단위 float로, 반올림하지 않는다. 표시용 반올림은 generate_brief와 main에서만 한다.
- 예외를 내지 않는다.
- 입력 DataFrame을 직접 수정하지 않는다.
- actuals_df의 revenue_krw가 결측인 분기는 "실적 없음"으로 본다(기준 분기에서 제외, 직전 분기라면 qoq_change_pct = None).
- 반환 dict의 months_available은 Python int로 돌려준다.

### <테스트 케이스 표>

**quarterly_df**

| quarter | export_usd | months_available | fx_avg |
|---|---|---|---|
| 2025Q1 | 1.0e10 (100억 달러) | 3 | 1400.0 |
| 2025Q2 | 1.0e10 | 3 | 1400.0 |
| 2025Q3 | 1.0e10 | 3 | 1400.0 |
| 2025Q4 | 1.0e10 | 3 | 1400.0 |
| 2026Q1 | 1.2e10 (120억 달러) | 3 | 1450.0 |

**actuals_df**

| quarter | revenue_krw | announced_date | 비율 (revenue_krw ÷ fx_avg ÷ export_usd) |
|---|---|---|---|
| 2025Q1 | 1.96e13 (19.6조) | 2025-04-24 | 1.4 |
| 2025Q2 | 2.10e13 (21.0조) | 2025-07-24 | 1.5 |
| 2025Q3 | 2.10e13 (21.0조) | 2025-10-23 | 1.5 |
| 2025Q4 | 2.24e13 (22.4조) | 2026-01-22 | 1.6 |

→ 비율 평균 1.5, 최소 1.4, 최대 1.6 (announced_date는 계산에 쓰지 않는 가상 값)

**계산 확인 (T07)**

- 중앙값 = 1.2e10 × 1.5 × 1450 = 2.61e13 (26.1조)
- 하한 = 1.2e10 × 1.4 × 1450 = 2.436e13 (24.36조)
- 상한 = 1.2e10 × 1.6 × 1450 = 2.784e13 (27.84조)
- qoq = (2.61e13 ÷ 2.24e13 − 1) × 100 ≈ 16.5179

금액·비율 비교는 `pytest.approx(rel=1e-6)`로 한다.

### 테스트 케이스

| ID | 범주 | 테스트 함수 | 입력 | 기대 출력 / 동작 |
|---|---|---|---|---|
| T07 | 정상 | test_t07_full_quarter | F, target "2026Q1" | status "ok", estimate 2.61e13, lower 2.436e13, upper 2.784e13, ratio_used 1.5, qoq_change_pct ≈ 16.5179, months_available 3 |
| T08 | 정상 | test_t08_partial_months_scaled | F에서 2026Q1만 export_usd 8.0e9, months_available 2 | 3개월분 1.2e10으로 환산 → estimate·lower·upper가 T07과 같음, months_available 2 |
| T09 | 경계 | test_t09_insufficient_history | F에서 actuals의 2025Q1 행 삭제(기준 분기 3개) | status "insufficient_history", 숫자 값 5개 모두 None, months_available 3 |
| T10 | 경계 | test_t10_ignores_future_actuals | F의 actuals에 2026Q1 실적 3.0e13 추가 | 결과 dict가 T07과 완전히 같음 |
| T11 | 예외 | test_t11_no_target_row | F, target "2026Q2"(quarterly에 행 없음) | status "no_data", 숫자 값 5개 모두 None, months_available 0, 예외 발생 없음 |
| A01 | 경계 | test_a01_zero_months_available | F에서 2026Q1을 export_usd 0.0, months_available 0으로 변경 | status "no_data", 숫자 값 5개 모두 None, months_available 0 |
| A02 | 예외 | test_a02_target_fx_missing | F에서 2026Q1 fx_avg를 NaN으로 변경 | status "no_data", 숫자 값 5개 모두 None, months_available 3 |
| A03 | 경계 | test_a03_no_prev_quarter_actual | F에 2024Q4 추가(quarterly: 1.0e10·3·1400.0 / actuals: 2.10e13), actuals의 2025Q4 행 삭제 | 기준 분기 = 2024Q4·2025Q1·2025Q2·2025Q3(비율 1.5·1.4·1.5·1.5) → status "ok", ratio_used 1.475, estimate 2.5665e13, lower 2.436e13, upper 2.61e13, qoq_change_pct None |
| A04 | 예외 | test_a04_revenue_nan_not_counted | F에서 actuals의 2025Q1 revenue_krw를 NaN으로 변경 | 2025Q1이 기준 분기에서 빠짐 → status "insufficient_history", 숫자 값 5개 모두 None |

범주 수: 정상 2 (T07·T08) · 경계 4 (T09·T10·A01·A03) · 예외 3 (T11·A02·A04)

---

## 2. 정밀 프롬프트 작성
**사용한 프롬프트**
```
당신은 파이썬 백엔드 개발을 돕는 어시스턴트입니다.
SK하이닉스 분기 매출 나우캐스팅 시스템의 분석 모듈 forecaster.py에 들어갈
함수 estimate_revenue를 구현해 주세요. 이 함수는 대상 분기 수출에 과거 4개 분기의
'달러 매출 ÷ 수출' 비율을 적용해 매출 중앙값과 범위를 추정합니다.
#file:test_estimate_revenue.py 의 테스트를 모두 통과해야 합니다. 테스트 파일은 수정하지 마세요.

[함수 시그니처 — 변경 금지]
import pandas as pd

def estimate_revenue(quarterly_df: pd.DataFrame, actuals_df: pd.DataFrame,
                     target_quarter: str) -> dict:

[입력 명세]
1) quarterly_df: 분기별 수출·환율 집계 표 (aggregate_quarterly의 출력)
   - quarter: str "YYYYQn" (키, 중복 없음)
   - export_usd: float (분기 수출 합계, 달러)
   - months_available: int (0~3, 수출 자료가 있는 달 수)
   - fx_avg: float (분기 평균 원/달러 환율, 결측 NaN 가능)
   - 대상 분기보다 뒤의 분기 행이 들어 있을 수 있다.
   예) quarter="2025Q4", export_usd=1.0e10, months_available=3, fx_avg=1400.0
2) actuals_df: 분기 확정 매출 표 (load_actuals의 출력)
   - quarter: str "YYYYQn" (키, 중복 없음)
   - revenue_krw: float (원, 연결 기준 분기 매출, 결측 NaN 가능)
   - announced_date: str "YYYY-MM-DD" (계산에 쓰지 않음)
   - 대상 분기와 그 이후 분기의 실적이 들어 있을 수 있다.
   예) quarter="2025Q4", revenue_krw=2.24e13, announced_date="2026-01-22"
3) target_quarter: str "YYYYQn" (예: "2026Q1")

[출력 명세] 어떤 경우에도 아래 키 8개를 모두 가진 dict를 반환한다
- quarter: str (= target_quarter)
- estimate_krw, lower_krw, upper_krw: float 또는 None (원 단위)
- qoq_change_pct: float 또는 None (직전 분기 실적 대비 %)
- ratio_used: float 또는 None (기준 분기 비율의 평균)
- months_available: int (대상 행의 값, 대상 행이 없으면 0). numpy 정수가 아닌 파이썬 int로 반환
- status: "ok", "no_data", "insufficient_history" 중 하나

[처리 순서 — Pseudocode]
대상 행 = quarterly_df에서 quarter == target_quarter인 행
IF 대상 행이 없거나 months_available이 0이거나 fx_avg가 결측이면
    RETURN status="no_data", months_available=대상 행의 값(없으면 0), 나머지 숫자 값 None
기준 분기 = target_quarter보다 앞선 분기 중 아래 조건을 모두 만족하는 분기
    (actuals_df에 revenue_krw가 결측이 아닌 실적 있음, months_available == 3,
     export_usd > 0, fx_avg 결측 아님)
IF 기준 분기가 RATIO_WINDOW(=4)개 미만이면
    RETURN status="insufficient_history", months_available=대상 행의 값, 나머지 숫자 값 None
비율 목록 = 가장 최근 기준 분기 4개 각각의 (revenue_krw ÷ fx_avg) ÷ export_usd
분기 수출 추정 = 대상 행 export_usd × 3 ÷ months_available
estimate_krw = 분기 수출 추정 × 비율 평균 × 대상 행 fx_avg
lower_krw    = 분기 수출 추정 × 비율 최솟값 × 대상 행 fx_avg
upper_krw    = 분기 수출 추정 × 비율 최댓값 × 대상 행 fx_avg
직전 분기 = target_quarter 바로 앞 분기 (2026Q1 → 2025Q4, 2026Q3 → 2026Q2)
IF actuals_df에 직전 분기 실적(revenue_krw 결측 아님)이 있으면
    qoq_change_pct = (estimate_krw ÷ 직전 분기 revenue_krw − 1) × 100
ELSE
    qoq_change_pct = None
RETURN status="ok", ratio_used=비율 평균, 위에서 계산한 값

[예외·경계 방침]
- 예외를 발생시키지 않는다. 자료 부족은 status 값으로만 알린다.
- 대상 분기와 그 이후의 actuals는 읽지 않는다(미래 정보 누수 방지).
- months_available이 1~2인 대상 분기는 3개월분으로 환산해 계산한다.
- revenue_krw가 결측인 actuals 행은 실적이 없는 것으로 본다.
- 결측 확인은 pd.isna()로 한다(== NaN 비교 금지).

[제약 조건 — 프로젝트 공통]
- 파이썬 표준 라이브러리와 pandas만 사용한다(numpy 등 직접 import 금지).
- 시그니처를 바꾸지 않는다. 공개 함수를 새로 만들지 않고, 보조 함수는
  밑줄로 시작하는 내부 함수(예: _prev_quarter)로 같은 파일에 둔다.
- 타입 힌트와 한국어 docstring(설명, Args, Returns, Raises)을 단다.
- 가변 기본값 인자 금지. 전역 변수를 읽거나 바꾸지 않는다(파일 맨 위 대문자 상수는 읽기 전용 허용).
- 입력 DataFrame을 직접 수정하지 않는다.
- print, 파일 읽기·쓰기, 다른 팀 모듈 import를 하지 않는다.

[제약 조건 — 함수별: estimate_revenue]
- 자료구조: 반환 dict의 키 8개 이름·타입 고정. months_available은 int, 금액은 float.
- 처리 방식: 금액은 원 단위 그대로 두고 반올림하지 않는다.
- 하지 말 것: 가이던스 등 다른 입력을 계산에 쓰지 않는다. 조 원 변환 같은 표시용 가공을 하지 않는다.
- 변경 대비: 파일 맨 위에 RATIO_WINDOW = 4 상수를 둔다.

[통과해야 할 테스트 — 설계 문서 파트 4 T07~T11 + 추가 A01~A04]
공통 입력 F
- quarterly_df: 2025Q1~2025Q4 → export_usd 1.0e10, months_available 3, fx_avg 1400.0
                2026Q1 → export_usd 1.2e10, months_available 3, fx_avg 1450.0
- actuals_df: 2025Q1 1.96e13, 2025Q2 2.10e13, 2025Q3 2.10e13, 2025Q4 2.24e13
  (비율 1.4·1.5·1.5·1.6 → 평균 1.5, 최소 1.4, 최대 1.6)
T07 정상: F, "2026Q1" → status "ok", estimate 2.61e13, lower 2.436e13, upper 2.784e13,
          ratio_used 1.5, qoq_change_pct ≈ 16.5179, months_available 3 (int)
T08 정상: F에서 2026Q1만 export_usd 8.0e9, months_available 2
          → estimate·lower·upper가 T07과 같음, months_available 2
T09 경계: F에서 actuals의 2025Q1 행 삭제 → status "insufficient_history",
          숫자 값 5개 모두 None, months_available 3
T10 경계: F의 actuals에 2026Q1 실적 3.0e13 추가 → 결과 dict가 T07과 완전히 같음
T11 예외: F, "2026Q2"(행 없음) → status "no_data", 숫자 값 모두 None,
          months_available 0, 예외 발생 없음
A01 경계: 2026Q1을 export_usd 0.0, months_available 0으로 변경 → "no_data", months_available 0
A02 예외: 2026Q1 fx_avg NaN → "no_data", 숫자 값 모두 None, months_available 3
A03 경계: F에 2024Q4(quarterly 1.0e10·3·1400.0 / actuals 2.10e13) 추가, actuals의 2025Q4 삭제
          → 기준 분기 2024Q4·2025Q1·2025Q2·2025Q3, status "ok", ratio_used 1.475,
            estimate 2.5665e13, lower 2.436e13, upper 2.61e13, qoq_change_pct None
A04 예외: actuals의 2025Q1 revenue_krw NaN → "insufficient_history", 숫자 값 모두 None
금액·비율 비교는 pytest.approx(rel=1e-6)로 한다.

[출력 방식]
- 파일을 직접 만들거나 수정하지 말고, 터미널 명령(pytest 등)도 실행하지 마세요.
- forecaster.py의 전체 코드를 채팅에 코드 블록 하나로만 보여 주세요.

```

## 3. AI 코드 생성
* 생성 코드 커밋 해시

  생성 코드 커밋: `c681b9d` (Copilot Chat 생성 원본, 수정 전, 240줄)

## 4. 코드 리딩.검증
### (1) 발견 결함
  **명세 밖 필수 열·타입 검사가 오류를 숨김** (원본 88~106줄, 체크리스트 3 예외 방침 · 5 명세 밖 동작)
   - 프롬프트에 없는 `required_quarterly_columns`·`required_actuals_columns` 검사와 `isinstance(..., pd.DataFrame)` 검사를 AI가 임의로 추가함
   - 열이 없으면 status `no_data`를 반환 → 열 누락(상류 함수의 버그)이 "예측할 데이터 없음"으로 둔갑함
   - 예: actuals의 열 이름이 `revenue_krw` 대신 `revenue`로 들어오면 오류 없이 no_data 반환 → 사용자·팀원 모두 "아직 수출 통계가 없다"로 오해
   - 열 보장은 `load_actuals`·`aggregate_quarterly`의 역할이며, 팀 공통 규칙 "예외를 조용히 삼키지 않는다"에도 어긋남

  ### 수정 내역

- 커밋 `74b0de4`: 필수 열·타입 검사 블록(원본 88~106줄) 삭제
  - 열이 없으면 `KeyError: '<열 이름>'`가 발생해 문제 위치가 바로 드러나도록 함
  - 판단 근거: 구현 가이드의 "예외를 내지 않는다"는 **자료 부족**(대상 분기 자료 없음, 기준 분기 부족)을 status로 알리라는 규칙으로 해석함. 코드 버그까지 status로 숨기라는 뜻이 아님
  
### (2) 발견 결함
  **months_available 음수가 출력에 그대로 나감** (원본 124~127줄, 체크리스트 2 경계 추적)
   - `result["months_available"] = months_available`로 결과에 먼저 대입한 뒤 `months_available <= 0`을 검사함
   - 입력 months_available이 -1이면 status `no_data`와 함께 `months_available: -1`이 출력됨 → 출력 명세(0~3) 위반
   - 이 값은 main에서 forecasts.csv와 화면의 "반영된 개월 수"에 그대로 기록됨
   - 0·3 입력은 결과가 같아 기존 테스트(A01 등)로는 발견되지 않음 → 음수를 대입해 한 줄씩 따라가며 코드 리딩으로 발견함

  ### 수정 내역

- 커밋 `2aa330c`: `months_available <= 0` 검사를 결과 대입보다 앞으로 옮김
  - 0 이하 입력이면 대입 전에 반환되어, `result` 초깃값 0이 출력됨
  - 정상값(1~3)일 때만 `result["months_available"]`에 대입됨
  - 입력 -1 → 수정 전 출력 -1, 수정 후 출력 0

### (3) 발견 결함
  **코드가 과도하게 복잡해 설명하기 어려움 · 기준 분기 fx_avg 0 미처리** (원본 119~227줄, 체크리스트 2 경계 추적 · 4 위험 관용구 · 6 설명 가능성)
   - itertuples → dict → set 교집합 → for문의 3단계 루프로 기준 분기를 고름 (약 60줄)
   - 이미 숫자인 값을 다시 변환하는 try/except 5곳 → 앞 단계 버그(숫자 열에 문자열 등)를 조용히 no_data·제외로 바꿀 수 있음
   - 기준 분기에서 `export_usd <= 0`만 거르고 `fx_avg`는 0을 거르지 않음 → fx_avg가 0이면 ZeroDivisionError (환율 계약상 0 초과라 드묾)
   - 비율 평균을 실제 개수 대신 상수 `RATIO_WINDOW`로 나눔, 매직 넘버 `3`, `float()` 중복 변환

  ### 수정 내역

- 커밋 `e382473`: 기준 분기 선택을 pandas `merge` + 조건 필터로 단순화
  - 4가지 조건(대상 분기 이전, months_available == 3, export_usd > 0, fx_avg > 0)을 마스크로 한 번에 적용하고 `sort_values` + `tail(4)`로 최근 4개 선택
  - 불필요한 try/except 제거, 조건에 `fx_avg > 0` 추가(결측과 0을 함께 제외)
  - 평균을 `len(ratios)`로 계산, `MONTHS_PER_QUARTER = 3` 상수 추가

## 5. 테스트

* **pytest 결과**
```python
================================================================================================================= test session starts =================================================================================================================
platform win32 -- Python 3.13.14, pytest-9.2.0, pluggy-1.7.0 -- C:\dev\ai_studio\ai_orchestration_team_project\신동훈\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\dev\ai_studio\ai_orchestration_team_project\신동훈
collected 9 items                                                                                                                                                                                                                                      

test_estimate_revenue.py::test_t07_full_quarter PASSED                                                                                                                                                                                           [ 11%]
test_estimate_revenue.py::test_t08_partial_months_scaled PASSED                                                                                                                                                                                  [ 22%]
test_estimate_revenue.py::test_t09_insufficient_history PASSED                                                                                                                                                                                   [ 33%]
test_estimate_revenue.py::test_t10_ignores_future_actuals PASSED                                                                                                                                                                                 [ 44%]
test_estimate_revenue.py::test_a01_zero_months_available PASSED                                                                                                                                                                                  [ 55%]
test_estimate_revenue.py::test_a03_no_prev_quarter_actual PASSED                                                                                                                                                                                 [ 66%]
test_estimate_revenue.py::test_t11_no_target_row PASSED                                                                                                                                                                                          [ 77%]
test_estimate_revenue.py::test_a02_target_fx_missing PASSED                                                                                                                                                                                      [ 88%]
test_estimate_revenue.py::test_a04_revenue_nan_not_counted PASSED                                                                                                                                                                                [100%]

================================================================================================================== 9 passed in 3.10s ==================================================================================================================
```

## 6. Git 커밋
* git log --oneline
```python
e382473 (HEAD -> feat/estimate-revenue, origin/feat/estimate-revenue) refactor: estimate_revenue 기준 분기 선택을 pandas 필터로 단순화
2aa330c fix: estimate_revenue 음수 months_available 출력 방지
74b0de4 fix: estimate_revenue 명세 밖 필수 열 검사 제거
c681b9d feat: add estimate_revenue (Copilot chat 생성 원본, 생성 직후)
70d3343 test: add estimate_revenue spec and tests (T07-T11, A01-A04)
37df945 (origin/main, origin/HEAD, main) Merge pull request #3 from qzxw77/kangmingyu_detect_anomaly
280cbb3 docs: add missing content
65d22ea Delete README.md
c2bead0 docs: add missing content
0e98677 Fix typo and markdown formatting issue
acee519 docs: update prompt_log.md
50a7d23 feat: add test_detect_anomaly.py
69d2da9 docs: update README.md and upload security_checklist.txt
6c4c7ee fix: correct region check and remove broad try/except in detect_anomaly - (한 지역만 있는 달 합계 포함 / 명세에 없는 threshold 검사 / 보조 함수 docstring 누락 / 함수 전체 try/except)
0fcbafc Merge pull request #2 from qzxw77/feat/chohyeonmo-clean-exports
ebfab05 (origin/feat/chohyeonmo-clean-exports) fix: pytest_result.txt UTF-8로 다시 저장 (GitHub 표시 깨짐 수정)
066dbbb feat: add forecaster.py(detect_anomaly) initial version
0153d3d Merge pull request #1 from qzxw77/feat/chohyeonmo-clean-exports
16f0131 docs: clean_exports 과정 기록, 보안 체크리스트
ceb1d1c fix: clean_exports 코드 리딩 결함 6건 수정
2c71515 feat: clean_exports Copilot 생성 원본
9c6a9f2 test: clean_exports 테스트 T01~T06 + 추가 X01~X11 작성
f6c719f Update prompt_log.md
adf968d Create prompt_log.md
6437102 Create .gitignore
581c4a8 Create README.md
3da9947 Create README.md
70ffa83 Create README.md
```
---
**과정 기록 표준 양식**

[모듈] forecaster.py · estimate_revenue — 2026-11-02, 작성자: 신동훈

- 사용 도구: GitHub Copilot Chat 
- 프롬프트: 위 양식 2번 내용
- 생성 코드 위치: c681b9d (수정 전 원본)
- 코드 리딩에서 발견한 결함:
  1)명세 밖 필수 열 검사 제거
  2)음수 month_available 출력 방지
  3)estimate_revenue 기준 분기 선택을 pandas 필터로 단순화
- 수정 내역: 74b0de4(수정1), 2aa330c(수정2), e382473(수정3)
- 테스트 결과: pytest 9 passed 