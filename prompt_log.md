# 알트(ALT) 팀 AI 활용 과정 기록

- 사이클(함수 하나) 1회전마다 항목 1개를 추가한다.
- 병합 충돌을 줄이기 위해 **자기 이름 섹션 안에만** 작성한다.
- 프롬프트에 실명, 전화번호 같은 개인정보, 실데이터, API 키를 넣지 않는다.
- 시그니처를 바꿨다면 그 사유를 항목에 함께 적는다.

<!--
항목 양식 (복사해서 사용)

### [모듈] 함수명 (YYYY-MM-DD, 작성자: 이름)
- 사용 도구:
- 프롬프트: (원문 전체를 그대로 붙여넣기)
- 생성 코드 위치: 커밋 (수정 전 원본 해시)
- 코드 리딩에서 발견한 결함:
  1)
  2)
- 수정 내역: 커밋 (수정 커밋 해시)
- 테스트 결과: pytest N passed
- 비고: (시그니처 변경 사유, 명세에서 새로 정한 규칙 등)
-->

---

## 강민규

[forecaster.py] detect_anomaly (2026-11-01, 작성자: 강민규)
- 사용 도구: GitHub Copilot Chat, Claude
- 프롬프트:  
    당신은 파이썬 데이터 분석 코드 작성을 돕는 어시스턴트입니다.
    SK하이닉스 분기 매출 나우캐스팅 시스템의 분석 모듈(forecaster.py, 숫자 계산 전담)에 들어갈 함수를 구현해 주세요.
    이 함수는 대상 월 수출의 전년 동월 대비 증가율이 직전 12개월의 평소 범위를 벗어났는지 판정합니다.
    
    [함수 시그니처, 변경 금지]
    def detect_anomaly(exports_df: pd.DataFrame, target_ym: str, threshold: float = 2.0) -> dict:
    
    [입력 명세]
    exports_df: 월별 지역 수출 표 (한 달은 이천시, 청주시 2행)
    ym: str "YYYY-MM" / region: str "이천시" 또는 "청주시" / hs_code: str "854232"
    export_usd: float (달러, 0 이상) / collected_at: str "YYYY-MM-DD"
    예) {"ym": "2026-09", "region": "이천시", "hs_code": "854232", "export_usd": 5.0e9, "collected_at": "2026-10-15"}
    target_ym: 판정할 월 "YYYY-MM" (예: "2026-09")
    threshold: |z| 기준값 (기본 2.0)
    
    [출력 명세]
    키가 정확히 5개인 dict
    {"ym": target_ym 그대로(str), "yoy_pct": float 또는 None, "z_score": float 또는 None,
    "is_anomaly": bool, "reason": "정상", "급증", "급감", "데이터 부족" 중 하나}
    예) {"ym": "2026-09", "yoy_pct": 25.0, "z_score": 1.0, "is_anomaly": False, "reason": "정상"}
    계산 정의
    - 월 합계 = 같은 ym의 이천시 export_usd + 청주시 export_usd
    - 전년동월비(m) = (월 합계[m] / 월 합계[m의 12개월 전] - 1) * 100, yoy_pct = 전년동월비(target_ym)
    - z = (yoy_pct - 직전 12개월 전년동월비의 평균) / 직전 12개월 전년동월비의 표본 표준편차(n - 1로 나눔)
    - |z| > threshold 이면 is_anomaly True, z가 양수면 "급증", 음수면 "급감". 그 외는 False, "정상"
    
    [예외, 경계 방침] 어떤 경우에도 예외를 발생시키지 않는다
    기본값 = {"ym": target_ym, "yoy_pct": None, "z_score": None, "is_anomaly": False, "reason": "데이터 부족"}
    - target_ym이 "YYYY-MM"(월 01~12) 형식이 아니면 기본값 반환
    - 빈 표이거나 ym, region, export_usd 열이 없으면 기본값 반환
    - 두 지역 중 하나만 있는 달은 월 합계가 없는 달로 본다
    - 대상 월과 그 앞 24개월(모두 25개월) 중 하나라도 월 합계가 없으면 기본값 반환 (행 개수가 아니라 달 기준으로 확인)
    - 전년동월비 13개(대상 월과 직전 12개월)를 구할 때 12개월 전 합계가 0인 달이 있으면 기본값 반환 (0으로 나누지 않음)
    - 표준편차가 STD_EPSILON 미만이면 0으로 보고, yoy_pct만 채운 기본값 반환
    (pandas std()는 같은 값만 있어도 0이 아니라 1e-15 수준을 돌려준다)
    - |z|가 threshold와 정확히 같으면 "정상" (초과일 때만 이상치)
    
    [제약 조건]
    - Python 3.10 이상, 표준 라이브러리와 pandas만 사용 (numpy 등 다른 라이브러리 import 금지)
    - 시그니처를 바꾸지 않는다. 공개 함수를 새로 만들지 않고, 보조 함수는 밑줄로 시작하는 내부 함수로 만든다 (예: _shift_ym)
    - 타입 힌트와 한국어 docstring(설명, Args, Returns, Raises) 필수. Raises는 "없음"으로 적는다
    - 입력 DataFrame을 직접 수정하지 않고 복사본에서 작업한다. 행 순서에 의존하지 않는다
    - 파일 읽기/쓰기, 네트워크, print, 프로젝트의 다른 모듈 import 금지. 값을 받아 RETURN만 한다
    - 반환값은 파이썬 기본 타입(float, bool, None)으로 돌려준다. numpy.float64, numpy.bool_ 금지
    - 계산 결과를 반올림하지 않는다. 값이 없으면 0이 아니라 None. 빠진 달을 0으로 채우지 않는다
    - 파일 맨 위 상수: ALLOWED_REGIONS = ("이천시", "청주시"), STD_EPSILON = 1e-9 (threshold 기본값 2.0은 시그니처 그대로 둔다)
    
    [통과해야 할 테스트, test_detect_anomaly.py, 테스트를 고쳐서 통과시키지 말 것]
    공통 입력 A: 매달 이천시 62.5% + 청주시 37.5% 두 행 (단위 1억 달러)
    2024-09\~2025-08 매달 64 / 2025-09\~2026-08: 64, 88, 40, 80, 48, 88, 40, 64, 64, 64, 64, 64
    직전 12개월 전년동월비 평균 0, 표본 표준편차 25
    - 정상 1: 대상 월 2026-09 합계 80 -> yoy_pct 25.0, z_score 1.0, is_anomaly False, reason "정상"
    - 정상 2: 합계 128 -> yoy_pct 100.0, z_score 4.0, is_anomaly True, reason "급증"
    - 경계 1: 2024-09가 없어 24개월 -> 기본값
    - 경계 2: 기준 해 100, 직전 12개월 110, 대상 월 121 -> yoy_pct 10.0, z_score None, reason "데이터 부족"
    - 예외 1: target_ym "2026-13" -> 예외 없이 기본값
    - 예외 2: 2025-03 합계 0 -> 예외 없이 기본값


- 생성 코드 위치: 066dbbb79bd7979ddd4eb9eb826a28311c7fb708  
- 코드 리딩에서 발견한 결함:  
  1) 한 지역만 있는 달도 월 합계에 들어감. 처음 보는 달에 두 지역을 0.0으로 미리 넣어 두 지역 확인 검사가 항상 통과함. 2025-09 청주시 자료가 빠지면 실제 0%인 달을 +60% "급증"으로 오경보 (프롬프트 31줄 위반)
  2) threshold를 float로 바꾸고 무한대면 "데이터 부족"을 돌려줌. 프롬프트는 판정을 |z| > threshold로만 정의하고, 기본값을 돌려줄 경우에 threshold는 없음 (프롬프트 25, 28~36줄 위반)
  3) 보조 함수 _is_valid_ym, _shift_ym에 docstring 없음 (프롬프트 41줄 위반)
  4) 함수 전체를 try/except로 감싸 코드 오류까지 "데이터 부족"으로 바꿈 (리딩 체크리스트 4번: 광범위한 except).  

- 수정 내역: 6c4c7eef6688f76693ec2e9aefce23a38acf85d0

| 번호 | 원본 줄 | 원래 코드 | 수정 | 근거와 이유 |  
|---|---|---|---|---|  
| 1 | 91~94 | `setdefault(ym, {"이천시": 0.0, "청주시": 0.0})[region] += amount` | `setdefault(ym, {})`로 빈 dict를 두고, 실제로 들어온 지역만 `regions.get(region, 0.0) + amount`로 더함 | 프롬프트 31줄 "두 지역 중 하나만 있는 달은 월 합계가 없는 달로 본다" 위반. 처음 보는 달에 두 지역을 0.0으로 미리 넣어서 원본 99줄의 `all(...)` 검사가 항상 True가 됨. 프롬프트의 공통 입력 A에서 2025-09 청주시 자료가 빠지면 실제 0%인 달을 +60% 급증으로 오경보 |
| 2 | 60~62, 134 | `threshold_value = float(threshold)`, `if not math.isfinite(threshold_value): return default` | 세 줄 삭제, 134줄에서 `threshold`를 그대로 비교 | threshold가 비정상일 때 "데이터 부족"을 돌려줘 원인(기준값 문제)과 결과(자료 부족)가 맞지 않고, 프롬프트 25줄의 판정 정의(무한대면 "정상")와도 다름. 또한 프롬프트에도 없었던 내용이라 삭제함 |
| 3 | 11, 22 | 보조 함수 `_is_valid_ym`, `_shift_ym`에 docstring 없음 | 두 함수에 설명, Args, Returns, Raises docstring 추가 | 프롬프트 41줄 "타입 힌트와 한국어 docstring(설명, Args, Returns, Raises) 필수" 위반 |
| 4 | 56, 150~151 (함께 16, 17줄) | 함수 본문 전체를 `try`로 감싸고 `except (AttributeError, KeyError, TypeError, ValueError, OverflowError): return default` | try/except를 지우고 본문 들여쓰기를 한 단계 줄임. “try가 없어도 형식 검사가 예외를 내지 않도록 `isdigit()`을 `isdecimal()`로 보완 | 리딩 체크리스트 4번 "광범위한 except"에 해당. 코드 실수로 난 KeyError, TypeError도 "데이터 부족"으로 바뀌어 자료가 정말 부족한 경우와 구별할 수 없음. 프롬프트 27줄을 따른 결과이므로 프롬프트도 고칠 대상(비고) |

- 테스트 결과: pytest 6 passed
- 비고:  
  1) 결함 4는 프롬프트 27줄 "어떤 경우에도 예외를 발생시키지 않는다"를 Copilot이 그대로 따른 결과다. 그러나 리딩 체크리스트 4번(광범위한 except)에 해당하고 코드 오류가 "데이터 부족"으로 가려질 수 있어 수정했다. 원인은 프롬프트 문구에 있으므로 다음 사이클에서는 27줄을 "자료 문제(형식 오류, 빈 표, 빠진 달, 0 나누기, 표준편차 0)로는 예외를 내지 않고 기본값을 반환한다. 함수 전체를 try/except로 감싸지 않는다"로 고친다.
  2) 수정 4 이후 숫자가 아닌 threshold처럼 호출하는 쪽이 잘못한 경우에는 TypeError가 난다. 의도한 동작이며 docstring Raises에 적었다.  

