"""Backward-compatible Phase 2 web research API.

The Phase 2 implementation now lives under ``agents.web_research``.  Older
tests and callers still import ``agents.web_research_agent`` and monkeypatch
module-level functions, so this module keeps that surface stable.
"""

from __future__ import annotations

import urllib

from agents.web_research.config import *
from agents.web_research import agent as _agent
from agents.web_research import extractor as _extractor
from agents.web_research import llm_client as _llm_client
from agents.web_research import scraper as _scraper
from agents.web_research import search_engine as _search_engine
from agents.web_research.validator import load_shortage_event, validate_candidate_results


search_web = _search_engine.search_web
fetch_page_text = _scraper.fetch_page_text
extract_candidate_details = _extractor.extract_candidate_details
get_exchange_rate_to_krw = _extractor.get_exchange_rate_to_krw

build_search_query = _llm_client.build_search_query
build_deterministic_query_candidates = _llm_client.build_deterministic_query_candidates
generate_query_candidates = _llm_client.generate_query_candidates
make_search_result = _search_engine.make_search_result
get_verified_search_results = _search_engine.get_verified_search_results
_canonical_url = _search_engine._canonical_url
_rank_search_results = _search_engine._rank_search_results
_parse_llm_query_response = _llm_client._parse_llm_query_response
extract_candidate_details_with_llm = _llm_client.extract_candidate_details_with_llm
_merge_candidate_details = _extractor._merge_candidate_details


def _sync_patchable_functions() -> None:
    _search_engine.search_web = search_web
    _scraper.fetch_page_text = fetch_page_text
    _extractor.fetch_page_text = fetch_page_text
    _extractor.extract_candidate_details = extract_candidate_details
    _extractor.get_exchange_rate_to_krw = get_exchange_rate_to_krw


def collect_search_results(
    queries: list[str],
    provider: str | None = None,
    max_results_per_query: int = DEFAULT_MAX_RESULTS_PER_QUERY,
) -> list[dict]:
    _sync_patchable_functions()
    return _search_engine.collect_search_results(
        queries,
        provider=provider,
        max_results_per_query=max_results_per_query,
    )


def build_candidate_results(*args, **kwargs) -> dict:
    _sync_patchable_functions()
    return _agent.build_candidate_results(*args, **kwargs)


def run_web_research(*args, **kwargs) -> dict:
    _sync_patchable_functions()
    return _agent.run_web_research(*args, **kwargs)


def extract_candidate_details_from_text(page_text: str) -> dict:
    _sync_patchable_functions()
    return _extractor.extract_candidate_details_from_text(page_text)


def _parse_candidate_detail_response(response_body: dict) -> dict:
    _sync_patchable_functions()
    text = response_body.get("output_text") or _llm_client._extract_response_text(response_body)
    if not text:
        raise RuntimeError("LLM detail extraction returned no text")
    import json

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("LLM detail extraction returned invalid JSON") from exc
    return _extractor._normalize_extracted_details(parsed)
