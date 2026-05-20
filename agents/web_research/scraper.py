from __future__ import annotations

import gzip
import zlib
from html.parser import HTMLParser
import json
import re
import urllib.error
import urllib.request

from .config import *
from .http_client import urlopen

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
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read(max_chars * 4)
            content_type = response.headers.get("Content-Type", "")
            content_encoding = response.headers.get("Content-Encoding", "")
    except (OSError, urllib.error.HTTPError) as exc:
        raise RuntimeError(f"page fetch failed: {exc}") from exc

    encoding = content_encoding.lower()
    try:
        if "gzip" in encoding:
            raw = gzip.decompress(raw)
        elif "deflate" in encoding:
            raw = zlib.decompress(raw)
    except (EOFError, OSError, zlib.error) as exc:
        raise RuntimeError(f"page decompression failed: {exc}") from exc

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

def _get_json(url: str, headers: dict[str, str] | None = None) -> dict:
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"web search request failed: {exc}") from exc


def capture_page_screenshot(url: str) -> str | None:
    """Capture a screenshot of the page using Playwright. Returns base64 string."""
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    except ImportError:
        print("Playwright is not installed. Please run: pip install playwright && playwright install")
        return None
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # Use a reasonable desktop viewport to capture "Above the fold"
            page = browser.new_page(viewport={"width": 1280, "height": 1080})
            try:
                page.goto(url, wait_until="networkidle", timeout=15000)
            except PlaywrightTimeoutError:
                pass  # Try to capture whatever is loaded if timeout occurs
            
            # Capture as JPEG to save tokens and bandwidth
            screenshot_bytes = page.screenshot(type="jpeg", quality=60, full_page=False)
            import base64
            browser.close()
            return base64.b64encode(screenshot_bytes).decode('utf-8')
    except Exception as e:
        print(f"Failed to capture screenshot for {url}: {e}")
        return None