[data_loader] fetch_fx_rates (2026-11-07, 작성자: 강민규)
- 사용 도구: GitHub Copilot Chat, Claude  
- 프롬프트:  
  당신은 파이썬 백엔드 개발을 돕는 어시스턴트입니다.
  SK하이닉스 분기 매출 나우캐스팅 시스템의 적재 모듈(data_loader.py, 외부 데이터 수집 전담)에 들어갈 함수 fetch_fx_rates 하나만 구현해 주세요.
  이 함수는 한국은행 ECOS Open API에서 원/달러 매매기준율 일별 값을 받아 fx 표 형식으로 돌려줍니다.
  돌려준 표는 upsert_records(키 ["date"])로 저장 표에 합쳐진 뒤, aggregate_quarterly에서 분기 평균 환율(fx_avg)로 쓰입니다.
  #file:test_fetch_fx_rates.py 의 테스트를 모두 통과해야 합니다. 테스트 파일은 수정하지 마세요.

  [함수 시그니처, 변경 금지]
  import pandas as pd

  def fetch_fx_rates(start_date: str, end_date: str) -> pd.DataFrame:

  [입력 명세]
  start_date, end_date: 조회 기간의 시작일과 끝일, "YYYY-MM-DD" 문자열 (예: "2021-01-01", "2026-11-07")
  - 네 자리 연도, 두 자리 월, 두 자리 일이고 달력에 있는 날짜여야 하며 start_date <= end_date
  API 키: 환경변수 ECOS_API_KEY (.env 파일에 저장, python-dotenv로 읽음)

  [ECOS API 명세]
  요청: GET, 인증키가 URL 경로 안에 들어간다
    {ECOS_BASE_URL}/{API 키}/json/kr/{시작 번호}/{끝 번호}/{ECOS_STAT_CODE}/{ECOS_CYCLE}/{시작일 YYYYMMDD}/{끝일 YYYYMMDD}/{ECOS_ITEM_CODE}
    예) https://ecos.bok.or.kr/api/StatisticSearch/<키>/json/kr/1/1000/731Y001/D/20260101/20260131/0000001
  나눠 받기: 시작 번호, 끝 번호는 1부터 세는 행 번호다. 한 번에 ECOS_PAGE_SIZE행씩 요청한다
    (1~ECOS_PAGE_SIZE, 그다음 ECOS_PAGE_SIZE+1~ECOS_PAGE_SIZE*2, ...).
    이번 요청의 row가 0개이거나, 지금까지 모은 행 수가 list_total_count 이상이면 그만 요청한다.
  성공 응답 (HTTP 200):
    {"StatisticSearch": {"list_total_count": 5, "row": [{"TIME": "20260102", "DATA_VALUE": "1445.0", ...그 밖의 키}, ...]}}
    list_total_count = 기간 전체 행 수, row = 이번 요청 범위의 행. row에서는 TIME과 DATA_VALUE만 쓴다.
  결과 코드 응답 (HTTP 200이어도 올 수 있음):
    {"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}}
    INFO-200만 "데이터 없음"이다. 그 밖의 코드(예: INFO-100 인증키 오류, ERROR-602 호출 제한)는 INFO로 시작해도 모두 실패다.

  [출력 명세]
  fx 표(DataFrame), 열은 정확히 2개, 이 순서: date, usdkrw
  - date: "YYYY-MM-DD" 문자열 (datetime, Timestamp로 돌려주지 않음)
  - usdkrw: float (1달러당 원, 0 초과)
  - date 오름차순, date 중복 없음, 행 번호 0부터
  - 0행이어도 열 2개짜리 빈 표를 돌려준다
  예) date="2026-01-02", usdkrw=1445.0
  변환 규칙
  - date = TIME("YYYYMMDD")을 "YYYY-MM-DD" 문자열로 바꾼 값. 달력에 없는 날짜면 결측
  - usdkrw = DATA_VALUE를 숫자로 바꾼 값. 빈 값, "-", null처럼 바꿀 수 없으면 결측
  - date나 usdkrw가 결측이거나 usdkrw가 0 이하인 행은 제거한다
  - 같은 date가 여러 번 오면 응답에서 나중에 나온 행만 남긴다
  - 값이 없는 날(주말, 공휴일)을 앞 값이나 0으로 채우지 않는다. 분기 평균은 값이 있는 날만으로 계산한다

  [예외, 경계 방침]
  검사 순서: 날짜 인자 -> API 키 -> ECOS 요청. 앞 단계에서 실패하면 ECOS를 부르지 않는다.
  - 날짜 인자가 "YYYY-MM-DD" 형식의 실제 날짜가 아니면 ValueError("날짜 형식 오류: <값>")
  - start_date > end_date이면 ValueError("시작일이 끝일보다 늦습니다: <start_date> > <end_date>")
  - ECOS_API_KEY가 없거나 공백뿐이면 RuntimeError("ECOS API 키가 없습니다")
  - 연결 오류, 시간 초과, HTTP 오류(4xx, 5xx)는 RuntimeError("ECOS API 호출 실패: <원인>")
    <원인>은 연결 오류와 시간 초과면 예외 클래스 이름(예: ConnectionError, Timeout), HTTP 오류면 "HTTP <상태 코드>"(예: HTTP 500)
  - 응답이 JSON이 아니거나, StatisticSearch, list_total_count, row 중 하나라도 없으면 RuntimeError("ECOS API 호출 실패: 응답 형식 오류")
  - RESULT 응답의 CODE가 INFO-200이면 예외 없이 요청을 멈추고 그때까지 모은 행으로 진행한다 (첫 요청이면 빈 표)
  - RESULT 응답의 CODE가 INFO-200이 아니면 RuntimeError("ECOS API 호출 실패: \<CODE> \<MESSAGE>")
  - 키 보호: requests 예외 문자열(str(e))에는 키가 들어간 요청 URL이 그대로 담긴다. 그래서
    1) 오류 메시지에 URL, 키, str(e)를 넣지 않는다
    2) RuntimeError는 raise ... from None으로 발생시켜 원래 예외가 traceback에 함께 찍히지 않게 한다
  - try/except는 requests.get과 raise_for_status() 호출, json() 해석 부분에만 짧게 둔다. 함수 전체를 try/except로 감싸지 않는다.
    except:, except Exception: 금지. 잡는 예외는 requests.RequestException(연결 오류, 시간 초과, HTTP 오류 포함)과 json()의 ValueError뿐이다
  - 재시도하지 않는다. 실패하면 이 함수를 부른 main이 경고를 띄우고 저장된 데이터로 진행한다

  [제약 조건, 프로젝트 공통]
  - Python 3.10 이상. 표준 라이브러리, pandas, requests, python-dotenv만 사용 (numpy 등 다른 라이브러리 import 금지)
  - 시그니처를 바꾸지 않는다. 공개 함수를 새로 만들지 않고, 보조 함수는 밑줄로 시작하는 내부 함수로 만든다 (예: _parse_date, _request_page, _empty_fx)
  - 모든 함수(보조 함수 포함)에 타입 힌트와 한국어 docstring(설명, Args, Returns, Raises) 필수
  - 가변 기본값 인자 금지. 전역 변수를 바꾸지 않는다 (파일 맨 위 대문자 상수는 읽기 전용)
  - print, 파일 읽기/쓰기, 프로젝트의 다른 모듈 import 금지. 값을 받아 RETURN만 한다
  - API 키를 코드에 쓰지 않고 환경변수에서만 읽는다
  - 오류 메시지는 한국어로, 무엇이 문제인지 담는다

  [제약 조건, 함수별: fetch_fx_rates]
  - 자료구조: 반환 열은 정확히 date, usdkrw 2개. date는 문자열, usdkrw는 float. 빈 표도 이 2개 열
  - 처리 방식: import requests 후 requests.get(url, timeout=REQUEST_TIMEOUT_SEC)로 호출한다.
    from requests import get, requests.Session은 쓰지 않는다 (테스트가 requests.get을 바꿔 끼운다).
    응답 객체에서는 status_code, raise_for_status(), json()만 쓴다
  - 처리 방식: load_dotenv()는 파일 맨 위에서 한 번만 호출하고, 함수 안에서는 os.getenv("ECOS_API_KEY")로만 읽는다
    (함수 안에서 load_dotenv를 부르면 테스트에서 지운 키가 .env에서 다시 살아난다)
  - 처리 방식: 상수는 함수 안에서 이름으로 읽는다. 기본값 인자로 묶지 않는다 (테스트가 ECOS_PAGE_SIZE를 바꿔 끼운다)
  - 처리 방식: 날짜 인자 검사는 strptime만으로 하지 않는다 (strptime은 "2026-1-01"도 통과시킨다). 자리 수까지 확인한다
  - 하지 말 것: 월/분기 평균을 내지 않는다 (aggregate_quarterly의 역할). 저장 표와 합치지 않는다 (upsert_records의 역할)
  - 변경 대비: 파일 맨 위 상수로 둔다
    ECOS_BASE_URL = "https://ecos.bok.or.kr/api/StatisticSearch"
    ECOS_STAT_CODE = "731Y001"      # 주요국 통화의 대원화환율
    ECOS_ITEM_CODE = "0000001"      # 원/미국달러(매매기준율)
    ECOS_CYCLE = "D"                # 일별
    ECOS_PAGE_SIZE = 1000
    ECOS_NO_DATA_CODE = "INFO-200"
    REQUEST_TIMEOUT_SEC = 10
    FX_COLUMNS = ("date", "usdkrw")

  [통과해야 할 테스트, test_fetch_fx_rates.py, 테스트를 고쳐서 통과시키지 말 것]
  실제 API를 부르지 않는다. requests.get을 가짜 함수로, ECOS_API_KEY를 가짜 키로 바꿔 끼운다. 환율 값은 가상의 더미 값이다.
  - 정상 1: 날짜 역순 3행 (20260106 "1452.25", 20260102 "1445.0", 20260105 "1450.5")
    -> date ["2026-01-02", "2026-01-05", "2026-01-06"], usdkrw [1445.0, 1450.5, 1452.25], 행 번호 0~2
    -> 요청 1번, URL에 "/StatisticSearch/<키>/json/kr/1/"이 있고 끝이 "/731Y001/D/20260101/20260131/0000001", timeout 있음
  - 정상 2: ECOS_PAGE_SIZE를 2로 바꾸고 전체 5행 -> 요청 범위 1~2, 3~4, 5~6으로 3번 요청해 5행 모두 반환
  - 경계 1: 값이 빈 값, "-", null, "0", "-3.5"인 행과 날짜가 20260230인 행은 제거.
    20260109가 1451.0, 1452.5 순서로 두 번 오면 1452.5만 남김 -> date ["2026-01-02", "2026-01-09"], usdkrw [1445.0, 1452.5]
  - 경계 2: INFO-200 응답 -> 예외 없이 열 2개(date, usdkrw) 0행
  - 예외 1: ECOS_API_KEY가 없거나 "   "이면 RuntimeError("ECOS API 키가 없습니다"), requests.get 호출 0번
  - 예외 2: 연결 오류, 시간 초과, HTTP 500 -> "ECOS API 호출 실패"로 시작하는 RuntimeError (HTTP 500이면 메시지에 500 포함).
    오류 메시지와 traceback 어디에도 키가 나오지 않음
  - 예외 3: INFO-100, ERROR-602 응답 -> 메시지에 그 코드가 든 RuntimeError.
    StatisticSearch도 RESULT도 없는 응답, JSON이 아닌 응답 -> 메시지에 "응답 형식"이 든 RuntimeError
  - 예외 4: "2026-13-01", "2026-02-30", "2026/01/01", "20260101", "2026-1-01", 시작일이 끝일보다 뒤 -> ValueError, requests.get 호출 0번

- 생성 코드 위치: c800da7c3f1421e6dda17f3f2fc681a0d339e313  
- 코드 리딩에서 발견한 결함:  
  1) 날짜 인자가 ASCII 숫자인지 확인하지 않음. 원본 35~41줄은 길이 10과 5, 8번째 글자의 "-"만 보고 나머지는 43~50줄 `pd.to_datetime`에 맡기는데, `pd.to_datetime`은 전각 숫자("２０２６")도 날짜로 읽는다. 그래서 끝일 "２０２６-01-31"이 형식 검사를 통과해 전각 숫자가 든 URL로 ECOS에 요청이 나간다. 사람이 고쳐야 하는 입력 문제인데 ValueError가 나지 않는다. 시작일이 전각이면 52줄 문자열 비교가 어긋나 "시작일이 끝일보다 늦습니다"라는 엉뚱한 메시지가 나온다 (프롬프트 14줄 "네 자리 연도, 두 자리 월, 두 자리 일", 47줄, 79줄 "자리 수까지 확인한다" 위반 / 리딩 체크리스트 2번 경계 추적, 3번 예외 방침 대조)
  2) INFO-200일 때 돌려주는 빈 표의 열 타입이 명세와 다름. 원본 128줄 `pd.DataFrame(columns=FX_COLUMNS)`는 열 이름만 있어 date, usdkrw가 모두 object다. 값이 모두 무효라 빈 표가 되는 경우(148~153줄)는 usdkrw가 float64라서, 같은 빈 표인데 경로마다 타입이 다르다. 이 빈 표를 저장 표와 이어 붙이면(upsert_records의 concat) pandas 3.0.5에서는 usdkrw 열 전체가 object로 바뀌고, pandas 2.2.3에서는 FutureWarning(곧 동작이 바뀐다는 경고)이 난다. 테스트 경계 2는 열 이름과 행 수만 확인해서 통과했다 (프롬프트 34줄 "usdkrw: float", 36줄, 72줄 "usdkrw는 float. 빈 표도 이 2개 열" 위반 / 리딩 체크리스트 1번 반환 형식 대조, 2번 경계 추적)
  3) list_total_count가 int일 때만 정상으로 보는 명세 밖 검사. 원본 112~118줄은 list_total_count가 int가 아니면 "응답 형식 오류"로 실패시킨다. 프롬프트는 이 키가 있는지만 요구하는데(52줄), 실제 응답에서 이 값이 숫자 문자열("1234")로 오면 정상 응답인데도 모든 호출이 RuntimeError가 된다. 키가 있어도 환율을 하나도 못 받는 상황이라 리팩터링으로 미룰 수 없는 동작 결함으로 판단했다 (프롬프트 26줄, 52줄과 불일치 / 리딩 체크리스트 1번 명세 대조, 2번 경계 추적)

- 수정 내역: 수정 1, 2 커밋 79dc0872523cbfdd4ca59f9ad93883caf093ccd5    수정 3 커밋 48a854030b839691392077ce6949234cb9b66cd8

| 번호 | 원본 줄 | 원래 코드 | 수정 | 근거와 이유 |
|---|---|---|---|---|
| 1 | 35~41 (관련 43~52) | 형식 검사가 `len(value) != 10`, `value[4] != "-"`, `value[7] != "-"`뿐 | 조건에 `or not value.isascii()` 한 줄 추가 | 프롬프트 14줄, 47줄, 79줄 위반. `pd.to_datetime(format="%Y-%m-%d")`가 전각 숫자를 날짜로 읽어, 시작일 "2026-01-01"과 끝일 "２０２６-01-31"을 넣으면 그대로 ECOS 요청까지 감. 수정 후 두 경우 모두 `ValueError("날짜 형식 오류: ...")`. 실제 호출하는 main은 ASCII 날짜만 넘기지만, 명세가 정한 입력 계약을 코드가 지키지 않으므로 수정 |
| 2 | 127~128 | `return pd.DataFrame(columns=FX_COLUMNS)` | `return pd.DataFrame({"date": pd.Series(dtype=str), "usdkrw": pd.Series(dtype=float)})` | 프롬프트 34줄, 36줄, 72줄 위반. 열 이름만 준 빈 표는 usdkrw가 object. 정상 표(float64)와 이어 붙이면 pandas 3.0.5에서 usdkrw가 object로 바뀌어 aggregate_quarterly의 분기 평균 계산에 영향. 수정 후 빈 표 타입이 정상 표와 같아지고(pandas 3: str/float64, pandas 2: object/float64), 이어 붙여도 float64 유지, 경고 없음 |
| 3 | 112~118 | `not isinstance(total_count, int)`, `isinstance(total_count, bool)`, `total_count < 0`이면 응답 형식 오류 | `not str(total_count).isdecimal()`이면 응답 형식 오류, 통과하면 `total_count = int(total_count)` | 프롬프트 26줄, 52줄과 불일치. 명세에 없는 타입 제한이라 숫자 문자열 "1"도 실패했음. 수정 후 1과 "1"은 정상, True, -1, "abc", 1.5, "-1"은 그대로 응답 형식 오류. try/except를 새로 두지 않으려고(프롬프트의 try 범위 제한) 먼저 숫자 표기인지 확인한 뒤 int로 바꿈 |

