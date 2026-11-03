# 알트(ALT) 팀 AI 활용 과정 기록

- 사이클(함수 하나) 1회전마다 항목 1개를 추가한다.
- 병합 충돌을 줄이기 위해 **자기 이름 섹션 안에만** 작성한다.
- 프롬프트에 실명, 전화번호 같은 개인정보, 실데이터, API 키를 넣지 않는다.
- 시그니처를 바꿨다면 그 사유를 항목에 함께 적는다.

<!--
항목 양식 (복사해서 사용)

### [모듈] 함수명 (YYYY-MM-DD, 작성자: 이름)
- 사용 도구:
- 프롬프트: (원문 전체를 그대로 붙여넣기)
- 생성 코드 위치: 커밋 (수정 전 원본 해시)
- 코드 리딩에서 발견한 결함:
  1)
  2)
- 수정 내역: 커밋 (수정 커밋 해시)
- 테스트 결과: pytest N passed
- 비고: (시그니처 변경 사유, 명세에서 새로 정한 규칙 등)
-->

---

## 강민규

[모듈] 함수명 (2026-11-01, 작성자: 강민규)
- 사용 도구: GitHub Copilot Chat, Claude
- 프롬프트:  
    당신은 파이썬 데이터 분석 코드 작성을 돕는 어시스턴트입니다.
    SK하이닉스 분기 매출 나우캐스팅 시스템의 분석 모듈(forecaster.py, 숫자 계산 전담)에 들어갈 함수를 구현해 주세요.
    이 함수는 대상 월 수출의 전년 동월 대비 증가율이 직전 12개월의 평소 범위를 벗어났는지 판정합니다.
    
    [함수 시그니처, 변경 금지]
    def detect_anomaly(exports_df: pd.DataFrame, target_ym: str, threshold: float = 2.0) -> dict:
    
    [입력 명세]
    exports_df: 월별 지역 수출 표 (한 달은 이천시, 청주시 2행)
    ym: str "YYYY-MM" / region: str "이천시" 또는 "청주시" / hs_code: str "854232"
    export_usd: float (달러, 0 이상) / collected_at: str "YYYY-MM-DD"
    예) {"ym": "2026-09", "region": "이천시", "hs_code": "854232", "export_usd": 5.0e9, "collected_at": "2026-10-15"}
    target_ym: 판정할 월 "YYYY-MM" (예: "2026-09")
    threshold: |z| 기준값 (기본 2.0)
    
    [출력 명세]
    키가 정확히 5개인 dict
    {"ym": target_ym 그대로(str), "yoy_pct": float 또는 None, "z_score": float 또는 None,
    "is_anomaly": bool, "reason": "정상", "급증", "급감", "데이터 부족" 중 하나}
    예) {"ym": "2026-09", "yoy_pct": 25.0, "z_score": 1.0, "is_anomaly": False, "reason": "정상"}
    계산 정의
    - 월 합계 = 같은 ym의 이천시 export_usd + 청주시 export_usd
    - 전년동월비(m) = (월 합계[m] / 월 합계[m의 12개월 전] - 1) * 100, yoy_pct = 전년동월비(target_ym)
    - z = (yoy_pct - 직전 12개월 전년동월비의 평균) / 직전 12개월 전년동월비의 표본 표준편차(n - 1로 나눔)
    - |z| > threshold 이면 is_anomaly True, z가 양수면 "급증", 음수면 "급감". 그 외는 False, "정상"
    
    [예외, 경계 방침] 어떤 경우에도 예외를 발생시키지 않는다
    기본값 = {"ym": target_ym, "yoy_pct": None, "z_score": None, "is_anomaly": False, "reason": "데이터 부족"}
    - target_ym이 "YYYY-MM"(월 01~12) 형식이 아니면 기본값 반환
    - 빈 표이거나 ym, region, export_usd 열이 없으면 기본값 반환
    - 두 지역 중 하나만 있는 달은 월 합계가 없는 달로 본다
    - 대상 월과 그 앞 24개월(모두 25개월) 중 하나라도 월 합계가 없으면 기본값 반환 (행 개수가 아니라 달 기준으로 확인)
    - 전년동월비 13개(대상 월과 직전 12개월)를 구할 때 12개월 전 합계가 0인 달이 있으면 기본값 반환 (0으로 나누지 않음)
    - 표준편차가 STD_EPSILON 미만이면 0으로 보고, yoy_pct만 채운 기본값 반환
    (pandas std()는 같은 값만 있어도 0이 아니라 1e-15 수준을 돌려준다)
    - |z|가 threshold와 정확히 같으면 "정상" (초과일 때만 이상치)
    
    [제약 조건]
    - Python 3.10 이상, 표준 라이브러리와 pandas만 사용 (numpy 등 다른 라이브러리 import 금지)
    - 시그니처를 바꾸지 않는다. 공개 함수를 새로 만들지 않고, 보조 함수는 밑줄로 시작하는 내부 함수로 만든다 (예: _shift_ym)
    - 타입 힌트와 한국어 docstring(설명, Args, Returns, Raises) 필수. Raises는 "없음"으로 적는다
    - 입력 DataFrame을 직접 수정하지 않고 복사본에서 작업한다. 행 순서에 의존하지 않는다
    - 파일 읽기/쓰기, 네트워크, print, 프로젝트의 다른 모듈 import 금지. 값을 받아 RETURN만 한다
    - 반환값은 파이썬 기본 타입(float, bool, None)으로 돌려준다. numpy.float64, numpy.bool_ 금지
    - 계산 결과를 반올림하지 않는다. 값이 없으면 0이 아니라 None. 빠진 달을 0으로 채우지 않는다
    - 파일 맨 위 상수: ALLOWED_REGIONS = ("이천시", "청주시"), STD_EPSILON = 1e-9 (threshold 기본값 2.0은 시그니처 그대로 둔다)
    
    [통과해야 할 테스트, test_detect_anomaly.py, 테스트를 고쳐서 통과시키지 말 것]
    공통 입력 A: 매달 이천시 62.5% + 청주시 37.5% 두 행 (단위 1억 달러)
    2024-09\~2025-08 매달 64 / 2025-09\~2026-08: 64, 88, 40, 80, 48, 88, 40, 64, 64, 64, 64, 64
    직전 12개월 전년동월비 평균 0, 표본 표준편차 25
    - 정상 1: 대상 월 2026-09 합계 80 -> yoy_pct 25.0, z_score 1.0, is_anomaly False, reason "정상"
    - 정상 2: 합계 128 -> yoy_pct 100.0, z_score 4.0, is_anomaly True, reason "급증"
    - 경계 1: 2024-09가 없어 24개월 -> 기본값
    - 경계 2: 기준 해 100, 직전 12개월 110, 대상 월 121 -> yoy_pct 10.0, z_score None, reason "데이터 부족"
    - 예외 1: target_ym "2026-13" -> 예외 없이 기본값
    - 예외 2: 2025-03 합계 0 -> 예외 없이 기본값


