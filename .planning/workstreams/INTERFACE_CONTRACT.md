# Phase 2 Workstream Interface Contract

**팀원 A (feature/search-infra) → 팀원 B (feature/extraction-logic) 경계**
**최종 승인:** 2026-05-13

## 두 워크스트림이 만나는 지점

```
search_engine.py          scraper.py             extractor.py
──────────────────        ──────────────         ──────────────────
collect_search_results()  fetch_page_text()  →   extract_candidate_details()
        │                        │                       │
   SearchResult 객체         page_text (str)        Candidate dict
   (verified=True만)        최대 12,000자
```

## SearchResult 객체 스펙 (팀원 A 생산)

```python
{
    "query": str,
    "title": str | None,
    "url": str | None,           # verified=True이면 반드시 존재
    "snippet": str | None,
    "source_type_hint": str,     # VALID_SOURCE_TYPES 중 하나
    "verified": bool,            # True = SerpAPI 실제 URL, False = LLM plan only
}
```

**팀원 A 보장:**
- `verified=True`인 결과만 `fetch_page_text()` 대상
- `verified=False` 결과는 Phase 3 후보로 승격하지 않음
- `source_type_hint`는 항상 `VALID_SOURCE_TYPES` 중 하나 (unknown 포함)

## page_text 스펙 (팀원 A → 팀원 B)

| 항목 | 규칙 |
| --- | --- |
| 최대 길이 | `DEFAULT_PAGE_TEXT_LIMIT = 12,000자` (`scraper.py` 절삭) |
| 빈 문자열 | fetch 실패 또는 본문 없음 — 팀원 B는 건너뜀 |
| 인코딩 | HTML Content-Type charset 기반, fallback UTF-8, 오류 `?` 치환 완료 |
| HTML | 태그 제거 완료, script/style 제거 완료, 공백 정규화 완료 |
| JS 렌더링 | 현재 미지원 — JS로만 렌더되는 가격은 추출 불가 (알려진 한계) |

## Candidate dict 스펙 (팀원 B 생산)

`extractor.py:_normalize_extracted_details()` 출력 기준:

```python
{
    "vendor_name": str | None,
    "price_krw": int | None,         # KRW 환산 완료
    "raw_price_text": str | None,    # 원문 가격 표기
    "listed_price": float | None,
    "listed_currency": str | None,   # SUPPORTED_PRICE_CURRENCIES 중 하나
    "lead_time_days": int | None,    # 일(day) 단위로 통일
    "moq": int | None,
    "location": str,                 # 'Domestic' | 'Overseas' | 'Unknown'
    "source_type": str,              # VALID_SOURCE_TYPES 중 하나
    "price_listed": bool,
    "stock_listed": bool,
    "leadtime_listed": bool,
    "spec_text": str | None,
    "spec_evidence": str | None,
}
```

## page_text 절삭 기준 합의

- 절삭 위치: `scraper.py:fetch_page_text()` 에서 `text[:max_chars]`로 앞부분 유지
- 근거: 대부분의 상품 페이지는 가격/재고/납기 정보가 상단에 집중
- 팀원 B는 절삭된 텍스트를 그대로 사용 — 추가 절삭 없음
- 만약 12,000자 이후에 중요한 정보가 있다고 판단되면 팀원 A에게 `DEFAULT_PAGE_TEXT_LIMIT` 증가 요청

## 변경 요청 프로세스

1. 이 문서를 먼저 업데이트
2. 영향받는 워크스트림 WORKSTREAM.md 반영
3. `tests/test_phase2_contract.py`에 회귀 케이스 추가