- 테스트 결과: pytest 19 passed  
- 비고:  
  1) 수정 3을 따로 커밋한 이유와 프롬프트와의 관계
     - 코드 리딩 당시에는 실제 키로 응답 타입을 확인한 뒤 판단하려고 보류했으나, 명세 밖 동작이고 정상 응답까지 실패시킬 수 있으므로 키 확인을 기다리지 않고 고치는 것이 맞다고 판단해 수정 1, 2 커밋 뒤에 별도 fix 커밋으로 반영했다.
     - 프롬프트 52줄은 list_total_count가 "있는지"만 요구하고 값의 타입은 정하지 않았다. int만 받도록 제한한 것은 생성 코드가 임의로 더한 동작이다.
     - 실제 응답 타입을 아직 확인하지 못했으므로 숫자(1234)와 숫자 문자열("1234") 모두 받도록 했다. 그 밖의 값(True, 음수, 소수, 문자)은 명세대로 "응답 형식 오류" RuntimeError로 알린다. int()로 바꾸기 전에 숫자 표기인지 먼저 확인하므로 TypeError, ValueError 같은 예상 밖 예외는 나지 않는다.
     - try/except로 감싸지 않은 이유: 프롬프트 58줄 "try/except는 requests.get과 raise_for_status() 호출, json() 해석 부분에만 짧게 둔다"를 지키기 위해서다. detect_anomaly 사이클에서 넓은 try/except가 코드 오류를 "데이터 부족"으로 가렸던 것과 같은 일을 막으려는 규칙이라, 검사를 먼저 하고 변환하는 방식으로 같은 결과를 냈다.
     - 동작이 바뀌는 수정이므로 refactor:가 아니라 fix:로 커밋했다.

---

## 신동훈

[forecaster.py] estimate_revenue — 2026-11-02, 작성자: 신동훈

- 사용 도구: GitHub Copilot Chat 
- 프롬프트:
```
당신은 파이썬 백엔드 개발을 돕는 어시스턴트입니다.
SK하이닉스 분기 매출 나우캐스팅 시스템의 분석 모듈 forecaster.py에 들어갈
함수 estimate_revenue를 구현해 주세요. 이 함수는 대상 분기 수출에 과거 4개 분기의
'달러 매출 ÷ 수출' 비율을 적용해 매출 중앙값과 범위를 추정합니다.
#file:test_estimate_revenue.py 의 테스트를 모두 통과해야 합니다. 테스트 파일은 수정하지 마세요.

[함수 시그니처 — 변경 금지]
import pandas as pd

def estimate_revenue(quarterly_df: pd.DataFrame, actuals_df: pd.DataFrame,
                     target_quarter: str) -> dict:

[입력 명세]
1) quarterly_df: 분기별 수출·환율 집계 표 (aggregate_quarterly의 출력)
   - quarter: str "YYYYQn" (키, 중복 없음)
   - export_usd: float (분기 수출 합계, 달러)
   - months_available: int (0~3, 수출 자료가 있는 달 수)
   - fx_avg: float (분기 평균 원/달러 환율, 결측 NaN 가능)
   - 대상 분기보다 뒤의 분기 행이 들어 있을 수 있다.
   예) quarter="2025Q4", export_usd=1.0e10, months_available=3, fx_avg=1400.0
2) actuals_df: 분기 확정 매출 표 (load_actuals의 출력)
   - quarter: str "YYYYQn" (키, 중복 없음)
   - revenue_krw: float (원, 연결 기준 분기 매출, 결측 NaN 가능)
   - announced_date: str "YYYY-MM-DD" (계산에 쓰지 않음)
   - 대상 분기와 그 이후 분기의 실적이 들어 있을 수 있다.
   예) quarter="2025Q4", revenue_krw=2.24e13, announced_date="2026-01-22"
3) target_quarter: str "YYYYQn" (예: "2026Q1")

[출력 명세] 어떤 경우에도 아래 키 8개를 모두 가진 dict를 반환한다
- quarter: str (= target_quarter)
- estimate_krw, lower_krw, upper_krw: float 또는 None (원 단위)
- qoq_change_pct: float 또는 None (직전 분기 실적 대비 %)
- ratio_used: float 또는 None (기준 분기 비율의 평균)
- months_available: int (대상 행의 값, 대상 행이 없으면 0). numpy 정수가 아닌 파이썬 int로 반환
- status: "ok", "no_data", "insufficient_history" 중 하나

[처리 순서 — Pseudocode]
대상 행 = quarterly_df에서 quarter == target_quarter인 행
IF 대상 행이 없거나 months_available이 0이거나 fx_avg가 결측이면
    RETURN status="no_data", months_available=대상 행의 값(없으면 0), 나머지 숫자 값 None
기준 분기 = target_quarter보다 앞선 분기 중 아래 조건을 모두 만족하는 분기
    (actuals_df에 revenue_krw가 결측이 아닌 실적 있음, months_available == 3,
     export_usd > 0, fx_avg 결측 아님)
IF 기준 분기가 RATIO_WINDOW(=4)개 미만이면
    RETURN status="insufficient_history", months_available=대상 행의 값, 나머지 숫자 값 None
비율 목록 = 가장 최근 기준 분기 4개 각각의 (revenue_krw ÷ fx_avg) ÷ export_usd
분기 수출 추정 = 대상 행 export_usd × 3 ÷ months_available
estimate_krw = 분기 수출 추정 × 비율 평균 × 대상 행 fx_avg
lower_krw    = 분기 수출 추정 × 비율 최솟값 × 대상 행 fx_avg
upper_krw    = 분기 수출 추정 × 비율 최댓값 × 대상 행 fx_avg
직전 분기 = target_quarter 바로 앞 분기 (2026Q1 → 2025Q4, 2026Q3 → 2026Q2)
IF actuals_df에 직전 분기 실적(revenue_krw 결측 아님)이 있으면
    qoq_change_pct = (estimate_krw ÷ 직전 분기 revenue_krw − 1) × 100
ELSE
    qoq_change_pct = None
RETURN status="ok", ratio_used=비율 평균, 위에서 계산한 값

[예외·경계 방침]
- 예외를 발생시키지 않는다. 자료 부족은 status 값으로만 알린다.
- 대상 분기와 그 이후의 actuals는 읽지 않는다(미래 정보 누수 방지).
- months_available이 1~2인 대상 분기는 3개월분으로 환산해 계산한다.
- revenue_krw가 결측인 actuals 행은 실적이 없는 것으로 본다.
- 결측 확인은 pd.isna()로 한다(== NaN 비교 금지).

[제약 조건 — 프로젝트 공통]
- 파이썬 표준 라이브러리와 pandas만 사용한다(numpy 등 직접 import 금지).
- 시그니처를 바꾸지 않는다. 공개 함수를 새로 만들지 않고, 보조 함수는
  밑줄로 시작하는 내부 함수(예: _prev_quarter)로 같은 파일에 둔다.
- 타입 힌트와 한국어 docstring(설명, Args, Returns, Raises)을 단다.
- 가변 기본값 인자 금지. 전역 변수를 읽거나 바꾸지 않는다(파일 맨 위 대문자 상수는 읽기 전용 허용).
- 입력 DataFrame을 직접 수정하지 않는다.
- print, 파일 읽기·쓰기, 다른 팀 모듈 import를 하지 않는다.

[제약 조건 — 함수별: estimate_revenue]
- 자료구조: 반환 dict의 키 8개 이름·타입 고정. months_available은 int, 금액은 float.
- 처리 방식: 금액은 원 단위 그대로 두고 반올림하지 않는다.
- 하지 말 것: 가이던스 등 다른 입력을 계산에 쓰지 않는다. 조 원 변환 같은 표시용 가공을 하지 않는다.
- 변경 대비: 파일 맨 위에 RATIO_WINDOW = 4 상수를 둔다.

[통과해야 할 테스트 — 설계 문서 파트 4 T07~T11 + 추가 A01~A04]
공통 입력 F
- quarterly_df: 2025Q1~2025Q4 → export_usd 1.0e10, months_available 3, fx_avg 1400.0
                2026Q1 → export_usd 1.2e10, months_available 3, fx_avg 1450.0
- actuals_df: 2025Q1 1.96e13, 2025Q2 2.10e13, 2025Q3 2.10e13, 2025Q4 2.24e13
  (비율 1.4·1.5·1.5·1.6 → 평균 1.5, 최소 1.4, 최대 1.6)
T07 정상: F, "2026Q1" → status "ok", estimate 2.61e13, lower 2.436e13, upper 2.784e13,
          ratio_used 1.5, qoq_change_pct ≈ 16.5179, months_available 3 (int)
T08 정상: F에서 2026Q1만 export_usd 8.0e9, months_available 2
          → estimate·lower·upper가 T07과 같음, months_available 2
T09 경계: F에서 actuals의 2025Q1 행 삭제 → status "insufficient_history",
          숫자 값 5개 모두 None, months_available 3
T10 경계: F의 actuals에 2026Q1 실적 3.0e13 추가 → 결과 dict가 T07과 완전히 같음
T11 예외: F, "2026Q2"(행 없음) → status "no_data", 숫자 값 모두 None,
          months_available 0, 예외 발생 없음
A01 경계: 2026Q1을 export_usd 0.0, months_available 0으로 변경 → "no_data", months_available 0
A02 예외: 2026Q1 fx_avg NaN → "no_data", 숫자 값 모두 None, months_available 3
A03 경계: F에 2024Q4(quarterly 1.0e10·3·1400.0 / actuals 2.10e13) 추가, actuals의 2025Q4 삭제
          → 기준 분기 2024Q4·2025Q1·2025Q2·2025Q3, status "ok", ratio_used 1.475,
            estimate 2.5665e13, lower 2.436e13, upper 2.61e13, qoq_change_pct None
A04 예외: actuals의 2025Q1 revenue_krw NaN → "insufficient_history", 숫자 값 모두 None
금액·비율 비교는 pytest.approx(rel=1e-6)로 한다.

[출력 방식]
- 파일을 직접 만들거나 수정하지 말고, 터미널 명령(pytest 등)도 실행하지 마세요.
- forecaster.py의 전체 코드를 채팅에 코드 블록 하나로만 보여 주세요.
```
- 생성 코드 위치: c681b9d (수정 전 원본)
- 코드 리딩에서 발견한 결함:
  1) 명세 밖 필수 열 검사
     - AI가 프롬프트에 없는 필수 열·DataFrame 타입 검사(원본 88~106줄)를 임의로 추가함
     - 열 누락은 상류 함수의 버그인데, 이를 status `no_data`로 반환해 "예측할 데이터 없음"으로 숨김. 예: actuals 열 이름이 `revenue_krw` 대신 `revenue`로 들어와도 오류 없이 no_data가 됨
     - 열 보장은 `load_actuals`·`aggregate_quarterly`의 역할임. 구현 가이드의 "예외를 내지 않는다"는 자료 부족에만 해당하므로, 이 검사는 팀 규칙 "예외를 조용히 삼키지 않는다"에 어긋남

  2) 음수 months_available 출력
     - 기존 코드는 결과에 먼저 대입한 뒤 검사해서, 입력 -1이 그대로 출력됨(원본 124~127줄)
     - 출력 명세(0~3) 위반이고, forecasts.csv와 화면의 "반영된 개월 수"까지 전달됨
     - 0·3 입력으로는 드러나지 않아 기존 테스트(A01 등)가 놓쳤고, 음수를 넣어 한 줄씩 따라가며 발견함

  3) 기준 분기 선택 코드의 과도한 복잡성
     - itertuples → dict → set 교집합 → for의 3단계 루프(약 60줄)로 기준 분기를 골라 설명하기 어려움(원본 119~227줄)
     - 이미 숫자인 값을 다시 변환하는 try/except 5곳이 앞 단계 버그를 조용히 no_data·제외로 바꿀 수 있음
     - 기준 분기에서 `fx_avg`가 0인 경우를 거르지 않아 ZeroDivisionError가 날 수 있음
     - 비율 평균을 실제 개수 대신 상수 `RATIO_WINDOW`로 나눔, 매직 넘버 `3` 사용

