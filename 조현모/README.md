# 조현모 — preprocess.py / clean_exports (★1 핵심)

담당: [모듈 2] 전처리 `clean_exports(raw_df: pd.DataFrame) -> pd.DataFrame`
책임: 수출 원자료를 정제해 결측·음수·대상 외 지역·중복 행이 없는 exports 표로 만든다.
근거: 설계 문서 V1 파트 2·3·4(T01~T06), 알트(ALT) 구현 가이드 1.2

## 파일

| 파일 | 내용 |
|---|---|
| `preprocess.py` | clean_exports 구현 (다른 함수는 각 담당자 브랜치에서 합침) |
| `tests/test_preprocess.py` | 설계 문서 T01~T06 + 구현 가이드 기반 추가 테스트 X01~X11 |
| `conftest.py` | pytest가 이 폴더를 import 경로에 넣도록 하는 빈 설정 파일 |
| `SECURITY_CHECKLIST.md` | 5주차 보안 체크리스트 |
| `pytest_result.txt` | 최종 pytest 실행 결과 |

## 실행

```powershell
cd 조현모
python -m pip install -r requirements.txt
python -m pytest -v | Tee-Object pytest_result.txt
```

## 처리 규칙 요약

| 상황 | 처리 |
|---|---|
| 0행 입력 | 열 5개짜리 빈 표 반환 (예외 없음) |
| 필수 열 누락 | `ValueError("필수 열 누락: ...")` — 유일한 예외 |
| 결측·숫자 아님·없는 달·음수·대상 외 지역 | 행 제거 (예외 없음) |
| export_usd = 0 | 유지 |
| 같은 키 중복 | collected_at 최신 1행 (빈 수집일 = 가장 오래됨) |
| 빠진 달 | 채우지 않음 |

## 팀 확인 필요 (카톡방 질문용)

1. `RAW_COLUMN_MAP` 실제 값: 관세청 API 응답 열 이름이 확정되면 신해성님과 맞춰 채움 (현재 빈 dict).
2. `ALLOWED_HS_CODES`(854232 외 행 거르기) 추가 여부: 현재 넣지 않음(구현 가이드상 담당자 재량).
3. `"2026-7"`처럼 0이 빠진 월은 애매한 값으로 보고 제거함 — 관세청 응답 형식 확인 후 필요하면 YM_FORMATS 조정.
