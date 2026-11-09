## [2026-11-09] fetch_fx_rates 가독성 리팩터링 (담당: 강민규)

- 대상 모듈: `data_loader.py` / 관련 커밋: 10주차 `48a8540` → 리팩터링 `e35123c`  
- 초기 프롬프트(요지): 오류 메시지, 검사 순서, 요청 횟수와 URL, 변환 결과는 그대로 두고 R1~R8(보조 함수 8개 추출, 오류 메시지 도우미, 상수와 중복 값 정리, HTTP 오류 구분 단순화, 날짜 검사 정리, 키가 지나가는 곳 문서화, docstring 계약 보강, 이력 주석 정리)만 하라고 요청. 변환 방식 변경, Session, 재시도, 버그 수정은 금지하고 발견한 점은 따로 적게 함.  
- AI 생성 결과(요지): 보조 함수 9개(지정 8개 + `_api_error`)로 나눠 fetch_fx_rates에는 호출 4줄만 남김. 상수 6개 추가, raise_for_status() 예외를 따로 잡아 HTTP 오류 구분, 달력 검사를 값마다 반복, `[수정 N]` 주석을 "왜" 주석 6개로 교체. "발견한 점" 8건(R4 경계, `from None`의 한계, R1 시그니처와 R6 충돌, list_total_count의 전각 숫자 등)은 코드에 넣지 않고 따로 적음.  
- 발견한 문제: diff 리딩에서 동작이 바뀌는 지시 밖 변경 없음
  - 확인한 항목: 오류 메시지 원문 7종, 검사 순서(형식 -> 달력 -> 시작일 > 끝일 -> 키 -> 요청), `exc.response` 미사용, try는 get, raise_for_status, json 세 곳뿐, "왜" 주석 6개 유지
  - 지시 밖 변경 3건: 기존 상수 3개에 뜻 주석, 지역 변수 `result` -> `table`, 지시보다 많은 설명 주석. 모두 동작과 무관
  - 프롬프트 쪽 문제: R4대로 HTTPError만 잡으면 원래(RequestException)보다 범위가 좁아, raise_for_status()가 다른 예외를 내면 키가 든 URL이 그대로 나갈 수 있음. 실제 requests는 400~599에서 HTTPError만 내므로 지금은 차이 없음
- 수정 내역: 코드는 고치지 않고 AI 결과 전체 채택. 지시 밖 변경 3건은 읽기에 도움이 되어 유지. AI의 "발견한 점"은 refactor 커밋에 섞지 않고 `fix:` 후보로 분리 (raise_for_status 예외 범위, `from None` 뒤에도 남는 `__context__`)
- 검증: pytest 26 passed
  - 실행 로그:  
    ============================================================================= test session starts ==============================================================================
    platform win32 -- Python 3.13.14, pytest-9.2.0, pluggy-1.7.0 -- C:\Users\mingyu\Desktop\ai_orch\venv1\Scripts\python.exe
    cachedir: .pytest_cache  
    rootdir: C:\Users\mingyu\Desktop\ai_orch\week10  
    collected 26 items    
    test_fetch_fx_rates_guard.py::test_guard_api_error_messages_exact[connection] PASSED                 [  3%]  
    test_fetch_fx_rates_guard.py::test_guard_api_error_messages_exact[timeout] PASSED                    [  7%]  
    test_fetch_fx_rates_guard.py::test_guard_api_error_messages_exact[http404] PASSED                    [ 11%]
    test_fetch_fx_rates_guard.py::test_guard_api_error_messages_exact[result_code] PASSED                [ 15%]
    test_fetch_fx_rates_guard.py::test_guard_api_error_messages_exact[not_json] PASSED                   [ 19%]
    test_fetch_fx_rates_guard.py::test_guard_malformed_responses[result_not_dict] PASSED                 [ 23%]
    test_fetch_fx_rates_guard.py::test_guard_malformed_responses[result_no_code] PASSED                  [ 26%]
    test_fetch_fx_rates_guard.py::test_guard_malformed_responses[payload_list] PASSED                    [ 30%]
    test_fetch_fx_rates_guard.py::test_guard_malformed_responses[row_not_list] PASSED                    [ 34%]
    test_fetch_fx_rates_guard.py::test_guard_malformed_responses[total_true] PASSED                      [ 38%]
    test_fetch_fx_rates_guard.py::test_guard_malformed_responses[total_negative] PASSED                  [ 42%]
    test_fetch_fx_rates_guard.py::test_guard_malformed_responses[total_text] PASSED                      [ 46%]
    test_fetch_fx_rates_guard.py::test_guard_malformed_responses[total_float] PASSED                     [ 50%]
    test_fetch_fx_rates_guard.py::test_guard_malformed_responses[total_negative_text] PASSED             [ 53%]
    test_fetch_fx_rates_guard.py::test_guard_numeric_string_total_count_with_paging PASSED               [ 57%]
    test_fetch_fx_rates_guard.py::test_guard_empty_tables_have_same_dtypes_as_normal PASSED              [ 61%]
    test_fetch_fx_rates_guard.py::test_guard_date_error_messages_and_order[calendar] PASSED              [ 65%]
    test_fetch_fx_rates_guard.py::test_guard_date_error_messages_and_order[start_after_end] PASSED       [ 69%]
    test_fetch_fx_rates_guard.py::test_guard_date_error_messages_and_order[format_checked_first] PASSED  [ 73%]
    test_fetch_fx_rates_guard.py::test_guard_date_error_messages_and_order[fullwidth_digits] PASSE       [ 76%]
    test_fetch_fx_rates_guard.py::test_guard_dates_checked_before_api_key PASSED                         [ 80%]
    test_fetch_fx_rates_guard.py::test_guard_same_start_and_end_is_allowed PASSED                        [ 84%]
    test_fetch_fx_rates_guard.py::test_guard_paging_stops_early[no_data] PASSED                          [ 88%]
    test_fetch_fx_rates_guard.py::test_guard_paging_stops_early[empty_rows] PASSED                       [ 92%]
    test_fetch_fx_rates_guard.py::test_guard_every_page_request_uses_same_settings PASSED                [ 96%]
    test_fetch_fx_rates_guard.py::test_guard_non_dict_rows_are_skipped PASSED                            [100%]
    ============================================================================== 26 passed in 2.11s ==============================================================================