- 수정 내역:
  - `74b0de4` (수정1): 필수 열·타입 검사 블록(원본 88~106줄) 삭제. 이제 열이 없으면 `KeyError: '<열 이름>'`가 발생해 문제 위치가 바로 드러남
  - `2aa330c` (수정2): `months_available <= 0` 검사를 결과 대입보다 앞으로 옮김. 0 이하 입력은 대입 전에 반환되어 초깃값 0이 출력되고, 1~3일 때만 결과에 대입됨 (입력 -1 → 수정 전 출력 -1, 수정 후 출력 0)
  - `e382473` (수정3): 기준 분기 선택을 `merge` + 조건 마스크(대상 분기 이전, months_available == 3, export_usd > 0, fx_avg > 0) + `sort_values().tail(4)`로 단순화. 불필요한 try/except 5곳 제거, 평균은 `len(ratios)`로 계산, `MONTHS_PER_QUARTER = 3` 상수 추가

- 테스트 결과: pytest 9 passed (정상 2 · 경계 4 · 예외 3)

  | ID | 범주 | 테스트 함수 | 테스트 내용 | 확인한 결과 |
  | --- | --- | --- | --- | --- |
  | T07 | 정상 | test_t07_full_quarter | 공통 입력 F, 대상 분기 2026Q1 (3개월 모두 있음) | status "ok", 중앙값 26.1조 / 하한 24.36조 / 상한 27.84조, ratio_used 1.5, qoq ≈ 16.52% |
  | T08 | 정상 | test_t08_partial_months_scaled | 2026Q1만 2개월치(80억 달러, months_available 2) | 3개월분 120억 달러로 환산되어 금액이 T07과 같음, months_available 2 |
  | T09 | 경계 | test_t09_insufficient_history | actuals의 2025Q1 삭제 → 기준 분기 3개 | status "insufficient_history", 숫자 값 5개 모두 None |
  | T10 | 경계 | test_t10_ignores_future_actuals | actuals에 대상 분기(2026Q1) 실적 30.0조 추가 | 결과가 T07과 완전히 같음 (미래 실적을 읽지 않음) |
  | T11 | 예외 | test_t11_no_target_row | 대상 분기 2026Q2 (quarterly에 행 없음) | status "no_data", 숫자 값 모두 None, months_available 0, 예외 없음 |
  | A01 | 경계 | test_a01_zero_months_available | 2026Q1을 수출 0, months_available 0으로 변경 | status "no_data", 숫자 값 모두 None, months_available 0 |
  | A02 | 예외 | test_a02_target_fx_missing | 2026Q1 fx_avg를 NaN으로 변경 | status "no_data", 숫자 값 모두 None, months_available 3 |
  | A03 | 경계 | test_a03_no_prev_quarter_actual | 2024Q4 추가, 직전 분기(2025Q4) 실적 삭제 | 기준 분기 2024Q4~2025Q3로 계산 (ratio_used 1.475, 중앙값 25.665조), qoq_change_pct만 None |
  | A04 | 예외 | test_a04_revenue_nan_not_counted | actuals의 2025Q1 revenue_krw를 NaN으로 변경 | 결측 실적은 기준 분기에서 빠짐 → status "insufficient_history" |

---

[data_loader.py] load_actuals — 2026-11-09, 작성자: 신동훈

- 사용 도구: GitHub Copilot Chat (Ask 모드, #file:test_load_actuals.py 참조)
- 설계 근거: 설계 문서 V1 파트 2 (3)·(4) actuals 표, 구현 가이드 1.1절 load_actuals Pseudocode·부록 6
- 테스트 파일: `521f13a` (Copilot 생성 전 커밋, L01~L12)
- 프롬프트:
```
당신은 파이썬 백엔드 개발을 돕는 어시스턴트입니다.
SK하이닉스 분기 매출 나우캐스팅 시스템의 적재 모듈 data_loader.py에 들어갈
함수 load_actuals를 구현해 주세요. 이 함수는 팀원이 DART 공시를 보고 손으로 작성한
분기 확정 매출 CSV를 읽어 형식을 검사한 뒤, 표준 스키마의 actuals 표로 돌려줍니다.
#file:test_load_actuals.py 의 테스트를 모두 통과해야 합니다. 테스트 파일은 수정하지 마세요.

[함수 시그니처 — 변경 금지]
import pandas as pd

def load_actuals(filepath: str) -> pd.DataFrame:

[입력 명세]
filepath: str — 실적 CSV 경로 (예: "data/actuals.csv")
- UTF-8 텍스트, 첫 줄은 열 이름. 엑셀로 저장해 UTF-8 BOM이 붙어 있을 수 있다.
- 필수 열 3개: quarter, revenue_krw, announced_date
  (열 순서는 파일마다 다를 수 있고, memo 같은 추가 열이 있을 수 있다)
- 사람이 입력한 파일이라 다음이 섞일 수 있다: 열 이름·값의 앞뒤 공백,
  천 단위 쉼표("19,600,000,000,000"), 지수 표기("1.96E+13"), 세 칸이 모두 빈 줄(",,")
예)
quarter,revenue_krw,announced_date
2025Q1,"19,600,000,000,000",2025-04-24
2025Q2,21000000000000,2025-07-24

[출력 명세] pd.DataFrame (actuals 표)
- 열은 정확히 3개, 이 순서로: quarter, revenue_krw, announced_date
- quarter: str "YYYYQn" (n은 1~4), 중복 없음
- revenue_krw: float (원 단위, 0 초과의 유한한 수), dtype float64
- announced_date: str "YYYY-MM-DD" (날짜 타입으로 바꾸지 않음)
- quarter 오름차순 정렬, 행 번호(index)는 0부터 다시 매긴다
- 결측(NaN)이 하나도 없다
- 데이터 행이 0개이면 위 열 3개만 있는 빈 표를 돌려준다
예) quarter="2025Q1", revenue_krw=1.96e13, announced_date="2025-04-24"

[처리 순서 — Pseudocode]
CSV를 CSV_ENCODING으로, 모든 열을 문자열로 읽는다
    (빈칸·"N/A" 같은 값을 결측으로 바꾸지 않고 원문 그대로 둔다 — 오류 메시지에 원래 값을 보여 주기 위해)
    (파일이 없으면 FileNotFoundError가 그대로 나가게 둔다)
IF 파일이 0바이트라 열 이름 줄도 없으면
    ValueError("필수 열 누락: quarter, revenue_krw, announced_date")를 발생시킨다
열 이름의 앞뒤 공백을 지운다
IF ACTUALS_COLUMNS 중 없는 열이 있으면
    ValueError("필수 열 누락: <없는 열 이름들, 쉼표로 이어서>")를 발생시킨다
표 = ACTUALS_COLUMNS 3개만 이 순서로 남긴 복사본 (추가 열은 버린다)
모든 값의 앞뒤 공백을 지운다
세 값이 모두 빈 문자열인 행을 제거한다
IF 남은 행이 0개이면
    RETURN 열 3개만 있는 빈 actuals 표
오류 목록 = 빈 목록
FOR 각 행 반복
    줄 번호 = 열 이름 줄을 1행, 첫 데이터 행을 2행으로 센 번호 (빈 행 제거 전 순서 기준)
    IF quarter가 QUARTER_PATTERN에 맞지 않으면
        오류 목록에 "<줄 번호>행 quarter '<원래 값>'"을 추가한다
    매출 = revenue_krw에서 쉼표를 지우고 float로 바꾼 값 (바꿀 수 없으면 결측)
    IF 매출이 결측이거나 유한한 수가 아니거나(inf, nan) 0 이하이면
        오류 목록에 "<줄 번호>행 revenue_krw '<원래 값>'"을 추가한다
    IF announced_date가 DATE_PATTERN에 맞지 않거나 DATE_FORMAT으로 실제 날짜로 읽히지 않으면
        오류 목록에 "<줄 번호>행 announced_date '<원래 값>'"을 추가한다
IF 오류 목록이 비어 있지 않으면
    ValueError("actuals.csv 형식 오류: " + 오류 목록을 "; "로 이어 붙인 문자열)를 발생시킨다
IF 같은 quarter가 두 번 이상 있으면
    ValueError("actuals.csv 분기 중복: <중복 quarter들, 쉼표로 이어서>")를 발생시킨다
revenue_krw 열을 변환한 float 값으로 바꾼다
quarter 오름차순으로 정렬하고 행 번호를 0부터 다시 매긴다
RETURN actuals 표

[예외·경계 방침]
- 사람이 고쳐야 하는 입력 문제는 모두 ValueError로 알린다. 잘못된 행을 조용히 지우거나 고치지 않는다.
- 형식 오류는 첫 오류에서 멈추지 않고 모든 행을 검사한 뒤 한 번에 알린다.
  메시지 예: "actuals.csv 형식 오류: 3행 quarter '2025-Q2'; 5행 revenue_krw 'N/A'"
- 형식 검사를 먼저 하고, 형식 오류가 없을 때만 분기 중복을 검사한다.
- 세 값이 모두 빈칸인 행만 무시한다. 일부 칸만 빈칸이면 형식 오류다.
- 열 이름 줄만 있는 파일은 오류가 아니다(빈 actuals 표 반환).
- "2025q1"처럼 비슷한 표기를 자동으로 고치지 않는다(형식 오류).
- announced_date는 월·일이 두 자리여야 하고 달력에 있는 날짜여야 한다("2025-4-24", "2025-02-30"은 형식 오류).
- 0바이트 파일에서 pandas가 내는 EmptyDataError만 잡아 위 ValueError로 바꾸어 발생시킨다(raise ... from 사용).
  그 밖의 except는 쓰지 않는다. except: 나 except Exception: pass 같은 광범위한 예외 삼키기를 금지한다.
- 결측 확인은 pd.isna() 또는 math.isfinite()로 한다(== NaN 비교 금지).

[제약 조건 — 프로젝트 공통]
- Python 3.10 이상. 이 함수에는 파이썬 표준 라이브러리(re, datetime, math 등)와 pandas만 사용한다.
  numpy 등을 직접 import하지 않는다. data_loader.py에 허용된 requests·python-dotenv도 이 함수에는 쓰지 않는다.
- 시그니처를 바꾸지 않는다. 공개 함수를 새로 만들지 않고, 보조 함수는
  밑줄로 시작하는 내부 함수(예: _parse_revenue)로 같은 파일에 둔다.
- 모든 함수(내부 함수 포함)에 타입 힌트와 한국어 docstring(설명, Args, Returns, Raises)을 단다.
- 가변 기본값 인자 금지. 전역 변수를 읽거나 바꾸지 않는다(파일 맨 위 대문자 상수는 읽기 전용 허용).
- 파일 읽기는 filepath 한 개만 하고, 파일 쓰기는 하지 않는다. print, 다른 팀 모듈 import를 하지 않는다.
- 오류 메시지는 한국어로, 무엇이 문제인지(열 이름, 줄 번호, 값, 분기)를 담는다.

[제약 조건 — 함수별: load_actuals]
- 자료구조: 반환 열 3개의 이름·순서·타입 고정. quarter·announced_date는 str, revenue_krw는 float64.
- 처리 방식: CSV는 모든 열을 문자열로 읽는다(숫자 자동 변환 금지). revenue_krw는 원 단위 그대로 두고 반올림하지 않는다.
- 하지 말 것: 잘못된 행 삭제, 결측을 0으로 채우기(clean_exports와 반대 방침).
  조 원 변환 같은 표시용 가공, 분기 집계·비율 계산(다른 모듈의 역할).
  발표일과 분기의 선후 관계처럼 명세에 없는 검사 추가.
- 변경 대비: 파일 맨 위에 아래 상수를 둔다.
  ACTUALS_COLUMNS = ("quarter", "revenue_krw", "announced_date")
  CSV_ENCODING = "utf-8-sig"
  QUARTER_PATTERN = r"^\d{4}Q[1-4]$"
  DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
  DATE_FORMAT = "%Y-%m-%d"

[통과해야 할 테스트 — L01~L12]
공통 파일 G (UTF-8, 정렬되지 않음)
quarter,revenue_krw,announced_date
2025Q3,21000000000000,2025-10-23
2025Q1,19600000000000,2025-04-24
2025Q4,"22,400,000,000,000",2026-01-22
2025Q2,21000000000000,2025-07-24

L01 정상: G → 4행, 열 [quarter, revenue_krw, announced_date],
          quarter ["2025Q1","2025Q2","2025Q3","2025Q4"], revenue_krw [1.96e13, 2.1e13, 2.1e13, 2.24e13] (float64),
          announced_date ["2025-04-24","2025-07-24","2025-10-23","2026-01-22"], index 0~3, 결측 없음
L02 정상: G와 같은 내용을 UTF-8 BOM으로 저장하고 열 이름·값 앞뒤 공백, memo 열, "2.1E+13" 표기를 섞음
          → L01과 완전히 같은 표(pd.testing.assert_frame_equal)
L03 경계: 열 이름 줄만 있는 파일 → 0행, 열 3개, 예외 없음
L04 경계: G 중간에 ",," 줄 삽입 → L01과 같은 결과
L05 예외: ① revenue_krw 열 없음 ② quarter·announced_date 열 없음
          → ValueError, 메시지에 "필수 열 누락"과 없는 열 이름 모두 포함
L06 예외: 0바이트 파일 → ValueError, 메시지에 "필수 열 누락"
L07 예외: 2025Q1 행 quarter를 "2025-Q1" / "2025Q5" / "25Q1" / "2025q1"로 변경
          → ValueError, 메시지에 "형식 오류"와 그 값 포함
L08 예외: 2025Q1 행 revenue_krw를 "N/A" / "" / "0" / "-1" / "inf" / "abc"로 변경
          → ValueError, 메시지에 "형식 오류"와 "revenue_krw" 포함
L09 예외: 2025Q1 행 announced_date를 "2025/04/24" / "2025-4-24" / "2025-02-30" / ""로 변경
          → ValueError, 메시지에 "형식 오류"와 "announced_date" 포함
L10 예외: G에 "2025Q1,19700000000000,2025-04-25" 행 추가 → ValueError, 메시지에 "분기 중복"과 "2025Q1"
L11 예외: 3행 quarter "2025-Q2", 5행 revenue_krw "N/A"(나머지 정상)
          → ValueError 한 번, 메시지에 "3행"과 "5행" 모두 포함
L12 예외: 존재하지 않는 경로 → FileNotFoundError
금액 비교는 pytest.approx(rel=1e-6) 또는 assert_frame_equal로 한다.

[출력 방식]
- 파일을 직접 만들거나 수정하지 말고, 터미널 명령(pytest 등)도 실행하지 마세요.
- data_loader.py에 넣을 코드(import, 상수, 내부 함수, load_actuals)만 채팅에 코드 블록 하나로 보여 주세요.
  같은 파일의 fetch_regional_exports·fetch_fx_rates는 작성하지 마세요.
```
- 생성 코드 위치: `7c4af18` (수정 전 원본)
- 코드 리딩에서 발견한 결함:
  1) 칸 수가 맞지 않는 줄에서 TypeError·영어 ValueError 발생
     - 헤더보다 칸이 많은 줄이 있으면 pandas가 앞쪽 칸을 index로 자동 추론함. 그러면 줄 번호 계산 `int(row_index) + 2`(원본 60줄)에서 오류가 나고 열도 한 칸씩 밀림
     - 따옴표 없이 쉼표를 쓴 매출(`2025Q1,19,600,000,000,000,2025-04-24`) → `TypeError`. 모든 행에 칸이 하나 더 있는 경우 → `invalid literal for int()` 영어 ValueError. 한 행만 칸이 많은 경우 → pandas `ParserError` 영어 메시지가 그대로 나감
     - 명세 "사람이 고쳐야 하는 입력 문제는 한국어 ValueError" 위반. L01~L12는 칸 수가 맞는 파일만 써서 24건 모두 통과했고, 메모장 입력 실수를 가정한 입력을 넣어 한 줄씩 따라가며 발견함

  2) 전각 숫자 quarter 통과
     - `QUARTER_PATTERN`의 `\d`(원본 10줄)는 0~9뿐 아니라 모든 유니코드 숫자와 맞아서, 전각 모드로 입력한 `２０２５Q1`이 형식 검사를 통과함
     - 화면에서는 2025Q1처럼 보이지만 문자열이 달라서 다음 문제가 생김: estimate_revenue가 실적을 찾지 못함(`insufficient_history`, qoq None). `2025Q1`과 함께 있어도 분기 중복 검사에 걸리지 않음. 정렬하면 맨 뒤로 밀림
     - announced_date는 strptime이 전각 숫자를 거부해 이중 검사로 막히지만, quarter는 정규식 하나로만 검사해서 생긴 구멍

  3) 빈 표의 revenue_krw dtype이 float64가 아님
     - 데이터 행이 0개일 때 `pd.DataFrame(columns=ACTUALS_COLUMNS)`(원본 54줄)로 새 표를 만들어서 세 열이 모두 object
     - 출력 명세 "revenue_krw dtype float64" 위반. L03은 행 수와 열 이름만 확인해서 놓침

  4) 공백 제거 후 열 이름이 겹치면 TypeError 발생
     - 헤더가 `quarter, quarter,...`이면 열 이름 공백 제거(원본 39줄) 후 quarter 열이 두 개가 됨. 그러면 `row["quarter"]`가 Series가 되어 정규식 검사에서 TypeError
     - 입력 문제는 ValueError로 알린다는 방침 위반

  - 기타 판단 (수정하지 않음):
    - `float()`가 언더스코어(`19_600_000_000_000`)와 전각 숫자 매출도 숫자로 읽음 → 읽힌 값 자체가 정확해서 데이터 오염이 없으므로 허용
    - `pd.isna(revenue)`는 `math.isfinite`와 중복이고, 마지막 `return actuals.loc[:, ACTUALS_COLUMNS]`는 이미 그 열만 있어 불필요 → 동작에 영향 없음
    - `DataFrame.map`은 pandas 2.1 이상 필요 → 팀 환경 버전 확인 필요
  - 의도대로 동작함을 확인한 부분:
    - `keep_default_na=False` + `skip_blank_lines=False`로 진짜 빈 줄이 있어도 오류 메시지의 줄 번호가 실제 파일 줄과 일치함. 프롬프트에서 요구하지 않은 경우까지 처리함
    - EmptyDataError만 좁게 잡아 `raise ... from`으로 변환함. 광범위한 except 없음

