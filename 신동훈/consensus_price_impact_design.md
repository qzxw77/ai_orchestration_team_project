# 설계서: 매출 컨센서스 비교와 주가 영향 판단

알트(ALT) MVP(SK하이닉스 분기 매출 나우캐스팅)에, FnGuide 연간 매출 컨센서스와 우리 추정 매출을 비교해 주가 영향 방향을 판단하고 화면에 보여 주는 기능을 더하는 설계입니다.

- 작성일: 2026-11-17
- 대상 코드: `alt_backend_week11/` (app.py, backend.py, hynix_nowcast/)
- 구현: 같은 브랜치(feat/consensus)에 반영됨. 구현하면서 바뀐 점은 11장에 정리
- 표기: **[팀 확인]** = 구현 전에 팀이 정할 것

## 목차

1. 문제 정의와 범위
2. 입력 데이터: FnGuide 엑셀에서 consensus.csv로
3. 핵심 로직: 연간 컨센서스를 분기 컨센서스로 환산
4. 모듈 분해 (IPO, 모듈 트리, 함수 목록)
5. 데이터 계약 (표와 dict)
6. 판정 규칙과 상수
7. Pseudocode
8. 화면 구성 (카드와 값의 대응)
9. 테스트 케이스 명세
10. 구현 규칙, 한계, 남은 결정

---

## 1. 문제 정의와 범위

### 1.1 왜 필요한가

주가는 실적이 좋은지보다 **시장 기대(컨센서스)보다 좋은지**에 반응합니다. 지금 MVP는 "이번 분기 매출이 얼마일지"만 보여 줍니다. 그래서 개인투자자는 그 숫자가 시장 기대보다 높은지 낮은지, 주가에 어떤 의미인지 알 수 없습니다.

### 1.2 이번에 추가하는 것

| 구분 | 내용 |
|---|---|
| 포함 | FnGuide 연간 매출 컨센서스(FY1) 수기 CSV, 분기 컨센서스 환산, 우리 추정과의 괴리율, 컨센서스 대비 위치(상회, 부합, 하회), 컨센서스 분포 안 위치, 컨센서스 1개월 리비전, 주가 영향 방향(긍정, 중립, 부정), 판단 신뢰도 점수, 화면 카드 |
| 이번에 제외 | 업종 펀더멘털 점수(재고와 가격 데이터 필요), 수출 증가율(직전 분기 대비) 카드, 브리프(LLM)에 주가 판단 넣기, 주가 데이터 수집과 목표 주가 계산 |
| 설계서 V1과의 관계 | V1 범위 '제외 1번(주가 예측)'은 수정될 수 있다는 전제로, 팀 합의에 따라 이번 설계에서는 적용하지 않음 **[팀 확인: 설계서 V1 범위 문구 수정]** |

### 1.3 주가 영향 판단의 정의

> 우리 추정 매출이 (분기로 환산한) 시장 컨센서스를 상회, 부합, 하회하는지 판정하고, 연간 컨센서스의 최근 변화(리비전)를 보조로 사용해 주가 영향 방향을 긍정, 중립, 부정으로 보여 준다. 판단 신뢰도는 근거 데이터가 얼마나 충분한지 나타내는 0~100 점수이며, 주가가 오를 확률이 아니다.

---

## 2. 입력 데이터: FnGuide 엑셀에서 consensus.csv로

### 2.1 원본 엑셀 (DataGuide 출력) 구조

| 항목 | 내용 |
|---|---|
| 시트 | Sheet1 하나. 1~14행은 머리글(설정, 코드, 아이템명, 집계주기), 15행부터 날짜별 1행 |
| 기간 | 2000-07-14 ~ 2026-11-11 (값이 있는 행 6,489개, 빈칸 없음) |
| 열 | A열 날짜, B~E열 FY1 매출액 평균, 최고, 최저, 중앙값, F~I열 FY2 같은 순서 |
| 단위 | 억 원 |
| FY1 | 그 날짜 기준으로 연간 실적이 아직 발표되지 않은 가장 가까운 회계연도 |
| FY1이 다음 해로 넘어가는 날 | 4분기 실적 발표일 당일 (2024-01-25, 2025-01-23, 2026-01-28 확인. actuals.csv의 announced_date와 같음) |

FnGuide에서 분기 컨센서스(FQ)를 받을 수 없다는 가정으로 설계합니다. 분기 컨센서스를 받게 되면 3장의 환산 부분만 바꾸면 됩니다(10.3).

### 2.2 consensus.csv (팀 수기 작성)

위치: `alt_backend_week11/data/consensus.csv`. actuals.csv와 같이 커밋합니다.

