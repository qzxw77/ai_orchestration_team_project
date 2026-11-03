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


---

## 신해성
[preprocess] aggregate_quarterly (2026-11-03, 작성자: 신해성)

- 사용 도구: GitHub Copilot, GPAI, pytest

### ① 논리 설계

- 구현 대상: `hynix_nowcast/preprocess.py`의 `aggregate_quarterly`
- 목적: 월별 지역 수출 자료와 일별 환율 자료를 분기별로 집계한다.

- 함수 시그니처:

```python
def aggregate_quarterly(
    exports_df: pd.DataFrame,
    fx_df: pd.DataFrame,
    lag_months: int = 0
) -> pd.DataFrame:
```

- 입력:
  - `exports_df`: `ym`, `region`, `hs_code`, `export_usd`, `collected_at` 열을 포함하는 월별 수출 표.
  - `fx_df`: `date`, `usdkrw` 열을 포함하는 일별 환율 표.
  - `lag_months`: 수출 월에 적용할 개월 단위 시차.

- 출력:
  - `quarter`: 분기 문자열.
  - `export_usd`: 분기별 수출액 합계.
  - `months_available`: 집계에 포함된 서로 다른 월 수.
  - `fx_avg`: 분기별 환율 관측값의 산술평균.

- 처리 흐름:
  1. 음수 `lag_months`이면 `ValueError`를 발생시킨다.
  2. 빈 수출 표이면 정해진 열을 갖는 빈 결과를 반환한다.
  3. 이천시와 청주시 자료만 선택한다.
  4. 두 지역이 모두 존재하는 달만 집계 대상으로 사용한다.
  5. 수출 월에 `lag_months`를 적용한 뒤 분기를 구한다.
  6. 분기별 수출액 합계와 포함 월 수를 계산한다.
  7. 환율에는 시차를 적용하지 않고 분기별 평균을 계산한다.
  8. 수출 분기를 기준으로 환율을 결합한다.
  9. 해당 분기에 환율 자료가 없으면 `NaN`을 유지한다.

- 비고:
  - 위 내용은 검토한 코드와 제공 테스트를 바탕으로 정리한 설계 요약이다.
  - 최초 논리 설계서에 별도 요구사항이 있다면 대조하여 보완한다.

### ② 정밀 프롬프트 작성

- 프롬프트:

```text
[모듈] aggregate_quarterly (2026-11-03, 작성자: 신해성)

사용 도구: GitHub Copilot Chat

프롬프트:
당신은 파이썬 백엔드 개발을 돕는 어시스턴트입니다. SK하이닉스 분기 매출 나우캐스팅 시스템의 전처리 모듈(preprocess.py)에 들어갈 분기 집계 함수를 구현해 주세요.

[함수 시그니처, 변경 금지]
def aggregate_quarterly(exports_df: pd.DataFrame, fx_df: pd.DataFrame, lag_months: int = 0) -> pd.DataFrame:

[입력 명세]
exports_df: 월별 수출 표. (열: ym "YYYY-MM", region "이천시" 또는 "청주시", hs_code "854232", export_usd float, collected_at "YYYY-MM-DD")
fx_df: 일별 환율 표. (열: date "YYYY-MM-DD", usdkrw float)
lag_months: 수출액을 몇 개월 뒤 분기의 실적으로 반영할지 결정하는 시차 (기본값 0)

[출력 명세]
반환 열은 정확히 4개, 이 순서대로: quarter(str, "YYYYQn"), export_usd(float, 분기 합계), months_available(int, 수출 자료가 있는 달 수, 1~3), fx_avg(float, 분기 평균 환율)

[세부 구현 및 처리 규칙]
예외 및 경계 처리: exports_df가 비어 있으면 반환 열 4개를 가진 빈 표를 즉시 반환한다. lag_months < 0 인 경우 ValueError("lag_months는 0 이상이어야 합니다")를 발생시킨다.
데이터 불변성: 입력된 DataFrame(exports_df, fx_df)을 직접 수정하지 않고 복사본이나 집계 연산을 통해 새로운 객체를 생성한다.
수출 집계 (지역 교집합 필터링): exports_df를 ym 단위로 그룹화할 때, region 열에 "이천시"와 "청주시"가 모두 존재하는 달만 남긴다. 한 지역만 있는 달은 합산하지 않고 버린다. 조건에 맞는 월에 한해 export_usd를 합산한다.
분기 환산과 시차(Lag) 적용: 파일 내부에 밑줄로 시작하는 보조 함수(예: _get_shifted_quarter)를 만들어 구현한다. "YYYY-MM" 문자열의 월(month)에 lag_months를 더할 때 연도가 넘어가는 경우를 안전하게 처리한 뒤, 귀속 월이 속한 분기("YYYYQn") 문자열을 반환한다. 해당 분기 단위로 수출액을 다시 합산하고, 분기 내 포함된 월의 개수를 months_available(1~3) 열에 기록한다.
환율 집계: fx_df의 date("YYYY-MM-DD")를 분기("YYYYQn")로 변환하여 분기별 usdkrw의 평균(fx_avg)을 구한다. 환율에는 시차(lag_months)를 적용하지 않는다.
병합 (Merge): 수출이 존재하는 분기를 기준으로 환율 집계 결과를 병합(Left Merge)한다. 수출 자료가 하나도 없는 분기는 결과 행을 만들지 않는다. 환율 자료가 없는 분기의 fx_avg는 결측치(NaN/None)로 유지하며, 빠진 데이터를 0으로 채우지 않는다.

[제약 조건]
Python 3.10 이상, 파이썬 표준 라이브러리와 pandas만 사용 (numpy 등 다른 라이브러리 import 금지).
타입 힌트와 한국어 docstring(설명, Args, Returns, Raises) 필수.
결과 표의 열을 [quarter, export_usd, months_available, fx_avg] 순서로 맞추고, quarter 오름차순 정렬 후 인덱스를 0부터 다시 매긴다 (reset_index(drop=True)).
[통과해야 할 테스트]

정상 통합: 2026년 1~3월 두 지역 수출 데이터 모두 존재(매달 합계 100) -> 2026Q1에 export_usd 300, months_available 3 반환.
lag_months 적용: 2025-12월 두 지역 수출 데이터 존재, lag_months=1 -> 2026Q1 실적으로 집계.
경계 - 한 지역만 있는 달: 2026-04에 이천시 데이터만 존재 -> 2026Q2 집계에서 4월 데이터는 제외됨(months_available 반영 안 됨).
예외 - 빈 표: exports_df가 빈 표이면 4개 열을 가진 빈 표 반환.
```

