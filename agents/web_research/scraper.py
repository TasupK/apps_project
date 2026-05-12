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

def _search_result_text(result: dict) -> str:
    parts = [result.get("title"), result.get("snippet")]
    text = ". ".join(str(part).strip() for part in parts if str(part or "").strip())
    return text or "Verified web search result with limited snippet evidence."
