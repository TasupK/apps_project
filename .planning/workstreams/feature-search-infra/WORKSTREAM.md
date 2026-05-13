# Workstream: feature/search-infra

**담당:** 팀원 A — The Collector
**연결 Phase:** Phase 2 (Web Research Agent & Source Collection)
**상태:** In Progress
**생성:** 2026-05-13

## 목표

검색 결과의 양과 질을 확보하고, 웹페이지 텍스트를 안정적으로 긁어오는 것.
Phase 2 파이프라인에서 "데이터를 구해오는" 전반부 책임.

## 주요 파일

| 파일 | 역할 |
| --- | --- |
| `agents/web_research/search_engine.py` | 검색 쿼리 실행, 결과 정규화, 랭킹 |
| `agents/web_research/scraper.py` | URL fetch, HTML 파싱, 텍스트 추출 |
| `agents/web_research/llm_client.py` (쿼리 생성부) | `generate_query_candidates()` — LLM 쿼리 플래닝 |
| `agents/web_research/config.py` | `QUERY_GENERATION_PROMPT`, `QUERY_RESPONSE_SCHEMA` |

## 세부 작업

### 1. 쿼리 플래닝 고도화
- **현황:** `generate_query_candidates()`는 `search_keywords` 배열을 그대로 연결하는 deterministic 방식 + LLM 방식 지원
- **목표:** LLM이 생성하는 쿼리에 국내 대리점용 (`site:*.kr`, `대리점`, `국내`) + 대체품용 (`replacement`, `alternative`, `대체품`) 쿼리를 더 정교하게 섞도록 프롬프트 개선
- **파일:** `config.py:QUERY_GENERATION_PROMPT` 튜닝, `llm_client.py`의 쿼리 생성 함수

### 2. SerpAPI 광고 필터링
- **현황:** `_search_with_serpapi()`는 `organic_results`만 사용 — 광고(ads) 필드는 이미 제외됨
- **목표:** 추가로 `shopping_results`, `knowledge_graph` 등 비유기적 결과 혼입 방지 + `position` 기반 상위 결과 우선 확인
- **파일:** `search_engine.py:_search_with_serpapi()`

### 3. 스크레이핑 안정화
- **현황:** `fetch_page_text()`는 `urllib` + `HTMLParser` 기반, JS 렌더링 대응 없음, charset은 Content-Type에서만 추론
- **목표:**
  - `<meta charset>` / `<meta http-equiv="Content-Type">` fallback 추가
  - 타임아웃/재시도 로직 추가 (현재 단일 시도)
  - 응답이 JSON인 경우 (SPA API 응답 등) 텍스트 변환 처리
  - 최대 본문 길이 `DEFAULT_PAGE_TEXT_LIMIT=12000` 도달 시 앞부분 밀도 있는 콘텐츠 우선 절삭 전략 검토
- **파일:** `scraper.py:fetch_page_text()`

## 팀원 B와의 인터페이스 (계약)

팀원 A가 생산하는 **SearchResult 객체** 형태:

```python
{
    "query": str,           # 사용된 검색 쿼리
    "title": str | None,
    "url": str | None,      # 실제 verified URL (있는 경우만)
    "snippet": str | None,
    "source_type_hint": str,  # 'official_distributor' | 'industrial_marketplace' | ...
    "verified": bool,       # True = 실제 URL 있음, False = LLM plan only
}
```

팀원 B에게 넘기는 **page_text** 규칙:
- 최대 `DEFAULT_PAGE_TEXT_LIMIT` (12,000자) — `scraper.py:fetch_page_text()`에서 절삭
- `verified=True`인 결과에 대해서만 fetch 시도
- fetch 실패 시 빈 문자열 `""` — 팀원 B의 extractor는 빈 텍스트를 `none`으로 처리
- 인코딩 실패 시 `errors="replace"` 적용 — 깨진 문자는 `?`로 치환

## 테스트 전략

```bash
# 현재 테스트
PYTHONPATH=. python -m unittest tests/test_phase2_research.py
PYTHONPATH=. python -m unittest tests/test_phase2_contract.py

# 검색 결과 랭킹 로직 확인
PYTHONPATH=. python -c "
from agents.web_research.search_engine import _purchase_signal_score
sample = {'title': '6204-ZZ 베어링 가격 재고', 'url': 'https://kr.misumi-ec.com/...', 'snippet': '재고 있음 납기 2일'}
print(_purchase_signal_score(sample))
"
```

## 완료 기준

- [ ] LLM 쿼리에 국내 대리점/대체품 특화 쿼리 2개 이상 포함
- [ ] SerpAPI 결과에서 `ads` 등 비유기적 결과 혼입 없음 확인
- [ ] `fetch_page_text()`가 `<meta charset>` fallback 처리
- [ ] fetch 재시도 로직 (2회, 타임아웃 20s 유지)
- [ ] `test_phase2_research.py` 전체 통과
