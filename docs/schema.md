# 알트(ALT) 팀 표준 스키마

SK하이닉스 분기 매출 나우캐스팅 시스템에서 모듈 경계를 오가는 표(DataFrame, CSV)와 dict의 형식을 정한 문서입니다.
- 작성일: 2026-11-09 
- 표기
  - **[V1 변경]**: 설계 문서 V1에서 바뀐 규칙 (8장 참고)
  - **[팀 확인]**: 팀이 정해야 하는 것

## 목차

1. 공통 규칙
2. 공통 상수
3. 표 스키마
4. dict 스키마
5. LLM 경계
6. 함수별 입출력과 예외
7. 데이터 흐름
8. 설계 문서 V1 대비 바뀐 점

---

## 1. 공통 규칙

### 1.1 값 표기

| 종류 | 타입 | 형식, 예 | 검사 기준 |
|---|---|---|---|
| 월 | str | "YYYY-MM", "2026-09" | 7글자, ASCII 숫자, 5번째 글자 "-", 월 01~12 |
| 일 | str | "YYYY-MM-DD", "2026-01-02" | 10글자, ASCII 숫자, 5번째와 8번째 글자 "-", 달력에 있는 날짜 |
| 분기 | str | "YYYYQn", "2026Q1" | 6글자, ASCII 숫자, 5번째 글자 "Q", n은 1~4 |
| 달러 금액 | float | export_usd | 달러 단위, 반올림하지 않음 |
| 원 금액 | float | revenue_krw, estimate_krw, lower_krw, upper_krw | 원 단위(조 원 아님), 반올림하지 않음 |
| 퍼센트 | float | qoq_change_pct = 16.52 | 100을 곱한 값 (0.1652가 아님) |
| 개월 수 | int | months_available | dict에서는 파이썬 int |
| 없는 값 | None, NaN | | dict는 None, DataFrame과 CSV는 NaN(빈칸). 0으로 채우지 않음 |

- 날짜, 월, 분기는 함수 사이에서 항상 문자열로 주고받습니다. 내부에서 날짜 타입으로 계산해도 돌려줄 때는 문자열로 바꿉니다.
- **[V1 변경]** 숫자 자리는 ASCII 숫자만 인정합니다. `isdecimal()`과 `pd.to_datetime`은 전각 숫자("２０２６")도 숫자로 읽으므로, 형식 검사에 `isascii()`를 함께 씁니다.
- 형식을 통과한 월, 일, 분기 문자열은 문자열 순서와 시간 순서가 같습니다. 그래서 `"2025Q4" < "2026Q1"`처럼 바로 비교해도 됩니다.
- 표시용 반올림(조 원, 소수 첫째 자리)은 generate_brief와 main에서만 합니다.

### 1.2 표(DataFrame) 규칙

1. 열 이름과 순서는 3장 그대로 둡니다. 3장에 없는 열을 더하지 않습니다(원자료 raw_exports만 예외).
2. 행은 키 열 오름차순으로 정렬하고, 행 번호는 0부터 다시 매깁니다(`reset_index(drop=True)`).
3. **[V1 변경] 0행 표도 열 이름과 dtype이 정상 표와 같아야 합니다.** 열 이름만 준 빈 표(`pd.DataFrame(columns=...)`)는 모든 열이 object라서, 저장 표와 이어 붙이면 float 열 전체가 object로 바뀝니다. 빈 표는 열마다 dtype을 지정하고, 표마다 `_empty_<표 이름>_table()` 보조 함수 한 곳에서 만듭니다.
   ```python
   pd.DataFrame({"date": pd.Series(dtype=str), "usdkrw": pd.Series(dtype=float)})
   ```
4. **[V1 변경] "빈 표"는 행 수로 판정합니다(`len(df) == 0`).** `df.empty`는 열이 0개인 1행 표도 True라서, 필수 열 검사를 건너뛰게 됩니다.
5. 받은 표를 수정하지 않습니다. 읽기만 하는 함수는 복사하지 않아도 됩니다.
6. 문자열 열의 dtype은 pandas 3에서는 `str`, pandas 2에서는 `object`로 보입니다. 둘 다 허용하며, 값은 반드시 파이썬 str입니다(숫자 854232가 아니라 "854232").

### 1.3 dict 규칙

1. 4장에 적은 키를 항상 모두 담습니다. 값이 없으면 키를 빼지 않고 None을 넣습니다.
2. **[V1 변경]** 값은 파이썬 기본 타입(str, int, float, bool, None, list[str])만 씁니다. numpy.float64, numpy.int64, numpy.bool_, NaN은 넣지 않습니다(NaN 대신 None).
3. **[V1 변경]** 호출할 때마다 새 dict를 만듭니다. 모듈 수준 기본값 dict를 고쳐 쓰면 앞 호출의 값이 다음 호출 결과로 샙니다.
4. 허용값 문자열(status, reason, 방향 등)은 파일 맨 위 대문자 상수로 두고, 본문에서는 상수 이름으로 씁니다.
5. 다른 함수가 만든 dict는 수정하지 않습니다. 예외를 내면 안 되는 함수(compare_guidance, generate_brief)는 키를 `.get()`으로 읽고, 숫자 자리에 bool, NaN, 무한대가 오면 없는 값(None)으로 봅니다.