- 생성 코드 위치: 066dbbb79bd7979ddd4eb9eb826a28311c7fb708  
- 코드 리딩에서 발견한 결함:  
  1) 한 지역만 있는 달도 월 합계에 들어감. 처음 보는 달에 두 지역을 0.0으로 미리 넣어 두 지역 확인 검사가 항상 통과함. 2025-09 청주시 자료가 빠지면 실제 0%인 달을 +60% "급증"으로 오경보 (프롬프트 31줄 위반)
  2) threshold를 float로 바꾸고 무한대면 "데이터 부족"을 돌려줌. 프롬프트는 판정을 |z| > threshold로만 정의하고, 기본값을 돌려줄 경우에 threshold는 없음 (프롬프트 25, 28~36줄 위반)
  3) 보조 함수 _is_valid_ym, _shift_ym에 docstring 없음 (프롬프트 41줄 위반)
  4) 함수 전체를 try/except로 감싸 코드 오류까지 "데이터 부족"으로 바꿈 (리딩 체크리스트 4번: 광범위한 except).  

- 수정 내역: 6c4c7eef6688f76693ec2e9aefce23a38acf85d0

| 번호 | 원본 줄 | 원래 코드 | 수정 | 근거와 이유 |  
|---|---|---|---|---|  
| 1 | 91~94 | `setdefault(ym, {"이천시": 0.0, "청주시": 0.0})[region] += amount` | `setdefault(ym, {})`로 빈 dict를 두고, 실제로 들어온 지역만 `regions.get(region, 0.0) + amount`로 더함 | 프롬프트 31줄 "두 지역 중 하나만 있는 달은 월 합계가 없는 달로 본다" 위반. 처음 보는 달에 두 지역을 0.0으로 미리 넣어서 원본 99줄의 `all(...)` 검사가 항상 True가 됨. 프롬프트의 공통 입력 A에서 2025-09 청주시 자료가 빠지면 실제 0%인 달을 +60% 급증으로 오경보 |
| 2 | 60~62, 134 | `threshold_value = float(threshold)`, `if not math.isfinite(threshold_value): return default` | 세 줄 삭제, 134줄에서 `threshold`를 그대로 비교 | threshold가 비정상일 때 "데이터 부족"을 돌려줘 원인(기준값 문제)과 결과(자료 부족)가 맞지 않고, 프롬프트 25줄의 판정 정의(무한대면 "정상")와도 다름. 또한 프롬프트에도 없었던 내용이라 삭제함 |
| 3 | 11, 22 | 보조 함수 `_is_valid_ym`, `_shift_ym`에 docstring 없음 | 두 함수에 설명, Args, Returns, Raises docstring 추가 | 프롬프트 41줄 "타입 힌트와 한국어 docstring(설명, Args, Returns, Raises) 필수" 위반 |
| 4 | 56, 150~151 (함께 16, 17줄) | 함수 본문 전체를 `try`로 감싸고 `except (AttributeError, KeyError, TypeError, ValueError, OverflowError): return default` | try/except를 지우고 본문 들여쓰기를 한 단계 줄임. “try가 없어도 형식 검사가 예외를 내지 않도록 `isdigit()`을 `isdecimal()`로 보완 | 리딩 체크리스트 4번 "광범위한 except"에 해당. 코드 실수로 난 KeyError, TypeError도 "데이터 부족"으로 바뀌어 자료가 정말 부족한 경우와 구별할 수 없음. 프롬프트 27줄을 따른 결과이므로 프롬프트도 고칠 대상(비고) |

