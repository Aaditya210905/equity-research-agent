"""
ir_anchor_fetcher.py

Drop-in replacement for the anchor-extraction step in the IR Discovery
Engine (Phase 1.4). Fixes the silent-failure mode that likely explains
why sites like tcs.com return zero candidates:

  1. No logging was ever configured, so logger.info(...) diagnostics
     (which is most of the useful output) were being dropped by Python's
     default WARNING-level root logger. You were debugging blind.
  2. A 200 status code was trusted as "got real content" even when the
     body is actually a bot-check / JS-challenge page. This module adds
     a `_looks_blocked()` check so that case is caught and logged
     instead of silently producing 0 anchors.
  3. The `requests` fallback path was discarding response content on
     403s (`resp.text if status < 400 else ""`), which threw away
     bodies that were sometimes still worth inspecting.
  4. `BeautifulSoup(..., "lxml")` errors were being caught by a bare
     `except Exception`, so if `lxml` isn't installed, EVERY page parse
     fails silently and you get 0 candidates for every site, not just
     TCS. This adds a parser fallback chain (lxml -> html.parser).

Usage
-----
    from ir_anchor_fetcher import get_all_anchors, diagnose_url

    result = get_all_anchors("https://www.tcs.com/investor-relations")
    for a in result["anchors"]:
        print(a["text"], "->", a["absolute_url"])

    # or just run this file directly against a URL to see what's happening:
    #   python ir_anchor_fetcher.py https://www.tcs.com/investor-relations
"""

import logging
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Phrases that show up on bot-check / access-denied / JS-challenge pages.
# A 200 status with one of these in the first few KB means "not real content",
# even though naive status-code checks would call it a success.
_BLOCK_SIGNS = [
    "access denied", "are you a human", "captcha", "unusual traffic",
    "please verify you are a human", "attention required",
    "request blocked", "bot detection", "enable javascript to continue",
    "checking your browser", "just a moment", "ddos protection by",
]

# Below this many characters, treat the fetch as suspect even without a
# keyword match — real corporate homepages/IR pages are never this small.
_MIN_PLAUSIBLE_LEN = 500


def _looks_blocked(html: str) -> bool:
    if not html or len(html) < _MIN_PLAUSIBLE_LEN:
        return True
    sample = html[:3000].lower()
    return any(sign in sample for sign in _BLOCK_SIGNS)


def _parse_html(html: str):
    """Try lxml first, fall back to the stdlib parser so a missing
    `lxml` install degrades gracefully instead of killing every parse."""
    for parser in ("lxml", "html.parser"):
        try:
            return BeautifulSoup(html, parser)
        except Exception as exc:
            logger.debug("Parser '%s' failed: %s", parser, exc)
    return None


