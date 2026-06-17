from __future__ import annotations

import json as _json
import re
import time
import urllib.parse

from .config import *
from .llm_client import extract_candidate_details_with_llm
from .scraper import fetch_page_html_and_text, fetch_page_text, _get_json, capture_page_screenshot

# exchange rate cache: currency -> (rate, fetched_at_epoch)
_RATE_CACHE: dict[str, tuple[float, float]] = {}
_RATE_CACHE_TTL = 3600

# patterns ordered most-specific first
_LEAD_TIME_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'당일\s*(?:출고|발송)|in\s+stock\b', re.IGNORECASE), "0"),
    (re.compile(r'within\s+24\s+(?:business\s+)?hours?', re.IGNORECASE), "1"),
    (re.compile(r'ships?\s+within\s+(\d+)\s*(?:business\s+)?day', re.IGNORECASE), "1"),
    (re.compile(r'ships?\s+in\s+(\d+)\s*(?:business\s+)?day', re.IGNORECASE), "1"),
    (re.compile(r'(\d+)\s*(?:business\s+)?day[s]?\s+ship', re.IGNORECASE), "1"),
    (re.compile(r'days?\s+to\s+ship\s*[:：]?\s*(\d+)', re.IGNORECASE), "1"),
    (re.compile(r'lead\s*[-\s]?time[:\s]+(\d+)', re.IGNORECASE), "1"),
    (re.compile(r'납기[:\s]*(\d+)\s*일', re.IGNORECASE), "1"),
    (re.compile(r'(\d+)\s*일\s*납기', re.IGNORECASE), "1"),
    (re.compile(r'(\d+)\s*[-~]\s*(\d+)\s*(?:business\s+)?day', re.IGNORECASE), "range"),
]

_PRICE_PATTERNS: list[re.Pattern] = [
    re.compile(r'\b(KRW|USD|EUR|JPY|CNY|GBP|CAD|AUD|TWD|SGD|INR)\s*([0-9][0-9,]*(?:\.[0-9]+)?)\b', re.IGNORECASE),
    re.compile(r'([₩$€¥£₹])\s*([0-9][0-9,]*(?:\.[0-9]+)?)'),
    re.compile(r'([0-9][0-9,]*(?:\.[0-9]+)?)\s*([₩$€¥£₹])'),
    re.compile(r'([0-9][0-9,]*(?:\.[0-9]+)?)\s*원\b'),
]

def extract_candidate_details(
    candidate: dict,
    page_text: str,
    shortage_event: dict,
    page_screenshot: str | None = None,
    extraction_mode: str = "none",
    model: str = DEFAULT_LLM_MODEL,
    api_key: str | None = None,
) -> dict:
    """Extract candidate fields using pure LLM logic."""
    if extraction_mode not in VALID_EXTRACTION_MODES:
        raise ValueError(f"extraction_mode must be one of {sorted(VALID_EXTRACTION_MODES)}")
    if extraction_mode == "none" or not page_text.strip():
        return {}
    
    try:
        print(f"[DEBUG] Calling LLM for {candidate.get('candidate_id')} (vision: {bool(page_screenshot)})")
        result = extract_candidate_details_with_llm(
            candidate, page_text, shortage_event, 
            page_screenshot=page_screenshot, 
            model=model, api_key=api_key
        )
        print(f"[DEBUG] LLM extraction success for {candidate.get('candidate_id')}")
        return result
    except Exception as e:
        print(f"[DEBUG] LLM extraction failed for {candidate.get('candidate_id')}: {e}")
        return {"_llm_error": str(e)}

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

    if normalized["lead_time_days"] is None and normalized["leadtime_listed"]:
        parsed = _parse_lead_time_from_text(normalized.get("spec_text") or "")
        if parsed is not None:
            normalized["lead_time_days"] = parsed

    return normalized


