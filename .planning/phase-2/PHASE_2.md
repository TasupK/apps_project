# Phase 2: Web Research Agent & Source Collection

**담당:** 팀원 B  
**목표:** Phase 1의 부족 자재 이벤트를 입력으로 받아 실제 웹 검색 결과를 수집하고, Phase 3가 평가할 수 있는 `candidate_results.json` 형태로 정규화한다.

## 핵심 역할

Phase 2는 구매 담당자가 하던 웹 리서치 업무를 자동화하는 구간이다.

현재 방향은 live search 중심이다. SerpAPI 같은 검색 provider가 실제 URL과 snippet을 가져오고, LLM은 검색 쿼리 생성과 이후 후보 정보 추출을 보조한다. LLM은 실제로 확인되지 않은 URL, 가격, 납기, 재고 정보를 추측해서 후보로 확정하면 안 된다.

## 작업 범위

- Phase 1의 `shortage_event.json` 입력 받기
- 부족 자재 이름, 카테고리, 기술 스펙, `search_keywords` 파싱
- LLM 또는 deterministic 방식으로 검색 쿼리 후보 생성
- SerpAPI 같은 검색 provider로 실제 검색 결과 수집
- 검색 결과의 `title`, `url`, `snippet`을 공통 `SearchResult` 형태로 정규화
- 실제 URL이 확인된 검색 결과만 후보 stub으로 승격
- 검증되지 않은 LLM search plan은 Phase 3 후보로 넘기지 않음
- 후보별 출처 URL, 출처 유형, 스펙 근거 텍스트를 `candidate_results.json` 계약에 맞게 전달
- 가격, 납기, 재고 수량 등 페이지 본문 추출이 필요한 값은 다음 LLM extraction 단계에서 채움

## 관련 계약 문서

- Phase 2 출력 형식: [Phase 2 Format Contract](PHASE_2_FORMAT_CONTRACT.md)
- Phase 3 인수인계 계약: [Phase 2 to Phase 3 Contract](PHASE_2_TO_PHASE_3_CONTRACT.md)
- Phase 1 입력 계약: `.planning/phase-1/PHASE_1_FORMAT_CONTRACT.md`

## 입력/출력 파일

| 구분 | 파일 |
| --- | --- |
| Phase 1 입력 샘플 | `.planning/phase-2/shortage_event.sample.json` |
| Phase 3 fastener 연동 입력 샘플 | `.planning/phase-2/fastener_shortage_event.sample.json` |
| Phase 2 출력 | `output/candidate_results.json` |
| Phase 2 기본 출력 샘플 | `.planning/phase-2/candidate_results.sample.json` |
| Phase 2 fastener 연동 출력 샘플 | `.planning/phase-2/candidate_results.fastener.sample.json` |

`candidate_results.sample.json`과 `candidate_results.fastener.sample.json`은 Phase 3 계약 및 회귀 테스트에서 참고할 수 있으므로 유지한다.

## 검색 쿼리 예시

```text
Ball Bearing 6204-ZZ 20mm 47mm 14mm steel replacement
6204-ZZ bearing alternative 6204-2RS distributor lead time
6204-ZZ official datasheet price stock
Ball Bearing 6204-ZZ 대체품 호환품 가격 재고 납기
```

## Live Search 환경변수

실제 키는 각자 로컬 `.env` 또는 OS 환경변수에만 둔다. `.env`는 Git에 올리지 않는다.

공유용 형식은 repo root의 `.env.example`을 따른다.

```env
PHASE2_SEARCH_PROVIDER=serpapi
SERPAPI_API_KEY=
OPENAI_API_KEY=
```

PowerShell에서 일시적으로 설정할 경우:

```powershell
$env:PHASE2_SEARCH_PROVIDER="serpapi"
$env:SERPAPI_API_KEY="..."
$env:OPENAI_API_KEY="..."
```

## 실행 방법

샘플 부족 이벤트로 SerpAPI live search 실행:

