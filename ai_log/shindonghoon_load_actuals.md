## [2026-11-09] load_actuals 입력 검증 오류 수정 (담당: 신동훈)

- 대상 모듈: `신동훈/data_loader.py` / 관련 커밋: 테스트 선커밋 `521f13a` → Copilot 생성본 `7c4af18` → 수정 `2b9acaa`·`10f0088`·`d8f5090`·`d791b97` → 회귀 테스트 `f24931f` (브랜치 `feat/load_actuals`)
- 초기 프롬프트(요지): 구현 가이드 1.1절 Pseudocode에 재량 항목 결정(utf-8-sig, 원문 문자열 그대로 읽기, 형식 오류를 모아 한 번에 알림, 빈 줄 무시 등)을 더했다. 여기에 시그니처, actuals 표 스키마, 예외 방침(입력 문제는 한국어 ValueError, 잘못된 행을 조용히 지우지 않음), 상수 5개, 테스트 L01~L12를 넣어 Copilot Chat(Ask 모드, `#file:test_load_actuals.py` 참조)에 요청했다. 테스트 파일은 생성 전에 먼저 커밋했다(`521f13a`). 프롬프트 원문은 `prompt_log.md`에 기록했다.
- AI 생성 결과(요지): 테스트 24건(L01~L12, 값을 바꿔 반복하는 케이스 포함)이 모두 통과했다. `keep_default_na=False` + `skip_blank_lines=False` 조합으로, 진짜 빈 줄이 있어도 오류 메시지의 줄 번호가 정확했다. 프롬프트보다 나은 처리라 그대로 채택했다. 생성본은 `7c4af18`에 보존했다.
- 발견한 문제: 테스트에 없는 경계 입력(메모장 입력 실수, 전각 입력)을 넣어 한 줄씩 따라가며 4건을 발견했다.
  1. 칸 수가 맞지 않는 줄: pandas가 넘치는 칸을 index로 자동 추론해서 `int(row_index)`에서 TypeError(따옴표 없는 쉼표 매출 `2025Q1,19,600,000,000,000,...`)나 영어 메시지 오류가 났다. "입력 문제는 한국어 ValueError" 방침 위반이다.
  2. 전각 숫자 quarter: 정규식 `\d`가 모든 유니코드 숫자와 맞아서 `２０２５Q1`이 통과했다. 화면에서는 같아 보이지만 estimate_revenue가 2025Q1 실적을 찾지 못하고, 분기 중복 검사와 정렬도 어긋난다.
  3. 빈 표를 돌려줄 때 `revenue_krw` dtype이 object였다(명세는 float64).
  4. 공백 제거 후 열 이름이 겹치면 `row["quarter"]`가 Series가 되어 TypeError가 났다.
- 수정 내역 (커밋 순서):
  - `2b9acaa` (fix, 문제 1): `read_csv`에 `index_col=False`를 추가하고, `ParserError`를 한국어 ValueError로 변환했다. 따옴표 없는 쉼표 입력은 이제 `2행 announced_date '600'` 형식 오류로 알린다. 칸이 밀린 탓에 문제 열이 announced_date로 표시되는 한계는 있다.
  - `10f0088` (fix, 문제 3): 빈 표 반환을 `actuals.astype({"revenue_krw": "float64"}).reset_index(drop=True)`로 교체했다. quarter·announced_date의 타입도 정상 경로와 같아졌다.
  - `d8f5090` (fix, 문제 2): `QUARTER_PATTERN`을 `^[0-9]{4}Q[1-4]$`로 바꿔 ASCII 숫자만 허용했다.
  - `d791b97` (fix, 문제 4): 열 이름 공백 제거 직후 중복 검사를 추가했다(`ValueError("actuals.csv 열 이름 중복: <열 이름>")`).
  - `f24931f` (test): 문제 1·2의 회귀 테스트 L13·L14를 추가했다. 원본 코드에서는 3 failed, 수정 코드에서는 통과했다. 기존 L01~L12는 수정하지 않았다. **정확성·보안(입력 검증)**을 개선한 사례다.
