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


---

## 신동훈


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