| 열 | 타입 | 규칙 |
|---|---|---|
| `as_of` | str "YYYY-MM-DD" | 엑셀 A열 날짜 |
| `fiscal_year` | int | FY1이 가리키는 회계연도 (2.3의 규칙으로 변환할 때 확정) |
| `mean_krw` | float | FY1 매출액 평균 × 1e8 (원 단위) |
| `high_krw` | float | FY1 매출액 최고 × 1e8 |
| `low_krw` | float | FY1 매출액 최저 × 1e8 |
| `median_krw` | float | FY1 매출액 중앙값 × 1e8 |
| `source` | str | "FnGuide" |

- 키: `as_of` (FY1만 저장하므로 날짜당 1행)
- 값 규칙: 4개 금액은 0보다 크고, `low_krw ≤ mean_krw ≤ high_krw`
- 저장 범위: 2024-01-25부터 (2024년이 FY1이 된 날, 약 679행)
- FY2를 저장하지 않는 이유: 대상 분기의 직전 분기 실적이 발표된 뒤에만 판단하므로(6.1), 그 시점에는 대상 연도가 항상 FY1입니다.

### 2.3 엑셀에서 CSV로 변환하는 절차 (수기)

1. DataGuide에서 엑셀을 새로 받는다(지금과 같은 설정).
2. A열 날짜와 B~E열(FY1)만 복사한다.
3. `fiscal_year`를 채운다. **날짜가 그해 '전년도 4분기 실적 발표일'(actuals.csv의 announced_date) 이후(당일 포함)이면 그해, 이전이면 전년.**
   - 예: 2026-01-27 → 2025, 2026-01-28 → 2026
4. 금액 4개 열에 1e8을 곱해 원 단위로 바꾼다(엑셀 수식 `=B15*100000000`).
5. 기존 CSV에 없는 날짜만 이어 붙이고, 같은 날짜는 새 값으로 바꾼다.
6. 한 명이 입력하고 다른 한 명이 최근 5개 날짜를 엑셀과 대조한다(actuals.csv 규칙과 같음).

**[팀 확인]** 매번 수기 변환이 번거로우면 변환 스크립트(엑셀 → CSV)를 별도 도구로 만들 수 있습니다. 앱 실행 경로에는 넣지 않습니다.

---

## 3. 핵심 로직: 연간 컨센서스를 분기 컨센서스로 환산

### 3.1 공통 식

```
남은 컨센서스 R = FY1 연간 컨센서스(평균) − 대상 연도에 이미 발표된 분기 실적 합(YTD)
남은 분기 수 k = 4 − (대상 분기 번호 − 1)
```

- **대상이 4분기(k = 1)이면** R이 곧 4분기 컨센서스이며 정확합니다(`method = "exact"`).
- **대상이 1~3분기(k ≥ 2)이면** R을 남은 분기에 나눠야 하므로 근사입니다(`method = "allocated"`). 아래 세 방법을 모두 계산하고 그 범위를 씁니다.

### 3.2 나누는 방법 세 가지 (k ≥ 2일 때)

| 이름 | 대상 분기 몫 | 가정 | 계산할 수 없을 때 |
|---|---|---|---|
| `even` 균등 분할 | R ÷ k | 남은 분기 매출이 같다 | 항상 계산됨 |
| `prior_share` 전년 비중 | R × s_t ÷ (s_t + … + s_4). s_q = 전년 q분기 실적 ÷ 전년 연간 실적 | 올해도 작년과 같은 분기 패턴 | 전년 4개 분기 실적 중 하나라도 없으면 None |
| `const_growth` 일정 성장 | 기준 실적 B(직전 분기 실적)에서 매 분기 같은 배수 x로 늘어 B·(x + x² + … + x^k) = R이 되는 x를 구하고, 대상 분기 = B·x | 시장 기대 성장률이 남은 분기에 고르게 이어진다 | 직전 분기 실적이 없거나 0 이하이면 None |

- **환산 중심값(center)** = 계산된 방법들의 중앙값 (2개면 평균, 1개면 그 값)
- **환산 범위(band)** = 계산된 방법들의 최솟값 ~ 최댓값
- `const_growth`의 x는 이분법으로 구합니다. 좌변이 x에 대해 단조 증가하므로 해는 하나입니다.

### 3.3 근거: 실제 데이터로 비교한 환산 오차

실제 2025년 연간 매출을 컨센서스라고 가정하고 각 분기에 나눴을 때의 오차입니다(나누는 과정에서만 생기는 오차).

| 대상 | 실제 | 균등 | 전년 비중 | 일정 성장 |
|---|---|---|---|---|
| 2025Q1 | 17.6조 | +37.7% | +3.4% | +21.5% |
| 2025Q2 | 22.2조 | +19.2% | +9.2% | −3.4% |
| 2025Q3 | 24.4조 | +17.1% | +10.3% | +7.4% |
| 2025Q4 | 32.8조 | 0.0% | 0.0% | 0.0% |

