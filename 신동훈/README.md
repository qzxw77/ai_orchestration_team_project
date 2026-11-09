# test_estimate_revenue.py pytest 결과
================================================================================================================= test session starts =================================================================================================================
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

================================================================================================================== 9 passed in 3.10s ==================================================================================================================


# test_load_actuals.py pytest 결과
=================================================================== test session starts ====================================================================
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

==================================================================== 27 passed in 3.09s ====================================================================