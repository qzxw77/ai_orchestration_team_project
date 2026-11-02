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
#file:test_forecaster.py 의 테스트를 모두 통과해야 합니다.

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
   - revenue_krw: float (원, 연결 기준 분기 매출)
   - announced_date: str "YYYY-MM-DD" (계산에 쓰지 않음)
   - 대상 분기와 그 이후 분기의 실적이 들어 있을 수 있다.
   예) quarter="2025Q4", revenue_krw=2.24e13, announced_date="2026-01-29"
3) target_quarter: str "YYYYQn" (예: "2026Q1")

[출력 명세] 어떤 경우에도 아래 키 8개를 모두 가진 dict를 반환한다
- quarter: str (= target_quarter)
- estimate_krw, lower_krw, upper_krw: float 또는 None (원 단위)
- qoq_change_pct: float 또는 None (직전 분기 실적 대비 %)
- ratio_used: float 또는 None (기준 분기 비율의 평균)
- months_available: int (대상 행의 값, 대상 행이 없으면 0)
- status: "ok", "no_data", "insufficient_history" 중 하나

[처리 순서 — Pseudocode]
대상 행 = quarterly_df에서 quarter == target_quarter인 행
IF 대상 행이 없거나 months_available이 0이거나 fx_avg가 결측이면
    RETURN status="no_data", months_available=대상 행의 값(없으면 0), 나머지 숫자 값 None
기준 분기 = target_quarter보다 앞선 분기 중 아래 조건을 모두 만족하는 분기
    (actuals_df에 실적 있음, months_available == 3, export_usd > 0, fx_avg 결측 아님)
IF 기준 분기가 RATIO_WINDOW(=4)개 미만이면
    RETURN status="insufficient_history", months_available=대상 행의 값, 나머지 숫자 값 None
비율 목록 = 가장 최근 기준 분기 4개 각각의 (revenue_krw ÷ fx_avg) ÷ export_usd
분기 수출 추정 = 대상 행 export_usd × 3 ÷ months_available
estimate_krw = 분기 수출 추정 × 비율 평균 × 대상 행 fx_avg
lower_krw    = 분기 수출 추정 × 비율 최솟값 × 대상 행 fx_avg
upper_krw    = 분기 수출 추정 × 비율 최댓값 × 대상 행 fx_avg
직전 분기 = target_quarter 바로 앞 분기 (2026Q1 → 2025Q4, 2026Q3 → 2026Q2)
IF actuals_df에 직전 분기 실적이 있으면
    qoq_change_pct = (estimate_krw ÷ 직전 분기 revenue_krw − 1) × 100
ELSE
    qoq_change_pct = None
RETURN status="ok", ratio_used=비율 평균, 위에서 계산한 값

[예외·경계 방침]
- 예외를 발생시키지 않는다. 자료 부족은 status 값으로만 알린다.
- 대상 분기와 그 이후의 actuals는 읽지 않는다(미래 정보 누수 방지).
- months_available이 1~2인 대상 분기는 3개월분으로 환산해 계산한다.
- revenue_krw가 결측인 actuals 행은 실적이 없는 것으로 본다.

[제약 조건]
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

[통과해야 할 테스트]
공통 입력 F
- quarterly_df: 2025Q1~2025Q4 → export_usd 1.0e10, months_available 3, fx_avg 1400.0
                2026Q1 → export_usd 1.2e10, months_available 3, fx_avg 1450.0
- actuals_df: 2025Q1 1.96e13, 2025Q2 2.10e13, 2025Q3 2.10e13, 2025Q4 2.24e13
  (비율 1.4·1.5·1.5·1.6 → 평균 1.5, 최소 1.4, 최대 1.6)
T07 정상: F, "2026Q1" → status "ok", estimate 2.61e13, lower 2.436e13, upper 2.784e13,
          ratio_used 1.5, qoq_change_pct ≈ 16.52, months_available 3
T08 정상: F에서 2026Q1만 export_usd 8.0e9, months_available 2
          → estimate·lower·upper가 T07과 같음, months_available 2
T09 경계: F에서 actuals의 2025Q1 행 삭제 → status "insufficient_history",
          estimate·lower·upper·ratio_used·qoq_change_pct 모두 None
T10 경계: F의 actuals에 2026Q1 실적 3.0e13 추가 → 결과가 T07과 완전히 같음
T11 예외: F, "2026Q2"(행 없음) → status "no_data", 숫자 값 모두 None,
          months_available 0, 예외 발생 없음
추가: 대상 분기 months_available 0 → "no_data", months_available 0
추가: 대상 분기 fx_avg NaN → "no_data", months_available은 대상 행 값 유지
금액 비교는 pytest.approx(rel=1e-6)로 한다.

```