def _merge_candidate_details(candidate: dict, details: dict) -> dict:
    merged = dict(candidate)
    for field in ["vendor_name", "location", "source_type", "spec_text", "spec_evidence"]:
        value = details.get(field)
        if value:
            if field == "source_type" and value == "unknown" and merged.get(field) != "unknown":
                continue
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
    cached = _RATE_CACHE.get(normalized)
    if cached and (time.time() - cached[1]) < _RATE_CACHE_TTL:
        return cached[0]
    url = f"https://api.frankfurter.dev/v1/latest?base={urllib.parse.quote(normalized)}&symbols=KRW"
    try:
        payload = _get_json(url)
    except RuntimeError as exc:
        print(f"[WARN] Exchange rate lookup failed for {normalized}: {exc}")
        fallback_rate = _get_fallback_exchange_rate_to_krw(normalized)
        if fallback_rate:
            _RATE_CACHE[normalized] = (fallback_rate, time.time())
            return fallback_rate
        return cached[0] if cached else None  # stale cache beats nothing
    rate = _to_float_or_none(payload.get("rates", {}).get("KRW"))
    if rate:
        _RATE_CACHE[normalized] = (rate, time.time())
    return rate


def _get_fallback_exchange_rate_to_krw(currency: str) -> float | None:
    url = f"https://open.er-api.com/v6/latest/{urllib.parse.quote(currency)}"
    try:
        payload = _get_json(url)
    except RuntimeError as exc:
        print(f"[WARN] Fallback exchange rate lookup failed for {currency}: {exc}")
        return None
    if payload.get("result") != "success":
        return None
    return _to_float_or_none(payload.get("rates", {}).get("KRW"))


def _parse_lead_time_from_text(text: str) -> int | None:
    for pattern, mode in _LEAD_TIME_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        if mode == "0":
            return 0
        if mode == "range":
            return min(int(m.group(1)), int(m.group(2)))
        try:
            return int(m.group(1))
        except (IndexError, ValueError):
            pass
    return None


def _append_fx_evidence(evidence: str | None, details: dict) -> str:
    raw_price = details.get("raw_price_text")
    currency = details.get("listed_currency")
    listed_price = details.get("listed_price")
    note = f"Converted listed price {raw_price or listed_price} {currency} to KRW using latest exchange rate."
    return f"{evidence} {note}".strip() if evidence else note





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
    if any(token in text for token in ["misumi", "mcmaster", "digikey", "mouser", "rs-online", "rs online", "authorized", "official distributor"]):
        return "official_distributor"
    if any(token in text for token in ["industrial", "industry", "daara", "bearingworks"]):
        return "industrial_marketplace"
    if any(token in text for token in ["amazon", "ebay", "aliexpress", "marketplace", "open market"]):
        return "marketplace"
    return "unknown"

def _enrich_candidate_from_page(candidate: dict, shortage_event: dict, model: str = DEFAULT_LLM_MODEL) -> dict:
    try:
        raw_html, page_text = fetch_page_html_and_text(candidate["source_url"])
        print(f"[DEBUG] Tier 1 fetch success: {len(page_text)} chars from {candidate['source_url']}")
    except RuntimeError as e:
        print(f"[DEBUG] Tier 1 fetch failed for {candidate['source_url']}: {e}")
        raw_html, page_text = "", ""

    # --- JSON-LD extraction from raw HTML (works even for JS-rendered price elements
    # because WooCommerce/Shopify embed schema.org data in <script> tags in the initial HTML)
    jsonld_details: dict = {}
    if raw_html:
        jsonld_price = _parse_price_from_jsonld(raw_html)
        if jsonld_price:
            raw_price_text, listed_price, listed_currency = jsonld_price
            jsonld_details = {
                "raw_price_text": raw_price_text,
                "listed_price": listed_price,
                "listed_currency": listed_currency,
                "price_listed": True,
                "spec_evidence": f"JSON-LD structured data: {raw_price_text}.",
            }
            jsonld_details = _normalize_extracted_details(jsonld_details)
            print(f"[DEBUG] JSON-LD price found for {candidate.get('candidate_id')}: {raw_price_text}")

    extraction_text = " ".join(
        part
        for part in [page_text, str(candidate.get("spec_text") or "")]
        if part
    )
    text_details = extract_candidate_details_from_text(extraction_text)

    if not page_text.strip():
        # If we couldn't fetch text, try pure vision approach
        details = {}
    else:
        # Tier 1: Text-only LLM extraction
        details = extract_candidate_details(candidate, page_text, shortage_event, extraction_mode="llm", model=model)
        details = _merge_extracted_fallback(details, text_details)

    # Merge JSON-LD price in (highest priority — structured data is reliable)
    if jsonld_details:
        details = _merge_extracted_fallback(jsonld_details, details)
        
    # Check if Tier 1 failed to get price — trigger vision fallback regardless of stock_listed.
    # (stock info can come from the search snippet while price needs a rendered page screenshot)
    if (
        details.get("price_krw") is None
        and details.get("raw_price_text") is None
        and not _is_llm_quota_error(details.get("_llm_error"))
    ):
        print(f"[DEBUG] Tier 2 fallback triggered for {candidate.get('candidate_id')}")
        # Tier 2: Vision LLM extraction fallback
        screenshot_base64 = capture_page_screenshot(candidate["source_url"])
        if screenshot_base64:
            print(f"[DEBUG] Screenshot captured for {candidate.get('candidate_id')}")
            vision_details = extract_candidate_details(
                candidate, page_text, shortage_event, 
                page_screenshot=screenshot_base64,
                extraction_mode="llm", 
                model=model
            )
            # Merge vision details over text details
            for k, v in vision_details.items():
                if v is not None and details.get(k) is None:
                    details[k] = v
                elif k in ["price_listed", "stock_listed", "leadtime_listed"]:
                    details[k] = bool(details.get(k)) or bool(vision_details.get(k))
                    
            details = _merge_extracted_fallback(details, text_details)

            if any(vision_details.get(f) is not None for f in ["price_krw", "raw_price_text"]):
                current_ev = details.get("spec_evidence") or ""
                details["spec_evidence"] = f"{current_ev} (Data extracted via Vision LLM from screenshot)".strip()

    return _merge_candidate_details(candidate, details)