### 1.4 오류 규칙

| 상황 | 처리 | 메시지 형식 | 해당 함수 |
|---|---|---|---|
| 외부 API 호출 실패 | RuntimeError | "<API 이름> 호출 실패: <원인>" | fetch_fx_rates, fetch_regional_exports |
| API 키 없음 | RuntimeError | "<API 이름> 키가 없습니다" | 위 두 함수 |
| 사람이 고쳐야 하는 입력 | ValueError | "<무엇> 오류: <값>", "필수 열 누락: <열>, <열>" | fetch_fx_rates(날짜), load_actuals, clean_exports, upsert_records, aggregate_quarterly |
| 자료 부족, 빈 입력 | 예외 없음 | status, reason 값으로 알림 | estimate_revenue, detect_anomaly, compare_guidance, extract_guidance, generate_brief |
| 호출 실수(계약 위반) | 잡지 않고 그대로 올림 | KeyError, TypeError | 아래 두 번째 항목 |

- **[V1 변경] 키 보호:** API 호출 실패의 <원인>에는 예외 클래스 이름, "HTTP <상태 코드>", "<결과 코드> <메시지>"만 넣습니다. requests 예외 문자열에는 키가 든 URL이 들어 있으므로 URL, API 키, `str(e)`는 넣지 않고 `raise ... from None`으로 올립니다. 메시지는 `_api_error(reason)` 같은 보조 함수 한 곳에서 만듭니다.
- **[V1 변경] 필수 열 검사는 바깥 자료를 처음 받는 함수만 합니다.** 원자료와 CSV를 처음 받는 clean_exports, load_actuals는 열을 검사해 ValueError를 냅니다. 그 뒤 함수(aggregate_quarterly, estimate_revenue)는 앞 함수의 출력 계약을 믿고 따로 검사하지 않으며, 열이 없으면 KeyError가 그대로 나서 어디가 틀렸는지 드러납니다. 열 누락을 status로 바꾸면 앞 단계 버그가 "데이터 없음"으로 숨기 때문입니다.
  - 예외: detect_anomaly는 열 누락과 DataFrame이 아닌 입력도 reason "데이터 부족"으로 돌려줍니다(테스트로 고정된 기존 동작).
- main은 RuntimeError를 받으면 "수집 실패, 저장된 데이터로 진행" 경고를 띄우고 계속하며, ValueError를 받으면 메시지를 화면에 보여 주고 멈춥니다.
- `except:`, `except Exception:`, `except: pass`는 쓰지 않습니다. 예외는 `_call_llm` 하나로, 실패하면 빈 문자열을 돌려줍니다.

### 1.5 CSV 규칙

| 표 | 파일 | upsert 키 | 정렬 |
|---|---|---|---|
| exports | data/exports.csv | ["ym", "region", "hs_code"] | ym, region, hs_code |
| fx | data/fx.csv | ["date"] | date |
| forecasts | data/forecasts.csv | ["quarter", "as_of"] | quarter, as_of |
| actuals | data/actuals.csv | 없음 (팀 수기 작성) | quarter |
| transcripts | data/transcripts/YYYYQn.txt | 없음 (팀 수기 작성) | |

- UTF-8, 첫 줄 열 이름, `index=False`로 저장합니다. 결측은 빈칸입니다.
- 읽을 때 문자열 열 8개는 `dtype=str`로 읽습니다: ym, region, hs_code, date, quarter, as_of, collected_at, announced_date. 숫자로 읽히면 "854232"와 854232가 다른 키가 되어 upsert_records가 중복을 찾지 못합니다.
- 파일 읽기, 쓰기는 main과 load_actuals만 합니다.

---

## 2. 공통 상수

모듈끼리 import하지 않으므로 같은 상수가 여러 파일에 따로 있습니다. 값은 아래와 같아야 하고, 통합 테스트가 모듈별 값이 같은지 확인합니다(10장).

| 상수 | 값 | 둘 파일 | 현재 코드 |
|---|---|---|---|
| ALLOWED_REGIONS | ("이천시", "청주시") | preprocess.py, forecaster.py | clean_exports, detect_anomaly에 있음. aggregate_quarterly는 값을 직접 적음(추후 수정) |
| EXPORTS_COLUMNS | ("ym", "region", "hs_code", "export_usd", "collected_at") | preprocess.py | clean_exports에 `_EXPORT_COLUMNS`(list)로 있음 |
| FX_COLUMNS | ("date", "usdkrw") | data_loader.py | 있음 |
| ACTUALS_COLUMNS | ("quarter", "revenue_krw", "announced_date") | data_loader.py | load_actuals 없음 |
| QUARTERLY_COLUMNS | ("quarter", "export_usd", "months_available", "fx_avg") | preprocess.py | aggregate_quarterly 본문에 직접 적음 |
| FORECASTS_COLUMNS | 3.6의 열 9개 | app.py | main 없음 |
| MONTHS_PER_QUARTER | 3 | forecaster.py | 있음 |
| RATIO_WINDOW | 4 | forecaster.py | 있음 |
| DIRECTION_BAND_PCT | 2.0 | forecaster.py | 있음 |
| STD_EPSILON | 1e-9 | forecaster.py | 있음 |
| YOY_LAG_MONTHS, BASELINE_MONTHS | 12, 12 | forecaster.py | 있음 |
| REASON_NORMAL, REASON_SURGE, REASON_DROP, REASON_INSUFFICIENT | "정상", "급증", "급감", "데이터 부족" | forecaster.py | 있음 |
| forecast status, 방향, 일치 여부 문자열 | 4.1, 4.4의 허용값 | forecaster.py | 본문에 직접 적음. forecaster.py로 합칠 때 상수로 빼기를 권장 |

