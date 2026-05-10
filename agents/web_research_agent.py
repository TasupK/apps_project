"""Phase 2 web research agent with live-search candidate collection."""

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


if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))


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


def load_shortage_event(path: str | Path) -> dict:
    """Load a Phase 1 shortage event JSON artifact."""
    event = json.loads(Path(path).read_text(encoding="utf-8"))
    _validate_shortage_event(event)
    return event


def _validate_shortage_event(event: dict) -> None:
    required = {
        "event_id",
        "status",
        "material_id",
        "material_name",
        "category",
        "technical_specification",
        "search_keywords",
        "detected_at",
    }
    missing = sorted(required - set(event))
    if missing:
        raise ValueError(f"shortage_event is missing required fields: {', '.join(missing)}")
    if event["status"] != "SHORTAGE_DETECTED":
        raise ValueError("Phase 2 expects a SHORTAGE_DETECTED event")
    if not isinstance(event["search_keywords"], list) or len(event["search_keywords"]) < 3:
        raise ValueError("shortage_event.search_keywords must contain at least three items")


def build_search_query(shortage_event: dict) -> str:
    """Build a deterministic MVP query from Phase 1 search keywords."""
    keywords = [str(item).strip() for item in shortage_event["search_keywords"] if str(item).strip()]
    if not keywords:
        return shortage_event["material_name"]
    return " ".join(keywords)


def build_deterministic_query_candidates(shortage_event: dict) -> list[str]:
    """Build stable non-LLM query candidates for live-search fallback."""
    base_query = build_search_query(shortage_event)
    material_name = shortage_event["material_name"]
    spec_text = shortage_event["technical_specification"]
    category = shortage_event["category"]

    candidates = [
        base_query,
        f"buy {material_name} price stock lead time distributor",
        f"{material_name} in stock price official distributor",
        f"{material_name} replacement alternative distributor lead time",
        f"{material_name} official datasheet price stock",
        f"{material_name} 구매 가격 재고 납기 국내 대리점",
        f"{material_name} 대체품 호환품 가격 재고 납기",
        f"{category} {material_name} compatible replacement {spec_text}",
    ]
    return _dedupe_queries(candidates)


def generate_query_candidates(
    shortage_event: dict,
    query_mode: str = "deterministic",
    model: str = DEFAULT_LLM_MODEL,
    api_key: str | None = None,
) -> list[str]:
    """Generate web search query candidates, optionally using an LLM."""
    if query_mode not in VALID_QUERY_MODES:
        raise ValueError(f"query_mode must be one of {sorted(VALID_QUERY_MODES)}")

    fallback_queries = build_deterministic_query_candidates(shortage_event)
    if query_mode == "deterministic":
        return fallback_queries

    try:
        llm_queries = generate_query_candidates_with_llm(shortage_event, model=model, api_key=api_key)
    except RuntimeError:
        return fallback_queries

    return _dedupe_queries(llm_queries + fallback_queries)


def generate_query_candidates_with_llm(
    shortage_event: dict,
    model: str = DEFAULT_LLM_MODEL,
    api_key: str | None = None,
) -> list[str]:
    """Ask OpenAI to generate search query candidates for live web research."""
    token = os.environ.get("OPENAI_API_KEY") if api_key is None else api_key
    if not token:
        raise RuntimeError("OPENAI_API_KEY is required for LLM query generation")

    request_body = {
        "model": model,
        "instructions": QUERY_GENERATION_PROMPT,
        "input": json.dumps(
            {
                "material_id": shortage_event["material_id"],
                "material_name": shortage_event["material_name"],
                "category": shortage_event["category"],
                "technical_specification": shortage_event["technical_specification"],
                "search_keywords": shortage_event["search_keywords"],
            },
            ensure_ascii=False,
        ),
        "text": {"format": QUERY_RESPONSE_SCHEMA},
    }
    payload = json.dumps(request_body).encode("utf-8")
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_body = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"LLM query generation failed: {exc}") from exc

    return _parse_llm_query_response(response_body)