- 테스트 결과: pytest 6 passed
- 비고:  
  1) 결함 4는 프롬프트 27줄 "어떤 경우에도 예외를 발생시키지 않는다"를 Copilot이 그대로 따른 결과다. 그러나 리딩 체크리스트 4번(광범위한 except)에 해당하고 코드 오류가 "데이터 부족"으로 가려질 수 있어 수정했다. 원인은 프롬프트 문구에 있으므로 다음 사이클에서는 27줄을 "자료 문제(형식 오류, 빈 표, 빠진 달, 0 나누기, 표준편차 0)로는 예외를 내지 않고 기본값을 반환한다. 함수 전체를 try/except로 감싸지 않는다"로 고친다.
  2) 수정 4 이후 숫자가 아닌 threshold처럼 호출하는 쪽이 잘못한 경우에는 TypeError가 난다. 의도한 동작이며 docstring Raises에 적었다

---

## 신동훈

[모듈] forecaster.py · estimate_revenue — 2026-11-02, 작성자: 신동훈

- 사용 도구: GitHub Copilot Chat 
- 프롬프트:
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
- 생성 코드 위치: c681b9d (수정 전 원본)
- 코드 리딩에서 발견한 결함:
  1) 명세 밖 필수 열 검사 제거 (커밋 `74b0de4`)
     - 수정: AI가 임의로 추가한 필수 열·DataFrame 타입 검사 블록(원본 88~106줄)을 삭제함. 이제 열이 없으면 `KeyError`가 나서 문제 위치가 바로 드러남
     - 근거: 열 누락은 상류 함수의 버그인데 이를 status `no_data`로 반환해 "예측할 데이터 없음"으로 숨김. 열 보장은 `load_actuals`·`aggregate_quarterly`의 역할임. 구현 가이드의 "예외를 내지 않는다"는 자료 부족에만 해당하므로, 이 검사는 팀 규칙 "예외를 조용히 삼키지 않는다"에 어긋남

  2) 음수 month_available 출력 방지 (커밋 `2aa330c`)
     - 근거: 기존 코드는 결과에 먼저 대입한 뒤 검사해서, 입력 -1이 그대로 출력됨. 이는 출력 명세(0~3) 위반이고, forecasts.csv와 화면의 "반영된 개월 수"까지 전달됨. 0·3 입력으로는 드러나지 않아 기존 테스트가 놓쳤고, 음수를 넣어 한 줄씩 따라가며 발견함

  3) estimate_revenue 기준 분기 선택을 pandas 필터로 단순화 (커밋 `e382473`)
     - 수정: 3단계 루프(itertuples → dict → set 교집합 → for, 약 60줄)를 `merge` + 조건 마스크(대상 분기 이전, months_available == 3, export_usd > 0, fx_avg > 0) + `sort_values().tail(4)`로 바꿈. 불필요한 try/except 5곳 제거, 평균은 `len(ratios)`로 계산, `MONTHS_PER_QUARTER = 3` 상수 추가
     - 근거: 코드가 지나치게 복잡해 설명하기 어려움. 중복 try/except는 앞 단계 버그를 조용히 no_data·제외로 바꿀 수 있음. `fx_avg`가 0이면 ZeroDivisionError가 날 수 있었음. 또 상수 `RATIO_WINDOW`로 나누면 기준 분기가 4개 미만일 때 평균이 틀어짐
