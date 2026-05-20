from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SAMPLE_INPUT = PROJECT_ROOT / ".planning" / "phase-2" / "shortage_event.sample.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "output" / "candidate_results.json"

VALID_SOURCE_TYPES = {
    "manufacturer_page",
    "official_distributor",
    "industrial_marketplace",
    "marketplace",
    "unknown",
}
VALID_LOCATIONS = {"Domestic", "Overseas", "Unknown"}
VALID_SEARCH_MODES = {"mock", "live", "mixed"}
RUNTIME_SEARCH_MODES = {"live", "mixed"}
VALID_QUERY_MODES = {"deterministic", "llm"}
VALID_EXTRACTION_MODES = {"none", "llm"}
VALID_SEARCH_PROVIDERS = {"llm_plan", "serpapi"}
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OLLAMA_MODEL = "gemma4"
DEFAULT_LLM_MODEL = DEFAULT_OPENAI_MODEL  # overridden at runtime by _get_llm_config
DEFAULT_LLM_API_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
DEFAULT_SEARCH_PROVIDER_ENV = "PHASE2_SEARCH_PROVIDER"
DEFAULT_PAGE_TEXT_LIMIT = 12000
DEFAULT_MAX_RESULTS_PER_QUERY = 3
DEFAULT_MAX_CANDIDATES = 6
SUPPORTED_PRICE_CURRENCIES = {
    "KRW",
    "USD",
    "EUR",
    "JPY",
    "CNY",
    "GBP",
    "CAD",
    "AUD",
    "TWD",
    "SGD",
    "INR",
}

ROOT_REQUIRED_FIELDS = {
    "search_id",
    "event_id",
    "material_id",
    "material_name",
    "category",
    "target_spec_text",
    "searched_at",
    "query_used",
    "search_mode",
    "candidates",
}

CANDIDATE_REQUIRED_FIELDS = {
    "candidate_id",
    "candidate_material_id",
    "vendor_name",
    "price_krw",
    "min_price_krw",
    "lead_time_days",
    "moq",
    "location",
    "source_type",
    "source_url",
    "price_listed",
    "stock_listed",
    "leadtime_listed",
    "spec_text",
    "spec_evidence",
}

QUERY_GENERATION_PROMPT = """너는 산업재 구매 워크플로우의 Phase 2 웹 리서치 쿼리 플래너다.

부족 자재의 이름, 카테고리, 기술 스펙, 검색 키워드를 바탕으로 실제 구매 가능한 후보 자재와 공급처 페이지를 찾기 위한 웹 검색 쿼리 후보를 생성한다.
목표는 검색 결과에서 가격, 재고, 납기, 장바구니, 견적 요청, 구매 버튼, 상품 옵션이 확인될 가능성이 높은 실제 상품 상세/구매 페이지를 찾는 것이다.
국내 공급처를 우선하되, 검색 결과를 지나치게 좁히지 않도록 글로벌 공식 제조사, 공식/인증 대리점, 산업재 유통사 검색 쿼리도 함께 포함한다.

규칙:
- 모델명, MPN, 규격, 치수, 나사산/직경/길이, 재질, 전압, RPM 등 중요한 기술 조건은 절대 제거하지 않는다.
- 검색 쿼리는 실제 검색창에 넣을 수 있는 짧은 키워드 조합으로 작성한다.
- 영어 검색 쿼리와 한국어 검색 쿼리를 함께 포함한다.
- 모든 쿼리를 Korea, 국내, site:.kr로 제한하지 않는다. 국내 공급처용 쿼리 일부에만 국내, 한국, 대리점, 산업재몰, site:.kr 신호를 사용한다.
- 단순 카탈로그, 블로그, 일반 설명, PDF만 찾는 쿼리에 치우치지 않는다.
- 서로 다른 검색 의도를 가진 쿼리를 생성한다:
  1. 원본 모델명과 핵심 스펙을 유지한 exact part/spec search
  2. 국내 대리점/국내 산업재몰/국내 구매 페이지 search
  3. price, stock, in stock, lead time, quote, buy, cart가 포함된 purchase search
  4. official distributor 또는 authorized distributor search
  5. replacement, alternative, equivalent, 대체품, 호환품 search
  6. 치수/규격/재질 기반 spec-dimension search
- 한국어 구매 신호로 구매, 가격, 재고, 납기, 당일출고, 견적, 장바구니, 상품상세를 활용한다.
- 후보 제품명, 업체명, 가격, URL, 호환성 판단은 추측하지 않는다.
- 출력은 요청된 JSON schema와 정확히 일치하는 JSON만 반환한다."""

