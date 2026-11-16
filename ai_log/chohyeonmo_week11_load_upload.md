# 11주차 A구역 업로드와 입력 방어 과정 기록 (담당: 조현모)

- 대상: `alt_backend_week11/app.py`의 `load_upload()`, `_show_upload_error()`, `backend.py`의 `read_uploaded_csv()`, `import_exports()`
- 브랜치: `feat/upload-hyeonmo` / 사용한 AI: Claude (Claude 앱의 코드 작업 세션)
- 형식: 9, 10주차 아카이브와 같이 [초기 프롬프트 → 생성 코드 → 발견한 문제 → 수정 내역 → pytest·Git 로그 → 수동 검증] 순서
- 환경: Python 3.13, Streamlit 1.67.0, pandas 3.0 / data 폴더는 팀 채팅의 `fx.csv`와 저장소의 `actuals.csv` (API 키 없이 실행, LLM은 mock)

---

## 기록 1. 백엔드: 필수 열 누락 메시지에 collected_at이 섞이는 문제

### 1-1. 초기 프롬프트

```
너는 alt_backend_week11의 backend.py만 고치는 담당이다(이번 주 backend.py와 hynix_nowcast/는 조현모만 수정).

문제: collected_at 열이 없는 CSV를 올렸는데 필수 열(expUsdAmt)도 빠져 있으면
"필수 열 누락: export_usd (원자료 열: ..., collected_at)"처럼 사용자가 올리지 않은 collected_at이 나온다.

조건
- import_exports의 반환 dict(exports, raw_rows, clean_rows, added)와 저장 동작은 바꾸지 않는다.
- 고치기 전과 후의 정제 결과가 같은지 확인할 방법도 제시한다.
- pytest 테스트를 tests/에 추가한다. data_dir는 tmp_path로 넘겨 실제 data/exports.csv를 건드리지 않는다.
- 빈 파일, UTF-16 파일은 지금 영어 원문 오류(No columns to parse from file, 'cp949' codec can't decode...)가
  나온다. app.py가 except ValueError만 잡으므로 ValueError를 유지한 채 한국어 메시지로 바꾼다.
```

### 1-2. 생성 코드 (요지)

AI는 원인을 `import_exports`가 정제 **전에** `raw[collected_at] = 오늘`을 붙이는 데서 찾고, 다음 두 안을 냈다.

- 안 A: `clean_exports`가 낸 ValueError 메시지에서 `, collected_at` 문자열을 지워 다시 던지기
- 안 B: 정제를 원본(`raw_df`)으로 먼저 하고, 열이 없을 때만 정제 결과의 collected_at을 오늘 날짜로 채우기

```python
new_exports = preprocess.clean_exports(raw_df)
if data_loader.COLLECTED_AT_COLUMN not in raw_df.columns:
    new_exports[data_loader.COLLECTED_AT_COLUMN] = (today or date.today()).strftime("%Y-%m-%d")
```

`read_uploaded_csv`는 `EmptyDataError`, `UnicodeDecodeError`, `ParserError`를 잡아 `raise ValueError("빈 파일: ...") from exc` 형태로 바꾸는 코드를 냈다.

### 1-3. 발견한 문제와 판단

| # | 문제 | 어떻게 찾았나 | 판단 |
|---|---|---|---|
| 1 | 안 A는 메시지 문자열을 고치는 땜질이라, 사용자가 실제로 collected_at을 올린 경우에도 지워 버린다 | 코드 리딩 | 안 B 채택 |
| 2 | 안 B가 정제 결과를 바꾸지 않는지 근거가 없음. `clean_exports`는 collected_at으로 중복을 고르므로 순서가 바뀌면 결과가 달라질 수 있다 | `clean_exports` 본문 확인 | 고치기 전 결과를 pickle로 저장해 두고 고친 뒤 `assert_frame_equal`로 비교 → collected_at 있음/없음 두 경우 모두 동일 |
| 3 | AI 코드의 `not in raw_df.columns`는 열 이름 앞뒤 공백을 고려하지 않는다. `clean_exports`는 열 이름을 strip하므로 `" collected_at"` 열을 올리면 사용자의 수집일이 오늘로 덮인다 | `clean_exports`의 `rename(... strip())`과 비교 | strip한 열 이름 집합으로 확인하도록 수정 |
| 4 | 한국어 메시지에 "고치는 방법"까지 넣어서, 화면(app.py)의 안내와 같은 문장이 두 번 나왔다 | 수동 검증(아래 기록 2) | backend 메시지는 원인만 남기도록 두 번째 커밋으로 수정 |