```powershell
python agents\web_research_agent.py --sample-input --search-mode live --search-provider serpapi --output output\candidate_results.json
```

LLM 검색 쿼리 생성까지 함께 사용:

```powershell
python agents\web_research_agent.py --sample-input --search-mode live --search-provider serpapi --query-mode llm --output output\candidate_results.json
```

검색 결과 URL의 페이지 텍스트를 가져와 LLM으로 가격/납기/재고/스펙 근거까지 추출:

```powershell
python agents\web_research_agent.py --sample-input --search-mode live --search-provider serpapi --query-mode llm --extraction-mode llm --max-candidates 5 --output output\candidate_results.json
```

Phase 1 실제 출력과 연동:

```powershell
python agents\web_research_agent.py --input output\shortage_event.json --search-mode live --search-provider serpapi --query-mode llm --extraction-mode llm --max-candidates 5 --output output\candidate_results.json
```

콘솔에도 결과 출력:

```powershell
python agents\web_research_agent.py --sample-input --search-mode live --search-provider serpapi --print
```

## 현재 구현 상태

- `build_search_query()`는 Phase 1의 `search_keywords`를 기반으로 기본 검색어를 만든다.
- `generate_query_candidates()`는 deterministic 또는 LLM 방식으로 검색 쿼리 후보를 만든다.
- `search_web()`은 provider별 검색 API를 호출하는 공통 진입점이다.
- `collect_search_results()`는 여러 쿼리를 실행하고 URL 중복을 제거한다.
- 검색 결과는 `price`, `stock`, `buy`, `lead time`, `구매`, `가격`, `재고`, `납기` 같은 구매 가능성 신호를 기준으로 랭킹한다.
- `get_verified_search_results()`는 실제 URL이 있는 검색 결과만 선별한다.
- 검증된 검색 결과는 `LIVE-001`, `LIVE-002` 같은 후보 stub으로 변환된다.
- `fetch_page_text()`는 verified URL의 HTML에서 보이는 텍스트만 압축해서 가져온다.
- `extract_candidate_details_with_llm()`은 페이지 텍스트에서 가격, 납기, MOQ, 재고 표시 여부, 스펙 근거를 추출한다.
- 외화 가격이 명시된 경우 LLM은 원문 가격/금액/통화만 추출하고, 코드는 Frankfurter 최신 환율 API로 KRW를 계산해 `price_krw`에 넣는다.
- LLM 추출이 실패하거나 값이 명시되지 않은 경우 가격/납기/MOQ는 `null`, 표시 여부는 `false`로 유지한다.
- `--max-results-per-query`와 `--max-candidates`로 검색 결과 수와 LLM 추출 대상 수를 제한한다.

## 완료 기준

- Phase 1 부족 이벤트를 읽고 검색 쿼리를 생성한다.
- SerpAPI provider로 실제 검색 결과 URL과 snippet을 가져올 수 있다.
- 실제 URL이 확인된 결과만 후보로 승격한다.
- 후보는 Phase 2 Format Contract의 필수 필드를 모두 포함한다.
- 알 수 없는 가격, 납기, MOQ는 `null`로 둔다.
- 알 수 없는 price/stock/leadtime 표시 여부는 `false`로 둔다.
- `source_type`은 Phase 3가 기대하는 snake_case enum을 사용한다.
- Phase 3 연동 샘플 JSON은 삭제하지 않는다.

## 테스트

```powershell
$env:PYTHONPATH="."
python -m unittest discover -s tests -p "test_phase2_*.py"
```

테스트는 실제 SerpAPI를 호출하지 않고, 검증된 검색 결과를 fake provider로 주입해서 계약을 확인한다.

## 다음 단계

- verified URL의 페이지 텍스트 가져오기
- 실사이트별 본문 추출 품질 개선
- LLM 추출 결과의 근거 문장 품질 개선
- 국내 공급사 검색 품질이 부족할 경우 Naver provider 추가 검토