- 수정 내역:
  - `2b9acaa` (수정1): `read_csv`에 `index_col=False` 추가. `ParserError`는 `ValueError("actuals.csv 형식 오류: 열 개수가 맞지 않는 줄이 있습니다 (...)")`로 변환. 따옴표 없는 쉼표 입력은 이제 `2행 announced_date '600'` 형식 오류로 알림(칸이 밀린 탓에 문제 열이 announced_date로 표시되는 한계는 있음)
  - `d8f5090` (수정2): `QUARTER_PATTERN`을 `r"^[0-9]{4}Q[1-4]$"`로 변경해 ASCII 숫자만 허용
  - `10f0088` (수정3): 빈 표 반환을 `actuals.astype({"revenue_krw": "float64"}).reset_index(drop=True)`로 교체. quarter·announced_date의 타입도 정상 경로와 같아짐
  - `d791b97` (수정4): 열 이름 공백 제거 직후 중복 검사 추가 → `ValueError("actuals.csv 열 이름 중복: <열 이름>")`
  - `f24931f` (테스트 추가): 결함 1·2 회귀 테스트 L13·L14 추가. 원본 코드에서 3건 실패, 수정 코드에서 통과 확인. 기존 L01~L12는 수정하지 않음

- 테스트 결과: pytest 27 passed (테스트 함수 14개: 정상 2 · 경계 2 · 예외 10, 값을 바꿔 반복하는 케이스 포함 27건)

  | ID | 범주 | 테스트 함수 | 테스트 내용 | 확인한 결과 |
  | --- | --- | --- | --- | --- |
  | L01 | 정상 | test_L01_normal_file | 공통 파일 G (정렬 안 됨, 쉼표 표기 매출 포함) | 4행, 열 순서 고정, quarter 2025Q1→Q4 정렬, 매출 float64(19.6조·21조·21조·22.4조), index 0~3, 결측 없음 |
  | L02 | 정상 | test_L02_messy_but_valid_file | G와 같은 내용에 BOM·앞뒤 공백·memo 열·`2.1E+13` 표기를 섞음 | L01과 완전히 같은 표 |
  | L03 | 경계 | test_L03_header_only_returns_empty_table | 열 이름 줄만 있는 파일 | 0행, 열 3개, 예외 없음 |
  | L04 | 경계 | test_L04_blank_row_is_ignored | G 중간에 `,,` 줄 삽입 | 빈 줄을 무시하고 L01과 같은 결과 |
  | L05 | 예외 | test_L05_missing_required_columns | ① revenue_krw 열 없음 ② quarter·announced_date 열 없음 | ValueError "필수 열 누락", 없는 열 이름 모두 표시 |
  | L06 | 예외 | test_L06_zero_byte_file | 0바이트 파일 | EmptyDataError가 아닌 ValueError "필수 열 누락" |
  | L07 | 예외 | test_L07_invalid_quarter | quarter `2025-Q1`·`2025Q5`·`25Q1`·`2025q1` | ValueError "형식 오류", 잘못된 값 표시 |
  | L08 | 예외 | test_L08_invalid_revenue | 매출 `N/A`·빈칸·`0`·`-1`·`inf`·`abc` | ValueError "형식 오류", revenue_krw 표시 |
  | L09 | 예외 | test_L09_invalid_announced_date | 날짜 `2025/04/24`·`2025-4-24`·`2025-02-30`·빈칸 | ValueError "형식 오류", announced_date 표시 |
  | L10 | 예외 | test_L10_duplicate_quarter | 2025Q1 행 중복 | ValueError "분기 중복: 2025Q1" |
  | L11 | 예외 | test_L11_all_format_errors_reported_at_once | 3행 quarter 오류, 5행 매출 오류 | ValueError 한 번에 3행·5행 모두 표시 |
  | L12 | 예외 | test_L12_file_not_found | 없는 경로 | FileNotFoundError 그대로 발생 |
  | L13 | 예외 | test_L13_fullwidth_digit_quarter | quarter `２０２５Q1` (결함 2 회귀) | ValueError "형식 오류", 전각 값 표시 |
  | L14 | 예외 | test_L14_mismatched_field_count | 따옴표 없는 쉼표 매출 / 한 행만 칸이 많음 (결함 1 회귀) | TypeError·영어 메시지 없이 ValueError "형식 오류" |
---

## 신해성
[preprocess] aggregate_quarterly (2026-11-03, 작성자: 신해성)

- 사용 도구: GitHub Copilot, GPAI, pytest

### ① 논리 설계

- 구현 대상: `hynix_nowcast/preprocess.py`의 `aggregate_quarterly`
- 목적: 월별 지역 수출 자료와 일별 환율 자료를 분기별로 집계한다.

- 함수 시그니처:

```python
def aggregate_quarterly(
    exports_df: pd.DataFrame,
    fx_df: pd.DataFrame,
    lag_months: int = 0
) -> pd.DataFrame:
```

- 입력:
  - `exports_df`: `ym`, `region`, `hs_code`, `export_usd`, `collected_at` 열을 포함하는 월별 수출 표.
  - `fx_df`: `date`, `usdkrw` 열을 포함하는 일별 환율 표.
  - `lag_months`: 수출 월에 적용할 개월 단위 시차.

- 출력:
  - `quarter`: 분기 문자열.
  - `export_usd`: 분기별 수출액 합계.
  - `months_available`: 집계에 포함된 서로 다른 월 수.
  - `fx_avg`: 분기별 환율 관측값의 산술평균.

- 처리 흐름:
  1. 음수 `lag_months`이면 `ValueError`를 발생시킨다.
  2. 빈 수출 표이면 정해진 열을 갖는 빈 결과를 반환한다.
  3. 이천시와 청주시 자료만 선택한다.
  4. 두 지역이 모두 존재하는 달만 집계 대상으로 사용한다.
  5. 수출 월에 `lag_months`를 적용한 뒤 분기를 구한다.
  6. 분기별 수출액 합계와 포함 월 수를 계산한다.
  7. 환율에는 시차를 적용하지 않고 분기별 평균을 계산한다.
  8. 수출 분기를 기준으로 환율을 결합한다.
  9. 해당 분기에 환율 자료가 없으면 `NaN`을 유지한다.

- 비고:
  - 위 내용은 검토한 코드와 제공 테스트를 바탕으로 정리한 설계 요약이다.
  - 최초 논리 설계서에 별도 요구사항이 있다면 대조하여 보완한다.

### ② 정밀 프롬프트 작성

- 프롬프트:

```text
[모듈] aggregate_quarterly (2026-11-03, 작성자: 신해성)

사용 도구: GitHub Copilot Chat

프롬프트:
당신은 파이썬 백엔드 개발을 돕는 어시스턴트입니다. SK하이닉스 분기 매출 나우캐스팅 시스템의 전처리 모듈(preprocess.py)에 들어갈 분기 집계 함수를 구현해 주세요.

[함수 시그니처, 변경 금지]
def aggregate_quarterly(exports_df: pd.DataFrame, fx_df: pd.DataFrame, lag_months: int = 0) -> pd.DataFrame:

[입력 명세]
exports_df: 월별 수출 표. (열: ym "YYYY-MM", region "이천시" 또는 "청주시", hs_code "854232", export_usd float, collected_at "YYYY-MM-DD")
fx_df: 일별 환율 표. (열: date "YYYY-MM-DD", usdkrw float)
lag_months: 수출액을 몇 개월 뒤 분기의 실적으로 반영할지 결정하는 시차 (기본값 0)

[출력 명세]
반환 열은 정확히 4개, 이 순서대로: quarter(str, "YYYYQn"), export_usd(float, 분기 합계), months_available(int, 수출 자료가 있는 달 수, 1~3), fx_avg(float, 분기 평균 환율)

[세부 구현 및 처리 규칙]
예외 및 경계 처리: exports_df가 비어 있으면 반환 열 4개를 가진 빈 표를 즉시 반환한다. lag_months < 0 인 경우 ValueError("lag_months는 0 이상이어야 합니다")를 발생시킨다.
데이터 불변성: 입력된 DataFrame(exports_df, fx_df)을 직접 수정하지 않고 복사본이나 집계 연산을 통해 새로운 객체를 생성한다.
수출 집계 (지역 교집합 필터링): exports_df를 ym 단위로 그룹화할 때, region 열에 "이천시"와 "청주시"가 모두 존재하는 달만 남긴다. 한 지역만 있는 달은 합산하지 않고 버린다. 조건에 맞는 월에 한해 export_usd를 합산한다.
분기 환산과 시차(Lag) 적용: 파일 내부에 밑줄로 시작하는 보조 함수(예: _get_shifted_quarter)를 만들어 구현한다. "YYYY-MM" 문자열의 월(month)에 lag_months를 더할 때 연도가 넘어가는 경우를 안전하게 처리한 뒤, 귀속 월이 속한 분기("YYYYQn") 문자열을 반환한다. 해당 분기 단위로 수출액을 다시 합산하고, 분기 내 포함된 월의 개수를 months_available(1~3) 열에 기록한다.
환율 집계: fx_df의 date("YYYY-MM-DD")를 분기("YYYYQn")로 변환하여 분기별 usdkrw의 평균(fx_avg)을 구한다. 환율에는 시차(lag_months)를 적용하지 않는다.
병합 (Merge): 수출이 존재하는 분기를 기준으로 환율 집계 결과를 병합(Left Merge)한다. 수출 자료가 하나도 없는 분기는 결과 행을 만들지 않는다. 환율 자료가 없는 분기의 fx_avg는 결측치(NaN/None)로 유지하며, 빠진 데이터를 0으로 채우지 않는다.

[제약 조건]
Python 3.10 이상, 파이썬 표준 라이브러리와 pandas만 사용 (numpy 등 다른 라이브러리 import 금지).
타입 힌트와 한국어 docstring(설명, Args, Returns, Raises) 필수.
결과 표의 열을 [quarter, export_usd, months_available, fx_avg] 순서로 맞추고, quarter 오름차순 정렬 후 인덱스를 0부터 다시 매긴다 (reset_index(drop=True)).
[통과해야 할 테스트]

정상 통합: 2026년 1~3월 두 지역 수출 데이터 모두 존재(매달 합계 100) -> 2026Q1에 export_usd 300, months_available 3 반환.
lag_months 적용: 2025-12월 두 지역 수출 데이터 존재, lag_months=1 -> 2026Q1 실적으로 집계.
경계 - 한 지역만 있는 달: 2026-04에 이천시 데이터만 존재 -> 2026Q2 집계에서 4월 데이터는 제외됨(months_available 반영 안 됨).
예외 - 빈 표: exports_df가 빈 표이면 4개 열을 가진 빈 표 반환.
```

