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
from .validator import load_shortage_event, validate_candidate_results
from .search_engine import collect_search_results, get_verified_search_results
from .llm_client import generate_query_candidates
from .extractor import (
    _apply_min_price,
    _enrich_candidate_from_page,
    _merge_candidate_details,
    _normalize_source_type,
    _vendor_name_from_search_result,
)
from .scraper import _search_result_text

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
    verified_results = _filter_relevant_search_results(
        get_verified_search_results(search_results),
        shortage_event,
    )[:max_candidates]
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


def _filter_relevant_search_results(results: list[dict], shortage_event: dict) -> list[dict]:
    """Keep live results anchored to the shortage material before promotion."""
    return [
        result
        for result in results
        if _search_result_matches_shortage_material(result, shortage_event)
    ]


def _search_result_matches_shortage_material(result: dict, shortage_event: dict) -> bool:
    haystack = _normalize_match_text(
        " ".join(
            str(result.get(field) or "")
            for field in ["title", "url", "snippet"]
        )
    )
    strong_terms, weak_terms = _target_match_terms(shortage_event)

    if any(term in haystack for term in strong_terms):
        return True

    weak_hits = sum(1 for term in weak_terms if term in haystack)
    return weak_hits >= 2


def _target_match_terms(shortage_event: dict) -> tuple[list[str], list[str]]:
    raw_terms = [
        shortage_event.get("material_name"),
        shortage_event.get("mpn"),
        shortage_event.get("brand"),
        *(shortage_event.get("search_keywords") or []),
    ]
    strong_terms: list[str] = []
    weak_terms: list[str] = []

    for raw_term in raw_terms:
        normalized = _normalize_match_text(raw_term)
        if not normalized:
            continue
        compact = normalized.replace(" ", "")
        token_terms = [
            token
            for token in normalized.split()
            if len(token) >= 4 or any(char.isdigit() for char in token)
        ]
        for term in {normalized, compact, *token_terms}:
            if _is_strong_match_term(term):
                strong_terms.append(term)
            elif len(term) >= 4:
                weak_terms.append(term)

    for value in (shortage_event.get("spec_attributes") or {}).values():
        normalized = _normalize_match_text(value)
        if normalized:
            weak_terms.append(normalized)

    return _dedupe_match_terms(strong_terms), _dedupe_match_terms(weak_terms)


def _is_strong_match_term(term: str) -> bool:
    if len(term) < 4:
        return False
    return any(char.isdigit() for char in term) or "-" in term


def _normalize_match_text(value: object) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^0-9a-z가-힣]+", " ", text)
    return " ".join(text.split())


def _dedupe_match_terms(terms: list[str]) -> list[str]:
    deduped = []
    seen = set()
    for term in terms:
        if term and term not in seen:
            deduped.append(term)
            seen.add(term)
    return deduped

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
        import sys
        sys.stdout.reconfigure(encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Wrote candidate results: {args.output}")


if __name__ == "__main__":
    main()