- 비고:
  - 실제 프롬프트 원문을 보존한다.
  - 사후에 정리한 설명을 최초 프롬프트인 것처럼 기록하지 않는다.

### ③ AI 코드 생성

- 생성 도구: GitHub Copilot
- 생성 코드 파일: `hynix_nowcast/preprocess.py`
- 공개 함수: `aggregate_quarterly`
- 내부 보조 함수:
  - `_get_shifted_quarter`
  - `_empty_result`

- 생성 코드 위치: 5acdc8dc4bd8f216cc72029899b892d424a8e590

- 생성된 코드를 그대로 최종 결과로 확정하지 않고, 코드 리딩과 테스트를 진행했다.

### ④ 코드 리딩·검증

- 검토 자료:
  - 원본 `preprocess.py`: 94줄.
  - 제공된 `test_preprocess.py`: 테스트 3개.

- 점검 내용:
  - 함수 문서 및 제공 테스트와 구현의 일치 여부.
  - 입력값 검증과 조기 반환의 실행 순서.
  - 두 지역이 모두 있는 달만 집계하는지 여부.
  - 수출 월 시차 적용과 분기 집계 방식.
  - 입력 DataFrame 직접 수정 여부.
  - 광범위한 예외 처리 등 위험 관용구.

#### 코드 리딩에서 발견한 결함

1. 빈 입력일 때 음수 `lag_months` 검증이 생략됨.

   원본 50~53줄은 `exports_df.empty`를 먼저 검사하여 빈 결과를 반환한다.
   따라서 빈 수출 표와 `lag_months=-1`을 함께 전달하면
   `ValueError`가 발생하지 않는다.

   함수 docstring 47~48줄은 음수 시차에 `ValueError`를 명시하고 있으며,
   제공된 `test_empty_and_negative_lag`도 빈 표와 음수 시차를 함께
   전달하여 `ValueError` 발생을 요구한다.

   따라서 입력값 검증이 조기 반환 때문에 생략되는 결함으로 판정했다.

#### 수정 내역

- 수정 코드 위치: 1798f34ba0fcb98ded10e4a9b08baede20e1e70d

| 번호 | 원본 줄 | 원래 코드 | 수정 | 근거와 이유 |
|---|---|---|---|---|
| 1 | 50~53 | `exports_df.empty`이면 반환한 다음 `lag_months < 0` 검사 | 음수 시차 검사를 먼저 실행하고 이후 빈 입력 반환 | 빈 표와 음수 시차가 함께 들어오면 검증이 생략됨. 함수 docstring과 `test_empty_and_negative_lag`의 예외 처리 조건을 만족하도록 순서를 변경함. |

- 수정 전:

```python
if exports_df.empty:
    return _empty_result()

if lag_months < 0:
    raise ValueError("lag_months는 0 이상이어야 합니다")
```

