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
from .extractor import _empty_to_none, _infer_source_type, _normalize_source_type
from .scraper import _get_json

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