- 이름 규칙: 표 열 목록은 `<표 이름 대문자>_COLUMNS` 튜플, 빈 표는 `_empty_<표 이름>_table()`로 짓습니다. 세 사람의 forecaster.py와 두 사람의 preprocess.py를 한 파일로 합치면 `_empty_result`처럼 어느 표인지 드러나지 않는 이름은 헷갈리기 쉽습니다. 지금 테스트는 이 이름들을 직접 쓰지 않으므로 바꿔도 테스트는 깨지지 않습니다.

---

## 3. 표 스키마

### 3.1 raw_exports (수출 원자료, 저장 안 함)

- 만드는 곳 -> 쓰는 곳: fetch_regional_exports -> clean_exports
- 열: 관세청 API 응답 열 그대로 + collected_at(str "YYYY-MM-DD", fetch_regional_exports를 실행한 날짜). 이름 바꾸기, 형식 변환, 필터 같은 가공은 하지 않습니다.
- 원본 열 이름을 표준 열 이름으로 바꾸는 표는 clean_exports의 `RAW_COLUMN_MAP`입니다. 지금은 빈 dict라서 원자료가 표준 열 이름으로 와야 하고, 관세청 API 명세가 확정되면 채웁니다.
- 0행이어도 그대로 돌려줍니다. K-stat CSV로 대체하게 되면 main이 그 CSV를 읽어 같은 자리(clean_exports 입력)에 넘깁니다.

### 3.2 exports (지역별 월 수출)

| 순서 | 열 | dtype | 규칙 | 결측 |
|---|---|---|---|---|
| 1 | ym | str | "YYYY-MM" | 불가 |
| 2 | region | str | ALLOWED_REGIONS 중 하나 ("경기도 이천시" 같은 표기는 clean_exports가 바꿈) | 불가 |
| 3 | hs_code | str | "854232"(HS 품목 코드, 메모리 반도체), 숫자로 바꾸지 않음 | 허용 (아래 참고) |
| 4 | export_usd | float64 | 달러, 0 이상, 유한한 값. 0은 유효한 값 | 불가 |
| 5 | collected_at | str | "YYYY-MM-DD", 우리가 받은 날짜(관세청 공표일 아님) | 허용 (가장 오래된 것으로 봄) |

- 키: ym + region + hs_code / 정렬: ym, region, hs_code **[V1 변경: V1은 ym만]**
- 만드는 곳 -> 쓰는 곳: clean_exports -> upsert_records -> main이 data/exports.csv에 저장 -> aggregate_quarterly, detect_anomaly, 화면 수출 차트
- 뒤 함수가 실제로 읽는 열은 ym, region, export_usd 3개입니다. hs_code와 collected_at은 중복 판정과 기록용입니다.
- 빠진 달을 0으로 채우지 않습니다. 한 지역만 있는 달도 저장은 하지만, 분기 집계와 이상치 판정에서는 "자료가 없는 달"로 봅니다(합계가 작게 잡혀 가짜 급감이 나오기 때문).
- 같은 키가 여러 번 오면: 한 번에 받은 자료 안에서는 clean_exports가 collected_at이 가장 최근인 행을, 저장 표와 새 자료 사이에서는 upsert_records가 새 자료 쪽 행을 남깁니다.
- hs_code는 그 행이 어떤 품목의 수출인지 나타냅니다. 지금은 854232 하나만 받으므로 모든 행이 같은 값이고, 키에 들어 있는 이유는 나중에 품목을 늘려도 같은 달, 같은 지역 행끼리 겹치지 않게 하기 위해서입니다.
- hs_code 결측: 지금 clean_exports는 hs_code가 비어 있는 행도 남깁니다(명세에 없는 제거라 9주차 코드 리딩에서 뺐음). 그런데 aggregate_quarterly와 detect_anomaly는 hs_code를 보지 않고 같은 달, 같은 지역 행을 모두 더하므로, 854232가 아니거나 비어 있는 행이 섞이면 수출이 부풀려집니다. 관세청 응답에 품목 코드 열이 오는지 명세로 확인한 뒤, clean_exports에 `ALLOWED_HS_CODES = ("854232",)` 필터를 넣을지 팀이 정합니다. **[팀 확인]**

### 3.3 fx (일별 원/달러 환율)

| 순서 | 열 | dtype | 규칙 | 결측 |
|---|---|---|---|---|
| 1 | date | str | "YYYY-MM-DD" | 불가 |
| 2 | usdkrw | float64 | 1달러당 원, 0 초과 | 불가 |