2026년 FY1 컨센서스로 환산한 값과 실제 실적은 다음과 같습니다.

| 대상 (컨센서스 기준일) | 균등 | 전년 비중 | 일정 성장 | 실제 |
|---|---|---|---|---|
| 2026Q2 (04-24) | 89.0조 | 74.6조 | 67.7조 | 79.3조 |
| 2026Q3 (07-30) | 107.4조 | 91.7조 | 96.8조 | 104.6조 |
| 2026Q4 (11-11) | 126.5조 | 126.5조 | 126.5조 | 미발표 |

결론: 어느 한 방법도 늘 맞지 않고 1~3분기 오차는 10~20% 수준입니다. 그래서 1~3분기는 **값 하나 대신 범위로 판정**하고, 남은 분기가 많을수록 신뢰도를 깎습니다.

### 3.4 4분기 실제 서프라이즈 (검증용)

| 대상 | FY1 평균 (기준일) | 1~3분기 실적 합 | 분기 컨센서스 | 실제 | 서프라이즈 |
|---|---|---|---|---|---|
| 2024Q4 | 66.11조 (2025-01-22) | 46.43조 | 19.68조 | 19.77조 | +0.4% |
| 2025Q4 | 95.30조 (2026-01-27) | 64.32조 | 30.98조 | 32.83조 | +6.0% |
| 2026Q4 | 363.04조 (2026-11-11) | 236.51조 | 126.53조 | 미발표 | – |

---

## 4. 모듈 분해

### 4.1 시스템 수준 IPO (추가분만)

| Input | Processing | Output |
|---|---|---|
| ① consensus.csv (FY1 연간 컨센서스, 날짜별) ② actuals.csv (기존) ③ forecast dict (기존 estimate_revenue 결과) ④ 예측 실행일(as_of) | ① 컨센서스 읽기 ② 기준일 고르기, 분기 환산, 리비전 계산 ③ 괴리율, 위치 판정 ④ 주가 영향 방향, 신뢰도 계산 | ① 시장 컨센서스(분기) 카드 ② 예상 괴리율 카드 ③ 주가 영향 판단 카드 4개 |

숫자 계산은 모두 forecaster.py에서 하고, LLM은 쓰지 않습니다.

### 4.2 모듈 트리 (★ = 이번 추가)

```
hynix_nowcast/
├── data_loader.py
│   ├── fetch_regional_exports, fetch_fx_rates, load_actuals   (기존)
│   └── ★ load_consensus(filepath)
├── preprocess.py                                               (변경 없음)
├── forecaster.py
│   ├── estimate_revenue, detect_anomaly, compare_guidance      (기존)
│   ├── ★ implied_quarter_consensus(consensus_df, actuals_df, target_quarter, as_of)
│   ├── ★ compare_consensus(forecast, consensus)
│   └── ★ judge_price_impact(forecast, consensus, comparison)
├── llm_module.py                                               (변경 없음)
backend.py
│   └── run_forecast  → ★ 위 함수 연결, result에 consensus, comparison, price_impact, consensus_facts 추가
app.py
    └── B 구역 render_forecast → ★ _show_consensus_metrics, _show_price_impact
```

### 4.3 함수 목록

| 함수 | 책임 (한 문장) | 입력 | 출력 | 파일·네트워크 |
|---|---|---|---|---|
| `load_consensus` | 팀이 작성한 연간 컨센서스 CSV를 읽어 consensus 표로 돌려준다. | filepath: str | DataFrame: consensus 표. 필수 열이 없으면 ValueError, 파일이 없으면 FileNotFoundError | 파일 읽기 |
| `implied_quarter_consensus` | 예측 실행일까지 공개된 FY1 컨센서스에서 이미 발표된 실적을 빼고 대상 분기 몫을 환산한다. | consensus_df, actuals_df: DataFrame, target_quarter: str, as_of: str "YYYY-MM-DD" | dict: consensus 형식 | 없음 |
| `compare_consensus` | 우리 추정 매출과 분기 컨센서스의 괴리율, 위치(상회, 부합, 하회), 분포 안 위치를 판정한다. | forecast: dict, consensus: dict | dict: comparison 형식 | 없음 |
| `judge_price_impact` | 위치 판정과 리비전으로 주가 영향 방향을, 근거 충분도로 신뢰도 점수를 정한다. | forecast, consensus, comparison: dict | dict: price_impact 형식 | 없음 |

---

## 5. 데이터 계약

### 5.1 표: consensus (`data/consensus.csv`)