### 1-4. 수정 내역

- `4b614e4` fix: collected_at을 정제 후에 채움, 공백 열 이름 대응, 빈 파일·인코딩·CSV 형식 오류를 한국어 ValueError로(`from exc`로 원래 예외 보존), 테스트 9개 추가
- `b3c27e6` fix: backend 메시지는 원인만 남기고 고치는 방법은 화면이 붙이도록 정리

| 입력 | 고치기 전 | 고친 뒤 |
|---|---|---|
| collected_at·expUsdAmt 없는 CSV | `(원자료 열: ..., sggNm, collected_at)` | `(원자료 열: ..., sggNm)` |
| 빈 파일 | `No columns to parse from file` | `빈 파일: 파일에 내용이 없습니다.` |
| UTF-16 파일 | `'cp949' codec can't decode byte 0xff ...` | `인코딩 오류: UTF-8과 cp949(엑셀 기본 CSV)로 모두 읽을 수 없습니다 (UTF-16 등).` |

### 1-5. pytest 결과

고치기 전에 테스트를 먼저 돌려 3개가 실패하는 것을 확인(`3 failed, 6 passed`)한 뒤 수정했다.

```
$ cd alt_backend_week11 && pytest -v tests
tests/test_upload_backend.py::test_missing_column_message_lists_only_uploaded_columns PASSED
tests/test_upload_backend.py::test_missing_column_message_keeps_uploaded_collected_at PASSED
tests/test_upload_backend.py::test_without_collected_at_fills_upload_date PASSED
tests/test_upload_backend.py::test_same_upload_twice_adds_nothing PASSED
tests/test_upload_backend.py::test_header_only_csv_returns_zero_clean_rows PASSED
tests/test_upload_backend.py::test_cp949_file_reads_same_as_utf8 PASSED
tests/test_upload_backend.py::test_empty_file_raises_korean_value_error PASSED
tests/test_upload_backend.py::test_utf16_file_raises_korean_value_error PASSED
tests/test_upload_backend.py::test_unreadable_errors_are_still_value_error_subclasses PASSED
============================== 9 passed in 0.55s ===============================
```

---

## 기록 2. 화면: load_upload() 구현

### 2-1. 초기 프롬프트

```
Streamlit app.py의 load_upload() 본문만 구현해 줘. 아래 docstring의 계약과 팀 규칙을 반드시 지킨다.

[계약] 반환 dict {"key": (파일 이름, 파일 크기), "raw": read_uploaded_csv 결과, "imported": import_exports 결과}.
업로드 전이거나 처리할 수 없는 파일이면 반환하지 않고 st.stop(). None을 돌려주지 않는다.

[할 일] 업로드 전 st.info 안내 후 st.stop / read_uploaded_csv → import_exports /
잘못된 파일은 ValueError를 잡아 st.error로 원인과 고치는 방법 후 st.stop /
같은 파일이면 다시 정제, 저장하지 않게 session_state 사용 / 정제 후 0행이면 st.warning

[팀 규칙] def 줄, import 줄, 맨 아래 실행 순서 구역은 고치지 않는다. app.py에서 pandas import와 표 가공 금지.
위젯 key와 session_state 키는 upload_ 접두어. session_state는 if "키" not in st.session_state: 관용구로 초기화.
예외는 필요한 종류만 잡는다(except Exception 금지). 구역은 st.subheader로 시작.
```

### 2-2. 생성 코드 (첫 초안, 그대로 보존)

```python
def load_upload() -> dict:
    uploaded = st.file_uploader("시군구별 수출 CSV를 끌어다 놓으세요", type="csv", key="upload_file")
    if uploaded is None:
        st.info("이천시, 청주시 월별 수출 CSV(priodTitle, sggNm, expUsdAmt 열)를 올려 주세요. 예시: samples/exports_normal.csv")
        st.stop()

    upload_key = (uploaded.name, uploaded.size)
    if st.session_state.get("upload_key") != upload_key:
        try:
            raw = backend.read_uploaded_csv(uploaded)
            imported = backend.import_exports(raw)
        except Exception as exc:
            st.error(f"파일을 처리하지 못했습니다: {exc}")
            st.stop()
        st.session_state["upload_key"] = upload_key
        st.session_state["upload_result"] = {"key": upload_key, "raw": raw, "imported": imported}

    upload = st.session_state["upload_result"]
    if upload["imported"]["clean_rows"] == 0:
        st.warning("정제 후 남은 행이 없습니다.")
    else:
        st.success(f"{upload['imported']['clean_rows']}행을 반영했습니다.")
    return upload
```