- 키: date / 정렬: date
- 만드는 곳 -> 쓰는 곳: fetch_fx_rates -> upsert_records -> main이 data/fx.csv에 저장 -> aggregate_quarterly
- 주말, 공휴일처럼 값이 없는 날은 행이 없습니다. 앞 값이나 0으로 채우지 않습니다.
- 응답에 같은 date가 여러 번 오면 나중 행을 남깁니다.
- 0행: ECOS 응답이 INFO-200(데이터 없음)이거나 유효한 행이 하나도 없으면, dtype을 지정한 0행 표를 돌려줍니다.

### 3.4 actuals (분기 확정 매출, 팀 수기)

| 순서 | 열 | dtype | 규칙 | 결측 |
|---|---|---|---|---|
| 1 | quarter | str | "YYYYQn", 중복 불가 | 불가 |
| 2 | revenue_krw | float64 | 원 단위, 연결 기준 3개월 매출, 0 초과 | 불가 |
| 3 | announced_date | str | "YYYY-MM-DD", 잠정실적 공정공시일 | 불가 |

- 키: quarter / 정렬: quarter
- 만드는 곳 -> 쓰는 곳: 팀원이 DART 공시로 작성 -> load_actuals -> estimate_revenue (백테스트는 announced_date도 씀)
- load_actuals는 잘못된 행을 지우지 않고 ValueError를 냅니다(사람이 고쳐야 하는 파일이라서). revenue_krw의 천 단위 쉼표는 지우고 읽습니다.
- 작성 규칙: DART 표는 보통 백만 원 단위이므로 원 단위로 바꿔 적습니다. 4분기 = 사업보고서 연간 매출 - 3분기보고서 누적 매출. 한 명이 입력하고 다른 한 명이 잠정실적 공시와 대조합니다(1% 넘게 차이 나면 다시 확인).

### 3.5 quarterly (분기 집계, 저장 안 함)

| 순서 | 열 | dtype | 규칙 | 결측 |
|---|---|---|---|---|
| 1 | quarter | str | "YYYYQn", lag_months를 적용한 귀속 분기 | 불가 |
| 2 | export_usd | float64 | 두 지역이 모두 있는 달의 수출 합계(달러) | 불가 |
| 3 | months_available | int64 | 1~3, 합계에 들어간 달 수 | 불가 |
| 4 | fx_avg | float64 | 그 분기에 값이 있는 날의 usdkrw 평균 | 허용 (환율 자료가 없는 분기) |

- 키: quarter / 정렬: quarter
- 만드는 곳 -> 쓰는 곳: aggregate_quarterly -> estimate_revenue
- 수출 자료가 하나도 없는 분기는 행을 만들지 않습니다. **[V1 변경]** 그래서 months_available은 0이 나오지 않습니다(V1은 0~3). estimate_revenue가 "행 없음"을 no_data로 처리합니다.
- lag_months는 수출에만 적용합니다. fx_avg는 그 분기 실제 날짜들의 평균입니다. 기본값 lag_months=0은 바꾸지 않고, 시차 실험은 백테스트에서만 합니다.

### 3.6 forecasts (예측 이력)

| 순서 | 열 | dtype | 규칙 | 결측 |
|---|---|---|---|---|
| 1 | quarter | str | 대상 분기 "YYYYQn" | 불가 |
| 2 | as_of | str | 예측을 실행한 날 "YYYY-MM-DD" | 불가 |
| 3 | estimate_krw | float64 | 원 | status가 "ok"가 아니면 빈칸 |
| 4 | lower_krw | float64 | 원 | 위와 같음 |
| 5 | upper_krw | float64 | 원 | 위와 같음 |
| 6 | qoq_change_pct | float64 | % | 위와 같음. 직전 분기 실적이 없어도 빈칸 |
| 7 | ratio_used | float64 | 기준 분기 비율 평균 | status가 "ok"가 아니면 빈칸 |
| 8 | months_available | int64 | 0~3 | 불가 |
| 9 | status | str | forecast의 status | 불가 |

- 키: quarter + as_of (같은 날 다시 실행하면 덮어씀) / 정렬: quarter, as_of
- 만드는 곳 -> 쓰는 곳: main이 forecast dict에 as_of를 붙여 1행을 만듦 -> upsert_records -> data/forecasts.csv에 저장 -> 화면 예측 이력 표
- **[V1 변경]** qoq_change_pct 열을 추가해, 열이 forecast dict 키 8개 + as_of와 같아졌습니다. main은 열을 골라 옮기지 않고 `{**forecast, "as_of": 오늘}`로 행을 만들 수 있고, 이력 표에서도 전분기 대비 변화를 보여 줄 수 있습니다.
- None이 든 dict로 바로 만든 행은 숫자 열이 object가 되므로, 저장 전에 숫자 열 5개를 float64로 바꿉니다.

### 3.7 transcripts (컨콜 텍스트)

- data/transcripts/YYYYQn.txt, UTF-8, 분기당 1개. 파일 이름은 실적을 발표한 분기입니다(2026Q3.txt = 3분기 실적발표, 4분기 전망 포함).
- 내용: 실적발표 보도자료의 전망 문단 + 컨콜 질의응답 기사 정리
- 대상 분기가 2026Q4이면 main이 직전 분기 파일 2026Q3.txt를 읽어 extract_guidance에 넘깁니다. 파일이 없으면 빈 문자열을 넘깁니다(결과는 empty_input -> 판단불가).

---

## 4. dict 스키마

### 4.1 forecast (estimate_revenue 반환)