- 수정 내역: 
    74b0de4(수정1), 2aa330c(수정2), e382473(수정3)
- 테스트 결과: pytest 9 passed


---

## 신해성


---

## 이다현


---

## 조현모

### [preprocess] clean_exports (2026-10-31, 작성자: 조현모)
- 사용 도구: GitHub Copilot Chat (VS Code, Copilot Free 플랜, 모델: auto)
  - 1차: Agent 모드로 전송됨 → 저장소 탐색 중(test_preprocess.py 읽음) 사용자가 중단
  - 2차: Ask 모드로 같은 프롬프트 재전송 → 응답 코드를 그대로 `조현모/preprocess.py`에 저장
  - 대화 기록: Export Chat(chat.json)으로 로컬 보관
- 프롬프트: (원문 전체)

```text
당신은 파이썬 백엔드 개발을 돕는 어시스턴트입니다.
SK하이닉스 분기 매출 나우캐스팅 시스템(알트 ALT)의 [모듈 2] preprocess.py에 들어갈 함수 clean_exports 하나만 구현해 주세요.
이 함수는 관세청에서 받은 이천시·청주시 메모리 반도체(HS 854232) 월별 수출 원자료를 정제합니다.

[함수 시그니처 — 변경 금지]
def clean_exports(raw_df: pd.DataFrame) -> pd.DataFrame:

[입력 명세]
raw_df: 수출 원자료 DataFrame. 필수 열(RAW_COLUMN_MAP으로 이름을 바꾼 뒤 기준): ym, region, hs_code, export_usd, collected_at
값 예시(지저분할 수 있음):
  {"ym": 202607, "region": "경기도 이천시", "hs_code": "854232", "export_usd": "5,000,000,000", "collected_at": "2026-09-15"}
  ym은 정수 202607, float 202607.0, 문자열 "2026-07"·"202607"·"2026.07"로 올 수 있다.

[출력 명세]
exports 표(DataFrame). 열은 정확히 5개, 이 순서: ym, region, hs_code, export_usd, collected_at
  - ym: "YYYY-MM" 문자열 / region: "이천시" 또는 "청주시" / hs_code: 문자열(숫자로 바꾸지 않음)
  - export_usd: float(달러, 0 이상) / collected_at: "YYYY-MM-DD" 문자열(수집일)
ym 오름차순으로 정렬하고 행 번호를 0부터 다시 매긴다.

[처리 순서 — Pseudocode]
함수 clean_exports — 입력: 수출 원자료 표(raw_df) / 출력: exports 표
    IF raw_df가 비어 있으면(행 0개)
        RETURN exports 표의 열 5개만 있는 빈 표
    표 = raw_df의 복사본
    RAW_COLUMN_MAP에 따라 원본 열 이름을 표준 열 이름으로 바꾼다(이미 표준 이름인 열은 그대로)
    IF ym, region, hs_code, export_usd, collected_at 중 없는 열이 있으면
        ValueError("필수 열 누락: <없는 열 이름들>")를 발생시킨다
    region = REGION_NAME_MAP에 따라 표준 이름으로 바꾼 값(예: "경기도 이천시" → "이천시")
    ym = YM_FORMATS 중 맞는 형식으로 읽어 "YYYY-MM" 문자열로 바꾼 값(어느 형식에도 안 맞으면 결측)
    hs_code = 문자열로 바꾼 값(앞자리 0 유지)
    export_usd = 숫자로 바꾼 값(바꿀 수 없으면 결측)
    ym 또는 export_usd가 결측인 행을 제거한다
    export_usd가 0보다 작은 행을 제거한다          # 0은 유효한 값이라 남긴다
    region이 ALLOWED_REGIONS에 없는 행을 제거한다
    키(ym, region, hs_code)가 같은 행은 collected_at이 가장 최근인 1행만 남긴다
        # collected_at이 빈 행은 가장 오래된 것으로 본다
    # 빠진 달은 0으로 채우지 않는다
    열을 ym, region, hs_code, export_usd, collected_at 순서로만 남긴다
    ym 오름차순으로 정렬하고 행 번호를 0부터 다시 매긴다
    RETURN 정제된 표

[예외·경계 방침]
- 빈 입력(0행, 열이 없는 빈 표 포함): 예외 없이 열 5개짜리 빈 표 반환. 필수 열 검사보다 먼저 한다.
- 필수 열 누락: ValueError("필수 열 누락: export_usd, ym")처럼 없는 열을 모두 적는다. ValueError는 이 경우에만 낸다.
- 지저분한 행(결측, "N/A"처럼 숫자로 바꿀 수 없는 값, 2026-13 같은 없는 달, 음수, 대상 외 지역)은 예외 없이 제거한다.
- export_usd = 0은 남긴다. 무한대는 결측으로 본다.
- 정제 후 남은 행이 없어도 열 5개짜리 빈 표를 반환한다.

[제약 조건 — 프로젝트 공통]
- Python 3.10 이상. 파이썬 표준 라이브러리와 pandas만 사용한다(numpy 직접 import 금지).
- 시그니처를 바꾸지 않는다. 보조 함수는 밑줄로 시작하는 내부 함수(예: _parse_ym)로 같은 파일에 만든다.
- 모든 함수에 타입 힌트와 한국어 docstring(설명, Args, Returns, Raises)을 단다.
- 가변 기본값 인자 금지. 전역 변수를 읽거나 바꾸지 않는다(파일 맨 위 대문자 상수는 읽기 전용으로 허용).
- 입력 DataFrame을 직접 수정하지 않는다. 복사본에서 작업한다.
- print 금지. 파일 읽기·쓰기, 외부 API 호출, 다른 프로젝트 모듈 import 금지.
- except: pass처럼 예외를 조용히 삼키지 않는다.

[제약 조건 — 함수별: clean_exports]
■ 자료구조: 반환 열은 정확히 5개, 위 순서. ym은 "YYYY-MM" 문자열, hs_code는 문자열, export_usd는 float.
■ 처리 방식: 키(ym, region, hs_code)가 같으면 collected_at이 가장 최근인 행만 남긴다(입력 순서와 무관하게).
■ 하지 말 것: 빠진 달을 0으로 채우지 않는다. 월·분기 합계를 계산하지 않는다(aggregate_quarterly의 역할).
■ 변경 대비: RAW_COLUMN_MAP(원본 열 → 표준 열, 지금은 빈 dict), REGION_NAME_MAP, ALLOWED_REGIONS = ("이천시", "청주시"),
  YM_FORMATS를 파일 맨 위 대문자 상수로 둔다.

[검증 기준 — 아래 테스트를 모두 통과해야 함(설계 문서 파트 4)]
기본값: hs_code "854232", collected_at "2026-09-15"
T01 [정상] ym 202608·이천시·5.5e9 / 202607·청주시·2.0e9 / 202607·이천시·5.0e9
     → 3행, ym = ["2026-07", "2026-07", "2026-08"], 열 5개
T02 [정상] 같은 키(2026-07·이천시·854232): collected_at 2026-08-15·5.0e9 / 2026-09-15·5.2e9
     → 1행, export_usd 5.2e9, collected_at "2026-09-15"
T03 [경계] 0행 빈 표 → 0행, 열 5개, 예외 없음
T04 [경계] export_usd 0(청주시), -1(이천시) → 청주시 0원 행 1개만 남음
T05 [예외] 정상 1행 + export_usd 빈칸 / "N/A" / ym "2026-13" / region "용인시" → 정상 1행만, 예외 없음
T06 [예외] export_usd 열이 없는 표 → ValueError, 메시지에 "export_usd" 포함

코드를 만든 뒤, 위 예외·경계 방침 각각이 코드의 어느 줄에서 처리되는지 짧게 설명해 주세요.
```