- 수정 후:

```python
if lag_months < 0:
    raise ValueError("lag_months는 0 이상이어야 합니다")

if exports_df.empty:
    return _empty_result()
```

#### 구간별 리딩 기록

| 원본 줄 | 점검 대상 | 결과 |
|---|---|---|
| 1~3 | 모듈 설명 및 import | pandas 사용 확인 |
| 6~17 | 월 시차 및 분기 변환 | 월에 시차를 적용한 뒤 분기를 구함 |
| 20~29 | 빈 결과 생성 | 반환 열 순서와 dtype 명시 |
| 32~49 | 공개 함수 문서 | 입력, 출력, 음수 시차 예외 설명 확인 |
| 50~53 | 입력 검증 및 조기 반환 | 검증 순서 결함 발견 및 수정 |
| 55~63 | 지역 선택 및 완전한 달 판정 | 복사본 사용. 실제 고유 지역 수로 두 지역 존재 여부 확인 |
| 65~70 | 유효 월 부재 및 시차 적용 | 빈 결과 처리 및 월 단위 시차 적용 확인 |
| 71~78 | 분기별 수출 집계 | 수출액 합계와 고유 월 수 계산 확인 |
| 80~89 | 분기별 환율 집계 | 복사본 사용. 환율에는 시차를 적용하지 않음 |
| 91~94 | 결합 및 결과 정리 | 수출 기준 left join, 열 순서 및 인덱스 초기화 확인 |

#### 위험 관용구 점검

- 함수 전체를 감싸는 광범위한 `try/except`: 없음.
- 입력 DataFrame 직접 수정: 없음. 복사본에서 작업함.
- 파일 읽기·쓰기: 없음.
- 네트워크 접근: 없음.
- `print` 사용: 없음.

#### 명세 확인이 필요한 사항

아래 항목은 최초 프롬프트 원문을 확인하지 못했으므로
확정 결함으로 기록하지 않았다.

- 동일 월·지역의 중복 행을 모두 합산해도 되는지.
- `hs_code`를 함수에서 필터링해야 하는지, 입력에서 이미 보장하는지.
- 결측 수출액의 처리 정책.
- 잘못된 날짜, 필수 열 누락, 잘못된 시차 타입의 처리 정책.
- 환율 자료의 중복 날짜 허용 여부.
- 보조 함수에도 `Args`, `Returns`, `Raises` 전체가 필수인지.

### ⑤ 테스트

- 테스트 파일: `hynix_nowcast/test_preprocess.py`
- 제공된 테스트는 수정하지 않았다.

- 실행 위치:

```text
C:\Users\s2h02\my_project
```

- 실행 명령:

```powershell
python -m pytest -v .\hynix_nowcast\test_preprocess.py
```

- 실행 환경:
  - Windows
  - Python 3.13.15
  - pytest 9.2.0

- 실제 실행 결과:

```text
collected 3 items

hynix_nowcast/test_preprocess.py::test_aggregate_normal PASSED
hynix_nowcast/test_preprocess.py::test_lag_months_and_missing_region PASSED
hynix_nowcast/test_preprocess.py::test_empty_and_negative_lag PASSED

3 passed in 1.08s
```

| 테스트 | 확인 내용 | 결과 |
|---|---|---|
| `test_aggregate_normal` | 정상 분기 집계, 수출액 합계, 포함 월 수 | PASSED |
| `test_lag_months_and_missing_region` | 한 지역 누락 월 제외 및 시차 적용 | PASSED |
| `test_empty_and_negative_lag` | 빈 결과와 열 순서, 음수 시차 ValueError 발생 | PASSED |

- 테스트 결과: **pytest 3 passed in 1.08s**

- 비고:
  1. 최초 실행에서는 테스트 파일 경로를 잘못 지정하여
     `file or directory not found`가 발생했다.
     실제 파일 위치를 확인하고 실행 경로를 수정했다.
     이는 코드 테스트 실패가 아닌 파일 경로 문제였다.
  2. 제공된 테스트 3개가 통과한 것이며,
     모든 입력 및 경계 조건에서 결함이 없음을 보장하는 것은 아니다.
  3. 정상 테스트에는 `fx_avg` 값을 직접 검증하는 assertion이 없으므로,
     이번 통과 결과만으로 환율 계산까지 충분히 검증했다고 볼 수는 없다.


---