def _parse_llm_query_response(response_body: dict) -> list[str]:
    text = response_body.get("output_text")
    if not text:
        text = _extract_response_text(response_body)
    if not text:
        raise RuntimeError("LLM query generation returned no text")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("LLM query generation returned invalid JSON") from exc

    queries = parsed.get("queries")
    if not isinstance(queries, list):
        raise RuntimeError("LLM query generation returned no queries array")
    return [str(query).strip() for query in queries if str(query).strip()]


def _extract_response_text(response_body: dict) -> str | None:
    for item in response_body.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                return content.get("text")
    return None


def _dedupe_queries(queries: list[str]) -> list[str]:
    deduped = []
    seen = set()
    for query in queries:
        text = " ".join(str(query).split())
        key = text.lower()
        if text and key not in seen:
            deduped.append(text)
            seen.add(key)
    return deduped


def make_search_result(
    query: str,
    title: str | None,
    url: str | None,
    snippet: str | None,
    source_type_hint: str = "unknown",
    verified: bool = False,
) -> dict:
    """Build a normalized web search result record."""
    return {
        "query": query,
        "title": title,
        "url": url,
        "snippet": snippet,
        "source_type_hint": _normalize_source_type(source_type_hint),
        "verified": verified and bool(url),
    }


def search_web(query: str, provider: str | None = None, max_results: int = 5) -> list[dict]:
    """Run one web search query and return normalized title/url/snippet records."""
    selected_provider = _resolve_search_provider(provider)
    if selected_provider == "llm_plan":
        return [
            make_search_result(
                query=query,
                title=None,
                url=None,
                snippet="LLM generated search plan only. No verified web source was fetched.",
                verified=False,
            )
        ]
    if selected_provider == "serpapi":
        return _search_with_serpapi(query, max_results=max_results)
    raise ValueError(f"Unsupported search provider: {selected_provider}")


def collect_search_results(
    queries: list[str],
    provider: str | None = None,
    max_results_per_query: int = 5,
) -> list[dict]:
    """Collect search results for multiple queries and dedupe verified URLs."""
    results: list[dict] = []
    seen_urls = set()
    seen_plans = set()

    for query in queries:
        for result in search_web(query, provider=provider, max_results=max_results_per_query):
            url = result.get("url")
            if result.get("verified") and url:
                key = _canonical_url(url)
                if key in seen_urls:
                    continue
                seen_urls.add(key)
            else:
                key = str(result.get("query") or "").strip().lower()
                if key in seen_plans:
                    continue
                seen_plans.add(key)
            results.append(result)
    return _rank_search_results(results)


def get_verified_search_results(results: list[dict]) -> list[dict]:
    """Return only search results backed by an actual provider URL."""
    return [result for result in results if result.get("verified") and result.get("url")]


TRACKING_QUERY_PARAMS = {
    "srsltid",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "msclkid",
}


def _canonical_url(url: object) -> str:
    text = str(url or "").strip()
    parsed = urllib.parse.urlsplit(text)
    query_pairs = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_QUERY_PARAMS
    ]
    normalized_query = urllib.parse.urlencode(query_pairs, doseq=True)
    normalized_path = parsed.path.rstrip("/") or parsed.path
    return urllib.parse.urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            normalized_path,
            normalized_query,
            "",
        )
    )


def _rank_search_results(results: list[dict]) -> list[dict]:
    return sorted(results, key=_search_result_rank_key)


def _search_result_rank_key(result: dict) -> tuple[int, str]:
    return (-_purchase_signal_score(result), str(result.get("url") or ""))


