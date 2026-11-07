9주차  
============================================================================= test session starts ==============================================================================  
platform win32 -- Python 3.13.14, pytest-9.2.0, pluggy-1.7.0 -- C:\Users\mingyu\Desktop\ai_orch\venv1\Scripts\python.exe  
cachedir: .pytest_cache  
rootdir: C:\Users\mingyu\Desktop\ai_orch\week09  
collected 6 items            
test_detect_anomaly.py::test_normal_within_range PASSED                                                    [ 16%]  
test_detect_anomaly.py::test_normal_surge PASSED                                                           [ 33%]  
test_detect_anomaly.py::test_boundary_24_months_is_insufficient PASSED                                     [ 50%]  
test_detect_anomaly.py::test_boundary_zero_std_is_insufficient PASSED                                      [ 66%]  
test_detect_anomaly.py::test_exception_invalid_target_ym PASSED                                            [ 83%]  
test_detect_anomaly.py::test_exception_zero_total_twelve_months_before PASSED                              [100%]  
============================================================================== 6 passed in 0.92s ===============================================================================  

10주차  
============================================================================= test session starts ==============================================================================
platform win32 -- Python 3.13.14, pytest-9.2.0, pluggy-1.7.0 -- C:\Users\mingyu\Desktop\ai_orch\venv1\Scripts\python.exe
cachedir: .pytest_cache  
rootdir: C:\Users\mingyu\Desktop\ai_orch\week10  
collected 19 items              

test_fetch_fx_rates.py::test_normal_converts_sorts_and_builds_request PASSED                               [  5%]
test_fetch_fx_rates.py::test_normal_reads_all_pages PASSED                                                 [ 10%]
test_fetch_fx_rates.py::test_boundary_drops_bad_rows_and_keeps_last_duplicate PASSED                       [ 15%]
test_fetch_fx_rates.py::test_boundary_no_data_returns_empty_table PASSED                                   [ 21%]
test_fetch_fx_rates.py::test_exception_missing_api_key[no_key] PASSED                                      [ 26%]
test_fetch_fx_rates.py::test_exception_missing_api_key[blank_key] PASSED                                   [ 31%]
test_fetch_fx_rates.py::test_exception_request_failure_hides_key[connection] PASSED                        [ 36%]
test_fetch_fx_rates.py::test_exception_request_failure_hides_key[timeout] PASSED                           [ 42%]
test_fetch_fx_rates.py::test_exception_request_failure_hides_key[http500] PASSED                           [ 47%]
test_fetch_fx_rates.py::test_exception_result_code_or_bad_response[info100_not_no_data] PASSED             [ 52%]
test_fetch_fx_rates.py::test_exception_result_code_or_bad_response[error602] PASSED                        [ 57%]
test_fetch_fx_rates.py::test_exception_result_code_or_bad_response[unknown_shape] PASSED                   [ 63%]
test_fetch_fx_rates.py::test_exception_result_code_or_bad_response[not_json] PASSED                        [ 68%]
test_fetch_fx_rates.py::test_exception_invalid_dates[2026-13-01-2026-12-31] PASSED                         [ 73%]
test_fetch_fx_rates.py::test_exception_invalid_dates[2026-02-30-2026-03-31] PASSED                         [ 78%]
test_fetch_fx_rates.py::test_exception_invalid_dates[2026/01/01-2026-01-31] PASSED                         [ 84%]
test_fetch_fx_rates.py::test_exception_invalid_dates[20260101-20260131] PASSED                             [ 89%]
test_fetch_fx_rates.py::test_exception_invalid_dates[2026-1-01-2026-01-31] PASSED                          [ 94%]
test_fetch_fx_rates.py::test_exception_invalid_dates[2026-02-01-2026-01-31] PASSED                         [100%]

============================================================================== 19 passed in 0.70s ==============================================================================