- 판단 메모:
  - 효율은 손대지 않음: 실제 크기(약 1,450행, 요청 2번, 네트워크 제외)를 처리하는 데 3.2ms였고, 변환은 이미 행 반복 없이 pandas로 한 번에 하고 있다
  - 오류 메시지 원문을 테스트로 고정: main이 이 메시지를 화면에 그대로 보여 주므로 외부 동작의 일부다. 메시지를 상수와 도우미로 옮기는 리팩터링이라 글자가 바뀌기 쉬워 먼저 고정했다
  - 상태 코드는 응답 객체에서 읽게 함: HTTPError의 .response는 직접 만든 예외에서는 None이라, exc.response.status_code로 바꾸면 AttributeError가 난다 (안전망 테스트로 확인)
  - 날짜 검사 순서 유지: 형식 검사를 두 값 모두 먼저 하지 않으면 ("2026-13-01", "2026/01/31")에서 오류 메시지에 나오는 값이 끝일에서 시작일로 바뀐다
  - 리팩터링과 버그 수정을 섞지 않음: 분석 중 키 앞뒤 공백을 검사할 때만 지우고 URL에는 원래 값을 넣는 것을 발견했다. python-dotenv는 따옴표 없는 값의 공백을 지워 주므로, .env에 따옴표로 감싼 값이나 OS 환경변수일 때만 생긴다. 동작이 바뀌는 수정이라 이번 커밋에 넣지 않고 별도 `fix:` 후보로 남긴다 (이번 refactor 커밋에는 미반영)
  - 그대로 둔 것: dict가 아닌 row를 거른 뒤 개수를 세서 비교하므로, 깨진 행이 섞이면 요청이 한 번 더 나갈 수 있다. 결과는 같고 정상 응답에서는 생기지 않아 바꾸지 않았다
  - 새로 알게 된 점: `from None`은 traceback 출력에서만 원래 예외를 숨기고, 새 예외의 `__context__`에는 키가 든 URL이 남는다. 리팩터링 지시 자체(R4)도 잡는 범위를 좁혀 동작을 바꿀 수 있다
  - 다음 프롬프트에 반영: 지시끼리 충돌하지 않는지 먼저 확인한다 (R1의 `_fetch_all_rows(api_key, ...)` 시그니처 때문에 R6의 "키는 세 함수 사이로만"을 그대로 지킬 수 없었다). "지시 밖 변경(이름 변경, 주석 추가)은 하지 말고, 했다면 목록으로 보고하라"를 넣는다