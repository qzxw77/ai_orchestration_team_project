# AI·데이터 보안 체크리스트 — forecaster.py · estimate_revenue

- 표기: ✅ 확인 완료 · ➖ 해당 없음(사유 기재)

## 1. 보안 체크리스트 (강의 3.6)

| 구분 | 번호 | 점검 항목 | 확인 | 근거 |
|---|---|---|---|---|
| 데이터 | S1 | 제출물에 실존 인물의 실명·전화번호·이메일 등 PII가 포함되지 않았다 (더미 데이터 사용) | ✅ | 테스트·명세의 수출액·환율·매출·날짜는 모두 가상 값(공통 입력 F). 작성자 표기는 과제 규정상 필요한 담당자 표시 |
| 데이터 | S2 | 외부 AI(챗봇·API)에 기업 기밀·타인 코드·PII를 입력하지 않았다 | ✅ | Copilot 프롬프트에는 함수 명세·가상 테스트 값만 포함. 다른 팀원의 코드는 입력하지 않음 |
| 데이터 | S3 | 외부 데이터 사용 시 출처·라이선스를 확인하고 PII 열을 비식별 처리했다 | ➖ | estimate_revenue는 실데이터를 읽지 않음(입력은 함수 인자로 받는 표). 테스트는 가상 값만 사용 |
| 키 관리 | S4 | API 키·비밀번호가 소스코드에 하드코딩되어 있지 않다 | ✅ | forecaster.py는 외부 API를 호출하지 않으며 키·비밀번호 문자열 없음 |
| 키 관리 | S5 | .env 파일이 .gitignore에 등록되어 있고, git ls-files 확인 결과 추적되지 않는다 | ✅ | 루트 `.gitignore`에 `.env`, `.env.*`, `.venv/`, `__pycache__/` 등록 확인. |
| 키 관리 | S6 | 커밋 히스토리에 키가 노출된 적이 없다 (노출 시 폐기·재발급 완료를 명기) | ✅ | 키를 사용하는 작업이 없었음.  |
| 키 관리 | S7 | 키·비밀 값을 print/log/스크린샷으로 전체 출력하지 않았다 | ✅ | forecaster.py에 print·로그 출력 없음(팀 규칙). 공유한 터미널 화면에 키 없음 |
| AI 사용 | S8 | AI 사용 내역(프롬프트·채택·수정)을 과제 규정에 따라 기록·첨부했다 | ✅ | `신동훈/prompt_log.md`에 프롬프트 원문, 생성 커밋 `c681b9d`, 결함 5건, 수정 커밋 `74b0de4`·`2aa330c`·`e382473` |
| AI 사용 | S9 | (LLM 기능 포함 시) 사용자 입력 검증과 출력 검증(형식 확인)을 적용했다 | ➖ | estimate_revenue는 LLM을 사용하지 않는 숫자 계산 함수(LLM 기능은 llm_module.py 담당) |
| AI 사용 | S10 | (LLM 기능 포함 시) 시스템 프롬프트에 비밀 정보를 포함하지 않았다 | ➖ | 위와 같은 사유로 해당 없음 |



## 3. 확인 결과 (S5·S6)

저장소 최상위에서 실행한 결과를 붙인다.

S5 — .env 등이 무시되고 추적되지 않음

> git check-ignore -v .env .venv/ __pycache__/ 신동훈/.venv/
```python
.gitignore:2:.env       .env
.gitignore:11:.venv/    .venv/
.gitignore:16:__pycache__/      __pycache__/
.gitignore:11:.venv/    "\354\213\240\353\217\231\355\233\210/.venv/"
```

> git ls-files | Select-String -Pattern "\.env|\.venv|__pycache__"

-> 아무것도 나타나지 않음

S6 — 커밋 히스토리에 키 노출 없음

> git log -p -- 신동훈/ | Select-String -Pattern "API_KEY|SECRET|PASSWORD|sk-"
-> 아무것도 나타나지 않음

---


---

# AI·데이터 보안 체크리스트 (10주차) — data_loader.py · load_actuals / forecaster.py · estimate_revenue 리팩터링

- 표기: ✅ 확인 완료 · ➖ 해당 없음(사유 기재)

## 1. 보안 체크리스트 (강의 3.6)