### 2-3. 발견한 문제

| # | 관점 | 문제 | 근거 |
|---|---|---|---|
| 1 | 안정성 | 프롬프트에서 금지했는데도 `except Exception`을 썼다. backend의 KeyError 같은 코드 실수까지 "파일 문제"로 안내해 원인을 숨긴다 | 팀 규칙, 11주차 강의 |
| 2 | Rerun 모델 | `st.session_state.get(...)`으로 대신해 초기화 관용구가 없다. 동작은 하지만 무엇을 세션에 두는지 한곳에서 보이지 않는다 | 11주차 강의 "초기화 관용구 누락" |
| 3 | 입력 방어 | 오류 안내가 backend 원문 한 줄뿐이라 고치는 방법이 없다. 빈 파일, UTF-16은 영어 원문이 그대로 나왔다 | 아래 수동 검증 ⑤⑥ |
| 4 | 문구 | 같은 파일을 다시 올려 새로 늘어난 행이 0이어도 st.success로 "68행을 반영했습니다"라고 성공을 강조한다. 늘어난 행은 C구역 지표가 보여 주므로 여기선 담담한 caption이 맞다 | 디자인 공통 규칙 |
| 5 | 문구 | 0행 경고가 "정제 후 남은 행이 없습니다"뿐이라 왜 없는지(이천시·청주시 HS 854232 행 없음), 아래 화면이 무엇을 그리는지 알 수 없다 | 화면 확인 |
| 6 | 공통 규칙 | 구역 시작 st.subheader가 없고, 업로드 창 help 툴팁이 없다 | 디자인 공통 규칙 |

보류한 것: key가 (파일 이름, 크기)라서 내용만 고치고 크기가 같은 파일은 같은 파일로 본다. `uploaded.file_id`를 쓰면 구분되지만, key 모양은 B, C, D가 믿는 계약이라 바꾸지 않고 12주차 UX 논의 때 제안하기로 했다.

### 2-4. 수정 내역

- `b0665c9` feat: 위 1~6 반영
  - `except ValueError`만 잡고 그 밖의 예외는 그대로 올라가게 함
  - `if "upload_key" not in st.session_state:` 관용구로 `upload_key`, `upload_result` 두 개만 초기화. 세션에 넣는 이유: 사이드바 필터를 움직일 때마다 스크립트 전체가 다시 실행되는데, 그때마다 같은 CSV를 다시 정제하고 `data/exports.csv`에 다시 저장하지 않기 위해서
  - 업로드 전 안내를 필요한 열 표(관세청 이름/한글 이름) + 샘플 위치 + 받는 곳으로 구성, 업로드 창에 help 툴팁
  - `_show_upload_error()`: backend 메시지 앞머리(필수 열 누락, 월·지역 형식 오류, 빈 파일, 인코딩 오류, CSV 형식 오류)로 고치는 방법을 골라 원인 한 줄 + 고치는 방법 + "저장하지 않았음"을 보여 줌
  - 0행이면 이유와 함께 st.warning. 저장된 자료가 있는지에 따라 "이전 자료로 그립니다" / "비어 있을 수 있습니다"를 나눔
- 디자인 의도: 업로드는 처음 한 번 보는 화면이라 "무엇을 올려야 하는지"를 표로 한눈에 보이게 하고, 실패했을 때는 원인과 다음 행동을 분리해 바로 고칠 수 있게 했다.
- `3b6c92c` feat: 역할 배분 문서 A구역 명령으로 `samples/exports_cp949.csv`, `samples/missing_column.csv` 생성 (강민규 수동 검증용)

### 2-5. 규칙 점검

| 항목 | 결과 |
|---|---|
| app.py에 pandas import, 표 가공 없음 | `grep "import pandas" app.py` 결과 없음. 0행 경고 문구 고를 때 `len(...)`만 사용 |
| def 줄, import 줄, 실행 순서 구역 변경 없음 | `git diff main -- alt_backend_week11/app.py`에서 A구역 함수 본문과 `_` 보조 함수만 바뀜 |
| key 접두어 | 위젯 `upload_file`, 세션 `upload_key`, `upload_result` |
| 반환 계약 | `{"key", "raw", "imported"}` 그대로, None 반환 경로 없음 |

### 2-6. 수동 검증 시나리오 결과

실제 `streamlit run app.py`를 띄우고 브라우저(Playwright로 조작)에서 파일을 올려 확인했다. 매번 새 세션이며, 화면 아래쪽 B, C, D구역은 아직 골격 상태다.