def _purchase_signal_score(result: dict) -> int:
    text = " ".join(
        str(result.get(field) or "").lower()
        for field in ["title", "url", "snippet", "source_type_hint"]
    )
    score = 0
    positive_terms = {
        "buy": 5,
        "price": 5,
        "stock": 5,
        "in stock": 7,
        "lead time": 5,
        "ships": 3,
        "cart": 3,
        "distributor": 4,
        "misumi": 6,
        "rs-online": 5,
        "mcmaster": 5,
        "motion.com": 4,
        "bearingsdirect": 4,
        "구매": 5,
        "가격": 5,
        "재고": 5,
        "납기": 5,
        "대리점": 4,
        "미스미": 6,
        "원": 3,
        "₩": 3,
        "$": 2,
    }
    negative_terms = {
        "blog": 5,
        "블로그": 5,
        "pdf": 3,
        "catalog": 2,
        "dimensions": 2,
        "specifications": 2,
        "wikipedia": 10,
    }
    for term, weight in positive_terms.items():
        if term in text:
            score += weight
    for term, weight in negative_terms.items():
        if term in text:
            score -= weight
    if result.get("source_type_hint") in {"official_distributor", "industrial_marketplace"}:
        score += 4
    if result.get("source_type_hint") == "marketplace":
        score += 1
    return score


def _resolve_search_provider(provider: str | None) -> str:
    selected = (provider or os.environ.get(DEFAULT_SEARCH_PROVIDER_ENV) or "llm_plan").strip().lower()
    if selected not in VALID_SEARCH_PROVIDERS:
        raise ValueError(f"search provider must be one of {sorted(VALID_SEARCH_PROVIDERS)}")
    return selected


def _search_with_serpapi(query: str, max_results: int = 5) -> list[dict]:
    api_key = os.environ.get("SERPAPI_API_KEY")
    if not api_key:
        raise RuntimeError("SERPAPI_API_KEY is required when PHASE2_SEARCH_PROVIDER=serpapi")

    params = urllib.parse.urlencode({"engine": "google", "q": query, "api_key": api_key, "num": max_results})
    payload = _get_json(f"https://serpapi.com/search.json?{params}")
    organic_results = payload.get("organic_results", [])

    results = []
    for item in organic_results[:max_results]:
        results.append(
            make_search_result(
                query=query,
                title=_empty_to_none(item.get("title")),
                url=_empty_to_none(item.get("link")),
                snippet=_empty_to_none(item.get("snippet")),
                source_type_hint=_infer_source_type(item.get("link"), item.get("title"), item.get("snippet")),
                verified=True,
            )
        )
    return results


def _get_json(url: str, headers: dict[str, str] | None = None) -> dict:
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"web search request failed: {exc}") from exc


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            text = " ".join(data.split())
            if text:
                self._parts.append(text)

    def text(self) -> str:
        return " ".join(self._parts)


def fetch_page_text(url: str, max_chars: int = DEFAULT_PAGE_TEXT_LIMIT) -> str:
    """Fetch a verified URL and return compact visible page text."""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 Phase2WebResearchAgent/1.0",
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read(max_chars * 4)
            content_type = response.headers.get("Content-Type", "")
    except (OSError, urllib.error.HTTPError) as exc:
        raise RuntimeError(f"page fetch failed: {exc}") from exc

    charset = _charset_from_content_type(content_type) or "utf-8"
    html = raw.decode(charset, errors="replace")
    parser = _HTMLTextExtractor()
    parser.feed(html)
    text = re.sub(r"\s+", " ", parser.text() or html).strip()
    return text[:max_chars]


def _charset_from_content_type(content_type: str) -> str | None:
    match = re.search(r"charset=([^;\s]+)", content_type, flags=re.IGNORECASE)
    return match.group(1).strip("\"'") if match else None


def extract_candidate_details(
    candidate: dict,
    page_text: str,
    shortage_event: dict,
    extraction_mode: str = "none",
    model: str = DEFAULT_LLM_MODEL,
    api_key: str | None = None,
) -> dict:
    """Extract candidate fields from fetched page text."""
    if extraction_mode not in VALID_EXTRACTION_MODES:
        raise ValueError(f"extraction_mode must be one of {sorted(VALID_EXTRACTION_MODES)}")
    if extraction_mode == "none" or not page_text.strip():
        return {}
    heuristic_details = extract_candidate_details_from_text(page_text)
    try:
        llm_details = extract_candidate_details_with_llm(candidate, page_text, shortage_event, model=model, api_key=api_key)
    except RuntimeError:
        llm_details = {}
    return _merge_extraction_details(llm_details, heuristic_details)