def _fetch_with_playwright(url: str, timeout: int = 20) -> str:
    """Last-resort fetch via a real headless browser. Handles both
    JS-rendered navigation and most JS-based bot challenges that
    curl_cffi/requests can't clear on their own.

    Requires: pip install playwright && playwright install chromium
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(user_agent=_HEADERS["User-Agent"])
            page.goto(url, timeout=timeout * 1000, wait_until="networkidle")
            return page.content()
        finally:
            browser.close()


def get_all_anchors(url: str, use_browser_fallback: bool = True, timeout: int = 20) -> dict:
    """Fetch a URL and extract every <a href> tag, trying progressively
    stronger fetch strategies until one produces real (non-blocked) content.

    Returns
    -------
    dict: {
        "anchors": [{"text": str, "href": str, "absolute_url": str}, ...],
        "diagnostics": {
            "attempts": [...],       # what was tried and what happened
            "final_method": str,     # which layer produced the content used
            "final_content_len": int,
            "looks_blocked": bool,   # true if even the best attempt looks blocked
        },
    }
    """
    diagnostics = {"url": url, "attempts": []}
    html, method = None, None

    # ---- Layer 1: curl_cffi (Chrome TLS/JA3 impersonation) ----
    try:
        from curl_cffi import requests as cffi_requests
        resp = cffi_requests.get(url, timeout=timeout, impersonate="chrome124", allow_redirects=True)
        candidate = resp.text
        diagnostics["attempts"].append({
            "method": "curl_cffi", "status": resp.status_code,
            "content_len": len(candidate or ""), "blocked": _looks_blocked(candidate),
        })
        if candidate and (not html or len(candidate) > len(html)):
            html, method = candidate, "curl_cffi"
    except Exception as exc:
        diagnostics["attempts"].append({"method": "curl_cffi", "error": str(exc)})

    # ---- Layer 2: plain requests ----
    if not html or _looks_blocked(html):
        try:
            resp = requests.get(url, timeout=timeout, headers=_HEADERS, allow_redirects=True)
            candidate = resp.text  # keep body regardless of status — a 403 body can still be diagnostic
            diagnostics["attempts"].append({
                "method": "requests", "status": resp.status_code,
                "content_len": len(candidate or ""), "blocked": _looks_blocked(candidate),
            })
            if candidate and (not html or len(candidate) > len(html)):
                html, method = candidate, "requests"
        except Exception as exc:
            diagnostics["attempts"].append({"method": "requests", "error": str(exc)})

    # ---- Layer 3: headless browser (only if still blocked/empty) ----
    if use_browser_fallback and (not html or _looks_blocked(html)):
        try:
            candidate = _fetch_with_playwright(url, timeout=timeout)
            diagnostics["attempts"].append({
                "method": "playwright", "content_len": len(candidate or ""),
                "blocked": _looks_blocked(candidate),
            })
            if candidate and (not html or len(candidate) > len(html)):
                html, method = candidate, "playwright"
        except Exception as exc:
            diagnostics["attempts"].append({"method": "playwright", "error": str(exc)})

    diagnostics["final_method"] = method
    diagnostics["final_content_len"] = len(html or "")
    diagnostics["looks_blocked"] = _looks_blocked(html) if html else True

    if not html:
        return {"anchors": [], "diagnostics": diagnostics}

    soup = _parse_html(html)
    if soup is None:
        diagnostics["parse_error"] = "no working HTML parser (check lxml install)"
        return {"anchors": [], "diagnostics": diagnostics}

    anchors = []
    for a in soup.find_all("a", href=True):
        anchors.append({
            "text": a.get_text(strip=True),
            "href": a["href"],
            "absolute_url": urljoin(url, a["href"]),
        })

    return {"anchors": anchors, "diagnostics": diagnostics}


def diagnose_url(url: str) -> None:
    """Print a human-readable diagnosis of what happens when fetching a URL.
    Run this against any 'doesn't work' site first — it tells you exactly
    which layer is failing instead of leaving you guessing."""
    result = get_all_anchors(url)
    diag = result["diagnostics"]

    print(f"\nURL: {url}")
    print("-" * 60)
    for attempt in diag["attempts"]:
        if "error" in attempt:
            print(f"  {attempt['method']:12s} ERROR: {attempt['error']}")
        else:
            flag = " <- looks blocked/bot-checked" if attempt.get("blocked") else ""
            print(f"  {attempt['method']:12s} status={attempt.get('status')} "
                  f"len={attempt['content_len']}{flag}")
    print("-" * 60)
    print(f"  Used: {diag['final_method']} | final length: {diag['final_content_len']} "
          f"| still looks blocked: {diag['looks_blocked']}")
    print(f"  Anchors extracted: {len(result['anchors'])}")
    if result["anchors"]:
        print("\n  Sample anchors:")
        for a in result["anchors"][:15]:
            text = (a["text"][:45] + "…") if len(a["text"]) > 45 else a["text"]
            print(f"    {text:46s} -> {a['absolute_url']}")
    print()


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    target = sys.argv[1] if len(sys.argv) > 1 else "https://www.tcs.com/investor-relations"
    diagnose_url(target)