def extract_candidate_details_from_text(page_text: str) -> dict:
    """Best-effort deterministic extraction from already-stripped page text.

    NOTE: This function receives *stripped* text (HTML tags already removed).
    JSON-LD extraction is therefore NOT done here — use ``_parse_price_from_jsonld``
    on the raw HTML *before* stripping instead (see ``_enrich_candidate_from_page``).
    """
    text = " ".join(str(page_text or "").split())
    if not text:
        return {}

    details: dict[str, object] = {
        "price_listed": False,
        "stock_listed": bool(re.search(r'\bin\s*stock\b|재고\s*(?:있음|보유)|ready\s+to\s+ship', text, re.IGNORECASE)),
        "leadtime_listed": bool(re.search(r'ships?\s+in|lead\s*[-\s]?time|납기|delivery\s+date', text, re.IGNORECASE)),
    }

    price = _parse_price_from_text(text)
    if price:
        raw_price_text, listed_price, listed_currency = price
        details.update(
            {
                "raw_price_text": raw_price_text,
                "listed_price": listed_price,
                "listed_currency": listed_currency,
                "price_listed": True,
                "spec_evidence": f"Page text lists price {raw_price_text}.",
            }
        )

    lead_time_days = _parse_lead_time_from_text(text)
    if lead_time_days is not None:
        details["lead_time_days"] = lead_time_days
        details["leadtime_listed"] = True

    moq = _parse_moq_from_text(text)
    if moq is not None:
        details["moq"] = moq

    return _normalize_extracted_details(details)


def _parse_price_from_jsonld(html: str) -> tuple[str, float, str] | None:
    """Extract price from JSON-LD schema.org/Product blocks embedded in page HTML.

    Handles both the raw HTML string and plain text (where the script tags may have
    been stripped by the HTML parser — in that case the JSON content is still present
    as inline text).
    """
    # Match <script type="application/ld+json">...</script> blocks
    pattern = re.compile(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>\s*([\s\S]*?)</script>',
        re.IGNORECASE,
    )
    blobs: list[str] = pattern.findall(html)

    # Fallback: if the HTML parser already stripped tags, look for raw JSON objects
    # that contain "@type" and "price" keys anywhere in the text.
    if not blobs:
        # Try to find JSON-like fragments with offer/price fields
        blobs = re.findall(r'\{[^{}]{0,2000}"@type"[^{}]{0,2000}\}', html)

    for blob in blobs:
        try:
            data = _json.loads(blob.strip())
        except (_json.JSONDecodeError, ValueError):
            continue

        price_info = _extract_price_from_jsonld_node(data)
        if price_info:
            return price_info

    return None