def extract_candidate_details_from_text(page_text: str) -> dict:
    """Extract high-confidence price/stock/lead-time hints directly from fetched page text."""
    return _normalize_extracted_details(
        {
            "vendor_name": None,
            "price_krw": None,
            **_extract_price_fields(page_text),
            "lead_time_days": _extract_lead_time_days(page_text),
            "moq": _extract_moq(page_text),
            "location": None,
            "source_type": None,
            "price_listed": _extract_price_fields(page_text).get("listed_price") is not None,
            "stock_listed": _has_stock_signal(page_text),
            "leadtime_listed": _extract_lead_time_days(page_text) is not None,
            "spec_text": None,
            "spec_evidence": None,
        }
    )


def _merge_extraction_details(primary: dict, fallback: dict) -> dict:
    merged = dict(primary)
    for field, value in fallback.items():
        if field in {"price_listed", "stock_listed", "leadtime_listed"}:
            merged[field] = bool(primary.get(field)) or bool(value)
        elif merged.get(field) is None and value is not None:
            merged[field] = value
    if fallback.get("price_krw") is not None:
        merged["price_krw"] = fallback["price_krw"]
    return merged


def extract_candidate_details_with_llm(
    candidate: dict,
    page_text: str,
    shortage_event: dict,
    model: str = DEFAULT_LLM_MODEL,
    api_key: str | None = None,
) -> dict:
    """Ask OpenAI to extract contract fields from one product/source page."""
    token = os.environ.get("OPENAI_API_KEY") if api_key is None else api_key
    if not token:
        raise RuntimeError("OPENAI_API_KEY is required for LLM detail extraction")

    request_body = {
        "model": model,
        "instructions": DETAIL_EXTRACTION_PROMPT,
        "input": json.dumps(
            {
                "shortage_event": {
                    "material_id": shortage_event["material_id"],
                    "material_name": shortage_event["material_name"],
                    "category": shortage_event["category"],
                    "technical_specification": shortage_event["technical_specification"],
                },
                "candidate": candidate,
                "page_text": page_text[:DEFAULT_PAGE_TEXT_LIMIT],
            },
            ensure_ascii=False,
        ),
        "text": {"format": DETAIL_RESPONSE_SCHEMA},
    }
    payload = json.dumps(request_body).encode("utf-8")
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_body = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"LLM detail extraction failed: {exc}") from exc

    return _parse_candidate_detail_response(response_body)


def _parse_candidate_detail_response(response_body: dict) -> dict:
    text = response_body.get("output_text") or _extract_response_text(response_body)
    if not text:
        raise RuntimeError("LLM detail extraction returned no text")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("LLM detail extraction returned invalid JSON") from exc
    return _normalize_extracted_details(parsed)


def _normalize_extracted_details(details: dict) -> dict:
    normalized = {
        "vendor_name": _empty_to_none(details.get("vendor_name")),
        "price_krw": _to_int_or_none(details.get("price_krw")),
        "raw_price_text": _empty_to_none(details.get("raw_price_text")),
        "listed_price": _to_float_or_none(details.get("listed_price")),
        "listed_currency": _normalize_currency(details.get("listed_currency")),
        "lead_time_days": _to_int_or_none(details.get("lead_time_days")),
        "moq": _to_int_or_none(details.get("moq")),
        "location": _normalize_location(details.get("location")),
        "source_type": _normalize_source_type(details.get("source_type")),
        "price_listed": _to_bool(details.get("price_listed")),
        "stock_listed": _to_bool(details.get("stock_listed")),
        "leadtime_listed": _to_bool(details.get("leadtime_listed")),
        "spec_text": _empty_to_none(details.get("spec_text")),
        "spec_evidence": _empty_to_none(details.get("spec_evidence")),
    }
    if normalized["price_krw"] is None:
        converted = _convert_listed_price_to_krw(normalized["listed_price"], normalized["listed_currency"])
        if converted is not None:
            normalized["price_krw"] = converted
            normalized["price_listed"] = True
            normalized["spec_evidence"] = _append_fx_evidence(normalized["spec_evidence"], normalized)
    return normalized