- 생성 코드 위치: 커밋 2c71515 (Copilot 생성 원본, 수정 없음)
- 원본 테스트 결과: pytest 19 passed. 1차 Agent 시도에서 Copilot이 테스트 파일을 읽었으므로 테스트에 맞춰진 코드일 수 있어 코드 리딩으로 추가 검증함
- 코드 리딩에서 발견한 결함 (강의 31쪽 체크리스트 기준, 각각 실행으로 확인):
  1) [하드코딩] `_parse_ym`이 형식마다 모양 검사를 직접 코딩하고 `else`를 "%Y.%m"으로 간주 → YM_FORMATS에 "%Y/%m"을 추가해도 "2026/07"이 None. 상수만 고치면 되도록 한 설계(변경 대비) 위반
  2) [경계·위험 관용구] `_parse_collected_at`이 `pd.to_datetime`에 형식 없이 날짜를 추측 → "03/04/2026"이 3월 4일, "2026"이 2026-01-01로 해석, UserWarning 발생
  3) [명세 불일치] 명세에 없는 "hs_code 결측 행 제거" 조건(`hs_code.notna()`)이 추가됨
  4) [경계] 최종 정렬이 ym만 기준 → 같은 달 행 순서가 수집일 순서에 따라 달라짐(결과가 입력에 의존)
  5) [설명 가능성] 모듈 docstring 없음, clean_exports docstring에 처리 규칙(0원 유지, 중복 규칙, 빈 달 미보충) 누락
  6) [불필요한 연산] 지역 처리 람다에서 `str(value).strip()`을 두 번 계산