def _extract_price_from_jsonld_node(node: object) -> tuple[str, float, str] | None:
    """Recursively walk a JSON-LD node looking for schema.org price information."""
    if isinstance(node, list):
        for item in node:
            result = _extract_price_from_jsonld_node(item)
            if result:
                return result
        return None

    if not isinstance(node, dict):
        return None

    # Recurse into @graph arrays
    if "@graph" in node:
        result = _extract_price_from_jsonld_node(node["@graph"])
        if result:
            return result

    # Look for Offer or Product nodes with a price
    node_type = str(node.get("@type") or "").lower()
    if node_type in {"product", "offer", "aggregateoffer", "pricespecification", "unitpricespecification"}:
        # Direct price field (also handles schema.org/PriceSpecification pattern)
        raw_price = node.get("price") or node.get("lowPrice") or node.get("highPrice")
        currency = str(node.get("priceCurrency") or "").strip().upper() or None
        if raw_price is not None and currency:
            amount = _to_float_or_none(str(raw_price).replace(",", ""))
            if amount is not None and amount > 0:
                normalized_currency = _normalize_currency(currency)
                if normalized_currency:
                    raw_text = f"{currency} {raw_price}"
                    return raw_text, amount, normalized_currency

        # Recurse into priceSpecification sub-object (BigCommerce / some WooCommerce sites
        # nest the price inside offers.priceSpecification rather than offers.price)
        price_spec = node.get("priceSpecification")
        if price_spec:
            result = _extract_price_from_jsonld_node(price_spec)
            if result:
                return result

        # Recurse into offers sub-object
        offers = node.get("offers")
        if offers:
            result = _extract_price_from_jsonld_node(offers)
            if result:
                return result


    # Recurse into all dict values
    for value in node.values():
        if isinstance(value, (dict, list)):
            result = _extract_price_from_jsonld_node(value)
            if result:
                return result

    return None


def _merge_extracted_fallback(details: dict, fallback: dict) -> dict:
    merged = dict(details or {})
    for key, value in (fallback or {}).items():
        if key in {"price_listed", "stock_listed", "leadtime_listed"}:
            merged[key] = bool(merged.get(key)) or bool(value)
        elif value is not None and merged.get(key) in {None, ""}:
            merged[key] = value
    return merged


def _is_llm_quota_error(error: object) -> bool:
    text = str(error or "").lower()
    return "429" in text or "insufficient_quota" in text or "quota" in text


def _parse_price_from_text(text: str) -> tuple[str, float, str] | None:
    for pattern in _PRICE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        if "원" in pattern.pattern:
            currency_token, amount_text = "KRW", match.group(1)
        elif pattern.pattern.startswith("([0-9]"):
            amount_text, currency_token = match.group(1), match.group(2)
        else:
            currency_token, amount_text = match.group(1), match.group(2)
        currency = _normalize_currency(currency_token)
        amount = _parse_price_number(amount_text)
        if currency and amount is not None and amount > 0:
            return match.group(0), amount, currency
    return None


def _parse_price_number(value: object) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    if "," in text and "." not in text:
        last_part = text.rsplit(",", 1)[-1]
        if len(last_part) == 2:
            text = text.replace(",", ".")
        else:
            text = text.replace(",", "")
    else:
        text = text.replace(",", "")
    return _to_float_or_none(text)


def _parse_moq_from_text(text: str) -> int | None:
    match = re.search(r'\bMOQ\s*[:：]?\s*(\d+)\b|minimum\s+order\s+(?:quantity\s*)?[:：]?\s*(\d+)\b', text, re.IGNORECASE)
    if not match:
        return None
    value = next((group for group in match.groups() if group), None)
    return _to_int_or_none(value)


def _vendor_name_from_search_result(result: dict) -> str:
    title = str(result.get("title") or "").strip()
    if " - " in title:
        return title.rsplit(" - ", 1)[-1].strip() or "Unknown Vendor"
    return title or "Unknown Vendor"

def _empty_to_none(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _to_int_or_none(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return round(float(text.replace(",", "")))


def _to_float_or_none(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
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
        "₹": "INR",
    }
    normalized = aliases.get(text, text)
    return normalized if normalized in SUPPORTED_PRICE_CURRENCIES else None