| 열: 타입 | 키 | 생성 → 사용 |
|---|---|---|
| as_of: str, fiscal_year: int, mean_krw, high_krw, low_krw, median_krw: float(원), source: str | as_of | 팀원이 FnGuide 엑셀로 작성 → load_consensus → implied_quarter_consensus |

### 5.2 dict: consensus (implied_quarter_consensus 결과)

| 키 | 타입 (허용값) | 설명 |
|---|---|---|
| status | "ok" / "no_consensus" / "not_ready" / "invalid" | no_consensus: 대상 연도의 컨센서스 행이 as_of 이전에 없음. not_ready: 직전 분기 실적이 as_of까지 발표되지 않았거나 YTD 실적 중 빠진 분기가 있음. invalid: R ≤ 0 |
| quarter | str "YYYYQn" | 대상 분기 |
| consensus_as_of | str 또는 None | 사용한 컨센서스 기준일 |
| fiscal_year | int | 대상 연도 |
| annual_mean_krw | float 또는 None | FY1 평균 |
| annual_high_krw, annual_low_krw | float 또는 None | FY1 최고, 최저 (구현에서 추가) |
| ytd_actual_krw | float 또는 None | 대상 연도에 발표된 분기 실적 합 |
| remaining_quarters | int (1~4) | k |
| method | "exact" / "allocated" / None | k = 1이면 exact |
| methods | dict {"even", "prior_share", "const_growth": float 또는 None} | k ≥ 2일 때 방법별 환산값. exact면 세 값 모두 R |
| center_krw | float 또는 None | 분기 컨센서스(환산 중심값) |
| band_low_krw, band_high_krw | float 또는 None | 환산 범위. exact면 둘 다 center |
| dist_low_krw, dist_high_krw | float 또는 None | 분포 카드용 최저~최고. exact: 연간 최저, 최고 − YTD. allocated: band와 같음 |
| revision_pct | float 또는 None | FY1 평균의 1개월 변화율(%). 기준일보다 30일 이상 앞선 날짜 중 가장 늦은 행과 비교, 없으면 None |
| days_since_consensus | int 또는 None | as_of − consensus_as_of (일) |
| days_after_announcement | int 또는 None | consensus_as_of − 직전 분기 실적 발표일 (일) |
| revision_base_krw, revision_base_as_of | float, str 또는 None | 리비전 비교에 쓴 30일 전 FY1 평균과 그 날짜 (구현에서 추가, 화면 문구용) |

status가 "ok"가 아니면 금액, 비율 키는 모두 None입니다.

### 5.3 dict: comparison (compare_consensus 결과)

| 키 | 타입 (허용값) | 설명 |
|---|---|---|
| status | "ok" / "unavailable" | forecast나 consensus의 status가 "ok"가 아니면 unavailable |
| surprise_pct | float 또는 None | (estimate_krw ÷ center_krw − 1) × 100 |
| position | "상회" / "부합" / "하회" / None | 6.2 규칙 |
| strength | "강" / "약" / None | 부합이면 None |
| dist_position_pct | float 또는 None | (estimate − dist_low) ÷ (dist_high − dist_low) × 100, 0~100으로 자름. dist_high = dist_low이면 None |

### 5.4 dict: price_impact (judge_price_impact 결과)

| 키 | 타입 (허용값) | 설명 |
|---|---|---|
| direction | "긍정" / "중립" / "부정" / "판단불가" | 6.3 규칙 |
| confidence | int (0~100) 또는 None | 6.4 규칙. 판단불가면 None |
| confidence_parts | dict {"months", "strength", "agreement", "freshness", "allocation_penalty": float} 또는 None | 신뢰도 구성 요소(화면 도움말과 테스트용) |
| reasons | list[str] | 코드가 만든 판단 근거 문장 (최대 3개). 예: "추정 128.4조가 분기 컨센서스 126.5조보다 1.5% 높아 부합 범위입니다." |

### 5.5 backend run_forecast 결과에 추가할 키

| 키 | 내용 |
|---|---|
| consensus, comparison, price_impact | 위 dict 3개. forecast status가 no_data면 계산은 하되 comparison과 price_impact는 unavailable, 판단불가 |
| consensus_facts | dict[str, str]: 화면 표시용 문자열 (8장). backend가 만들고 app.py는 그리기만 함 |

---

## 6. 판정 규칙과 상수

### 6.1 컨센서스 기준일 고르기 (미래 정보 금지)

