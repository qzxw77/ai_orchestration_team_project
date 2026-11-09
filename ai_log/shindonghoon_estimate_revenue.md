## [2026-11-02] estimate_revenue 가독성 리팩터링 (담당: 신동훈)

- 대상 모듈: `신동훈/forecaster.py` / 관련 커밋: Copilot 생성본 `c681b9d` → 오류 수정 `74b0de4`·`2aa330c` → 리팩터링 `e382473`
- 초기 프롬프트(요지): 설계 문서 V1의 시그니처, forecast dict 키 8개, Pseudocode, 예외 방침(예외 없이 status로만 알림, 대상 분기와 그 이후의 actuals는 읽지 않음), 공통 제약(pandas만 사용, 입력 표 미수정, `RATIO_WINDOW` 상수)과 테스트 T07~T11·A01~A04를 넣어 Copilot Chat에 요청했다. 프롬프트 원문은 `prompt_log.md`에 기록했다.
- AI 생성 결과(요지): 테스트는 통과했지만 기준 분기를 itertuples → dict → set 교집합 → for 반복의 3단계로 고르는 약 60줄짜리 코드(원본 119~227줄)였다. 이미 숫자인 값을 다시 변환하는 try/except가 5곳 있었고, 프롬프트에 없는 필수 열·타입 검사(원본 88~106줄)도 임의로 추가되어 있었다. 생성본은 `c681b9d`에 보존했다.
- 발견한 문제:
  - 가독성: 기준 분기 선택 로직을 한 줄씩 설명하기 어려웠다. 평균을 실제 개수가 아니라 상수 `RATIO_WINDOW`로 나눴고, 매직 넘버 `3`을 썼다.
  - 정확성: try/except 5곳과 필수 열 검사가 상류 함수의 버그(열 이름 오타 등)를 `no_data`로 조용히 숨겼다. 팀 규칙 "예외를 조용히 삼키지 않는다" 위반이다.
  - 경계: 결과에 먼저 대입한 뒤 검사해서 `months_available` -1이 그대로 출력됐다(원본 124~127줄). 기준 분기의 `fx_avg`가 0이면 ZeroDivisionError가 날 수 있었다.
- 수정 내역:
  - `74b0de4` (fix): 명세 밖 필수 열·타입 검사를 삭제했다. 이제 열이 없으면 `KeyError`가 나서 문제 위치가 바로 드러난다.
  - `2aa330c` (fix): `months_available <= 0` 검사를 결과 대입 앞으로 옮겼다(입력 -1 → 출력 0).
  - `e382473` (refactor): 기준 분기 선택을 `merge` + 조건 마스크(대상 분기 이전, months_available == 3, export_usd > 0, fx_avg > 0) + `sort_values().tail(4)`로 바꿨다. try/except 5곳을 제거하고, 평균은 `len(ratios)`로 계산하고, `MONTHS_PER_QUARTER = 3` 상수를 추가했다. 기준 분기 선택이 약 60줄 → 약 15줄(108~122줄)로 줄고, 파이썬 반복문 대신 pandas 연산을 쓴다. 시그니처와 반환 dict는 유지했다. **가독성·효율**을 개선한 사례다.
- 검증: pytest 9 passed (T07~T11, A01~A04), 커밋 `e382473`
- pytest 결과
    =============================================================================================== test session starts ===============================================================================================
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

    =============================================================================================== 9 passed in 3.10s ===============================================================================================

- 판단 메모: `fx_avg > 0` 조건은 ZeroDivisionError를 막는 동작 변경이라, 엄밀히 말하면 refactor가 아니라 별도 fix 커밋으로 나눴어야 했다. 다음 리팩터링부터는 "동작이 바뀌는가"를 기준으로 커밋을 나눈다.