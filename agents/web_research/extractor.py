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

from .config import *
from .llm_client import extract_candidate_details_with_llm
from .scraper import fetch_page_text, _search_result_text

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