| 키 | 타입 | 규칙 |
|---|---|---|
| quarter | str | 받은 target_quarter 그대로 |
| estimate_krw | float, None | 중앙값(원). lower_krw <= estimate_krw <= upper_krw |
| lower_krw | float, None | 하한(원) |
| upper_krw | float, None | 상한(원) |
| qoq_change_pct | float, None | 직전 분기 실적 대비 % |
| ratio_used | float, None | 기준 분기 비율 RATIO_WINDOW개의 평균 |
| months_available | int | 0~3, 대상 분기에 반영된 수출 개월 수 |
| status | str | "ok", "no_data", "insufficient_history" |

| status | 언제 | 숫자 키 5개 | months_available |
|---|---|---|---|
| ok | 계산 성공 | estimate, lower, upper, ratio_used를 채움. qoq_change_pct는 직전 분기 실적이 있고 0이 아닐 때만 | 1~3 |
| no_data | target_quarter 형식 오류 / 대상 행 없음 / months_available이 결측이거나 0 이하 / 대상 행의 export_usd나 fx_avg가 결측 | 모두 None | 대상 행의 값. 행이 없거나 0 이하이면 0 |
| insufficient_history | 기준 분기가 RATIO_WINDOW(4)개 미만 | 모두 None | 대상 행의 값 |

- 기준 분기: 대상 분기보다 앞서고, actuals에 revenue_krw가 결측이 아닌 실적이 있고, months_available == 3, export_usd > 0, fx_avg > 0인 분기 중 가장 최근 4개 **[V1 변경: fx_avg > 0과 revenue_krw 결측 제외를 명시]**
- 비율 = (revenue_krw / fx_avg) / export_usd
- 분기 수출 추정 = 대상 행 export_usd x 3 / months_available
- 중앙값, 하한, 상한 = 분기 수출 추정 x (비율 평균, 최솟값, 최댓값) x 대상 행 fx_avg
- 대상 분기와 그 이후의 실적은 읽지 않습니다(미래 정보 누수 방지). 가이던스는 계산에 쓰지 않습니다.

### 4.2 anomaly (detect_anomaly 반환)

| 키 | 타입 | 규칙 |
|---|---|---|
| ym | str | 받은 target_ym 그대로 |
| yoy_pct | float, None | 대상 월의 전년 동월 대비 증가율(%) |
| z_score | float, None | (yoy_pct - 직전 12개월 전년동월비 평균) / 표본 표준편차 |
| is_anomaly | bool | abs(z_score) > threshold이면 True |
| reason | str | "정상", "급증", "급감", "데이터 부족" |

- 판정: abs(z) > threshold일 때만 이상치이고, 같으면 "정상"입니다. z가 양수면 "급증", 음수면 "급감"입니다.
- "데이터 부족"이면 z_score는 None, is_anomaly는 False입니다. yoy_pct는 표준편차가 STD_EPSILON 미만인 경우에만 채우고, 나머지 "데이터 부족"에서는 None입니다.
- **[V1 변경]** "데이터 부족"이 되는 경우 (V1은 25개월 부족과 표준편차 0만 적었음)
  - target_ym이 "YYYY-MM" 형식이 아님
  - exports_df가 DataFrame이 아님, 0행, 필수 열(ym, region, export_usd) 누락
  - 대상 월과 그 앞 24개월(모두 25개월) 중 월 합계가 없는 달이 있음 (한 지역만 있는 달은 없는 달)
  - 12개월 전 월 합계가 0
  - 직전 12개월 전년동월비의 표준편차가 STD_EPSILON(1e-9) 미만 (부동소수 오차 때문에 == 0 대신 씀)
- 월 합계를 만들 때 잘못된 ym, 대상 외 지역, 숫자로 바꿀 수 없는 값, 결측, 음수, 무한대인 행은 건너뛰고, 같은 달, 같은 지역 행은 더합니다.
- threshold가 숫자가 아니면 TypeError가 그대로 납니다(자료 문제가 아니라 호출 실수).
- 평균과 표준편차는 합 / 개수, 제곱합 / (개수 - 1), math.sqrt로 구합니다. statistics나 pandas 함수로 바꾸면 끝자리가 달라져 abs(z) == threshold 경계 판정이 뒤집힐 수 있습니다.

### 4.3 guidance (extract_guidance 반환)

| 키 | 타입 | 허용값, 규칙 | 기본값 |
|---|---|---|---|
| status | str | "ok", "empty_input"(빈 텍스트), "parse_error"(LLM 응답이 JSON이 아님) | |
| target_quarter | str, None | "YYYYQn" 형식이 아니면 None | None |
| dram_bit_growth_pct | float, None | D램 출하 증가율 전망(%), -50~100. 숫자가 아니거나(bool 포함) 범위 밖이면 None | None |
| nand_bit_growth_pct | float, None | 낸드, 같은 규칙 | None |
| price_outlook | str | "상승", "보합", "하락", "언급없음"(원문에 가격 전망 없음), "NA"(추출 실패, 허용값 밖) | "NA" |
| hbm_comment | str | 100자 이내, 없으면 "" | "" |
| evidence | list[str] | 근거 원문 문장, 앞에서부터 최대 3개 | [] |

