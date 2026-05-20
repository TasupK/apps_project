from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .config import *
from .http_client import urlopen

def _get_llm_config(api_key: str | None = None) -> tuple[str, str, str]:
    """Return (base_url, token, model) — prefers OpenAI if a key is found, else Ollama."""
    token = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("GPT_API_KEY")
    if token:
        return "https://api.openai.com/v1", token, DEFAULT_OPENAI_MODEL
    base = os.environ.get("OLLAMA_BASE_URL", DEFAULT_LLM_API_BASE).rstrip("/")
    return base, "ollama", DEFAULT_OLLAMA_MODEL


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
        f"{base_query}",
        f"{material_name} {spec_text}",
        f"{material_name} 국내 대리점 가격 재고 납기",
        f"{material_name} 구매 가격 재고 납기 당일출고 견적 장바구니",
        f"{material_name} 산업재몰 상품상세 site:.kr",
        f"{material_name} official distributor price stock lead time",
        f"{material_name} official datasheet price stock",
        f"{material_name} authorized distributor in stock quote buy",
        f"{material_name} price stock lead time quote buy",
        f"{material_name} replacement alternative equivalent",
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

    return _dedupe_queries(fallback_queries + llm_queries)


def generate_query_candidates_with_llm(
    shortage_event: dict,
    model: str = DEFAULT_LLM_MODEL,
    api_key: str | None = None,
) -> list[str]:
    """Ask the configured LLM to generate search query candidates for live web research."""
    base_url, token, model = _get_llm_config(api_key)

    request_body = {
        "model": model,
        "messages": [
            {"role": "system", "content": QUERY_GENERATION_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "material_id": shortage_event["material_id"],
                        "material_name": shortage_event["material_name"],
                        "category": shortage_event["category"],
                        "technical_specification": shortage_event["technical_specification"],
                        "search_keywords": shortage_event["search_keywords"],
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "max_tokens": 300,
        "response_format": {"type": "json_object"},
    }
    payload = json.dumps(request_body).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            response_body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"LLM query generation failed: {_format_http_error(exc)}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"LLM query generation failed: {exc}") from exc

    return _parse_llm_query_response(response_body)


def _parse_llm_query_response(response_body: dict) -> list[str]:
    choices = response_body.get("choices", [])
    if choices:
        text = choices[0].get("message", {}).get("content")
    else:
        text = response_body.get("output_text") or _extract_response_text(response_body)
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
    """Ask the configured LLM to extract contract fields from one product/source page."""
    base_url, token, model = _get_llm_config(api_key)

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
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            response_body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"LLM detail extraction failed: {_format_http_error(exc)}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"LLM detail extraction failed: {exc}") from exc

    return _parse_candidate_detail_response(response_body)


def _format_http_error(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8", errors="replace")
        payload = json.loads(body)
        error = payload.get("error", {})
        message = error.get("message") or body
        code = error.get("code")
        if code:
            return f"HTTP {exc.code} {code}: {message}"
        return f"HTTP {exc.code}: {message}"
    except Exception:
        return f"HTTP {exc.code}: {exc.reason}"


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