| 구분 | 번호 | 점검 항목 | 확인 | 근거 |
|---|---|---|---|---|
| 데이터 | S1 | 제출물에 실존 인물의 실명·전화번호·이메일 등 PII가 포함되지 않았다 (더미 데이터 사용) | ✅ | 테스트의 매출·발표일은 공통 입력 F와 같은 가상 값. actuals 표 열(quarter·revenue_krw·announced_date)에 개인정보 없음 |
| 데이터 | S2 | 외부 AI(챗봇·API)에 기업 기밀·타인 코드·PII를 입력하지 않았다 | ✅ | Copilot 프롬프트에는 함수 명세와 가상 CSV(공통 파일 G)만 포함. 실제 `data/actuals.csv` 내용과 다른 팀원 코드는 입력하지 않음 |
| 데이터 | S3 | 외부 데이터 사용 시 출처·라이선스를 확인하고 PII 열을 비식별 처리했다 | ✅ | load_actuals가 읽는 실적 CSV의 출처는 DART 공시(공개 자료)이며 PII 열 없음. 테스트 CSV는 pytest `tmp_path`에 생성되어 저장소에 남지 않음 |
| 키 관리 | S4 | API 키·비밀번호가 소스코드에 하드코딩되어 있지 않다 | ✅ | load_actuals는 로컬 CSV만 읽고 외부 API를 호출하지 않음. data_loader.py·forecaster.py에 키·비밀번호 문자열 없음 |
| 키 관리 | S5 | .env 파일이 .gitignore에 등록되어 있고, git ls-files 확인 결과 추적되지 않는다 | ✅ | 아래 3절 실행 결과 |
| 키 관리 | S6 | 커밋 히스토리에 키가 노출된 적이 없다 (노출 시 폐기·재발급 완료를 명기) | ✅ | 모든 브랜치 히스토리에서 `.env` 커밋 이력 없음. 아래 3절 실행 결과 |
| 키 관리 | S7 | 키·비밀 값을 print/log/스크린샷으로 전체 출력하지 않았다 | ✅ | print·로그 출력 없음. 오류 메시지에는 CSV의 분기·매출·날짜 값만 표시(비밀 값 아님) |
| AI 사용 | S8 | AI 사용 내역(프롬프트·채택·수정)을 과제 규정에 따라 기록·첨부했다 | ✅ | `prompt_log.md`와 `ai_log/`에 기록. load_actuals: 테스트 `521f13a` → 생성본 `7c4af18` → 수정 `2b9acaa`·`10f0088`·`d8f5090`·`d791b97` → 회귀 테스트 `f24931f`. estimate_revenue 리팩터링: `e382473` |
| AI 사용 | S9 | (LLM 기능 포함 시) 사용자 입력 검증과 출력 검증(형식 확인)을 적용했다 | ➖ | LLM 미사용 함수. 참고로 load_actuals는 사람이 입력한 CSV를 형식 검증함(한국어 ValueError) |
| AI 사용 | S10 | (LLM 기능 포함 시) 시스템 프롬프트에 비밀 정보를 포함하지 않았다 | ➖ | 위와 같은 사유로 해당 없음 |

## 3. 확인 결과 (S5·S6)

저장소 최상위에서 실행한 결과를 붙인다.

S5 — .env 등이 무시되고 추적되지 않음

> git check-ignore -v .env .venv/ __pycache__/ 신동훈/.venv/ 신동훈/__pycache__/
```
.gitignore:2:.env       .env
.gitignore:11:.venv/    .venv/
.gitignore:16:__pycache__/      __pycache__/
.gitignore:11:.venv/    "\354\213\240\353\217\231\355\233\210/.venv/"
.gitignore:16:__pycache__/      "\354\213\240\353\217\231\355\233\210/__pycache__/"
```

> git ls-files | Select-String -Pattern "\.env|\.venv|__pycache__"

-> 아무것도 나타나지 않음

S6 — 커밋 히스토리에 .env·키 노출 없음

> git log --all --oneline -- .env "**/.env"

-> 아무것도 나타나지 않음

> git log --all -p -- 신동훈/ | Select-String -Pattern "API_KEY|SECRET|PASSWORD|sk-"

-> 아무것도 나타나지 않음