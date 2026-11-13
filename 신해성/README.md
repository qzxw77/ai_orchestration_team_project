====================== 9주차 (preprocess.py) test session starts =======================
platform win32 -- Python 3.13.15, pytest-9.2.0, pluggy-1.7.0 -- C:\Users\s2h02\my_project\venv1\Scripts\python.exe
cachedir: .pytest_cache
rootdir: <repository-root>
collected 3 items                                                 

hynix_nowcast/test_preprocess.py::test_aggregate_normal PASSED [ 33%]
hynix_nowcast/test_preprocess.py::test_lag_months_and_missing_region PASSED [ 66%]
hynix_nowcast/test_preprocess.py::test_empty_and_negative_lag PASSED [100%]

============================== 3 passed in 1.50s ==============================

============================= week09 (data_loader.py) test session starts =============================
platform win32 -- Python 3.13.15, pytest-9.2.0, pluggy-1.7.0 -- C:\Users\s2h02\my_project\venv1\Scripts\python.exe
cachedir: .pytest_cache
rootdir: <repository-root>
collecting ... collected 19 items

hynix_nowcast/test_data_loader.py::test_validate_months_rejects_invalid_values PASSED [  5%]
hynix_nowcast/test_data_loader.py::test_month_chunks_split_long_period PASSED [ 10%]
hynix_nowcast/test_data_loader.py::test_parse_customs_page_returns_rows_and_total_count PASSED [ 15%]
hynix_nowcast/test_data_loader.py::test_parse_customs_page_handles_no_data PASSED [ 21%]
hynix_nowcast/test_data_loader.py::test_fetch_regional_exports_uses_mocked_rows PASSED [ 26%]
hynix_nowcast/test_data_loader.py::test_to_raw_exports_table_preserves_fields PASSED [ 31%]
hynix_nowcast/test_data_loader.py::test_validate_months_rejects_non_string PASSED [ 36%]
hynix_nowcast/test_data_loader.py::test_validate_months_rejects_full_width_digits PASSED [ 42%]
hynix_nowcast/test_data_loader.py::test_get_customs_api_key_rejects_missing_key PASSED [ 47%]
hynix_nowcast/test_data_loader.py::test_get_customs_api_key_rejects_blank_key PASSED [ 52%]
hynix_nowcast/test_data_loader.py::test_fetch_regional_exports_splits_each_region_into_12_month_chunks PASSED [ 57%]
hynix_nowcast/test_data_loader.py::test_fetch_regional_exports_deduplicates_same_sido PASSED [ 63%]
hynix_nowcast/test_data_loader.py::test_request_customs_xml_passes_expected_url_and_parameters PASSED [ 68%]
hynix_nowcast/test_data_loader.py::test_request_customs_xml_hides_request_exception_details PASSED [ 73%]
hynix_nowcast/test_data_loader.py::test_request_customs_xml_reports_http_status_without_url PASSED [ 78%]
hynix_nowcast/test_data_loader.py::test_request_customs_xml_rejects_non_xml_response PASSED [ 84%]
hynix_nowcast/test_data_loader.py::test_parse_customs_page_reports_api_error_code PASSED [ 89%]
hynix_nowcast/test_data_loader.py::test_parse_customs_page_rejects_success_without_body PASSED [ 94%]
hynix_nowcast/test_data_loader.py::test_fetch_customs_rows_requests_next_page_until_total_count PASSED [100%]

============================= 19 passed in 1.26s ==============================

## 2026-11-13 데이터 계약 점검 및 리뷰 피드백

팀 표준 스키마 [`docs/schema.md`](../docs/schema.md)의 6장 함수별 입출력
계약과 1.4 오류 규칙을 기준으로 `preprocess.py`와 `data_loader.py`를
점검했다.

### 함수별 데이터 계약 반영

