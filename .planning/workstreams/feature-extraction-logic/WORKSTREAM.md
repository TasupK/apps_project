# Workstream: feature/extraction-logic

**담당:** 팀원 B — The Parser
**연결 Phase:** Phase 2 (Web Research Agent & Source Collection)
**상태:** In Progress
**생성:** 2026-05-13

## 목표

수집된 날것의 텍스트에서 가격, 납기, 재고 정보를 정확하게 뽑아내고 Phase 2 JSON 스키마에 맞게 검증하는 것.
Phase 2 파이프라인에서 "데이터를 정제하고 검증하는" 후반부 책임.

## 주요 파일

| 파일 | 역할 |
| --- | --- |
| `agents/web_research/extractor.py` | heuristic 파싱, LLM 결과 병합, KRW 환산 |
| `agents/web_research/validator.py` | Phase 2 JSON 스키마 계약 검증 |
| `agents/web_research/llm_client.py` (추출부) | `extract_candidate_details_with_llm()` |
| `agents/web_research/config.py` | `DETAIL_EXTRACTION_PROMPT`, `DETAIL_RESPONSE_SCHEMA` |

## 세부 작업

### 1. Heuristic 추출 로직 고도화
- **현황:** `_extract_price_fields()`는 USD/KRW/EUR 패턴 처리 (`extractor.py:146-167`)
- **목표:**
  - JPY (`¥`, `円`), CNY (元), GBP (`£`) 추가
  - `SUPPORTED_PRICE_CURRENCIES = {"KRW","USD","EUR","JPY","CNY","GBP","CAD","AUD"}` 중 미지원 패턴 커버
  - 납기 패턴: `D+영업일`, `주(週)` 단위 → 일수 변환 (`_extract_lead_time_days()` 확장)
  - MOQ: `1pc`, `1개`, `1ea` 형태 포함 (`_extract_moq()` 확장)
- **파일:** `extractor.py:_extract_price_fields()`, `_extract_lead_time_days()`, `_extract_moq()`

### 2. LLM 추출 프롬프트 튜닝
- **현황:** `DETAIL_EXTRACTION_PROMPT`는 기본 규칙 존재, 긴 페이지에서 스펙 요약 품질 불균일
- **목표:**
  - 스펙 일치 여부 판단을 `spec_evidence`에 근거 문장으로 명시하도록 프롬프트 강화
  - 상업적 조건 (MOQ, 납기, 재고 여부)을 페이지에서 직접 인용하도록 지시 추가
  - 긴 텍스트 입력 시 LLM이 앞부분(가격/재고 정보 집중 구간)을 우선 보도록 가이드
- **파일:** `config.py:DETAIL_EXTRACTION_PROMPT`

### 3. 데이터 정규화
- **현황:** `_normalize_extracted_details()`에서 KRW 환산 처리 (`extractor.py:71-94`)
- **목표:**
  - `get_exchange_rate_to_krw()` 실패 시 fallback rate 캐시 또는 명시적 에러 로깅
  - `lead_time_days` 주→일 변환 multiplier 확인 (현재 ×7, 주 5영업일 기준으로 변경 검토)
  - `min_price_krw` 계산 (`_apply_min_price()`)이 후보 목록 전체에 걸쳐 정확히 적용되는지 확인
- **파일:** `extractor.py:get_exchange_rate_to_krw()`, `_apply_min_price()`

### 4. Phase 2 JSON 스키마 계약 검증
- **현황:** `validate_candidate_results()`는 필수 필드 존재 여부 + 타입 체크 수행 (`validator.py`)
- **목표:**
  - `CANDIDATE_REQUIRED_FIELDS`가 `DETAIL_RESPONSE_SCHEMA`와 완전히 일치하는지 교차 검증
  - `spec_text`, `spec_evidence` null이 아닌 유의미한 값인지 검사 추가 (현재는 필드 존재 여부만)
  - 계약 위반 시 에러 메시지에 후보 `candidate_id` + 위반 필드명 포함
- **파일:** `validator.py:validate_candidate_results()`, `_validate_candidate()`

## 팀원 A로부터 받는 인터페이스 (계약)

팀원 A가 전달하는 **page_text** 규칙:
- 타입: `str` (최대 12,000자, `DEFAULT_PAGE_TEXT_LIMIT`)
- 빈 문자열 `""` 가능 — fetch 실패 또는 내용 없음 의미
- 인코딩 오류는 `?`로 치환 완료된 상태
- HTML 태그 제거 완료, 공백 정규화 완료

**처리 원칙:**
- `page_text.strip() == ""`이면 추출 건너뜀 → 전체 필드 `null` / `false`
- LLM 추출이 RuntimeError이면 `llm_details = {}` — heuristic 결과만 사용
- heuristic + LLM 병합 순서: LLM primary, heuristic fallback (`_merge_extraction_details()`)

## 테스트 전략

```bash
# Phase 2 계약 테스트
PYTHONPATH=. python -m unittest tests/test_phase2_contract.py

# heuristic 파서 직접 테스트
PYTHONPATH=. python -c "
from agents.web_research.extractor import extract_candidate_details_from_text
sample = '재고: 재고 있음 납기: 3일 가격: ₩15,000 MOQ: 10개'
import json; print(json.dumps(extract_candidate_details_from_text(sample), ensure_ascii=False, indent=2))
"

# 환율 변환 테스트
PYTHONPATH=. python -c "
from agents.web_research.extractor import get_exchange_rate_to_krw
print('USD->KRW:', get_exchange_rate_to_krw('USD'))
print('JPY->KRW:', get_exchange_rate_to_krw('JPY'))
"
```

## 완료 기준

- [ ] JPY/CNY/GBP 가격 패턴 heuristic 파싱 통과
- [ ] `lead_time_days` 주 단위 변환 로직 검토 완료 (×7 유지 또는 ×5 변경)
- [ ] `spec_evidence` 필드에 페이지 인용 근거 문장 포함 확인
- [ ] `validate_candidate_results()` 에러 메시지에 `candidate_id` 포함
- [ ] `test_phase2_contract.py` 전체 통과
