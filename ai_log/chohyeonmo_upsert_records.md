## [2026-11-04] upsert_records 경계 리팩터링 (담당: 조현모)

- 대상 모듈: `조현모/preprocess.py` / 관련 커밋: Copilot 생성본 `ed0d94c` → 테스트 검토 `0bb38cc` → 리팩터링 `2e9dcff`.
- 초기 프롬프트(요지): 기존 행과 새 행을 키 기준으로 병합해 새 행을 우선하고, 빈 표·키 누락을 처리하도록 Copilot Chat에 요청했다. 첫 요청 초안과 실제 코드 생성 요청 원문은 최상위 `prompt_log.md`에 구분해 기록했다. Codex가 준비한 초기 작업본을 참고했다.
- AI 생성 결과: Copilot 코드가 `pd.concat` 후 `drop_duplicates(keep="last")`로 새 행을 우선했다. 생성본은 `ed0d94c`에 보존했다.
- 발견한 문제: 첫 pytest에서 3건은 테스트가 설계에 없는 오류 메시지까지 고정해 실패했다. 이후 10주차 경계 검토에서 `DataFrame.empty`가 열 0개·행 1개에도 참이어서, 키 열 누락을 놓치는 문제를 새 테스트로 재현했다(수정 전 1 failed, 2 passed).
- 수정 내역: `0bb38cc`에서 테스트를 `ValueError` 타입 계약에 맞췄다. `2e9dcff`는 Copilot 코드의 모호한 `.empty` 판정을 `len(frame)` 행 수 검사로 바꾸고, 전처리 경계 테스트를 추가한 별도 `refactor:` 커밋이다. **가독성·정확성**을 함께 개선했으며 다른 함수 시그니처는 유지했다.
- 검증: 10주차 본인 폴더 `pytest 33 passed`(기존 30개 + 새 경계 3개). 실행 로그는 `조현모/pytest_result_10w.txt`에 보존한다.
- 판단 메모: pandas의 `.empty`는 ‘행 0개’와 다르다. 다음 프롬프트에는 빈 입력을 행 수로 정의하고, 열 없는 1행 표도 키 검증 사례에 넣는다.