- 비고:
  - 실제 프롬프트 원문을 보존한다.
  - 사후에 정리한 설명을 최초 프롬프트인 것처럼 기록하지 않는다.

### ③ AI 코드 생성

- 생성 도구: GitHub Copilot
- 생성 코드 파일: `hynix_nowcast/preprocess.py`
- 공개 함수: `aggregate_quarterly`
- 내부 보조 함수:
  - `_get_shifted_quarter`
  - `_empty_result`

- 생성 코드 위치: 5acdc8dc4bd8f216cc72029899b892d424a8e590

- 생성된 코드를 그대로 최종 결과로 확정하지 않고, 코드 리딩과 테스트를 진행했다.

### ④ 코드 리딩·검증

- 검토 자료:
  - 원본 `preprocess.py`: 94줄.
  - 제공된 `test_preprocess.py`: 테스트 3개.

- 점검 내용:
  - 함수 문서 및 제공 테스트와 구현의 일치 여부.
  - 입력값 검증과 조기 반환의 실행 순서.
  - 두 지역이 모두 있는 달만 집계하는지 여부.
  - 수출 월 시차 적용과 분기 집계 방식.
  - 입력 DataFrame 직접 수정 여부.
  - 광범위한 예외 처리 등 위험 관용구.

#### 코드 리딩에서 발견한 결함

1. 빈 입력일 때 음수 `lag_months` 검증이 생략됨.

   원본 50~53줄은 `exports_df.empty`를 먼저 검사하여 빈 결과를 반환한다.
   따라서 빈 수출 표와 `lag_months=-1`을 함께 전달하면
   `ValueError`가 발생하지 않는다.

   함수 docstring 47~48줄은 음수 시차에 `ValueError`를 명시하고 있으며,
   제공된 `test_empty_and_negative_lag`도 빈 표와 음수 시차를 함께
   전달하여 `ValueError` 발생을 요구한다.

   따라서 입력값 검증이 조기 반환 때문에 생략되는 결함으로 판정했다.

#### 수정 내역

- 수정 코드 위치: 1798f34ba0fcb98ded10e4a9b08baede20e1e70d

| 번호 | 원본 줄 | 원래 코드 | 수정 | 근거와 이유 |
|---|---|---|---|---|
| 1 | 50~53 | `exports_df.empty`이면 반환한 다음 `lag_months < 0` 검사 | 음수 시차 검사를 먼저 실행하고 이후 빈 입력 반환 | 빈 표와 음수 시차가 함께 들어오면 검증이 생략됨. 함수 docstring과 `test_empty_and_negative_lag`의 예외 처리 조건을 만족하도록 순서를 변경함. |

- 수정 전:

```python
if exports_df.empty:
    return _empty_result()

if lag_months < 0:
    raise ValueError("lag_months는 0 이상이어야 합니다")
```

- 수정 후:

```python
if lag_months < 0:
    raise ValueError("lag_months는 0 이상이어야 합니다")

if exports_df.empty:
    return _empty_result()
```

#### 구간별 리딩 기록

| 원본 줄 | 점검 대상 | 결과 |
|---|---|---|
| 1~3 | 모듈 설명 및 import | pandas 사용 확인 |
| 6~17 | 월 시차 및 분기 변환 | 월에 시차를 적용한 뒤 분기를 구함 |
| 20~29 | 빈 결과 생성 | 반환 열 순서와 dtype 명시 |
| 32~49 | 공개 함수 문서 | 입력, 출력, 음수 시차 예외 설명 확인 |
| 50~53 | 입력 검증 및 조기 반환 | 검증 순서 결함 발견 및 수정 |
| 55~63 | 지역 선택 및 완전한 달 판정 | 복사본 사용. 실제 고유 지역 수로 두 지역 존재 여부 확인 |
| 65~70 | 유효 월 부재 및 시차 적용 | 빈 결과 처리 및 월 단위 시차 적용 확인 |
| 71~78 | 분기별 수출 집계 | 수출액 합계와 고유 월 수 계산 확인 |
| 80~89 | 분기별 환율 집계 | 복사본 사용. 환율에는 시차를 적용하지 않음 |
| 91~94 | 결합 및 결과 정리 | 수출 기준 left join, 열 순서 및 인덱스 초기화 확인 |

#### 위험 관용구 점검

- 함수 전체를 감싸는 광범위한 `try/except`: 없음.
- 입력 DataFrame 직접 수정: 없음. 복사본에서 작업함.
- 파일 읽기·쓰기: 없음.
- 네트워크 접근: 없음.
- `print` 사용: 없음.

#### 명세 확인이 필요한 사항

아래 항목은 최초 프롬프트 원문을 확인하지 못했으므로
확정 결함으로 기록하지 않았다.

- 동일 월·지역의 중복 행을 모두 합산해도 되는지.
- `hs_code`를 함수에서 필터링해야 하는지, 입력에서 이미 보장하는지.
- 결측 수출액의 처리 정책.
- 잘못된 날짜, 필수 열 누락, 잘못된 시차 타입의 처리 정책.
- 환율 자료의 중복 날짜 허용 여부.
- 보조 함수에도 `Args`, `Returns`, `Raises` 전체가 필수인지.

### ⑤ 테스트

- 테스트 파일: `hynix_nowcast/test_preprocess.py`
- 제공된 테스트는 수정하지 않았다.

- 실행 위치:

```text
C:\Users\s2h02\my_project
```

- 실행 명령:

```powershell
python -m pytest -v .\hynix_nowcast\test_preprocess.py
```

- 실행 환경:
  - Windows
  - Python 3.13.15
  - pytest 9.2.0

- 실제 실행 결과:

```text
collected 3 items

hynix_nowcast/test_preprocess.py::test_aggregate_normal PASSED
hynix_nowcast/test_preprocess.py::test_lag_months_and_missing_region PASSED
hynix_nowcast/test_preprocess.py::test_empty_and_negative_lag PASSED

3 passed in 1.08s
```

| 테스트 | 확인 내용 | 결과 |
|---|---|---|
| `test_aggregate_normal` | 정상 분기 집계, 수출액 합계, 포함 월 수 | PASSED |
| `test_lag_months_and_missing_region` | 한 지역 누락 월 제외 및 시차 적용 | PASSED |
| `test_empty_and_negative_lag` | 빈 결과와 열 순서, 음수 시차 ValueError 발생 | PASSED |

- 테스트 결과: **pytest 3 passed in 1.08s**

- 비고:
  1. 최초 실행에서는 테스트 파일 경로를 잘못 지정하여
     `file or directory not found`가 발생했다.
     실제 파일 위치를 확인하고 실행 경로를 수정했다.
     이는 코드 테스트 실패가 아닌 파일 경로 문제였다.
  2. 제공된 테스트 3개가 통과한 것이며,
     모든 입력 및 경계 조건에서 결함이 없음을 보장하는 것은 아니다.
  3. 정상 테스트에는 `fx_avg` 값을 직접 검증하는 assertion이 없으므로,
     이번 통과 결과만으로 환율 계산까지 충분히 검증했다고 볼 수는 없다.


---

### [data_loader] fetch_regional_exports (2026-11-13, 작성자: 신해성)

- 사용 도구: GitHub Copilot, GPAI, pytest
- 기준: 지역 수출 원자료 수집 구현 가이드와 공공데이터포털 API 명세

### ① 요구사항 정리

- 구현 대상: `신해성/data_loader.py`의 `fetch_regional_exports`
- 책임: 관세청 API에서 이천시·청주시 메모리 반도체(HS 854232)의 월별 수출 원자료를 받는다.
- 시그니처:

```python
def fetch_regional_exports(start_ym: str, end_ym: str) -> pd.DataFrame:
```

- 입력: `start_ym`, `end_ym`은 `YYYY-MM` 형식의 시작월과 끝월이다.
- 출력: API 응답 행을 원래 열 이름과 값으로 유지한 DataFrame이며, 실행 날짜를 `collected_at` 열로 추가한다.
- 고정 규칙: 열 이름 변경, 형식 변환, 지역 필터, 결측치 필터는 하지 않는다. 이 작업은 `clean_exports`의 책임이다.
- 재량 규칙: 지역별 요청, 기간 분할, 페이지 반복, timeout은 구현자가 정한다.

### ② API 계약 설계

- API 주소와 요청 변수는 공공데이터포털 명세를 따른다.
- 요청 변수는 `serviceKey`, `strtYymm`, `endYymm`, `HsSgn`, `sidoCd`이다.
- `HsSgn`은 `854232`로 고정한다.
- 이천시는 경기도 `41`, 청주시는 충청북도 `43`으로 요청한다.
- 응답 필드(`year`, `sgguNm`, `hsSgn`, `expDlr` 등)는 가정값이므로 코드에서 이름을 바꾸지 않는다.
- API 키는 `.env`의 `CUSTOMS_API_KEY`에서 읽으며 일반 인증키(Decoding)를 사용한다.

### ③ 6단계 정밀 프롬프트

아래 프롬프트는 구현 가이드의 내용을 6단계로 나누어 작성한 최종 구현 프롬프트이다.

```text
1단계 - 역할과 목표
당신은 파이썬 백엔드 개발을 돕는 어시스턴트입니다. SK하이닉스 분기 매출 나우캐스팅 시스템의 data_loader.py에 관세청 원자료 수집 함수를 구현하세요. 함수는 이천시와 청주시의 HS 854232 월별 수출액 원자료를 수집하되, 후속 clean_exports가 처리할 수 있도록 원자료를 가공하지 않아야 합니다.

2단계 - 함수 계약
다음 시그니처를 변경하지 마세요.

def fetch_regional_exports(start_ym: str, end_ym: str) -> pd.DataFrame:

start_ym과 end_ym은 YYYY-MM 형식입니다. 반환값은 API 응답 item을 행으로 만든 pandas DataFrame입니다. API 응답의 열 이름과 값은 그대로 유지하고, 함수 실행일을 YYYY-MM-DD 형식의 collected_at 열로 추가하세요. 행이 없어도 collected_at 열을 가진 0행 DataFrame을 반환하세요.

3단계 - API 요청 명세
공공데이터포털 관세청 시군구별 품목별 수출입실적 XML API의 명세를 사용하세요. 요청 주소와 다음 요청 변수 이름을 파일 상수로 명확히 두세요: serviceKey, strtYymm, endYymm, HsSgn, sidoCd. HsSgn은 854232로 고정하고, 이천시는 시도 코드 41, 청주시는 시도 코드 43으로 요청하세요. serviceKey는 .env의 CUSTOMS_API_KEY에서 읽고 일반 인증키(Decoding)를 사용하세요.

4단계 - 수집 흐름과 경계 조건
월 입력을 먼저 검증하고, 형식이 틀리거나 시작월이 끝월보다 늦으면 ValueError를 발생시키세요. API 키가 없거나 공백뿐이면 관세청 요청 전에 RuntimeError("관세청 API 키가 없습니다")를 발생시키세요. 기간은 API의 12개월 제한을 고려해 YYYYMM 구간으로 나누고, 두 지역을 요청하세요. 응답에 totalCount와 페이지 정보가 있으면 마지막 페이지까지 수집하고, 같은 시도 코드가 중복되면 한 번만 요청하세요.

5단계 - 오류와 보안
연결 오류, timeout, HTTP 오류, XML 형식 오류, API 응답 오류 코드, 게이트웨이 오류는 모두 RuntimeError로 변환하세요. 오류 메시지는 "관세청 API 호출 실패: <지역>, <원인>" 형식을 사용하세요. URL, API 키, str(e)의 원문을 오류 메시지에 포함하지 말고, 필요한 예외 변환에는 from None을 사용하세요. 광범위한 try/except로 오류를 삼키거나 성공처럼 보이는 빈 결과로 대체하지 마세요.

6단계 - 구현 품질과 검증
Python 3.10 이상에서 동작하도록 타입 힌트와 한국어 docstring(설명, Args, Returns, Raises)을 작성하세요. requests 호출과 XML 파싱을 보조 함수로 분리해 monkeypatch 가능한 구조로 만드세요. 응답 필드명을 매핑하거나 지역·결측 필터를 적용하지 마세요. 실제 API 키와 네트워크를 테스트에 사용하지 말고, 입력 검증·요청 파라미터·기간 분할·페이지 처리·응답 파싱·오류 메시지 보안·collected_at을 mock 기반 pytest로 검증하세요.
```