- status가 "ok"가 아니면 나머지 6개 키는 모두 기본값입니다.
- "NA"와 "언급없음"을 섞지 않습니다. 추출 실패를 "언급없음"으로 채우면 "가이던스 없음"으로 둔갑합니다.
- 빈 입력(None, 공백뿐)이면 LLM을 부르지 않습니다.
- mock 모드에서는 hbm_comment(비어 있지 않을 때)와 evidence의 각 문장 앞에 "[MOCK] "이 붙습니다(5.1). 100자 제한은 표식을 포함한 길이입니다.
- compare_guidance가 읽는 키는 status, price_outlook, dram_bit_growth_pct 3개입니다.

### 4.4 consistency (compare_guidance 반환)

| 키 | 타입 | 허용값 |
|---|---|---|
| status | str | "일치", "불일치", "판단불가" |
| forecast_direction | str, None | "상승", "보합", "하락", None |
| guidance_direction | str, None | "상승", "하락", None |

- 예측 방향: forecast의 status가 "ok"이고 qoq_change_pct가 유효한 숫자일 때만 정합니다. +2 초과 "상승", -2 미만 "하락", -2 이상 +2 이하 "보합"입니다.
- 가이던스 방향(D램 기준): guidance의 status가 "ok"일 때만 정합니다. price_outlook이 "상승"이고 dram_bit_growth_pct가 None 또는 0 이상이면 "상승", "하락"이고 None 또는 0 이하이면 "하락", 그 밖은 None입니다.
- 판정: 두 방향 중 하나가 None이거나 예측이 "보합"이면 "판단불가", 같으면 "일치", 다르면 "불일치"입니다. 낸드 전망은 쓰지 않습니다.
- **[V1 변경]** 어떤 입력에도 예외를 내지 않습니다. 인자가 dict가 아니거나, 키가 없거나, 숫자 자리에 bool, 문자열, NaN, 무한대가 오면 그 방향을 None으로 보고 "판단불가"로 돌려줍니다.

### 4.5 brief (generate_brief 반환, str)

- forecast의 status가 "ok"이면 3~5문장을 공백 하나로 이은 문자열입니다.
- status가 "no_data"이면 "대상 분기의 수출 자료가 아직 없어 매출을 추정할 수 없습니다.", "insufficient_history"이면 "비교할 과거 실적이 4개 분기보다 적어 매출을 추정할 수 없습니다." 한 문장을 돌려주고 LLM을 부르지 않습니다.
- 문장 속 숫자는 facts(5.4) 값과 ALLOWED_EXTRA_NUMBERS에 있는 것만 씁니다. 그 밖의 숫자가 있거나 문장 수가 3~5개가 아니면 BRIEF_TEMPLATES 문장으로 바꿉니다.
- "투자 권유가 아님" 고지는 붙이지 않습니다(main이 화면에 표시).
- mock 모드에서는 LLM 응답에서 온 문장마다 앞에 "[MOCK] "이 붙습니다(5.1). 코드가 만든 안내 문장과 템플릿 대체 문장에는 붙지 않습니다.

---

## 5. LLM 경계

llm_module.py 내부 형식이지만, prompts/ 템플릿과 mock, 테스트가 함께 기대는 형식이라 여기에 적습니다.

### 5.1 _call_llm

- `def _call_llm(prompt: str) -> str:` LLM 호출은 이 함수 한 곳에서만 합니다. 13주차에는 이 함수의 실제 모드 부분만 바꿉니다.
- **[V1 변경]** 모드 스위치는 강의 2.5절 Mock 패턴대로 llm_module.py 맨 위의 상수입니다.
  ```python
  USE_MOCK = True  # 13주차에 False로 전환

  def _call_llm(prompt: str) -> str:
      if USE_MOCK:
          return _mock_response(prompt)  # "[원문]"이면 _mock_guidance, "[입력]"이면 _mock_brief
      return _call_real(prompt)  # 13주차 구현 예정
  ```
- 강의 예시는 공개 함수 안에서 mock과 실제로 갈리지만, 우리는 `_call_llm` 안에서 갈립니다. JSON 해석, 허용값 검사, 숫자 검사가 extract_guidance, generate_brief 본문에 있어야 mock과 실제 응답이 같은 코드로 걸러지고, T12~T16을 13주차에도 그대로 쓸 수 있기 때문입니다.
- 13주차에 False로 바꾼 뒤에도 단위 테스트는 `monkeypatch`로 USE_MOCK을 True로 두거나 `_call_llm`을 바꿔 끼워 API 없이 돌립니다.
- 실패(키 없음, API 오류, 시간 초과 20초)하면 예외 없이 빈 문자열을 돌려주고, 호출한 함수가 parse_error나 템플릿 경로로 처리합니다.
- **[MOCK] 표식은 키를 새로 만들지 않고 문자열 안에 넣습니다.**
  - mock 응답에서 사람이 읽는 문장 값 앞에만 "[MOCK] "을 붙입니다: guidance의 hbm_comment(빈 문자열이면 그대로 ""), evidence의 각 문장, 브리프의 각 문장
  - 허용값이 정해진 값(status, price_outlook, target_quarter, 숫자)에는 붙이지 않습니다. 붙이면 검사에서 "NA"나 None으로 바뀝니다.
  - 표식은 mock이 만든 문장에만 있습니다. 코드가 만든 문장(no_data 안내, 템플릿 대체 문장)과 실제 모드 응답에는 없으므로, 화면에 [MOCK]이 보이면 그 문장이 mock 응답에서 왔다는 뜻입니다.
  - 키가 늘지 않으므로 dict 형식(guidance 키 7개, 허용값)은 mock과 실제 모드가 같습니다.