1. 대상 연도 Y, 대상 분기 번호 t.
2. **직전 분기 실적 조건:** 직전 분기(t = 1이면 전년 4분기)의 announced_date가 as_of 이하여야 한다. 아니면 not_ready.
3. **YTD 조건:** Y년 1 ~ (t−1)분기 실적이 actuals에 모두 있어야 한다. 아니면 not_ready.
4. consensus 표에서 fiscal_year = Y이고 as_of(컨센서스) ≤ as_of(예측 실행일)인 행 중 가장 늦은 행을 쓴다. 없으면 no_consensus.

백테스트에서도 같은 규칙을 쓰면 그 시점에 공개된 컨센서스만 사용하게 됩니다.

### 6.2 위치 판정 (compare_consensus)

**대상이 4분기 (method = exact)**

| 순서 | 조건 | position, strength |
|---|---|---|
| 1 | forecast.lower_krw > center | 상회, 강 |
| 2 | forecast.upper_krw < center | 하회, 강 |
| 3 | surprise_pct ≥ +SURPRISE_BAND_PCT | 상회, 약 |
| 4 | surprise_pct ≤ −SURPRISE_BAND_PCT | 하회, 약 |
| 5 | 그 외 | 부합 |

**대상이 1~3분기 (method = allocated)**

| 순서 | 조건 | position, strength |
|---|---|---|
| 1 | forecast.lower_krw > band_high | 상회, 강 |
| 2 | forecast.upper_krw < band_low | 하회, 강 |
| 3 | estimate > band_high | 상회, 약 |
| 4 | estimate < band_low | 하회, 약 |
| 5 | 그 외 | 부합 |

### 6.3 주가 영향 방향 (judge_price_impact)

| 조건 | direction |
|---|---|
| comparison.status ≠ "ok" | 판단불가 |
| position = 상회 | 긍정 |
| position = 하회 | 부정 |
| 부합이고 revision_pct ≥ +REVISION_BAND_PCT | 긍정 |
| 부합이고 revision_pct ≤ −REVISION_BAND_PCT | 부정 |
| 부합이고 그 외 (revision_pct가 None인 경우 포함) | 중립 |

### 6.4 판단 신뢰도 (0~100, 정수로 반올림)

| 요소 | 최대 | 계산 |
|---|---|---|
| months 수출 반영 개월 | 40 | 40 × months_available ÷ 3 |
| strength 신호 강도 | 30 | 컨센서스(center)가 우리 범위 [lower, upper] 밖이면 30. 안이면 30 × min(\|surprise_pct\| ÷ half_width_pct, 1). half_width_pct = (upper − lower) ÷ 2 ÷ estimate × 100, 0이면 30 |
| agreement 컨센서스 합의도 | 15 | spread = (dist_high − dist_low) ÷ center × 100. spread ≤ 20이면 15, ≥ 60이면 0, 그 사이는 15 × (60 − spread) ÷ 40 |
| freshness 컨센서스 최신성 | 15 | days_after_announcement < 5이면 0 (발표 직후 애널리스트 수정 중). 아니면 days_since_consensus ≤ 7이면 15, ≤ 30이면 8, 그 외 0 |
| allocation_penalty 환산 감점 | − | 남은 분기 k = 1: 0, 2: 15, 3: 25, 4: 30 |

신뢰도 = 0~100으로 자른 (months + strength + agreement + freshness − allocation_penalty)

### 6.5 상수 (forecaster.py 상단, 백테스트로 조정)

| 상수 | 초기값 | 근거 |
|---|---|---|
| SURPRISE_BAND_PCT | 5.0 | 매출 서프라이즈의 통상 기준. 2025Q4 실제 서프라이즈 +6.0% |
| REVISION_BAND_PCT | 3.0 | 1개월 연간 컨센서스 변화의 의미 있는 크기 |
| REVISION_LOOKBACK_DAYS | 30 | 1개월 리비전 |
| FRESH_DAYS, STALE_DAYS | 7, 30 | 최신성 점수 구간 |
| POST_ANNOUNCEMENT_DAYS | 5 | 2026-10-28 발표 뒤 10-30까지 FY1이 341.6조 → 361.4조로 바뀜 |
| SPREAD_FULL_PCT, SPREAD_ZERO_PCT | 20, 60 | 합의도 점수 구간 |
| ALLOCATION_PENALTY | {1: 0, 2: 15, 3: 25, 4: 30} | 3.3의 환산 오차 크기 |

### 6.6 계산 예시 (2026Q4, 화면 시안의 숫자)

입력: 추정 128.4조 (범위 119.2~137.9조), 수출 2/3개월, 예측 실행일 2026-11-17, 컨센서스 기준일 2026-11-11

