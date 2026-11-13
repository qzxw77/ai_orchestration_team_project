====================== test session starts =======================
platform win32 -- Python 3.13.15, pytest-9.2.0, pluggy-1.7.0 -- C:\Users\s2h02\my_project\venv1\Scripts\python.exe
cachedir: .pytest_cache
rootdir: <repository-root>
collected 3 items                                                 

hynix_nowcast/test_preprocess.py::test_aggregate_normal PASSED [ 33%]
hynix_nowcast/test_preprocess.py::test_lag_months_and_missing_region PASSED [ 66%]
hynix_nowcast/test_preprocess.py::test_empty_and_negative_lag PASSED [100%]

============================== 3 passed in 1.50s ==============================

============================= test session starts =============================
platform win32 -- Python 3.13.15, pytest-9.2.0, pluggy-1.7.0 -- C:\Users\s2h02\my_project\venv1\Scripts\python.exe
rootdir: <repository-root>
collected 18 items

hynix_nowcast/test_data_loader.py::test_validate_months_rejects_invalid_values PASSED [  5%]
hynix_nowcast/test_data_loader.py::test_month_chunks_split_long_period PASSED [ 11%]
hynix_nowcast/test_data_loader.py::test_parse_customs_page_returns_rows_and_total_count PASSED [ 16%]
hynix_nowcast/test_data_loader.py::test_parse_customs_page_handles_no_data PASSED [ 22%]
hynix_nowcast/test_data_loader.py::test_fetch_regional_exports_uses_mocked_rows PASSED [ 27%]
hynix_nowcast/test_data_loader.py::test_to_raw_exports_table_preserves_fields PASSED [ 33%]
hynix_nowcast/test_data_loader.py::test_validate_months_rejects_non_string PASSED [ 38%]
hynix_nowcast/test_data_loader.py::test_validate_months_rejects_full_width_digits PASSED [ 44%]
hynix_nowcast/test_data_loader.py::test_get_customs_api_key_rejects_missing_key PASSED [ 50%]
hynix_nowcast/test_data_loader.py::test_get_customs_api_key_rejects_blank_key PASSED [ 55%]
hynix_nowcast/test_data_loader.py::test_fetch_regional_exports_splits_each_region_into_12_month_chunks PASSED [ 61%]
hynix_nowcast/test_data_loader.py::test_fetch_regional_exports_deduplicates_same_sido PASSED [ 66%]
hynix_nowcast/test_data_loader.py::test_request_customs_xml_passes_expected_url_and_parameters PASSED [ 72%]
hynix_nowcast/test_data_loader.py::test_request_customs_xml_hides_request_exception_details PASSED [ 77%]
hynix_nowcast/test_data_loader.py::test_request_customs_xml_reports_http_status_without_url PASSED [ 83%]
hynix_nowcast/test_data_loader.py::test_request_customs_xml_rejects_non_xml_response PASSED [ 88%]
hynix_nowcast/test_data_loader.py::test_parse_customs_page_reports_api_error_code PASSED [ 94%]
hynix_nowcast/test_data_loader.py::test_fetch_customs_rows_requests_next_page_until_total_count PASSED [100%]

============================= 18 passed in 1.16s ==============================