### 5.2 프롬프트 표시 줄

- 가이던스 추출 프롬프트: 지시문 다음에 "[원문]" 한 줄, 그 아래 컨콜 텍스트
- 브리프 프롬프트: 지시문 다음에 "[입력]" 한 줄, 그 아래 facts JSON
- mock은 이 표시 줄로 어떤 요청인지 구분하므로, prompts/의 템플릿 문구를 고쳐도 이 두 줄은 바꾸지 않습니다.

### 5.3 LLM 응답 JSON

| 요청 | 응답 JSON | 코드가 거르는 방법 |
|---|---|---|
| 가이던스 추출 | `{"target_quarter", "dram_bit_growth_pct", "nand_bit_growth_pct", "price_outlook", "hbm_comment", "evidence"}` 6개 키. 원문에 없는 숫자는 null, price_outlook은 "상승", "보합", "하락", "언급없음" 중 하나 | 4.3 규칙. status는 코드가 붙임. 그 밖의 키는 버리고 빠진 키는 기본값 |
| 브리프 | `{"sentences": [문장, ...]}`, 문장 3~5개 | 4.5 규칙 |

### 5.4 facts (generate_brief가 LLM에 넘기는 입력)

모든 값은 표시용 문자열이고, 원래 값이 None이면 "확인 불가"입니다.

| 키 | 출처 | 형식, 예 |
|---|---|---|
| quarter | forecast.quarter | "2026Q4" |
| estimate | forecast.estimate_krw | 조 원, 소수 첫째 자리: "26.1조 원" |
| range | forecast.lower_krw, upper_krw | "24.4~27.8조 원" |
| qoq | forecast.qoq_change_pct | 부호 포함 소수 첫째 자리: "+16.5%" |
| months | forecast.months_available | "2개월" |
| ratio | forecast.ratio_used | 소수 둘째 자리: "1.50" |
| export_yoy | anomaly.yoy_pct | 부호 포함 소수 첫째 자리: "+40.0%" |
| anomaly | anomaly.reason | "정상" |
| consistency | consistency.status | "일치" |

---

## 6. 함수별 입출력과 예외

시그니처는 설계 문서 V1과 같고 바꾸지 않습니다.

| 모듈 | 함수 | 받는 것 -> 돌려주는 것 | 예외와 메시지 | main 브랜치 |
|---|---|---|---|---|
| data_loader | `fetch_regional_exports(start_ym: str, end_ym: str) -> pd.DataFrame` | 월 2개 -> raw_exports | RuntimeError "관세청 API 키가 없습니다", "관세청 API 호출 실패: <지역>, <원인>" | 없음 |
| data_loader | `fetch_fx_rates(start_date: str, end_date: str) -> pd.DataFrame` | 일 2개 -> fx | ValueError "날짜 형식 오류: <값>", "시작일이 끝일보다 늦습니다: <시작일> > <끝일>" / RuntimeError "ECOS API 키가 없습니다", "ECOS API 호출 실패: <원인>" | 강민규 |
| data_loader | `load_actuals(filepath: str) -> pd.DataFrame` | CSV 경로 -> actuals | ValueError "필수 열 누락: <열>", "actuals.csv 형식 오류: <행 번호 또는 quarter>", "actuals.csv 분기 중복: <quarter>" / 파일이 없으면 FileNotFoundError 그대로 | 없음 |
| preprocess | `clean_exports(raw_df: pd.DataFrame) -> pd.DataFrame` | raw_exports -> exports | ValueError "필수 열 누락: <열>, <열>" | 조현모 |
| preprocess | `upsert_records(store_df: pd.DataFrame, new_df: pd.DataFrame, key_cols: list[str]) -> pd.DataFrame` | 같은 스키마 표 2개 -> 같은 스키마 표 | ValueError "key_cols는 비어 있을 수 없습니다.", "<store_df 또는 new_df>에 키 열이 없습니다: <열>, <열>" | 조현모 |
| preprocess | `aggregate_quarterly(exports_df: pd.DataFrame, fx_df: pd.DataFrame, lag_months: int = 0) -> pd.DataFrame` | exports, fx -> quarterly | ValueError "lag_months는 0 이상이어야 합니다" | 신해성 (import 오류, 9장 1번) |
| forecaster | `estimate_revenue(quarterly_df: pd.DataFrame, actuals_df: pd.DataFrame, target_quarter: str) -> dict` | quarterly, actuals -> forecast | 없음 (열 누락은 KeyError 그대로) | 신동훈 |
| forecaster | `detect_anomaly(exports_df: pd.DataFrame, target_ym: str, threshold: float = 2.0) -> dict` | exports -> anomaly | TypeError (threshold가 숫자가 아님) | 강민규 |
| forecaster | `compare_guidance(forecast: dict, guidance: dict) -> dict` | forecast, guidance -> consistency | 없음 | 이다현 |
| llm_module | `extract_guidance(transcript_text: str) -> dict` | 컨콜 텍스트 -> guidance | 없음 | 없음 |
| llm_module | `generate_brief(forecast: dict, anomaly: dict, consistency: dict) -> str` | dict 3개 -> brief | 없음 | 없음 |
| app | `main() -> None` | 화면 입력 -> 화면 표시, CSV 저장 | RuntimeError는 경고 후 진행, ValueError는 표시 후 멈춤 | 없음 |