| 항목 | 계산 | 결과 |
|---|---|---|
| 분기 컨센서스 | 363.04 − (52.58 + 79.32 + 104.62) | 126.53조 (exact) |
| 분포 | 최저 337.59 − 236.51 ~ 최고 383.60 − 236.51 | 101.08 ~ 147.09조 |
| 괴리율 | 128.4 ÷ 126.53 − 1 | +1.5% → 부합 |
| 분포 안 위치 | (128.4 − 101.08) ÷ (147.09 − 101.08) | 59% |
| 리비전 | 363.04 ÷ 342.29(10-12) − 1 | +6.1% |
| 방향 | 부합, 리비전 ≥ +3% | **긍정** |
| 신뢰도 | months 26.7 + strength 30×1.48÷7.28=6.1 + agreement 15×(60−36.4)÷40=8.9 + freshness 15 − 0 | **57** |

---

## 7. Pseudocode

### 7.1 implied_quarter_consensus

```
함수 implied_quarter_consensus — 입력: consensus 표, actuals 표, 대상 분기, 예측 실행일 / 출력: consensus dict
    기본 dict를 만든다 (status="no_consensus", 금액·비율은 None)
    Y, t = 대상 분기의 연도와 분기 번호
    직전 분기 = t가 1이면 (Y−1)년 4분기, 아니면 Y년 (t−1)분기
    IF 직전 분기 실적이 없거나 그 announced_date > 예측 실행일
        RETURN status="not_ready"
    YTD 분기 = Y년 1 ~ (t−1)분기
    IF YTD 분기 중 actuals에 없는 분기가 있으면
        RETURN status="not_ready"
    후보 = consensus 표에서 fiscal_year = Y 이고 as_of ≤ 예측 실행일인 행
    IF 후보가 없으면
        RETURN status="no_consensus"
    행 = 후보 중 as_of가 가장 늦은 행
    ytd = YTD 분기 실적 합 (t=1이면 0)
    R = 행.mean_krw − ytd
    IF R ≤ 0
        RETURN status="invalid"
    k = 5 − t
    IF k = 1
        center = R, band = [R, R], dist = [행.low_krw − ytd, 행.high_krw − ytd], method="exact"
        methods = 세 방법 모두 R
    ELSE
        even = R ÷ k
        prior_share = 전년 4개 분기 실적이 모두 있으면 R × s_t ÷ (s_t + … + s_4), 아니면 None
        const_growth = 직전 분기 실적 B > 0 이면 B·(x+…+x^k) = R 인 x를 이분법으로 구해 B·x, 아니면 None
        값들 = None이 아닌 방법 값
        center = 값들의 중앙값, band = [최솟값, 최댓값], dist = band, method="allocated"
    이전 행 = 후보 중 as_of ≤ 행.as_of − 30일 인 행 중 가장 늦은 행
    revision_pct = 이전 행이 있으면 (행.mean_krw ÷ 이전 행.mean_krw − 1) × 100, 없으면 None
    days_since_consensus = 예측 실행일 − 행.as_of
    days_after_announcement = 행.as_of − 직전 분기 announced_date
    RETURN status="ok"와 위 값
```

### 7.2 compare_consensus

```
함수 compare_consensus — 입력: forecast dict, consensus dict / 출력: comparison dict
    IF forecast.status ≠ "ok" 또는 consensus.status ≠ "ok"
        RETURN status="unavailable", 나머지 None
    surprise = (forecast.estimate_krw ÷ consensus.center_krw − 1) × 100
    IF consensus.method = "exact"
        6.2 표(4분기)의 순서대로 position, strength를 정한다
    ELSE
        6.2 표(1~3분기)의 순서대로 position, strength를 정한다
    IF dist_high > dist_low
        dist_position = (estimate − dist_low) ÷ (dist_high − dist_low) × 100 을 0~100으로 자른다
    ELSE
        dist_position = None
    RETURN status="ok", surprise, position, strength, dist_position
```

### 7.3 judge_price_impact

```
함수 judge_price_impact — 입력: forecast, consensus, comparison dict / 출력: price_impact dict
    IF comparison.status ≠ "ok"
        RETURN direction="판단불가", confidence=None, reasons=[판단불가 사유 1문장]
    6.3 표로 direction을 정한다
    6.4 표로 months, strength, agreement, freshness, allocation_penalty를 계산한다
    confidence = round(clip(months + strength + agreement + freshness − allocation_penalty, 0, 100))
    reasons = [괴리율·위치 문장, 리비전 문장(값이 있을 때), 환산 근사 문장(allocated일 때)] 중 최대 3개
    RETURN direction, confidence, confidence_parts, reasons
```

---

## 8. 화면 구성 (카드와 값의 대응)

B 구역(`render_forecast`) 안에 보조 함수 두 개를 추가합니다. 실행 순서 블록은 바꾸지 않습니다. 모든 문자열은 backend의 `consensus_facts`가 만듭니다.

### 8.1 매출 전망 지표 (오른쪽 두 카드)