def _merge_candidate_details(candidate: dict, details: dict) -> dict:
    merged = dict(candidate)
    for field in ["vendor_name", "location", "source_type", "spec_text", "spec_evidence"]:
        value = details.get(field)
        if value:
            merged[field] = value
    for field in ["price_krw", "lead_time_days", "moq"]:
        if details.get(field) is not None:
            merged[field] = details[field]
    for field in ["price_listed", "stock_listed", "leadtime_listed"]:
        if field in details:
            merged[field] = bool(details[field])
    return merged


def _convert_listed_price_to_krw(listed_price: float | None, currency: str | None) -> int | None:
    if listed_price is None or currency is None:
        return None
    if currency == "KRW":
        return round(listed_price)
    rate = get_exchange_rate_to_krw(currency)
    if rate is None:
        return None
    return round(listed_price * rate)


def get_exchange_rate_to_krw(currency: str) -> float | None:
    normalized = _normalize_currency(currency)
    if not normalized:
        return None
    if normalized == "KRW":
        return 1.0
    url = f"https://api.frankfurter.dev/v1/latest?base={urllib.parse.quote(normalized)}&symbols=KRW"
    try:
        payload = _get_json(url)
    except RuntimeError:
        return None
    rate = payload.get("rates", {}).get("KRW")
    return _to_float_or_none(rate)


def _append_fx_evidence(evidence: str | None, details: dict) -> str:
    raw_price = details.get("raw_price_text")
    currency = details.get("listed_currency")
    listed_price = details.get("listed_price")
    note = f"Converted listed price {raw_price or listed_price} {currency} to KRW using latest exchange rate."
    return f"{evidence} {note}".strip() if evidence else note


def _extract_price_fields(text: str) -> dict:
    compact = " ".join(str(text or "").split())
    patterns = [
        (r"(?:Price|Unit Price|Your Price|Sale Price)\s*[:\-]?\s*\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:/each|each|ea)?", "USD", "$"),
        (r"\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:/each|each|ea)?", "USD", "$"),
        (r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:USD|US dollars?)", "USD", "USD"),
        (r"([0-9][0-9,]*)\s*원", "KRW", "원"),
        (r"₩\s*([0-9][0-9,]*)", "KRW", "₩"),
        (r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:EUR|€)", "EUR", "EUR"),
        (r"€\s*([0-9][0-9,]*(?:\.[0-9]+)?)", "EUR", "€"),
    ]
    for pattern, currency, symbol in patterns:
        match = re.search(pattern, compact, flags=re.IGNORECASE)
        if match:
            amount = _to_float_or_none(match.group(1))
            if amount is not None:
                return {
                    "raw_price_text": f"{symbol}{match.group(1)}" if symbol in {"$", "₩", "€"} else f"{match.group(1)} {symbol}",
                    "listed_price": amount,
                    "listed_currency": currency,
                }
    return {"raw_price_text": None, "listed_price": None, "listed_currency": None}


def _has_stock_signal(text: str) -> bool:
    lowered = str(text or "").lower()
    stock_terms = [
        "in stock",
        "available to ship",
        "ships today",
        "add to cart",
        "재고 있음",
        "재고",
        "출하",
        "당일",
    ]
    out_of_stock_terms = ["out of stock", "sold out", "품절", "재고 없음"]
    return any(term in lowered for term in stock_terms) and not any(term in lowered for term in out_of_stock_terms)


