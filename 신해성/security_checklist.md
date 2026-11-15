# AI·데이터 보안 체크리스트

- 대상: `신해성/data_loader.py`, `신해성/preprocess.py`,
  `신해성/test_data_loader.py`, `신해성/test_preprocess.py`,
  `ai_log/haesung_*.md`
- 점검일: 2026-11-15
- 판정: 예 / 해당 없음

| 구분 | 번호 | 점검 항목 | 판정 | 근거 |
|---|---|---|---|---|
| 데이터 | S1 | 제출물에 실존 인물의 전화번호·이메일 등 PII가 없고 더미 데이터를 사용했는가 | 예 | 테스트 수출액·환율·XML은 직접 만든 더미 값이며 PII 열이 없다. |
| 데이터 | S2 | 외부 AI에 기업 기밀·타인 코드·PII를 입력하지 않았는가 | 예 | 프롬프트에는 함수 계약, 더미 데이터, 오류 조건만 사용했다. 실제 API 키와 실데이터는 포함하지 않았다. |
| 데이터 | S3 | 외부 데이터의 출처·라이선스를 확인하고 PII를 비식별 처리했는가 | 해당 없음 | 단위 테스트는 실제 외부 데이터가 아닌 mock 응답을 사용했다. 실제 관세청 통계 사용 시 공공데이터포털 출처를 표기한다. |
| 키 관리 | S4 | API 키·비밀번호를 소스에 하드코딩하지 않았는가 | 예 | `CUSTOMS_API_KEY`는 `.env` 환경변수에서 읽고 테스트에는 가짜 키만 사용했다. |
| 키 관리 | S5 | `.env`가 `.gitignore`에 등록되고 Git 추적에서 제외되었는가 | 예 | `.gitignore`의 `.env`, `.env.*` 규칙과 `git ls-files` 결과를 확인했다. `.env` 추적 파일은 없었다. |
| 키 관리 | S6 | 커밋 히스토리에 키가 노출되지 않았는가 | 예 | `git log --all`과 파일 이력에서 `.env` 및 실제 키 문자열의 커밋을 확인하지 못했다. |
| 키 관리 | S7 | 키·비밀 값을 print/log/스크린샷으로 전체 출력하지 않았는가 | 예 | 오류 메시지는 URL·키·`str(e)`를 제외하며 테스트와 기록에도 실제 키가 없다. |
| AI 사용 | S8 | AI 사용 내역과 채택·수정 사항을 기록했는가 | 예 | `ai_log/haesung_fetch_regional_exports.md`, `haesung_aggregate_quarterly.md`에 5개 필수 요소를 기록했다. |
| AI 사용 | S9 | LLM 기능이면 사용자 입력과 출력 형식을 검증했는가 | 해당 없음 | 두 대상 함수는 LLM을 실행하지 않는 API 수집·pandas 집계 함수다. |
| AI 사용 | S10 | LLM 시스템 프롬프트에 비밀 정보가 없는가 | 해당 없음 | 대상 함수에는 서비스 내부 LLM 시스템 프롬프트가 없다. |

## 확인 명령

```powershell
git ls-files --error-unmatch .env
git log --all -- .env
git log --all -S"CUSTOMS_API_KEY=" --oneline
```

위 명령에서 추적 파일·커밋·실제 키 노출이 확인되지 않았다. `.env.example`에는
변수 이름만 두고 실제 값은 넣지 않는다.