---

## 7. 데이터 흐름

```text
[데이터 갱신]
fetch_regional_exports -> raw_exports -> clean_exports -> exports(새 자료)
    -> upsert_records(저장된 exports, 새 자료, ["ym", "region", "hs_code"]) -> data/exports.csv
fetch_fx_rates -> fx(새 자료)
    -> upsert_records(저장된 fx, 새 자료, ["date"]) -> data/fx.csv
(수집 실패 RuntimeError -> 경고 후 저장된 데이터로 진행)

[예측 실행]
load_actuals("data/actuals.csv")                  -> actuals
aggregate_quarterly(exports, fx)                  -> quarterly
estimate_revenue(quarterly, actuals, 대상 분기)     -> forecast   (no_data면 여기서 멈춤)
detect_anomaly(exports, 대상 분기 안 가장 최근 ym)   -> anomaly
extract_guidance(직전 분기 transcripts 텍스트 또는 "") -> guidance
compare_guidance(forecast, guidance)              -> consistency
generate_brief(forecast, anomaly, consistency)    -> brief
upsert_records(저장된 forecasts, forecast + as_of 1행, ["quarter", "as_of"]) -> data/forecasts.csv
```

---

## 8. 설계 문서 V1 대비 바뀐 점

| 번호 | 대상 | V1 | 이 문서 | 근거 |
|---|---|---|---|---|
| 1 | 모든 표 | 0행 표는 열 이름만 규정 | dtype까지 정상 표와 같게, `_empty_<표>_table()`에서 만듦 | fetch_fx_rates 코드 리딩 수정 2. clean_exports의 빈 표를 저장 표에 upsert하면 export_usd가 object로 바뀌는 것을 이번에 재현 |
| 2 | 모든 표 | 빈 표 판정 방법 없음 | `len(df) == 0` | upsert_records 리팩터링(`2e9dcff`): `.empty`는 열 0개 1행 표도 True |
| 3 | 월, 일, 분기 문자열 | 형식만 규정 | ASCII 숫자만 인정 | fetch_fx_rates 수정 1, detect_anomaly 리팩터링에서 발견한 전각 숫자 통과 |
| 4 | 모든 dict | 키와 타입 | 파이썬 기본 타입만, 호출마다 새 dict | detect_anomaly 리팩터링 R4와 반환 타입 테스트, estimate_revenue의 int 변환 |
| 5 | 허용값, 지역 이름 | 문서에만 적음 | 파일 맨 위 상수(REASON_*, ALLOWED_REGIONS)로만 씀 | detect_anomaly 리팩터링 R2, R3: 지역 이름을 코드에 다시 적으면 상수만 바꿨을 때 KeyError |
| 6 | 외부 호출 오류 | RuntimeError | 메시지 형식 고정, URL과 키와 str(e) 금지, from None | fetch_fx_rates 리팩터링 R2, R6과 안전망 테스트(메시지 원문 고정) |
| 7 | 필수 열 검사 | 정하지 않음 | 바깥 자료를 처음 받는 함수만 ValueError, 안쪽 함수는 KeyError 그대로 | estimate_revenue 코드 리딩 수정 1: 열 누락을 no_data로 바꾸면 앞 단계 버그가 숨음 |
| 8 | exports 정렬 | ym | ym, region, hs_code | clean_exports 코드 리딩: 정렬 키를 고정해야 행 순서가 실행마다 같음 |
| 9 | quarterly.months_available | 0~3 | 1~3 | aggregate_quarterly: 수출이 없는 분기는 행을 만들지 않음 |
| 10 | forecast | 기준 분기 조건 3개 | fx_avg > 0, revenue_krw 결측 제외, 형식이 틀린 분기는 no_data, months_available 0 이하는 0 | estimate_revenue 코드 리딩 수정 2, 3과 테스트 A01~A04 |
| 11 | anomaly | 25개월 부족, 표준편차 0 | 데이터 부족 조건 5가지, STD_EPSILON, yoy_pct를 채우는 경우 명시 | detect_anomaly 리팩터링의 docstring 계약과 guard 테스트 15개 |
| 12 | consistency | 판정 규칙만 | 비정상 입력도 예외 없이 판단불가 | compare_guidance 코드 리딩 수정 1~3 |
| 13 | forecasts | 열 8개(qoq_change_pct 없음) | forecast 키 8개 + as_of | 이 문서에서 정함: dict와 표의 키가 같아 main의 열 옮기기 코드가 필요 없음 |
| 14 | Mock 스위치와 표식 | 환경변수 LLM_MODE(기본값 mock), 표식 없음 | 상수 `USE_MOCK = True`(13주차에 False), mock 응답의 문장 값 앞에 "[MOCK] " | 10주차 강의 2.5절 Mock 패턴과 과제 1-3 요구 |

---