def _extract_lead_time_days(text: str) -> int | None:
    lowered = str(text or "").lower()
    if any(term in lowered for term in ["ships today", "same day", "당일 출고", "당일출고"]):
        return 0
    patterns = [
        r"ships?\s+(?:in|within)\s+([0-9]+)\s+(?:business\s+)?days?",
        r"lead\s*time\s*[:\-]?\s*([0-9]+)\s+days?",
        r"([0-9]+)\s*(?:business\s+)?days?\s+to\s+ship",
        r"납기\s*[:\-]?\s*([0-9]+)\s*일",
        r"([0-9]+)\s*일(?:째)?\s*출하",
        r"출하일\s*[:\-]?\s*([0-9]+)\s*일",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered, flags=re.IGNORECASE)
        if match:
            return _to_int_or_none(match.group(1))
    return None


def _extract_moq(text: str) -> int | None:
    lowered = str(text or "").lower()
    patterns = [
        r"(?:moq|minimum order quantity|min\.?\s*order)\s*[:\-]?\s*([0-9][0-9,]*)",
        r"최소\s*주문\s*수량\s*[:\-]?\s*([0-9][0-9,]*)",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered, flags=re.IGNORECASE)
        if match:
            return _to_int_or_none(match.group(1))
    return None


def _apply_min_price(candidates: list[dict]) -> list[dict]:
    prices = [candidate.get("price_krw") for candidate in candidates if candidate.get("price_krw") is not None]
    min_price = min(prices) if prices else None
    for candidate in candidates:
        candidate["min_price_krw"] = min_price
    return candidates


def _infer_source_type(url: object, title: object = None, snippet: object = None) -> str:
    text = " ".join(str(value or "").lower() for value in [url, title, snippet])
    if any(token in text for token in ["manufacturer", "datasheet", "catalog"]):
        return "manufacturer_page"
    if any(token in text for token in ["misumi", "mcmaster", "digikey", "mouser", "authorized", "official distributor"]):
        return "official_distributor"
    if any(token in text for token in ["industrial", "industry", "daara"]):
        return "industrial_marketplace"
    if any(token in text for token in ["amazon", "ebay", "aliexpress", "marketplace", "open market"]):
        return "marketplace"
    return "unknown"


def build_candidate_results(
    shortage_event: dict,
    search_mode: str = "live",
    query_mode: str = "deterministic",
    extraction_mode: str = "none",
    llm_model: str = DEFAULT_LLM_MODEL,
    search_provider: str | None = None,
    max_results_per_query: int = DEFAULT_MAX_RESULTS_PER_QUERY,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
    searched_at: str | None = None,
) -> dict:
    """Build a Phase 2 candidate_results payload from verified live search results."""
    if search_mode not in RUNTIME_SEARCH_MODES:
        raise ValueError(f"search_mode must be one of {sorted(RUNTIME_SEARCH_MODES)}")

    target_material_id = shortage_event["material_id"]
    query_candidates = generate_query_candidates(shortage_event, query_mode=query_mode, model=llm_model)
    search_results = collect_search_results(
        query_candidates,
        provider=search_provider,
        max_results_per_query=max_results_per_query,
    )
    verified_results = get_verified_search_results(search_results)[:max_candidates]
    candidates = _candidate_stubs_from_verified_search_results(
        verified_results,
        shortage_event=shortage_event,
        extraction_mode=extraction_mode,
        llm_model=llm_model,
    )

    return {
        "search_id": f"SR-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "event_id": shortage_event["event_id"],
        "material_id": target_material_id,
        "material_name": shortage_event["material_name"],
        "category": shortage_event["category"],
        "target_spec_text": shortage_event["technical_specification"],
        "searched_at": searched_at or datetime.now().astimezone().isoformat(timespec="seconds"),
        "query_used": query_candidates[0],
        "search_mode": search_mode,
        "candidates": candidates,
    }