| 카드 | 큰 값 | 보조 문구 | 값 없을 때 |
|---|---|---|---|
| 시장 컨센서스 | center_krw (조 원). allocated면 "≈" 앞에 붙임 | exact: "연간 363.0조 − 1~3Q 실적 236.5조 · 기준일 11-11". allocated: "연간 컨센서스 환산(근사) · 범위 91.7~107.4조" | "—" + status 사유 (컨센서스 없음, 직전 분기 실적 미발표 등) |
| 예상 괴리율 | surprise_pct (±0.0%) | position과 strength (예: "부합", "상회(강)") | "—" |

### 8.2 주가 영향 판단 (카드 4개, 기존 시안의 '업종 펀더멘털 점수' 자리 대체)

| 카드 | 큰 값 | 보조 문구 |
|---|---|---|
| 컨센서스 분포 안 위치 | dist_position_pct (예: 59%) | exact: "애널리스트 최저 101.1조 ~ 최고 147.1조 중". allocated: "환산 범위 안 위치" |
| 컨센서스 추세 (1개월) | revision_pct (예: +6.1%) | "연간 컨센서스 342.3조 → 363.0조" |
| 주가 영향 방향 | direction (긍정, 중립, 부정, 판단불가) | reasons 첫 문장 |
| 판단 신뢰도 | confidence (예: 57점) | "근거 데이터 충분도 점수이며 주가 상승 확률이 아님". 도움말에 confidence_parts 표시 |

화면 맨 위의 DISCLAIMER는 그대로 둡니다.

---

## 9. 테스트 케이스 명세

**공통 입력 G (가상값, 단위 조 원):** 전년(2025) 실적 Q1 10, Q2 15, Q3 20, Q4 25 / 올해(2026) 실적 Q1 20, Q2 25, Q3 30. 발표일은 각 분기 다음 달 25일(예: 2026Q3 → 2026-10-25). consensus 행: 2026-11-10 fiscal_year 2026, 평균 105, 최고 115, 최저 95 / 2026-10-01 fiscal_year 2026, 평균 100. 금액 비교는 pytest.approx(rel=1e-6).

| ID | 대상 함수 | 범주 | 입력 | 기대 출력 / 동작 |
|---|---|---|---|---|
| C01 | load_consensus | 정상 | 7개 열 CSV 2행 | 2행, fiscal_year int, 금액 float |
| C02 | load_consensus | 예외 | mean_krw 열 없음 | ValueError("필수 열 누락: mean_krw") |
| C03 | implied_quarter_consensus | 정상 | G, 2026Q4, as_of 2026-11-17 | status ok, exact, center 30 (105 − 75), dist 20~40, band 30~30 |
| C04 | implied_quarter_consensus | 정상 | G, 2026Q3, as_of 2026-08-01, 컨센서스 행 as_of 2026-07-30 평균 105 | allocated, R 60, even 30, prior_share 26.6667, const_growth 28.1971, center 28.1971, band 26.6667~30 |
| C05 | implied_quarter_consensus | 경계 | C04에서 전년 실적 Q2 삭제 | prior_share None, center = (30 + 28.1971) ÷ 2 |
| C06 | implied_quarter_consensus | 미래 정보 | G, 2026Q4, as_of 2026-11-05 | 2026-11-10 행은 쓰지 않고 2026-10-01 행 사용 (center 25) |
| C07 | implied_quarter_consensus | 예외 경로 | G, 2026Q4, as_of 2026-10-20 (3분기 실적 발표 전) | status not_ready |
| C08 | implied_quarter_consensus | 예외 경로 | consensus에 fiscal_year 2026 행 없음 | status no_consensus |
| C09 | implied_quarter_consensus | 예외 경로 | 평균 70 (R = −5) | status invalid |
| C10 | implied_quarter_consensus | 정상 | C03 입력 | revision_pct = (105 ÷ 100 − 1) × 100 = 5.0 |
| C11 | compare_consensus | 정상 | center 30, 추정 33 (범위 31~35) | lower > center → 상회, 강, surprise +10% |
| C12 | compare_consensus | 경계 | center 30, 추정 31.5 (범위 29~34) | surprise 정확히 +5% → 상회, 약 (≥ 포함) |
| C13 | compare_consensus | 정상 | allocated band 26.67~30, 추정 29 (범위 27~31) | 부합, strength None |
| C14 | compare_consensus | 예외 경로 | forecast status no_data | status unavailable |
| C15 | judge_price_impact | 경계 | 부합, revision_pct 3.0 | 긍정 (≥ 포함) |
| C16 | judge_price_impact | 정상 | 6.6 예시 값 | 긍정, confidence 57 |
| C17 | judge_price_impact | 정상 | days_after_announcement 2 | freshness 0 |
| C18 | judge_price_impact | 예외 경로 | comparison unavailable | 판단불가, confidence None |
| C19 | 세 함수 | 불변 | 입력 DataFrame, dict | 호출 뒤 입력이 바뀌지 않음 |