- `aggregate_quarterly(exports_df: pd.DataFrame, fx_df: pd.DataFrame, lag_months: int = 0) -> pd.DataFrame`
  - 반환 열은 `quarter`, `export_usd`, `months_available`, `fx_avg` 순서다.
  - 반환 타입을 docstring에 명시했다.
  - `hs_code == "854232"`인 대상 품목과 이천시·청주시의 완전한 월만 집계한다.
  - 환율은 결측값, 0 이하, 양·음의 무한대를 제외한다.
- `fetch_regional_exports`와 내부 보조 함수 전부에 입력 타입,
  반환 타입, `Returns` 형식, `Raises`를 확인하고 보완했다.

### 1조 코드 리뷰 피드백 판단

| 피드백 | 판단 | 확인·수정 내용 | 관련 커밋 |
|---|---|---|---|
| `preprocess.py` 1행 문법 오류로 import 불가 | 보류(현재 재현되지 않음) | 2026-11-13 현재 파일 1행은 정상적인 모듈 docstring이며 `python -m pytest` 수집이 성공했다. | `e141087` |
| `extract_guidance`의 `_call_llm` 미정의 | 보류(대상 아님) | 현재 신해성 `preprocess.py`에는 `extract_guidance`가 없고, `_call_llm`을 호출하는 코드도 없다. | `e141087` |
| 환율 필터가 양의 무한대를 거르지 않음 | 수용 및 수정 | 2026-11-13 `preprocess.py`에서 `pd.to_numeric`, `math.isfinite`, `> 0` 조건으로 결측·0 이하·무한대를 제거한 뒤 평균을 계산하도록 수정했다. | `e141087` |
| `hs_code` 결측·타 품목 행이 과대 집계될 수 있음 | 수용 및 수정 | 2026-11-13 `aggregate_quarterly`에서 `hs_code == "854232"`인 행만 집계하도록 수정했다. | `e141087` |
| `docs/schema.md`의 import 오류 표시 | 보류(표시 유지) | 과거 리뷰 이력을 보존했다. 현재 파일은 import 가능하므로 후속 문서 정리에서 상태를 갱신할 수 있다. | `006d3b0` |

### 피드백 반영 커밋 요약

| 날짜 | 피드백 | 판단과 이유 | 관련 커밋 |
|---|---|---|---|
| 2026-11-13 | 환율 필터에서 양의 무한대가 제외되지 않음 | **수용** — `math.isfinite`와 `usdkrw > 0` 검사를 추가해 NaN, 양·음의 무한대, 0 이하 값을 평균에서 제외했다. 잘못된 환율이 `fx_avg`를 오염시킬 수 있어 수정했다. | `e141087 fix: enforce module data contracts` |
| 2026-11-13 | `hs_code` 결측·타 품목 행이 수출액에 포함될 수 있음 | **수용** — `hs_code == "854232"` 조건을 추가했다. 다른 품목이 합산되면 메모리 반도체 수출액이 과대 집계될 수 있어 수정했다. | `e141087 fix: enforce module data contracts` |
| 2026-11-13 | `preprocess.py` 1행 문법 오류로 import 불가 | **보류** — 현재 파일에서 SyntaxError가 재현되지 않고 pytest 수집도 성공했다. 과거 리뷰 이력은 유지하되 코드는 변경하지 않았다. | `006d3b0 docs: record preprocess contract fixes` |
| 2026-11-13 | `extract_guidance`의 `_call_llm` 미정의 | **보류** — 해당 함수와 호출이 신해성 `preprocess.py`에 없어 이 모듈의 수정 범위가 아니다. | `006d3b0 docs: record preprocess contract fixes` |

### 검증 결과

```text
hynix_nowcast/test_preprocess.py: 4 passed
hynix_nowcast/test_data_loader.py: 19 passed
총 23 passed
```

추가한 회귀 테스트 `test_filters_non_target_hs_codes_and_invalid_exchange_rates`는
타 품목·결측 HS 코드와 0·음수·무한대·NaN 환율이 집계에서 제외되는지 검증한다.