def _candidate_stubs_from_verified_search_results(
    results: list[dict],
    shortage_event: dict | None = None,
    extraction_mode: str = "none",
    llm_model: str = DEFAULT_LLM_MODEL,
) -> list[dict]:
    """Convert verified search results into conservative candidate stubs.

    Detailed price/spec extraction is intentionally deferred to the next LLM
    extraction step. Search-plan-only results are never passed here.
    """
    candidates = []
    for index, result in enumerate(results, start=1):
        candidate = {
            "candidate_id": f"LIVE-{index:03d}",
            "candidate_material_id": None,
            "vendor_name": _vendor_name_from_search_result(result),
            "price_krw": None,
            "min_price_krw": None,
            "lead_time_days": None,
            "moq": None,
            "location": "Unknown",
            "source_type": _normalize_source_type(result.get("source_type_hint")),
            "source_url": result["url"],
            "price_listed": False,
            "stock_listed": False,
            "leadtime_listed": False,
            "spec_text": _search_result_text(result),
            "spec_evidence": "Verified search result only. Detailed price, stock, lead time, and spec extraction is pending.",
        }
        if extraction_mode == "llm" and shortage_event:
            candidate = _enrich_candidate_from_page(candidate, shortage_event, model=llm_model)
        candidates.append(candidate)
    return _apply_min_price(candidates)


def _enrich_candidate_from_page(candidate: dict, shortage_event: dict, model: str = DEFAULT_LLM_MODEL) -> dict:
    try:
        page_text = fetch_page_text(candidate["source_url"])
    except RuntimeError:
        return candidate
    details = extract_candidate_details(candidate, page_text, shortage_event, extraction_mode="llm", model=model)
    return _merge_candidate_details(candidate, details)


def _vendor_name_from_search_result(result: dict) -> str:
    title = str(result.get("title") or "").strip()
    if " - " in title:
        return title.rsplit(" - ", 1)[-1].strip() or "Unknown Vendor"
    return title or "Unknown Vendor"


def _search_result_text(result: dict) -> str:
    parts = [result.get("title"), result.get("snippet")]
    text = ". ".join(str(part).strip() for part in parts if str(part or "").strip())
    return text or "Verified web search result with limited snippet evidence."