C04 계산 확인: 2026Q3 대상 YTD = 20 + 25 = 45, R = 105 − 45 = 60, k = 2. 전년 비중 s3 = 20/70, s4 = 25/70 → 60 × 20 ÷ 45 = 26.6667. 일정 성장 25(x + x²) = 60 → x = 1.12788 → 28.1971.

---

## 10. 구현 규칙, 한계, 남은 결정

### 10.1 구현 규칙

- 새 forecaster 함수 세 개는 파일과 네트워크 없이 값만 받아 RETURN한다(기존 규칙과 같음).
- 파일 읽기는 load_consensus와 backend만 한다. consensus.csv가 없으면 오류로 멈추지 않고 consensus status를 no_consensus로 둔다(컨콜 파일과 같은 선택 데이터).
- app.py는 pandas를 쓰지 않고 consensus_facts의 문자열만 그린다. 위젯과 session_state 키는 B 구역 접두어 `forecast_`를 쓴다.
- 예측 이력(forecasts.csv)에 컨센서스 값을 저장할지는 이번 범위에서 제외한다 **[팀 확인]**.
- 브리프(LLM)에는 이번에 넣지 않는다. 넣으려면 brief_generation.txt의 투자 권유 금지 문구를 먼저 다시 정해야 한다.

### 10.2 한계

- 1~3분기 컨센서스는 연간 값을 나눈 근사값이다(오차 10~20%). 그래서 범위로 판정하고 신뢰도를 깎는다.
- 매출만 비교한다. 실제 주가 반응은 영업이익, 가이던스, 시장 전체 흐름의 영향도 크게 받는다.
- 4분기 정확 비교로 검증할 수 있는 과거 표본은 2024Q4, 2025Q4 두 개뿐이다.
- 컨센서스는 수기 갱신이라 최신성이 팀의 입력 주기에 달려 있다(신뢰도의 freshness가 이를 반영).

### 10.3 분기 컨센서스를 받게 되면

FnGuide에서 분기 집계주기(FQ) 데이터를 받으면 consensus.csv에 `fiscal_quarter` 열을 추가하고, implied_quarter_consensus 안에서 환산 대신 해당 분기 값을 바로 쓴다(method = "exact"). 다른 함수와 화면은 바꾸지 않는다.

### 10.4 남은 결정 [팀 확인]

1. 설계서 V1 범위 '제외 1번' 문구 수정
2. 상수 초기값(6.5) 확정
3. consensus.csv 변환을 수기로 할지, 변환 스크립트를 만들지
4. 예측 이력에 컨센서스와 판단 결과를 함께 저장할지
5. 화면의 '수출 증가율(직전 분기 대비)' 카드는 별도 작업으로 진행할지

---

## 11. 구현하면서 바뀐 점 (2026-11-17)

| 항목 | 설계 | 구현 |
|---|---|---|
| FY1 전환일 | 2025년 전환일을 2025-01-24로 적음 | 엑셀을 다시 확인해 **2025-01-23**으로 바로잡음(actuals.csv의 2024Q4 발표일과 같음) |
| consensus.csv 작성 | 수기 변환 | 첫 파일은 2.3 절차를 그대로 따르는 일회성 변환으로 만듦(2024-01-25~2026-11-11, 679행). 이후 갱신은 수기 |
| consensus dict | 5.2 표 | `annual_high_krw`, `annual_low_krw`, `revision_base_krw`, `revision_base_as_of` 추가 |
| 형식 오류 | – | `load_consensus`의 ValueError: "필수 열 누락: …", "consensus.csv 형식 오류: …"(최대 5건 표시), "consensus.csv 날짜 중복: …", "consensus.csv 인코딩 오류: …" |
| 표시 문자열 | `consensus_facts` | `backend.consensus_facts()`가 만드는 키 13개: consensus_value/note, surprise_value/note, dist_value/note, revision_value/note, direction_value/note, confidence_value/note/help. 값이 없으면 "—" |
| 화면 | 8장 | B 구역 `_show_consensus_metrics`, `_show_price_impact`. 지표 4개 아래에 '시장 컨센서스 비교' 2개, '주가 영향 판단' 4개 카드 |
| 테스트 | C01~C19 | `alt_backend_week11/tests/test_consensus.py` 27건 (C01~C19 + 형식 오류, 하회(강), 1분기 환산, 환산 감점, 팀 consensus.csv 검사, backend 연결 2건) |
