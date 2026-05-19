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
from .scraper import fetch_page_text, _search_result_text, _get_json, capture_page_screenshot

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
        return {}

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
        page_text = fetch_page_text(candidate["source_url"])
        print(f"[DEBUG] Tier 1 fetch success: {len(page_text)} chars from {candidate['source_url']}")
    except RuntimeError as e:
        print(f"[DEBUG] Tier 1 fetch failed for {candidate['source_url']}: {e}")
        page_text = ""
        
    if not page_text.strip():
        # If we couldn't fetch text, try pure vision approach
        details = {}
    else:
        # Tier 1: Text-only LLM extraction
        details = extract_candidate_details(candidate, page_text, shortage_event, extraction_mode="llm", model=model)
        
    # Check if Tier 1 failed to get essential commercial data (price or stock)
    if details.get("price_krw") is None and details.get("raw_price_text") is None and not details.get("stock_listed"):
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
                    
            if any(vision_details.get(f) is not None for f in ["price_krw", "raw_price_text"]):
                current_ev = details.get("spec_evidence") or ""
                details["spec_evidence"] = f"{current_ev} (Data extracted via Vision LLM from screenshot)".strip()

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
    }
    normalized = aliases.get(text, text)
    return normalized if normalized in SUPPORTED_PRICE_CURRENCIES else None