def _empty_to_none(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _to_int_or_none(value: object) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    return round(float(text.replace(",", "")))


def _to_float_or_none(value: object) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    return float(text.replace(",", ""))


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().upper() == "TRUE"


def _normalize_source_type(value: object) -> str:
    normalized = str(value or "unknown").strip().lower().replace(" ", "_")
    if normalized not in VALID_SOURCE_TYPES:
        return "unknown"
    return normalized


def _normalize_location(value: object) -> str:
    text = str(value or "Unknown").strip()
    return text if text in VALID_LOCATIONS else "Unknown"


def _normalize_currency(value: object) -> str | None:
    text = str(value or "").strip().upper()
    aliases = {
        "₩": "KRW",
        "원": "KRW",
        "$": "USD",
        "US$": "USD",
        "USD$": "USD",
        "€": "EUR",
        "¥": "JPY",
        "£": "GBP",
    }
    normalized = aliases.get(text, text)
    return normalized if normalized in SUPPORTED_PRICE_CURRENCIES else None


def validate_candidate_results(report: dict) -> list[str]:
    """Return Phase 2 contract validation errors."""
    errors: list[str] = []
    _require_fields(report, ROOT_REQUIRED_FIELDS, "root", errors)
    if errors:
        return errors

    if report["search_mode"] not in VALID_SEARCH_MODES:
        errors.append("root.search_mode is invalid")
    if not isinstance(report["candidates"], list):
        errors.append("root.candidates must be an array")
        return errors

    for index, candidate in enumerate(report["candidates"]):
        _validate_candidate(candidate, index, errors)
    return errors


def _validate_candidate(candidate: dict, index: int, errors: list[str]) -> None:
    prefix = f"candidates[{index}]"
    if not isinstance(candidate, dict):
        errors.append(f"{prefix} must be an object")
        return

    _require_fields(candidate, CANDIDATE_REQUIRED_FIELDS, prefix, errors)
    if any(error.startswith(prefix) for error in errors):
        return

    if candidate["source_type"] not in VALID_SOURCE_TYPES:
        errors.append(f"{prefix}.source_type is invalid")
    if candidate["location"] not in VALID_LOCATIONS:
        errors.append(f"{prefix}.location is invalid")
    for field in ["price_listed", "stock_listed", "leadtime_listed"]:
        if not isinstance(candidate[field], bool):
            errors.append(f"{prefix}.{field} must be boolean")
    for field in ["price_krw", "min_price_krw", "lead_time_days", "moq"]:
        if candidate[field] is not None and not isinstance(candidate[field], int):
            errors.append(f"{prefix}.{field} must be integer or null")


def _require_fields(payload: dict, required_fields: set[str], prefix: str, errors: list[str]) -> None:
    missing = sorted(required_fields - set(payload))
    for field in missing:
        errors.append(f"{prefix}.{field} is required")


def write_candidate_results(report: dict, output_path: str | Path) -> Path:
    errors = validate_candidate_results(report)
    if errors:
        raise ValueError("candidate_results failed contract validation: " + "; ".join(errors))

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination


def run_web_research(
    input_path: str | Path = DEFAULT_SAMPLE_INPUT,
    output_path: str | Path = DEFAULT_OUTPUT,
    search_mode: str = "live",
    query_mode: str = "deterministic",
    extraction_mode: str = "none",
    llm_model: str = DEFAULT_LLM_MODEL,
    search_provider: str | None = None,
    max_results_per_query: int = DEFAULT_MAX_RESULTS_PER_QUERY,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
) -> dict:
    shortage_event = load_shortage_event(input_path)
    report = build_candidate_results(
        shortage_event,
        search_mode=search_mode,
        query_mode=query_mode,
        extraction_mode=extraction_mode,
        llm_model=llm_model,
        search_provider=search_provider,
        max_results_per_query=max_results_per_query,
        max_candidates=max_candidates,
    )
    write_candidate_results(report, output_path)
    return report


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Phase 2 web research candidate collection.")
    parser.add_argument("--sample-input", action="store_true", help="Use the Phase 2 sample shortage event.")
    parser.add_argument("--mock-input", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--input", type=Path, help="Path to Phase 1 shortage_event.json.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Candidate results JSON output path.")
    parser.add_argument("--search-mode", choices=sorted(RUNTIME_SEARCH_MODES), default="live", help="Search mode label.")
    parser.add_argument(
        "--search-provider",
        choices=sorted(VALID_SEARCH_PROVIDERS),
        help=f"Live search provider. Defaults to ${DEFAULT_SEARCH_PROVIDER_ENV} or llm_plan.",
    )
    parser.add_argument(
        "--query-mode",
        choices=sorted(VALID_QUERY_MODES),
        default="deterministic",
        help="Use deterministic search keywords or ask an LLM to generate query candidates.",
    )
    parser.add_argument(
        "--extraction-mode",
        choices=sorted(VALID_EXTRACTION_MODES),
        default="none",
        help="Use fetched page text plus an LLM to fill price, lead time, stock, and spec evidence.",
    )
    parser.add_argument("--llm-model", default=DEFAULT_LLM_MODEL, help="OpenAI model for LLM query generation.")
    parser.add_argument(
        "--max-results-per-query",
        type=int,
        default=DEFAULT_MAX_RESULTS_PER_QUERY,
        help="Maximum provider results to request per search query.",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=DEFAULT_MAX_CANDIDATES,
        help="Maximum verified search results to promote and optionally extract.",
    )
    parser.add_argument("--print", action="store_true", dest="print_report", help="Also print the report to stdout.")
    return parser


def main() -> None:
    args = build_argument_parser().parse_args()
    input_path = DEFAULT_SAMPLE_INPUT if args.sample_input or args.mock_input or not args.input else args.input
    report = run_web_research(
        input_path=input_path,
        output_path=args.output,
        search_mode=args.search_mode,
        query_mode=args.query_mode,
        extraction_mode=args.extraction_mode,
        llm_model=args.llm_model,
        search_provider=args.search_provider,
        max_results_per_query=args.max_results_per_query,
        max_candidates=args.max_candidates,
    )
    if args.print_report:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Wrote candidate results: {args.output}")


if __name__ == "__main__":
    main()