QUERY_RESPONSE_SCHEMA = {
    "type": "json_schema",
    "name": "phase2_query_candidates",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "queries": {
                "type": "array",
                "minItems": 1,
                "maxItems": 6,
                "items": {"type": "string"},
            }
        },
        "required": ["queries"],
    },
}

DETAIL_EXTRACTION_PROMPT = """너는 산업재 구매 웹 리서치 결과를 정규화하는 Phase 2 추출기다.
너에게는 (1) 웹페이지의 정제된 마크다운 텍스트와 (2) 웹페이지 전체를 캡처한 스크린샷 이미지가 함께 제공될 수 있다.

입력으로 부족 자재 정보, 검색 결과 후보, 그리고 웹페이지 데이터가 주어진다.
웹페이지에 명시된 값만 추출해서 Phase 3가 평가할 수 있는 후보 필드로 정리한다.

추출 규칙:
1. **텍스트와 이미지의 상호보완:** 마크다운 텍스트에서는 정확한 수치와 명칭(가격, 모델명 등)을 읽고, 스크린샷 이미지에서는 레이아웃과 시각적 위치를 통해 해당 정보가 우리가 찾는 상품에 대한 것인지 문맥을 파악하라.
2. **정확성:** 가격, 납기, MOQ, 재고 표시 여부는 페이지에 명시된 경우만 추출한다. 명시되지 않은 값은 추측하지 말고 null 또는 false로 둔다.
3. **이미지 내 정보:** 텍스트 데이터에 정보가 부족하더라도 스크린샷 내의 표, 차트, 배너 등에 명확한 수치 정보가 있다면 이를 적극적으로 반영하라.
4. **외화 처리:** 외화 가격이 명시된 경우 원문 가격, 숫자 금액, 통화 코드를 추출한다. KRW 환산은 코드가 담당한다.
5. **근거 명시:** spec_evidence 필드에는 해당 정보를 추출한 텍스트 구절을 인용하거나, "스크린샷 내 규격표 확인" 등 어떤 근거로 판단했는지 명시하라.
6. **출력 형식:** 출력은 요청된 JSON schema와 정확히 일치하는 JSON만 반환한다."""

DETAIL_RESPONSE_SCHEMA = {
    "type": "json_schema",
    "name": "phase2_candidate_detail",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "vendor_name": {"type": ["string", "null"]},
            "price_krw": {"type": ["integer", "null"]},
            "raw_price_text": {"type": ["string", "null"]},
            "listed_price": {"type": ["number", "null"]},
            "listed_currency": {"type": ["string", "null"]},
            "lead_time_days": {"type": ["integer", "null"]},
            "moq": {"type": ["integer", "null"]},
            "location": {"type": ["string", "null"]},
            "source_type": {"type": ["string", "null"]},
            "price_listed": {"type": "boolean"},
            "stock_listed": {"type": "boolean"},
            "leadtime_listed": {"type": "boolean"},
            "spec_text": {"type": ["string", "null"]},
            "spec_evidence": {"type": ["string", "null"]},
        },
        "required": [
            "vendor_name",
            "price_krw",
            "raw_price_text",
            "listed_price",
            "listed_currency",
            "lead_time_days",
            "moq",
            "location",
            "source_type",
            "price_listed",
            "stock_listed",
            "leadtime_listed",
            "spec_text",
            "spec_evidence",
        ],
    },
}
