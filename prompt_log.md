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
- 사용 도구: GitHub Copilot Chat
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
    2024-09~2025-08 매달 64 / 2025-09~2026-08: 64, 88, 40, 80, 48, 88, 40, 64, 64, 64, 64, 64
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
| 4 | 56, 150~151 (함께 16, 17줄) | 함수 본문 전체를 `try`로 감싸고 `except (AttributeError, KeyError, TypeError, ValueError, OverflowError): return default` | try/except를 지우고 본문 들여쓰기를 한 단계 줄임. 그 결과 드러난 `_is_valid_ym`의 `isdigit()`을 `isdecimal()`로 바꿈 | 리딩 체크리스트 4번 "광범위한 except"에 해당. 코드 실수로 난 KeyError, TypeError도 "데이터 부족"으로 바뀌어 자료가 정말 부족한 경우와 구별할 수 없음. 프롬프트 27줄을 따른 결과이므로 프롬프트도 고칠 대상(비고) |

- 테스트 결과: pytest 6 passed
- 비고:  
  1) 결함 4는 프롬프트 27줄 "어떤 경우에도 예외를 발생시키지 않는다"를 Copilot이 그대로 따른 결과다. 그러나 리딩 체크리스트 4번(광범위한 except)에 해당하고 실제로 오류를 숨기고 있었으므로 수정했다. 원인은 프롬프트 문구에 있으므로 다음 사이클에서는 27줄을 "자료 문제(형식 오류, 빈 표, 빠진 달, 0 나누기, 표준편차 0)로는 예외를 내지 않고 기본값을 반환한다. 함수 전체를 try/except로 감싸지 않는다"로 고친다.
  2) 수정 4 이후 숫자가 아닌 threshold처럼 호출하는 쪽이 잘못한 경우에는 TypeError가 난다. 의도한 동작이며 docstring Raises에 적었다

---

## 신동훈


---

## 신해성


---

## 이다현


---

## 조현모