### ④ 구현 결과

- 공개 함수: `fetch_regional_exports`
- 내부 보조 함수:
  - `_validate_months`
  - `_get_customs_api_key`
  - `_month_chunks`
  - `_index_to_param_ym`
  - `_fetch_customs_rows`
  - `_request_customs_xml`
  - `_parse_customs_page`
  - `_customs_api_error`
  - `_to_raw_exports_table`
- 주요 상수: API 주소, API 키 환경변수 이름, HS 코드, 시도 코드, 12개월 제한, 페이지 크기, 성공·데이터 없음 코드, timeout, 결과 열 이름

### ⑤ 코드 한 줄씩 점검 및 수정 내역

`data_loader.py`를 import·상수·공개 함수·입력 검증·기간 분할·요청·응답 파싱·결과 변환 순서로 점검했다.

1. 모듈 설명과 import
   - import된 모듈은 API 요청, XML 파싱, 날짜 기록, DataFrame 생성에 사용된다.
   - API 키는 환경변수에서만 읽으며 소스에 하드코딩하지 않는다.
2. 상수와 API 계약
   - API 주소, HS 코드, 시도 코드와 요청 제한을 상수로 분리했다.
   - 기존 주석의 정의되지 않은 `ALLOWED_REGIONS` 참조를 `clean_exports` 설명으로 수정했다.
3. `fetch_regional_exports`
   - 월 검증 → API 키 확인 → 지역·기간별 요청 → 원자료 표 생성 순서가 요구사항과 일치한다.
   - 응답 필터나 열 이름 변환을 하지 않고 `collected_at`만 추가한다.
4. 입력·기간 처리
   - ASCII `YYYY-MM`과 1~12월을 검증하고 역순 기간을 거부한다.
   - 12개월 단위 분할과 연도 경계를 확인했다.
5. 요청·오류 처리
   - timeout, HTTP 상태, 네트워크 예외, XML 파싱 실패를 명시적 RuntimeError로 변환한다.
   - 오류에는 URL, API 키, `str(e)` 원문을 넣지 않는다.
   - 성공 코드인데 `<body>`가 없는 응답은 데이터 없음으로 오인하지 않도록 `응답 형식 오류` RuntimeError를 발생시키도록 수정했다.
6. 응답·결과 처리
   - `item`의 자식 태그를 원래 키로 유지하고 값이 없는 필드는 빈 문자열로 둔다.
   - `totalCount`가 있으면 페이지를 반복하고, 없으면 첫 응답에서 종료한다.
   - 데이터 없음 응답은 빈 행 목록으로 처리하되 `collected_at` 열은 유지한다.

### ⑥ 테스트와 기록

- 테스트 파일: `신해성/test_data_loader.py`
- 실제 관세청 API와 API 키는 사용하지 않고 mock으로 검증했다.
- 성공 코드인데 body가 없는 응답을 거부하는 테스트를 추가했다.
- 실행 명령:

```powershell
python -m pytest -v 신해성/test_data_loader.py
```

- 수정 후 결과: **19 passed**
- 점검 항목: 월 입력·기간 분할, API 키, 요청 URL·변수·timeout, 시도 코드, XML 성공·오류 응답, 비정상 body, 페이지 반복, 원자료 열 보존, 민감정보 비노출

- 비고: 실제 API 응답 필드 이름, 시도 코드, 12개월 제한, 페이지 변수 지원 여부는 공공데이터포털 명세와 실제 응답으로 최종 확인해야 한다.

---

## 이다현
[모듈] compare_guidance (2026-11-03, 작성자: 이다현)
- 사용 도구: Gemini, GitHub Copilot Chat
- 
- 프롬프트:
- 당신은 파이썬 데이터 분석 코드 작성을 돕는 어시스턴트입니다. SK하이닉스 분기 매출 나우캐스팅 시스템의 분석 모듈(forecaster.py, 숫자 계산 전담)에 들어갈 함수를 구현해 주세요. 이 함수는 추정 매출의 전분기 대비 방향이 컨콜 가이던스가 가리키는 방향과 같은지 판정합니다.
- [함수 시그니처, 변경 금지] def compare_guidance(forecast: dict, guidance: dict) -> dict:
- [입력 명세] forecast: estimate_revenue 반환 dict (키: status, qoq_change_pct 등) / guidance: extract_guidance 반환 dict (키: status, price_outlook, dram_bit_growth_pct 등)
- [출력 명세] 키가 정확히 3개인 dict {"status": "일치"|"불일치"|"판단불가", "forecast_direction": "상승"|"보합"|"하락"|None, "guidance_direction": "상승"|"하락"|None}
- [계산 정의]
  -추정치 방향: forecast status가 "ok"일 때, qoq_change_pct > 2 이면 "상승", < -2 이면 "하락", 그 사이(±2 포함)면 "보합"
  -가이던스 방향: guidance status가 "ok"일 때, price_outlook이 "상승"이고 dram_bit_growth_pct가 0 이상(또는 None)이면 "상승". price_outlook이 "하락"이고dram_bit_growth_pct가 0 이하(또는 None)면 "하락". 그 외는 None
  -판정: 둘 중 하나라도 방향이 None이거나 추정치가 "보합"이면 "판단불가". 두 방향이 일치하면 "일치", 아니면 "불일치"
- [예외, 경계 방침] 어떤 경우에도 예외를 발생시키지 않는다. 입력이 누락되거나 비정상 값이 들어오면 "판단불가"로 반환한다.
- [제약 조건]
  - 방향 판정 경계값(2.0%)은 파일 맨 위 상수로 둔다 (DIRECTION_BAND_PCT = 2.0).
  - 입력 DataFrame/dict를 직접 수정하지 않고 새 dict를 반환한다.
  - 타입 힌트와 한국어 docstring 필수 작성. Raises는 없음.
- [통과해야 할 테스트] 직접 작성한 test_forecaster.py의 16개 파라미터 테스트 및 불변성/타입 방어 테스트 통과 필요.
- 생성 코드 위치: fb1612286abbf274ddf843b3928e57676768bc8c
- 코드 리딩에서 발견한 결함 (AI와의 설계 논의 과정 중 발견):
  1. 숫자가 아닌 불리언(True/False)이나 문자열이 들어올 경우 `q > 2` 등 비교 연산에서 `TypeError` 발생 가능성 존재.
  2. 값에 결측치(`NaN`)가 들어올 경우 크기 비교가 항상 `False`가 되어 "보합" 등 엉뚱한 값으로 오판정될 위험 존재.
  3. `forecast["status"]`와 같이 직접 접근할 경우 필수 키가 없는 비정상 입력 시 `KeyError` 발생 위험 존재 (어떤 경우에도 예외가 발생하면 안 된다는 규칙 위반).

| 번호 | 원본 방식 | 수정 코드 | 근거와 이유 |
| :--- | :--- | :--- | :--- |
| 1 | `forecast["status"]` 방식의 직접 접근 | `forecast.get("status") == "ok"` 방식으로 변경 | 딕셔너리에 키가 누락된 비정상 입력이 들어와도 `KeyError` 예외가 발생하지 않고 안전하게 처리하여 "판단불가"로 넘기기 위함. |
| 2 | `q > DIRECTION_BAND_PCT` 단순 비교 | `_is_valid_number(q)` 헬퍼 함수를 추가하여 검증 후 비교 | `NaN`이나 무한대, `True/False` 같은 비정상 타입이 들어와서 프로그램이 터지거나 오판정(보합)되는 것을 막기 위한 방어 로직. |
| 3 | `d >= 0` 단순 비교 | `d is None or (_is_valid_number(d) and d >= 0)` | 출하량 증감률(d) 값이 없어도 예외가 터지지 않게 하고, 확실히 유효한 숫자일 때만 상승/하락 조건에 반영하기 위함. |

- 테스트 결과: pytest 18 passed
- 비고:
  1. 구현 가이드의 "어떤 경우에도 예외를 내지 않는다"는 규칙을 준수하기 위해 `try-except`로 전체를 덮는 대신, `get()`과 `_is_valid_number()`를 활용해 타입 에러 자체를 원천 차단하는 방식으로 구현함.
  2. 추후 팀 통합 과정에서 방향 판정 경계값이 변경될 것을 대비해 DIRECTION_BAND_PCT = 2.0을 전역 상수로 분리하여 유지보수성을 높임.

[모듈] llm_module.py (extract_guidance 및 LLM 도우미) (2026-11-09, 작성자: 이다현)
- 사용 도구: Gemini, GitHub Copilot Chat
- 
- 프롬프트:
- 당신은 파이썬 데이터 분석 코드 작성을 돕는 어시스턴트입니다. SK하이닉스 분기 매출 나우캐스팅 시스템의 LLM 모듈(llm_module.py, 텍스트 입출력 전담)에 들어갈 함수를 구현해 주세요. 이 함수는 컨퍼런스콜 텍스트에서 다음 분기 출하가격 전망을 LLM으로 추출하여 guidance 형식으로 정리합니다.
- [함수 시그니처, 변경 금지] def extract_guidance(transcript_text: str) -> dict:
- [입력 명세] transcript_text: str (컨퍼런스콜 원문 텍스트)
- [출력 명세] guidance 형식 dict (키: status, target_quarter, dram_bit_growth_pct, nand_bit_growth_pct, price_outlook, hbm_comment, evidence)
- [계산 정의]
  - 빈 입력(None, 공백뿐) 처리: LLM을 부르지 않고 status를 "empty_input"으로 반환
  - LLM 응답이 JSON이 아니거나 해석 불가능한 경우: status를 "parse_error"로 반환
  - 정상 처리 시: 응답 값을 검증 및 정규화하여 status를 "ok"로 반환 (추출 실패는 "NA", 전망 없음은 "언급없음")
- [예외, 경계 방침] 어떤 경우에도 예외를 발생시키지 않는다. 파싱 실패나 규격 외 값은 status와 기본값으로 처리한다.
- [제약 조건]
  - LLM 호출은 내부 도우미 `_call_llm(prompt)` 한 곳에서만 수행한다.
  - schema.md 및 구현 가이드에 따라 mock 모드 전환은 상수 `USE_MOCK = True`로 관리한다.
  - mock 응답 시 hbm_comment와 evidence 문장 앞에 '[MOCK] ' 표식을 붙인다.
  - 입력 DataFrame/dict를 직접 수정하지 않고 새 dict를 반환한다 (호출마다 새로운 dict 생성).
  - 타입 힌트와 한국어 docstring 필수 작성. Raises는 없음.
- [통과해야 할 테스트] pytest 단위 테스트 (T12~T16) 및 형식 계약 검증 통과 필요.
- 코드 리딩에서 발견한 결함 (AI와의 설계 논의 과정 중 발견):
  1. `_call_llm`의 모드 스위치가 환경변수(`LLM_MODE`) 방식이었으나 최신 `schema.md` 규격에서 파일 상단 상수(`USE_MOCK = True`)로 변경됨에 따른 정비 필요.
  2. mock 응답의 사람이 읽는 문장 값(`hbm_comment`, `evidence`, 브리프 문장) 앞에 `"[MOCK] "` 표식이 누락될 경우 테스트 검증 통과 불가.
  3. 파이썬 기본 정규식 `\d` 사용 시 전각 숫자가 숫자로 오인식될 수 있어 ASCII 숫자(`re.ASCII`) 검증이 필요함.

| 번호 | 원본 방식 | 수정 코드 | 근거와 이유 |
| :--- | :--- | :--- | :--- |
| 1 | 환경변수 `os.getenv("LLM_MODE")` 분기 | 파일 맨 위 상수 `USE_MOCK = True` 사용 | `schema.md` 5.1절 규격에 맞춰 13주차 전환 전후를 상수 하나로 일관되게 제어하기 위함. |
| 2 | 원문 텍스트 문장을 그대로 반환하는 mock | `hbm_comment` 및 `evidence` 각 문장 앞에 `"[MOCK] "` 표식 추가 | `schema.md` 4.3절 및 5.1절에 따라 mock 응답임을 식별할 수 있도록 표식을 명시하기 위함. |
| 3 | 일반 `\d` 기반 정규식 매칭 | `re.ASCII` 플래그 및 `isascii()` 검사 추가 | 전각 숫자(`"２０２６"`) 등이 숫자로 잘못 인식되는 결함을 차단하여 데이터 계약을 엄격히 준수하기 위함.

- 테스트 결과: pytest passed (T12~T16 검증 완료)
- 비고:
  1. 구현 가이드 및 `schema.md`의 "어떤 경우에도 예외를 내지 않는다"는 원칙을 지키기 위해, `json.loads` 및 타입 검증 과정에서 발생하는 예외를 철저히 방어하여 `parse_error` 또는 기본값으로 안전하게 전환함.
  2. 모듈 수준의 단일 기본 dict를 재사용하면 앞선 호출의 값이 오염될 수 있으므로, 매 호출마다 새로운 dict를 생성하는 `_new_default_guidance()` 함수를 도입함
  