| # | 올린 파일 | 기대 | 관찰 | 결과 |
|---|---|---|---|---|
| ⓪ | 없음 | 안내만 보이고 아래는 비어 있음 | 필요한 열 표와 샘플 위치 안내, 아래 구역 없음 ([화면](img/chohyeonmo_week11/0_before_upload.png)) | 통과 |
| ① | samples/exports_normal.csv | 다른 구역이 그려짐 | "953행 중 68행을 반영" caption, 예상 매출 77.7조 원, 이천시·청주시 차트 ([화면](img/chohyeonmo_week11/1_normal.png)) | 통과 |
| ①-2 | ① 뒤 rerun 2번(R 키) | 다시 정제, 저장하지 않음 | `data/exports.csv` 수정 시각이 그대로 | 통과 |
| ② | samples/exports_cp949.csv | 정상 CSV와 같은 화면 | ①과 같은 행 수, 같은 지표 ([화면](img/chohyeonmo_week11/2_cp949.png)) | 통과 |
| ③ | samples/missing_column.csv | st.error 안내, 앱은 그대로 | "필수 열 누락: export_usd" + 고치는 방법, 빨간 예외 화면 없음 ([화면](img/chohyeonmo_week11/3_missing_column.png)) | 통과 |
| ④ | collected_at·expUsdAmt 없는 CSV | 원자료 열에 collected_at 없음 | `(원자료 열: ..., priodTitle, sggNm)` | 통과 (백엔드 수정 확인) |
| ⑤ | 빈 파일 | 한국어 안내 | "빈 파일: 파일에 내용이 없습니다." | 통과 |
| ⑥ | UTF-16 파일 | 한국어 안내 | "인코딩 오류: UTF-8과 cp949...로 모두 읽을 수 없습니다" ([화면](img/chohyeonmo_week11/6_utf16.png)) | 통과 |
| ⑦ | 이천시·청주시가 없는 CSV | st.error 안내 | "지역 형식 오류: sggNm 열에서 이천시, 청주시를 찾지 못했습니다 (값 예: ...)" | 통과 |
| ⑧ | 열 이름만 있는 CSV (빈 data 폴더) | st.warning, 앱은 그대로 | 0행 경고 + "저장된 자료도 없어 비어 있을 수 있습니다", 예상 매출 "확인 불가" ([화면](img/chohyeonmo_week11/8b_header_only_fresh.png)) | 통과 |
| ⑨ | 정상 → 열 누락 → 같은 정상 파일 (한 세션) | 실패 파일은 저장 안 함, 정상 파일은 캐시 사용 | 열 누락 때 오류 안내, exports.csv 그대로 / 정상 파일로 돌아오자 다시 정제하지 않고 지표 표시 | 통과 |

처음 돌렸을 때 ⑤⑥에서 "고치는 방법"이 backend 메시지와 화면 안내에 두 번 나왔다. 이를 기록 1의 문제 4로 고친 뒤 다시 돌린 결과가 위 표다.

### 2-7. Git 로그

```
$ git log --oneline main..feat/upload-hyeonmo
3b6c92c feat: 수동 검증용 cp949, 열 누락 샘플 CSV 추가
b0665c9 feat: 업로드 전 안내, 잘못된 CSV 안내, 같은 파일 재정제 방지 추가
b3c27e6 fix: 업로드 오류 메시지를 원인만 남기고 안내는 화면이 붙이도록 정리
4b614e4 fix: 업로드 CSV 오류 메시지 정리 (collected_at 혼입, 빈 파일, 인코딩)
```

이 과정 기록은 별도 `docs:` 커밋으로 올린다. `data/fx.csv`와 `.env`는 커밋하지 않았다(`git status`에서 fx.csv는 untracked로만 보임).

## README 담당(강민규)에게 전달

- session_state: A구역은 `upload_key`(마지막으로 처리한 파일의 이름과 크기), `upload_result`(그 파일의 업로드 결과) 두 개만 둔다. 필터를 움직일 때마다 스크립트가 다시 실행되어도 같은 CSV를 다시 정제하고 `data/exports.csv`에 다시 저장하지 않기 위해서다.
- .gitignore: 지금 루트 `.gitignore`에는 `data/forecasts.csv`만 있고 `data/exports.csv`, `data/fx.csv`, `data/raw_exports_last.csv`는 주석 처리돼 있다. 역할 배분 문서의 "생성 CSV 4개" 기준에 맞추려면 주석을 풀어야 한다.
