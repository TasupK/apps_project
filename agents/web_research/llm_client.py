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
        f"{base_query} Korea distributor site:.kr",
        f"buy {material_name} Korea price stock lead time distributor site:.kr",
        f"{material_name} in stock price Korean official distributor",
        f"{material_name} replacement alternative Korea distributor lead time",
        f"{material_name} official datasheet price stock Korea",
        f"{material_name} 구매 가격 재고 납기 국내 대리점",
        f"{material_name} 대체품 호환품 가격 재고 납기",
        f"{category} {material_name} compatible replacement {spec_text} Korea",
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

    return _dedupe_queries(fallback_queries + llm_queries)


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
        "max_tokens": 300,  # OpenAI 응답 토큰 제한
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

def extract_candidate_details_with_llm(
    candidate: dict,
    page_text: str,
    shortage_event: dict,
    page_screenshot: str | None = None,
    model: str = DEFAULT_LLM_MODEL,
    api_key: str | None = None,
) -> dict:
    """Ask OpenAI to extract contract fields from one product/source page using Multimodal (Text + Vision)."""
    token = os.environ.get("OPENAI_API_KEY") if api_key is None else api_key
    if not token:
        raise RuntimeError("OPENAI_API_KEY is required for LLM detail extraction")

    content = [
        {
            "type": "text",
            "text": f"Instruction: {DETAIL_EXTRACTION_PROMPT}\n\nInput Data: " + json.dumps({
                "shortage_event": {
                    "material_id": shortage_event["material_id"],
                    "material_name": shortage_event["material_name"],
                    "category": shortage_event["category"],
                    "technical_specification": shortage_event["technical_specification"],
                },
                "candidate": candidate,
                "page_text": page_text[:DEFAULT_PAGE_TEXT_LIMIT],
            }, ensure_ascii=False)
        }
    ]
    
    if page_screenshot:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{page_screenshot}"}
        })

    request_body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a professional industrial procurement assistant."},
            {"role": "user", "content": content}
        ],
        "max_tokens": 1000,
        "response_format": {"type": "json_object"}
    }
    payload = json.dumps(request_body).encode("utf-8")
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
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
    # Chat Completions API response structure
    choices = response_body.get("choices", [])
    if not choices:
        # Fallback to previous custom format if needed
        text = response_body.get("output_text") or _extract_response_text(response_body)
    else:
        text = choices[0].get("message", {}).get("content")

    if not text:
        raise RuntimeError("LLM detail extraction returned no text")
    try:
        from .extractor import _normalize_extracted_details
        parsed = json.loads(text)
    except (json.JSONDecodeError, ImportError) as exc:
        raise RuntimeError(f"LLM detail extraction failed to parse JSON: {exc}") from exc
    return _normalize_extracted_details(parsed)