---

## 조현모

### [preprocess] clean_exports (2026-10-31, 작성자: 조현모)
- 사용 도구: GitHub Copilot Chat (VS Code, Copilot Free 플랜, 모델: auto)
  - 1차: Agent 모드로 전송됨 → 저장소 탐색 중(test_preprocess.py 읽음) 사용자가 중단
  - 2차: Ask 모드로 같은 프롬프트 재전송 → 응답 코드를 그대로 `조현모/preprocess.py`에 저장
  - 대화 기록: Export Chat(chat.json)으로 로컬 보관
- 프롬프트: (원문 전체)

```text
당신은 파이썬 백엔드 개발을 돕는 어시스턴트입니다.
SK하이닉스 분기 매출 나우캐스팅 시스템(알트 ALT)의 [모듈 2] preprocess.py에 들어갈 함수 clean_exports 하나만 구현해 주세요.
이 함수는 관세청에서 받은 이천시·청주시 메모리 반도체(HS 854232) 월별 수출 원자료를 정제합니다.

[함수 시그니처 — 변경 금지]
def clean_exports(raw_df: pd.DataFrame) -> pd.DataFrame:

[입력 명세]
raw_df: 수출 원자료 DataFrame. 필수 열(RAW_COLUMN_MAP으로 이름을 바꾼 뒤 기준): ym, region, hs_code, export_usd, collected_at
값 예시(지저분할 수 있음):
  {"ym": 202607, "region": "경기도 이천시", "hs_code": "854232", "export_usd": "5,000,000,000", "collected_at": "2026-09-15"}
  ym은 정수 202607, float 202607.0, 문자열 "2026-07"·"202607"·"2026.07"로 올 수 있다.

[출력 명세]
exports 표(DataFrame). 열은 정확히 5개, 이 순서: ym, region, hs_code, export_usd, collected_at
  - ym: "YYYY-MM" 문자열 / region: "이천시" 또는 "청주시" / hs_code: 문자열(숫자로 바꾸지 않음)
  - export_usd: float(달러, 0 이상) / collected_at: "YYYY-MM-DD" 문자열(수집일)
ym 오름차순으로 정렬하고 행 번호를 0부터 다시 매긴다.

[처리 순서 — Pseudocode]
함수 clean_exports — 입력: 수출 원자료 표(raw_df) / 출력: exports 표
    IF raw_df가 비어 있으면(행 0개)
        RETURN exports 표의 열 5개만 있는 빈 표
    표 = raw_df의 복사본
    RAW_COLUMN_MAP에 따라 원본 열 이름을 표준 열 이름으로 바꾼다(이미 표준 이름인 열은 그대로)
    IF ym, region, hs_code, export_usd, collected_at 중 없는 열이 있으면
        ValueError("필수 열 누락: <없는 열 이름들>")를 발생시킨다
    region = REGION_NAME_MAP에 따라 표준 이름으로 바꾼 값(예: "경기도 이천시" → "이천시")
    ym = YM_FORMATS 중 맞는 형식으로 읽어 "YYYY-MM" 문자열로 바꾼 값(어느 형식에도 안 맞으면 결측)
    hs_code = 문자열로 바꾼 값(앞자리 0 유지)
    export_usd = 숫자로 바꾼 값(바꿀 수 없으면 결측)
    ym 또는 export_usd가 결측인 행을 제거한다
    export_usd가 0보다 작은 행을 제거한다          # 0은 유효한 값이라 남긴다
    region이 ALLOWED_REGIONS에 없는 행을 제거한다
    키(ym, region, hs_code)가 같은 행은 collected_at이 가장 최근인 1행만 남긴다
        # collected_at이 빈 행은 가장 오래된 것으로 본다
    # 빠진 달은 0으로 채우지 않는다
    열을 ym, region, hs_code, export_usd, collected_at 순서로만 남긴다
    ym 오름차순으로 정렬하고 행 번호를 0부터 다시 매긴다
    RETURN 정제된 표

[예외·경계 방침]
- 빈 입력(0행, 열이 없는 빈 표 포함): 예외 없이 열 5개짜리 빈 표 반환. 필수 열 검사보다 먼저 한다.
- 필수 열 누락: ValueError("필수 열 누락: export_usd, ym")처럼 없는 열을 모두 적는다. ValueError는 이 경우에만 낸다.
- 지저분한 행(결측, "N/A"처럼 숫자로 바꿀 수 없는 값, 2026-13 같은 없는 달, 음수, 대상 외 지역)은 예외 없이 제거한다.
- export_usd = 0은 남긴다. 무한대는 결측으로 본다.
- 정제 후 남은 행이 없어도 열 5개짜리 빈 표를 반환한다.

[제약 조건 — 프로젝트 공통]
- Python 3.10 이상. 파이썬 표준 라이브러리와 pandas만 사용한다(numpy 직접 import 금지).
- 시그니처를 바꾸지 않는다. 보조 함수는 밑줄로 시작하는 내부 함수(예: _parse_ym)로 같은 파일에 만든다.
- 모든 함수에 타입 힌트와 한국어 docstring(설명, Args, Returns, Raises)을 단다.
- 가변 기본값 인자 금지. 전역 변수를 읽거나 바꾸지 않는다(파일 맨 위 대문자 상수는 읽기 전용으로 허용).
- 입력 DataFrame을 직접 수정하지 않는다. 복사본에서 작업한다.
- print 금지. 파일 읽기·쓰기, 외부 API 호출, 다른 프로젝트 모듈 import 금지.
- except: pass처럼 예외를 조용히 삼키지 않는다.

[제약 조건 — 함수별: clean_exports]
■ 자료구조: 반환 열은 정확히 5개, 위 순서. ym은 "YYYY-MM" 문자열, hs_code는 문자열, export_usd는 float.
■ 처리 방식: 키(ym, region, hs_code)가 같으면 collected_at이 가장 최근인 행만 남긴다(입력 순서와 무관하게).
■ 하지 말 것: 빠진 달을 0으로 채우지 않는다. 월·분기 합계를 계산하지 않는다(aggregate_quarterly의 역할).
■ 변경 대비: RAW_COLUMN_MAP(원본 열 → 표준 열, 지금은 빈 dict), REGION_NAME_MAP, ALLOWED_REGIONS = ("이천시", "청주시"),
  YM_FORMATS를 파일 맨 위 대문자 상수로 둔다.

[검증 기준 — 아래 테스트를 모두 통과해야 함(설계 문서 파트 4)]
기본값: hs_code "854232", collected_at "2026-09-15"
T01 [정상] ym 202608·이천시·5.5e9 / 202607·청주시·2.0e9 / 202607·이천시·5.0e9
     → 3행, ym = ["2026-07", "2026-07", "2026-08"], 열 5개
T02 [정상] 같은 키(2026-07·이천시·854232): collected_at 2026-08-15·5.0e9 / 2026-09-15·5.2e9
     → 1행, export_usd 5.2e9, collected_at "2026-09-15"
T03 [경계] 0행 빈 표 → 0행, 열 5개, 예외 없음
T04 [경계] export_usd 0(청주시), -1(이천시) → 청주시 0원 행 1개만 남음
T05 [예외] 정상 1행 + export_usd 빈칸 / "N/A" / ym "2026-13" / region "용인시" → 정상 1행만, 예외 없음
T06 [예외] export_usd 열이 없는 표 → ValueError, 메시지에 "export_usd" 포함

코드를 만든 뒤, 위 예외·경계 방침 각각이 코드의 어느 줄에서 처리되는지 짧게 설명해 주세요.
```

- 생성 코드 위치: 커밋 2c71515 (Copilot 생성 원본, 수정 없음)
- 원본 테스트 결과: pytest 19 passed. 1차 Agent 시도에서 Copilot이 테스트 파일을 읽었으므로 테스트에 맞춰진 코드일 수 있어 코드 리딩으로 추가 검증함
- 코드 리딩에서 발견한 결함 (강의 31쪽 체크리스트 기준, 각각 실행으로 확인):
  1) [하드코딩] `_parse_ym`이 형식마다 모양 검사를 직접 코딩하고 `else`를 "%Y.%m"으로 간주 → YM_FORMATS에 "%Y/%m"을 추가해도 "2026/07"이 None. 상수만 고치면 되도록 한 설계(변경 대비) 위반
  2) [경계·위험 관용구] `_parse_collected_at`이 `pd.to_datetime`에 형식 없이 날짜를 추측 → "03/04/2026"이 3월 4일, "2026"이 2026-01-01로 해석, UserWarning 발생
  3) [명세 불일치] 명세에 없는 "hs_code 결측 행 제거" 조건(`hs_code.notna()`)이 추가됨
  4) [경계] 최종 정렬이 ym만 기준 → 같은 달 행 순서가 수집일 순서에 따라 달라짐(결과가 입력에 의존)
  5) [설명 가능성] 모듈 docstring 없음, clean_exports docstring에 처리 규칙(0원 유지, 중복 규칙, 빈 달 미보충) 누락
  6) [불필요한 연산] 지역 처리 람다에서 `str(value).strip()`을 두 번 계산
- 수정 내역: 커밋 ceb1d1c
  1) 해석 결과를 같은 형식으로 다시 써서 원래 글자와 같은지 비교하는 방식으로 변경, YM_FORMATS에 "%Y/%m" 추가
  2) COLLECTED_AT_FORMAT = "%Y-%m-%d" 상수 추가 후 format 지정
  3) `hs_code.notna()` 조건 삭제(설계 문서·구현 가이드 명세대로)
  4) 정렬 키를 ["ym", "region", "hs_code"]로 고정
  5) 모듈 docstring 추가, clean_exports docstring에 처리 규칙 3줄 추가
  6) 내부 함수 `_normalize_region`으로 분리
  - 결함 확인과 수정 코드 작성에 Claude(Cowork)를 보조로 사용함. 수정 내용은 git diff로 직접 검토함
- 테스트 결과: pytest 19 passed (T01~T06 + 추가 X01~X11), `조현모/pytest_result.txt`
- 비고:
  - 시그니처 변경 없음
  - 테스트 X01~X11은 구현 가이드 1.2 '반드시 지킬 것'과 공통 제약을 검사하려고 추가함. 테스트 작성에 Claude(Cowork) 보조 사용
  - 담당자 재량으로 정한 것: YM_FORMATS 4종, REGION_NAME_MAP 2건, 천 단위 쉼표 제거, 무한대 = 결측, ALLOWED_HS_CODES 미적용
  - 팀 확인 필요: RAW_COLUMN_MAP 실제 값(관세청 API 명세 확정 후, 신해성), "2026-7"처럼 0이 빠진 월은 현재 제거됨

### [preprocess] upsert_records (2026-11-04, 작성자: 조현모)
- 사용 도구: Codex 작업본을 준비한 뒤 GitHub Copilot Chat에 코드 생성을 요청함. 첫 Copilot 응답은 기존 코드 설명 및 읽기 전용 안내였고, 두 번째 요청에서 함수 코드를 받아 preprocess.py에 반영함.
- 프롬프트 원문: 첫 요청은 `조현모/upsert_prompt.txt` 내용을 전달함(기존 함수 확인·읽기 전용 안내로 종료). 두 번째 요청은 아래 원문을 전달해 코드 답변을 받음.

```text
기존 preprocess.py에 함수가 있는 것은 알고 있습니다. 기존 코드의 존재 여부를 설명하거나 테스트 통과를 추측하지 말고, 아래 명세에 따라 upsert_records 함수의 새로운 구현 코드를 채팅 답변에 전체 코드 블록으로 작성해 주세요. 파일 수정 권한은 필요하지 않습니다.
함수 시그니처:
def upsert_records(store_df: pd.DataFrame, new_df: pd.DataFrame, key_cols: list[str]) -> pd.DataFrame:
요구사항:
- 기존 표와 새 표를 합치되 같은 키는 새 표의 행 전체로 교체
- 각 표 내부에 중복 키가 있으면 마지막 행 유지
- 열 없는 빈 표 허용
- key_cols가 비었거나, 행이 있는 표에 키 열이 없으면 ValueError
- 입력 DataFrame을 변경하지 않음
- pandas 사용, 한국어 docstring과 타입 힌트 포함
- clean_exports 코드는 작성하거나 변경하지 않음
출력:
1. upsert_records 함수의 실행 가능한 Python 코드 전체
2. 빈 표·키 누락·중복 키를 어떻게 처리했는지 짧은 설명
```
- 생성 코드 위치: 커밋 ed0d94c (Copilot 제안을 반영한 upsert_records 함수, 검토·수정 전 상태).
- 코드 리딩에서 발견한 결함: 구현 동작은 설계 계약과 일치. 새 테스트 3건이 설계에 없는 특정 ValueError 메시지 `키 열 누락:`까지 요구해 pytest가 27 passed, 3 failed였음.
- 수정 내용: `tests/test_upsert_records.py`의 메시지 정규식 검사 두 곳을 예외 타입 검사로 변경. 함수 구현은 수정하지 않음. 검토·테스트 기록 커밋 0bb38cc.
- 최종 테스트 결과: 기존 clean_exports 19건과 upsert_records 11건, pytest 30 passed. `조현모/pytest_result.txt`에 실행 결과 저장.
- 비고: 빈 키 목록 오류, 열 없는 빈 표 허용, 표 내부 중복의 마지막 행 선택은 설계문서의 빈칸을 채운 경계 방침. 시그니처 변경 없음.
