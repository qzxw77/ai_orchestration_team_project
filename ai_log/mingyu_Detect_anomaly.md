## [2026-11-09] detect_anomaly 가독성 리팩터링 (담당: 강민규)

- 대상 모듈: `forecaster.py` / 관련 커밋: 9주차 `6c4c7ee` → 리팩터링 `05f05ad`
- 초기 프롬프트(요지): 외부 동작과 평균, 표준편차 계산식은 그대로 두고 R1~R9(상수화, 지역 하드코딩 제거, 결과 문자열 상수화, 기본값 dict 변형 제거, 보조 함수 4개 추출, 불필요한 복사 제거, docstring 계약 보강, 이력 주석 정리, Any를 object로)만 하라고 요청. 벡터화, 계산식 교체, 버그 수정은 금지하고 발견한 점은 따로 적게 함.
- AI 생성 결과(요지): R1~R9를 모두 반영해 보조 함수 5개(_insufficient_result, _monthly_totals, _yoy_values, _mean_and_sample_std, _classify)로 분리. itertuples, 계산식, 기존 try/except는 유지. 생성 직후 pytest 15 passed
  - AI가 적은 "발견한 점" 8건 중 핵심: 전각 숫자 target_ym 통과, 월 합계가 inf가 되면 z가 nan이 되어 "정상" 판정, Python 3.12부터 sum()이 보정 합산이라 테스트에 고정한 z 값이 버전마다 다를 수 있음
- 발견한 문제: diff 리딩에서 지시 밖 동작 변경 없음
  - 확인한 항목: 반환 키 5개와 타입, reason 4개 문자열, 계산식(합 / 개수, 제곱합 / (개수 - 1), math.sqrt), `abs(z) > threshold` 비교, guard 순서, try/except 추가 없음, 입력 표 미수정
- 수정 내역: 코드는 AI 결과를 그대로 채택(추가된 주석도 벡터화, 계산식 교체를 막는 이유라 유지). "발견한 점"은 코드에 넣지 않고 동작이 바뀌는 수정이라 보류
- 검증: pytest 15 passed, 커밋 `05f05ad`
  - 실행 로그:  
    ============================================================================= test session starts ==============================================================================
    platform win32 -- Python 3.13.14, pytest-9.2.0, pluggy-1.7.0 -- C:\Users\mingyu\Desktop\ai_orch\venv1\Scripts\python.exe
    cachedir: .pytest_cache
    rootdir: C:\Users\mingyu\Desktop\ai_orch\week10           
    collected 15 items  
    test_detect_anomaly_guard.py::test_guard_sharp_drop PASSED                                                           [  6%]  
    test_detect_anomaly_guard.py::test_guard_z_equal_to_threshold_is_normal PASSED                                       [ 13%]  
    test_detect_anomaly_guard.py::test_guard_calculation_order_is_kept PASSED                                            [ 20%]  
    test_detect_anomaly_guard.py::test_guard_threshold_argument_is_used PASSED                                           [ 26%]  
    test_detect_anomaly_guard.py::test_guard_one_region_month_counts_as_missing PASSED                                   [ 33%]  
    test_detect_anomaly_guard.py::test_guard_region_absent_everywhere PASSED                                             [ 40%]  
    test_detect_anomaly_guard.py::test_guard_dirty_rows_are_skipped PASSED                                               [ 46%]  
    test_detect_anomaly_guard.py::test_guard_value_forms_give_same_result[numeric_strings] PASSED                        [ 53%]  
    test_detect_anomaly_guard.py::test_guard_value_forms_give_same_result[split_rows] PASSED                             [ 60%]  
    test_detect_anomaly_guard.py::test_guard_invalid_inputs_return_default[empty] PASSED                                 [ 66%]  
    test_detect_anomaly_guard.py::test_guard_invalid_inputs_return_default[missing_column] PASSED                        [ 73%]  
    test_detect_anomaly_guard.py::test_guard_invalid_inputs_return_default[not_dataframe] PASSED                         [ 80%]  
    test_detect_anomaly_guard.py::test_guard_non_numeric_threshold_raises_type_error PASSED                              [ 86%]  
    test_detect_anomaly_guard.py::test_guard_return_types_and_input_unchanged PASSED                                     [ 93%]  
    test_detect_anomaly_guard.py::test_guard_insufficient_results_do_not_share_state PASSED                              [100%]  
    ============================================================================== 15 passed in 3.66s ==============================================================================

- 판단 메모:
  - 벡터화는 하지 않음: 실제 크기(70개월 x 2지역 = 140행)에서 지금 코드가 0.45ms라 속도 이득이 없고, pd.to_numeric은 float()와 달리 "1_000", 전각 숫자 "５", True를 다르게 처리해 외부 동작이 바뀐다
  - 계산식은 그대로 둠: statistics.stdev, pandas std는 무작위 2000회 중 각각 369회, 475회 끝자리가 달라, |z|가 threshold와 같은 경계 판정이 뒤집힐 수 있다. 
  - 리팩터링과 버그 수정을 섞지 않음: 분석 중 _is_valid_ym이 전각 숫자 target_ym("２０２６-09")을 통과시키는 것을 발견했다 (isdecimal은 전각 숫자도 참). 동작이 바뀌는 수정이라 이번 refactor 커밋에 넣지 않고 별도 `fix:` 커밋으로 처리한다
  - 새로 알게 된 점: "하지 말 것"에 이유까지 적고 "발견한 점"을 따로 쓰게 하자, AI가 벡터화나 버그 수정을 섞지 않고 보고만 했다. 다음 프롬프트에도 두 장치를 유지한다
  - 다음 프롬프트에 반영할 점: 끝자리까지 고정한 테스트는 Python 버전에 따라 달라질 수 있어 실행 버전(3.13.14)을 명시하고, R 목록(R1~R9) 밖의 변경도 따로 보고하게 요구한다