## 이다현
[모듈] compare_guidance (2026-11-03, 작성자: 이다현)
- 사용 도구: Gemini, GitHub Copilot Chat
- 
- 프롬프트:
- 당신은 파이썬 데이터 분석 코드 작성을 돕는 어시스턴트입니다. SK하이닉스 분기 매출 나우캐스팅 시스템의 분석 모듈(forecaster.py, 숫자 계산 전담)에 들어갈 함수를 구현해 주세요. 이 함수는 추정 매출의 전분기 대비 방향이 컨콜 가이던스가 가리키는 방향과 같은지 판정합니다.
- [함수 시그니처, 변경 금지] def compare_guidance(forecast: dict, guidance: dict) -> dict:
- [입력 명세] forecast: estimate_revenue 반환 dict (키: status, qoq_change_pct 등) / guidance: extract_guidance 반환 dict (키: status, price_outlook, dram_bit_growth_pct 등)
- [출력 명세] 키가 정확히 3개인 dict {"status": "일치"|"불일치"|"판단불가", "forecast_direction": "상승"|"보합"|"하락"|None, "guidance_direction": "상승"|"하락"|None}
- [계산 정의]
  -추정치 방향: forecast status가 "ok"일 때, qoq_change_pct > 2 이면 "상승", < -2 이면 "하락", 그 사이(±2 포함)면 "보합"
  -가이던스 방향: guidance status가 "ok"일 때, price_outlook이 "상승"이고 dram_bit_growth_pct가 0 이상(또는 None)이면 "상승". price_outlook이 "하락"이고dram_bit_growth_pct가 0 이하(또는 None)면 "하락". 그 외는 None
  -판정: 둘 중 하나라도 방향이 None이거나 추정치가 "보합"이면 "판단불가". 두 방향이 일치하면 "일치", 아니면 "불일치"
- [예외, 경계 방침] 어떤 경우에도 예외를 발생시키지 않는다. 입력이 누락되거나 비정상 값이 들어오면 "판단불가"로 반환한다.
- [제약 조건]
  - 방향 판정 경계값(2.0%)은 파일 맨 위 상수로 둔다 (DIRECTION_BAND_PCT = 2.0).
  - 입력 DataFrame/dict를 직접 수정하지 않고 새 dict를 반환한다.
  - 타입 힌트와 한국어 docstring 필수 작성. Raises는 없음.
- [통과해야 할 테스트] 직접 작성한 test_forecaster.py의 16개 파라미터 테스트 및 불변성/타입 방어 테스트 통과 필요.
- 생성 코드 위치: fb1612286abbf274ddf843b3928e57676768bc8c
- 코드 리딩에서 발견한 결함 (AI와의 설계 논의 과정 중 발견):
  1. 숫자가 아닌 불리언(True/False)이나 문자열이 들어올 경우 `q > 2` 등 비교 연산에서 `TypeError` 발생 가능성 존재.
  2. 값에 결측치(`NaN`)가 들어올 경우 크기 비교가 항상 `False`가 되어 "보합" 등 엉뚱한 값으로 오판정될 위험 존재.
  3. `forecast["status"]`와 같이 직접 접근할 경우 필수 키가 없는 비정상 입력 시 `KeyError` 발생 위험 존재 (어떤 경우에도 예외가 발생하면 안 된다는 규칙 위반).

| 번호 | 원본 방식 | 수정 코드 | 근거와 이유 |
| :--- | :--- | :--- | :--- |
| 1 | `forecast["status"]` 방식의 직접 접근 | `forecast.get("status") == "ok"` 방식으로 변경 | 딕셔너리에 키가 누락된 비정상 입력이 들어와도 `KeyError` 예외가 발생하지 않고 안전하게 처리하여 "판단불가"로 넘기기 위함. |
| 2 | `q > DIRECTION_BAND_PCT` 단순 비교 | `_is_valid_number(q)` 헬퍼 함수를 추가하여 검증 후 비교 | `NaN`이나 무한대, `True/False` 같은 비정상 타입이 들어와서 프로그램이 터지거나 오판정(보합)되는 것을 막기 위한 방어 로직. |
| 3 | `d >= 0` 단순 비교 | `d is None or (_is_valid_number(d) and d >= 0)` | 출하량 증감률(d) 값이 없어도 예외가 터지지 않게 하고, 확실히 유효한 숫자일 때만 상승/하락 조건에 반영하기 위함. |

- 테스트 결과: pytest 18 passed
- 비고:
  1. 구현 가이드의 "어떤 경우에도 예외를 내지 않는다"는 규칙을 준수하기 위해 `try-except`로 전체를 덮는 대신, `get()`과 `_is_valid_number()`를 활용해 타입 에러 자체를 원천 차단하는 방식으로 구현함.
  2. 추후 팀 통합 과정에서 방향 판정 경계값이 변경될 것을 대비해 DIRECTION_BAND_PCT = 2.0을 전역 상수로 분리하여 유지보수성을 높임.

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
