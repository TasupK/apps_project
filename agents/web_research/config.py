from __future__ import annotations

from datetime import datetime
from html.parser import HTMLParser
import argparse
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

PROJECT_ROOT = Path(__file__).resolve().parents[1]
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
DEFAULT_LLM_MODEL = "gpt-4o-mini"
DEFAULT_SEARCH_PROVIDER_ENV = "PHASE2_SEARCH_PROVIDER"
DEFAULT_PAGE_TEXT_LIMIT = 12000
DEFAULT_MAX_RESULTS_PER_QUERY = 3
DEFAULT_MAX_CANDIDATES = 6
SUPPORTED_PRICE_CURRENCIES = {"KRW", "USD", "EUR", "JPY", "CNY", "GBP", "CAD", "AUD"}

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

부족 자재의 이름, 카테고리, 기술 스펙, 검색 키워드를 바탕으로 실제 구매 가능한 대체 후보를 찾기 위한 웹 검색 쿼리 후보를 생성한다.
제조사 공식 페이지, 공식 대리점, 산업재몰, 마켓플레이스 중 가격, 재고, 납기, 데이터시트가 표시될 가능성이 높은 페이지를 찾는 데 집중한다.
단순 스펙/카탈로그 페이지보다 실제 구매, 장바구니, 재고, 가격, 납기 정보가 있는 페이지를 우선 찾는다.

규칙:
- 모델명, 규격, 치수, 나사산/직경/길이, 재질, 전압, RPM 등 중요한 기술 조건은 절대 제거하지 않는다.
- 영어 검색 쿼리와 한국어 검색 쿼리를 함께 포함한다.
- 최소 하나는 원본 스펙을 최대한 유지한 정확 검색 쿼리여야 한다.
- 최소 두 개는 buy, price, stock, in stock, lead time, distributor, 구매, 가격, 재고, 납기, 국내 같은 구매 가능성 신호를 포함해야 한다.
- 최소 하나는 replacement, alternative, 대체품, 호환품처럼 더 넓은 후보를 찾는 쿼리여야 한다.
- catalog, dimensions, specification만 찾는 쿼리에 치우치지 않는다.
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

입력으로 부족 자재 정보, 검색 결과 후보, 그리고 실제 웹페이지 텍스트가 주어진다.
웹페이지에 명시된 값만 추출해서 Phase 3가 평가할 수 있는 후보 필드로 정리한다.

규칙:
- 가격, 납기, MOQ, 재고 표시 여부는 페이지 텍스트에 명시된 경우만 추출한다.
- 명시되지 않은 값은 추측하지 말고 null 또는 false로 둔다.
- 외화 가격이 명시된 경우 원문 가격, 숫자 금액, 통화 코드를 추출한다. KRW 환산은 코드가 담당한다.
- URL은 입력 후보의 source_url을 그대로 사용하며 새 URL을 만들지 않는다.
- 호환성 최종 판단, 추천, 거절 판단은 하지 않는다.
- spec_text와 spec_evidence는 페이지 텍스트에 근거해야 한다.
- 출력은 요청된 JSON schema와 정확히 일치하는 JSON만 반환한다."""

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