- 수정 내역: 커밋 ceb1d1c
  1) 해석 결과를 같은 형식으로 다시 써서 원래 글자와 같은지 비교하는 방식으로 변경, YM_FORMATS에 "%Y/%m" 추가
  2) COLLECTED_AT_FORMAT = "%Y-%m-%d" 상수 추가 후 format 지정
  3) `hs_code.notna()` 조건 삭제(설계 문서·구현 가이드 명세대로)
  4) 정렬 키를 ["ym", "region", "hs_code"]로 고정
  5) 모듈 docstring 추가, clean_exports docstring에 처리 규칙 3줄 추가
  6) 내부 함수 `_normalize_region`으로 분리
  - 결함 확인과 수정 코드 작성에 Claude(Cowork)를 보조로 사용함. 수정 내용은 git diff로 직접 검토함
- 테스트 결과: pytest 19 passed (T01~T06 + 추가 X01~X11), `조현모/pytest_result.txt`
- 비고:
  - 시그니처 변경 없음
  - 테스트 X01~X11은 구현 가이드 1.2 '반드시 지킬 것'과 공통 제약을 검사하려고 추가함. 테스트 작성에 Claude(Cowork) 보조 사용
  - 담당자 재량으로 정한 것: YM_FORMATS 4종, REGION_NAME_MAP 2건, 천 단위 쉼표 제거, 무한대 = 결측, ALLOWED_HS_CODES 미적용
  - 팀 확인 필요: RAW_COLUMN_MAP 실제 값(관세청 API 명세 확정 후, 신해성), "2026-7"처럼 0이 빠진 월은 현재 제거됨