- 검증: pytest 27 passed (기존 24 + 새 3), 커밋 `f24931f`. 
- pytest 결과
    
    ===================== test session start========================

    platform win32 -- Python 3.13.14, pytest-9.2.0, pluggy-1.7.0 -- C:\dev\ai_studio\ai_orchestration_team_project\신동훈\.venv\Scripts\python.exe
    cachedir: .pytest_cache
    rootdir: C:\dev\ai_studio\ai_orchestration_team_project\신동훈
    collected 27 items                                                                                                                                          

    test_load_actuals.py::test_L01_normal_file PASSED                                                                                                     [  3%]
    test_load_actuals.py::test_L02_messy_but_valid_file PASSED                                                                                            [  7%]
    test_load_actuals.py::test_L03_header_only_returns_empty_table PASSED                                                                                 [ 11%]
    test_load_actuals.py::test_L04_blank_row_is_ignored PASSED                                                                                            [ 14%]
    test_load_actuals.py::test_L05_missing_required_columns[no_revenue_krw] PASSED                                                                        [ 18%]
    test_load_actuals.py::test_L05_missing_required_columns[no_quarter_and_date] PASSED                                                                   [ 22%]
    test_load_actuals.py::test_L06_zero_byte_file PASSED                                                                                                  [ 25%]
    test_load_actuals.py::test_L07_invalid_quarter[2025-Q1] PASSED                                                                                        [ 29%]
    test_load_actuals.py::test_L07_invalid_quarter[2025Q5] PASSED                                                                                         [ 33%]
    test_load_actuals.py::test_L07_invalid_quarter[25Q1] PASSED                                                                                           [ 37%]
    test_load_actuals.py::test_L07_invalid_quarter[2025q1] PASSED                                                                                         [ 40%]
    test_load_actuals.py::test_L08_invalid_revenue[NA] PASSED                                                                                             [ 44%]
    test_load_actuals.py::test_L08_invalid_revenue[blank] PASSED                                                                                          [ 48%]
    test_load_actuals.py::test_L08_invalid_revenue[zero] PASSED                                                                                           [ 51%]
    test_load_actuals.py::test_L08_invalid_revenue[negative] PASSED                                                                                       [ 55%]
    test_load_actuals.py::test_L08_invalid_revenue[inf] PASSED                                                                                            [ 59%]
    test_load_actuals.py::test_L08_invalid_revenue[text] PASSED                                                                                           [ 62%]
    test_load_actuals.py::test_L09_invalid_announced_date[slash] PASSED                                                                                   [ 66%]
    test_load_actuals.py::test_L09_invalid_announced_date[one_digit_month] PASSED                                                                         [ 70%]
    test_load_actuals.py::test_L09_invalid_announced_date[not_a_real_date] PASSED                                                                         [ 74%]
    test_load_actuals.py::test_L09_invalid_announced_date[blank] PASSED                                                                                   [ 77%]
    test_load_actuals.py::test_L10_duplicate_quarter PASSED                                                                                               [ 81%]
    test_load_actuals.py::test_L11_all_format_errors_reported_at_once PASSED                                                                              [ 85%]
    test_load_actuals.py::test_L12_file_not_found PASSED                                                                                                  [ 88%]
    test_load_actuals.py::test_L13_fullwidth_digit_quarter PASSED                                                                                         [ 92%]
    test_load_actuals.py::test_L14_mismatched_field_count[unquoted_comma_revenue] PASSED                                                                  [ 96%]
    test_load_actuals.py::test_L14_mismatched_field_count[one_row_extra_field] PASSED                                                                     [100%]

    ============================================== 27 passed in 3.09s ==================================== 


- 판단 메모: 원본 코드도 24 passed였다. "테스트 전체 통과"가 곧 명세 준수는 아니었다. 사람이 입력하는 파일은 따옴표 누락, 전각 입력 같은 현실적인 오입력을 먼저 떠올려 경계 케이스로 넣는다. 같은 유니코드 숫자 문제가 `forecaster.py`의 `_quarter_index`(`isdecimal()`)에도 있지만, target_quarter는 화면에서 고르는 값이고 결과가 no_data로 끝나 영향이 낮아 보류했다.