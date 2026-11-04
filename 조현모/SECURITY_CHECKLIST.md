# AI·데이터 보안 체크리스트 (5주차 첨부 1호) — 9주차 clean_exports

대상 제출물: `조현모/` 폴더 (preprocess.py, tests/, README.md), 루트 `prompt_log.md`의 조현모 항목
작성자: 조현모 · 확인일: 2026-10-31

> 아래 확인 명령 3개의 결과로 S5·S6을 최종 확인했다.

| 구분 | 번호 | 점검 항목 | 확인 | 근거·비고 |
|---|---|---|---|---|
| 데이터 | S1 | 제출물에 실존 인물의 PII가 없다 (더미 데이터 사용) | ☑ | 테스트 데이터는 가상의 지역·금액 값뿐. 개인 정보 열 없음 |
| 데이터 | S2 | 외부 AI에 기업 기밀·타인 코드·PII를 입력하지 않았다 | ☑ | Copilot·Claude 프롬프트에는 설계 문서의 함수 명세와 가상 테스트 값만 넣음. 실데이터·키 입력 없음 |
| 데이터 | S3 | 외부 데이터 사용 시 출처·라이선스를 확인했다 | ☑ | 이번 커밋에는 실데이터 없음. 관세청 데이터는 공공누리 공개 데이터(연동 시 출처 표기) |
| 키 관리 | S4 | API 키가 코드에 하드코딩되어 있지 않다 | ☑ | clean_exports는 API를 호출하지 않음(키 사용 없음) |
| 키 관리 | S5 | `.env`가 `.gitignore`에 등록되어 있고 추적되지 않는다 | ☑ | 루트 `.gitignore`에 `.env`, `.env.*` 등록. 저장소에 .env 파일 없음 |
| 키 관리 | S6 | 커밋 히스토리에 키가 노출된 적이 없다 | ☑ | 조현모/ 커밋 3개(9c6a9f2, 2c71515, ceb1d1c)에 키 없음 |
| 키 관리 | S7 | 키·비밀값을 print/log/스크린샷으로 출력하지 않았다 | ☑ | print 사용 없음 |
| AI 사용 | S8 | AI 사용 내역(프롬프트·채택·수정)을 기록했다 | ☑ | 루트 `prompt_log.md` 조현모 섹션, Copilot 대화 Export 보관 |
| AI 사용 | S9 | (LLM 기능 포함 시) 입력·출력 검증을 적용했다 | ☑ (해당 없음) | clean_exports는 LLM을 쓰지 않음 |
| AI 사용 | S10 | (LLM 기능 포함 시) 시스템 프롬프트에 비밀 정보가 없다 | ☑ (해당 없음) | 해당 없음 |

확인 명령 (PowerShell, 저장소 최상위에서):

```powershell
git check-ignore -v .env                 # .gitignore:N:.env 가 나오면 정상
git ls-files | Select-String "\.env"     # 아무것도 안 나와야 정상
git log -p -- 조현모/ | Select-String -Pattern "API_KEY|sk-"   # 아무것도 안 나와야 정상
```

## 10주차 재점검 (2026-11-04)

- S1~S4, S7~S10: 본인 담당 `clean_exports`·`upsert_records`, 테스트 3개와 `ai_log/chohyeonmo_*.md`를 재확인했다. 입력은 가상 값이며 API 호출·LLM 호출·키 출력이 없다. 앞 표의 표시를 그대로 적용한다.
- S5: `.gitignore`의 `.env` 규칙을 `git check-ignore -v .env`로 확인했다. 현재 추적 파일 목록에 `.env`가 없다.
- S6: `git log --all --name-only`로 모든 로컬 참조의 커밋 파일명을 확인했다. `.env` 또는 `.env.*` 커밋은 없고 `week05/.env.example`만 있다. 이 검사는 파일명 기준이며 비밀값 내용 전체를 보증하지 않는다.
- 실제 API·LLM 연동과 팀 전체 저장소 보안 점검은 각 담당 모듈 통합 시 다시 수행해야 한다.
