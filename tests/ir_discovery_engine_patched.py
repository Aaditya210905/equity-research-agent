"""
Investor Relations Discovery Engine — Phase 1.4 v3 (Patched)

Same architecture as v2, with three fixes applied:

  1. Every BeautifulSoup(html, "lxml") call now goes through get_all_anchors()
     (from ir_anchor_fetcher.py), which falls back to "html.parser" if lxml
     isn't installed, instead of silently returning 0 candidates.
  2. get_all_anchors() also detects bot-check/JS-challenge pages that return
     200 but aren't real content, and escalates to curl_cffi -> requests ->
     (optional) Playwright automatically.
  3. _fetch_page's requests fallback no longer discards the response body
     on non-2xx statuses.

Run with logging configured, or you're debugging blind again:
    logging.basicConfig(level=logging.INFO)

Architecture:
    Ticker
      → yfinance → domain candidate
      → IR Discovery (navigation + search + patterns → candidate pool → ranking)
      → IR Crawl → document discovery → PDF validation → storage
"""

import sys
from pathlib import Path

# Ensure backend directory is in sys.path
backend_dir = str(Path(__file__).resolve().parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import logging
import re
import time
from typing import Optional
from urllib.parse import urljoin, urlparse, parse_qs, unquote, quote_plus, urlunparse

import requests
import tldextract
from bs4 import BeautifulSoup

from ir_anchor_fetcher import get_all_anchors  # <-- the fix

logger = logging.getLogger(__name__)


# ===========================================================================
# Constants
# ===========================================================================

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_TIMEOUT = 15

PAGE_STATUS = {
    200: "accessible",
    301: "redirected",
    302: "redirected",
    403: "blocked_403",
    404: "not_found_404",
    None: "connection_error",
}

IR_URL_PATTERNS = [
    "/investors", "/investors/", "/investor-relations", "/investor-relations/",
    "/investor", "/investor/", "/investors.html", "/investor.html",
    "/about/investor-relations", "/about-us/investor-relations",
    "/about/investors", "/investor-information", "/investor-centre",
    "/investor-center", "/shareholder", "/shareholders", "/financial-information",
]

IR_LINK_KEYWORDS = [
    "investor relation", "investor", "investors", "shareholder", "shareholders",
    "financial information", "investor information", "investor centre",
    "investor center",
]

STRONG_IR_SIGNALS = {
    "investor relations": 10, "investor presentation": 10, "annual report": 10,
    "financial results": 10, "quarterly results": 10, "earnings call": 10,
    "earnings transcript": 10, "shareholding pattern": 8, "regulatory disclosure": 8,
}

MEDIUM_IR_SIGNALS = {
    "financial statements": 5, "corporate announcements": 5,
    "investor information": 5, "shareholder information": 5,
    "analyst": 4, "corporate governance": 3,
}

WEAK_IR_SIGNALS = {
    "dividend": 1, "board of directors": 1, "share price": 1, "stock information": 1,
}

REPORT_LINK_KEYWORDS = [
    "annual report", "annual review", "integrated report",
    "integrated annual report", "financial results", "quarterly results",
    "investor presentation", "earnings presentation", "quarterly report",
    "financial statement", "annual return",
]

SUBPAGE_PRIORITIES = {
    "annual report": 10, "annual review": 10, "financial result": 10,
    "quarterly result": 10, "earnings call": 10, "investor presentation": 10,
    "transcript": 10, "financial statement": 8, "corporate announcement": 5,
    "governance": 3, "policies": 2,
}

CRAWL_CONFIG = {"max_depth": 3, "max_pages": 100, "request_delay": 0.5, "timeout": 15}


# ===========================================================================
# Phase 1.4.1 — URL Utilities  (unchanged)
# ===========================================================================

def _normalize_search_url(url: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    for key in ("uddg", "url", "target"):
        if key in params:
            return unquote(params[key][0])
    return url


def _canonicalize_url(url: str) -> str:
    parsed = urlparse(url)
    clean_query = ""
    if parsed.query:
        params = parse_qs(parsed.query)
        tracking_keys = {"utm_source", "utm_medium", "utm_campaign", "utm_content", "ref"}
        clean_params = {k: v for k, v in params.items() if k not in tracking_keys}
        if clean_params:
            clean_query = "&".join(f"{k}={v[0]}" for k, v in sorted(clean_params.items()))
    path = parsed.path
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse((parsed.scheme, parsed.netloc.lower(), path, "", clean_query, ""))


def _get_registrable_domain(url: str) -> str:
    ext = tldextract.extract(url)
    return f"{ext.domain}.{ext.suffix}".lower()


def _same_registrable_domain(url1: str, url2: str) -> bool:
    return _get_registrable_domain(url1) == _get_registrable_domain(url2)


# ===========================================================================
# Phase 1.4.2 — Smart HTTP Fetcher  (403 content-drop bug fixed)
# ===========================================================================

def _get_page_status(status_code: int) -> str:
    if status_code is None:
        return "connection_error"
    if status_code == 200:
        return "accessible"
    if status_code in (301, 302):
        return "redirected"
    if status_code == 403:
        return "blocked_403"
    if status_code == 404:
        return "not_found_404"
    if status_code >= 500:
        return "server_error"
    return "unknown"


def _fetch_page(url: str, timeout: int = _TIMEOUT) -> dict:
    """Fetch a URL using curl_cffi with requests fallback.

    FIX: content is now kept regardless of status code (previously the
    requests fallback discarded the body on any status >= 400, which
    threw away potentially-useful 403/challenge-page content).
    """
    try:
        from curl_cffi import requests as cffi_requests
        resp = cffi_requests.get(url, timeout=timeout, impersonate="chrome", allow_redirects=True)
        status = resp.status_code
        return {
            "status": status,
            "page_status": _get_page_status(status),
            "content": resp.text,
            "accessible": status == 200,
            "method": "curl_cffi",
        }
    except Exception as exc:
        logger.debug("curl_cffi failed for '%s': %s", url, exc)

    try:
        resp = requests.get(url, timeout=timeout, headers=_HEADERS, allow_redirects=True)
        status = resp.status_code
        return {
            "status": status,
            "page_status": _get_page_status(status),
            "content": resp.text,  # was: resp.text if status < 400 else ""
            "accessible": status == 200,
            "method": "requests",
        }
    except requests.exceptions.Timeout:
        return {"status": None, "page_status": "timeout", "content": None,
                "accessible": False, "method": "failed"}
    except requests.RequestException:
        return {"status": None, "page_status": "connection_error", "content": None,
                "accessible": False, "method": "failed"}


# ===========================================================================
# Phase 1.4.3 — Discovery Channels
# ===========================================================================

def _normalize_for_matching(s: str) -> str:
    """Lowercase and turn URL-slug delimiters into spaces so phrase keywords
    like "annual report" match slugs/filenames like "annual_report" or
    "annual-report" the same way they'd match prose text. Without this,
    keyword lists written for prose text never match anything that came
    from a URL path or filename (which is most of what a crawler sees)."""
    s = s.lower()
    s = re.sub(r'[-_+]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def _is_ir_link(text: str, href: str) -> bool:
    combined = _normalize_for_matching(text + " " + href)
    return any(kw in combined for kw in IR_LINK_KEYWORDS)


def _discover_from_navigation(website: str) -> list[dict]:
    """Scan homepage <a> tags for IR links.

    FIX: uses get_all_anchors() (curl_cffi -> requests -> optional
    Playwright, with a parser fallback chain) instead of a single
    BeautifulSoup(html, "lxml") call that silently returned 0 results
    whenever that parser wasn't available or the fetch was blocked.
    """
    candidates = []
    result = get_all_anchors(website)
    diag = result["diagnostics"]

    if not result["anchors"]:
        logger.warning("Navigation: 0 anchors from %s | diagnostics=%s", website, diag)
        return candidates

    for a in result["anchors"]:
        if _is_ir_link(a["text"], a["href"]):
            candidates.append({
                "url": _canonicalize_url(a["absolute_url"]),
                "text": a["text"],
                "method": "navigation",
                "http_status": None,
                "page_status": None,
            })

    logger.info("Navigation: %d candidates from %s (fetched via %s, %d total anchors)",
                len(candidates), website, diag.get("final_method"), len(result["anchors"]))
    return candidates


def _discover_from_search(domain: str, company_name: str = "") -> list[dict]:
    """Use DuckDuckGo to find IR pages and documents. (unchanged)"""
    candidates = []
    netloc = urlparse(domain).netloc or domain.replace("https://", "").replace("http://", "")
    registrable = _get_registrable_domain(domain)

    queries = [f"site:{netloc} investor relations", f"site:{netloc} annual report"]
    if company_name:
        queries.append(f"{company_name} investor relations")

    for query in queries:
        try:
            search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            resp = requests.get(search_url, timeout=10, headers=_HEADERS)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "lxml") if _has_lxml() else BeautifulSoup(resp.text, "html.parser")
            for a_tag in soup.find_all("a", href=True):
                href = _normalize_search_url(a_tag["href"])
                text = a_tag.get_text(strip=True)
                if _get_registrable_domain(href) == registrable:
                    candidates.append({
                        "url": _canonicalize_url(href), "text": text,
                        "method": "search_index", "http_status": None, "page_status": None,
                    })
            time.sleep(1)
        except Exception as exc:
            logger.debug("Search query failed '%s': %s", query, exc)

    logger.info("Search: %d candidates for %s", len(candidates), registrable)
    return candidates


def _has_lxml() -> bool:
    try:
        import lxml  # noqa: F401
        return True
    except ImportError:
        return False


def _discover_from_patterns(website: str) -> list[dict]:
    """Try common URL patterns. Does NOT break on first match. (unchanged)"""
    candidates = []
    base = website.rstrip("/")

    for pattern in IR_URL_PATTERNS:
        url = base + pattern
        result = _fetch_page(url, timeout=8)

        if result["page_status"] in ("not_found_404", "connection_error", "timeout", "server_error"):
            continue

        candidates.append({
            "url": _canonicalize_url(url), "text": pattern, "method": "url_pattern",
            "pattern": pattern, "http_status": result["status"],
            "page_status": result["page_status"], "accessible": result["accessible"],
        })
        logger.info("Pattern: %s → %s (%s)", pattern, result["status"], result["page_status"])

    return candidates


# ===========================================================================
# Phase 1.4.4 — Candidate Scoring  (unchanged)
# ===========================================================================

def _score_ir_candidate(candidate: dict) -> dict:
    score = 0
    evidence = []
    url = candidate["url"].lower()
    text = (candidate.get("text") or "").lower()

    if "investor-relations" in url:
        score += 40; evidence.append("+40 URL contains 'investor-relations'")
    elif "investors" in url:
        score += 35; evidence.append("+35 URL contains 'investors'")
    elif "investor" in url:
        score += 30; evidence.append("+30 URL contains 'investor'")
    elif "shareholder" in url:
        score += 20; evidence.append("+20 URL contains 'shareholder'")

    if "investor relations" in text:
        score += 30; evidence.append("+30 anchor contains 'investor relations'")
    elif "investors" in text:
        score += 25; evidence.append("+25 anchor contains 'investors'")
    elif "investor" in text:
        score += 20; evidence.append("+20 anchor contains 'investor'")
    elif "shareholder" in text:
        score += 15; evidence.append("+15 anchor contains 'shareholder'")

    content = ""
    page_result = _fetch_page(candidate["url"])
    if page_result["content"]:
        content = page_result["content"].lower()
        candidate["http_status"] = page_result["status"]
        candidate["page_status"] = page_result["page_status"]
        candidate["accessible"] = page_result["accessible"]

    if content:
        for signal, weight in STRONG_IR_SIGNALS.items():
            if signal in content:
                score += weight; evidence.append(f"+{weight} content: '{signal}'")
        for signal, weight in MEDIUM_IR_SIGNALS.items():
            if signal in content:
                score += weight; evidence.append(f"+{weight} content: '{signal}'")
        weak_total = 0
        for signal, weight in WEAK_IR_SIGNALS.items():
            if signal in content and weak_total < 3:
                score += weight; evidence.append(f"+{weight} content (weak): '{signal}'")
                weak_total += weight

    if candidate.get("method") == "navigation":
        score += 5; evidence.append("+5 found via homepage navigation")
    elif candidate.get("method") == "search_index":
        score += 3; evidence.append("+3 found via search index")

    candidate["score"] = score
    candidate["evidence"] = evidence
    return candidate


def _classify_confidence(score: int) -> str:
    if score >= 70:
        return "very_high"
    if score >= 50:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


# ===========================================================================
# Phase 1.4.5 — Document Classification  (unchanged)
# ===========================================================================

def _classify_document(text: str, url: str) -> Optional[str]:
    combined = _normalize_for_matching(text + " " + url)
    if any(kw in combined for kw in ["annual report", "annual review", "integrated report",
                                      "integrated annual report", "annual return"]):
        return "annual_report"
    if any(kw in combined for kw in ["transcript", "earnings call transcript"]):
        return "earnings_call_transcript"
    if any(kw in combined for kw in ["investor presentation", "earnings presentation",
                                      "corporate presentation", "results presentation"]):
        return "investor_presentation"
    if any(kw in combined for kw in ["quarterly result", "quarterly report"]):
        return "quarterly_result"
    if any(kw in combined for kw in ["financial result", "financial statement"]):
        return "financial_statement"
    return None


# ===========================================================================
# Phase 1.4.6 — Indian Financial Period Extraction  (unchanged)
# ===========================================================================

def _extract_financial_period(text: str) -> dict:
    result = {"financial_year": None, "quarter": None, "calendar_year": None}
    text_clean = text.upper().replace("\u2013", "-").replace("\u2014", "-")

    quarter_match = re.search(r'\b(Q[1-4]|H[12]|9M)\b', text_clean)
    if quarter_match:
        result["quarter"] = quarter_match.group(1)

    fy_range = re.search(r'FY\s*(\d{4})\s*-\s*(\d{2})', text_clean)
    if fy_range:
        end_yr = int(fy_range.group(1)[:2] + fy_range.group(2))
        result["financial_year"] = f"FY{end_yr}"; result["calendar_year"] = end_yr - 1
        return result

    fy_short = re.search(r'FY\s*(\d{2})\b', text_clean)
    if fy_short:
        yr = int(fy_short.group(1))
        full_yr = 2000 + yr if yr < 50 else 1900 + yr
        result["financial_year"] = f"FY{full_yr}"; result["calendar_year"] = full_yr - 1
        return result

    fy_full = re.search(r'FY\s*(\d{4})\b', text_clean)
    if fy_full:
        yr = int(fy_full.group(1))
        result["financial_year"] = f"FY{yr}"; result["calendar_year"] = yr - 1
        return result

    range_match = re.search(r'(\d{4})\s*-\s*(\d{2})\b', text_clean)
    if range_match:
        end_yr = int(range_match.group(1)[:2] + range_match.group(2))
        result["financial_year"] = f"FY{end_yr}"; result["calendar_year"] = end_yr - 1
        return result

    bare_year = re.search(r'\b(20[12]\d)\b', text_clean)
    if bare_year:
        yr = int(bare_year.group(1))
        if 2018 <= yr <= 2030:
            result["calendar_year"] = yr
            return result

    return result


def _get_year_from_period(period: dict) -> Optional[int]:
    if period.get("calendar_year"):
        return period["calendar_year"]
    fy = period.get("financial_year")
    if fy:
        match = re.search(r'\d{4}', fy)
        if match:
            return int(match.group()) - 1
    return None


# ===========================================================================
# Phase 1.4.7 — PDF Validation  (unchanged)
# ===========================================================================

def _is_valid_pdf(content: bytes, content_type: str = "") -> bool:
    magic_ok = len(content) >= 5 and content[:5] == b"%PDF-"
    type_ok = "application/pdf" in content_type.lower() if content_type else False
    return magic_ok or (type_ok and len(content) > 1024)


# ===========================================================================
# Company Website Discovery  (unchanged)
# ===========================================================================

def get_company_website(ticker: str) -> Optional[str]:
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        website = info.get("website")
        if website:
            logger.info("yfinance website for '%s': %s", ticker, website)
            return website
        logger.warning("No website in yfinance metadata for '%s'", ticker)
        return None
    except Exception as exc:
        logger.error("Failed to get website for '%s': %s", ticker, exc)
        return None


def get_company_name(ticker: str) -> str:
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        return info.get("longName") or info.get("shortName") or ""
    except Exception:
        return ""


# ===========================================================================
# IR Page Discovery — Pooled + Ranked  (unchanged logic, relies on fixed channels)
# ===========================================================================

def discover_ir_page(website: str, company_name: str = "") -> Optional[dict]:
    logger.info("Discovering IR page for: %s", website)
    all_candidates = []

    nav = _discover_from_navigation(website)
    all_candidates.extend(nav)

    search = _discover_from_search(website, company_name)
    all_candidates.extend(search)

    patterns = _discover_from_patterns(website)
    all_candidates.extend(patterns)

    if not all_candidates:
        logger.warning("No IR candidates found for '%s'", website)
        return None

    logger.info("Total raw candidates: %d (nav=%d, search=%d, patterns=%d)",
                len(all_candidates), len(nav), len(search), len(patterns))

    seen = {}
    for c in all_candidates:
        canonical = _canonicalize_url(c["url"])
        if canonical not in seen:
            seen[canonical] = c
            seen[canonical]["url"] = canonical
        else:
            existing = seen[canonical]
            if c.get("method") == "navigation" and existing.get("method") != "navigation":
                c["url"] = canonical
                seen[canonical] = c

    unique_candidates = list(seen.values())
    logger.info("After dedup: %d unique candidates", len(unique_candidates))

    company_domain = _get_registrable_domain(website)
    domain_filtered = [c for c in unique_candidates if _get_registrable_domain(c["url"]) == company_domain]
    if not domain_filtered:
        domain_filtered = unique_candidates

    scored = []
    for candidate in domain_filtered[:8]:
        scored_candidate = _score_ir_candidate(candidate)
        scored_candidate["confidence"] = _classify_confidence(scored_candidate["score"])
        scored.append(scored_candidate)
        time.sleep(0.3)

    scored.sort(key=lambda c: c["score"], reverse=True)
    best = scored[0]
    logger.info("Best IR candidate: %s (score=%d, confidence=%s, method=%s)",
                best["url"], best["score"], best["confidence"], best["method"])
    for e in best.get("evidence", []):
        logger.debug("  Evidence: %s", e)

    return best


# ===========================================================================
# Phase 1.4.8 — Document Discovery  (sub-page extraction fixed)
# ===========================================================================

def _score_subpage_link(text: str, href: str) -> int:
    combined = _normalize_for_matching(text + " " + href)
    score = 0
    for keyword, priority in SUBPAGE_PRIORITIES.items():
        if keyword in combined:
            score = max(score, priority)
    return score


def discover_documents(ir_url: str, company_domain: str = "") -> list[dict]:
    documents = []
    visited = {_canonicalize_url(ir_url)}
    max_pages = CRAWL_CONFIG["max_pages"]

    docs = _scan_page_for_documents(ir_url)
    documents.extend(docs)

    # FIX: sub-page discovery now goes through get_all_anchors() instead of
    # a raw BeautifulSoup(html, "lxml") call on _fetch_page's output.
    subpage_queue = []
    anchor_result = get_all_anchors(ir_url)
    if not anchor_result["anchors"]:
        logger.warning("Sub-page scan: 0 anchors from %s | diagnostics=%s",
                        ir_url, anchor_result["diagnostics"])

    for a in anchor_result["anchors"]:
        text, href = a["text"], a["href"]
        full_url = a["absolute_url"]
        canonical = _canonicalize_url(full_url)

        if (canonical not in visited
                and not href.lower().endswith(".pdf")
                and _same_registrable_domain(ir_url, full_url)):
            priority = _score_subpage_link(text, href)
            if priority > 0:
                subpage_queue.append((priority, canonical, text))

    subpage_queue.sort(key=lambda x: x[0], reverse=True)
    pages_crawled = 0

    for priority, url, text in subpage_queue:
        if pages_crawled >= max_pages:
            break
        if url in visited:
            continue
        visited.add(url)
        sub_docs = _scan_page_for_documents(url)
        documents.extend(sub_docs)
        pages_crawled += 1
        time.sleep(CRAWL_CONFIG["request_delay"])

    seen = set()
    unique = []
    for doc in documents:
        canon = _canonicalize_url(doc["url"])
        if canon not in seen:
            seen.add(canon)
            doc["url"] = canon
            unique.append(doc)

    type_priority = {
        "annual_report": 0, "quarterly_result": 1, "financial_statement": 2,
        "investor_presentation": 3, "earnings_call_transcript": 4,
    }
    unique.sort(key=lambda d: (
        type_priority.get(d["doc_type"], 9),
        -(d.get("calendar_year") or d.get("year") or 0),
    ))

    unique = unique[:50]
    logger.info("Found %d documents on IR page: %s", len(unique), ir_url)
    return unique


def _discover_documents_from_search(domain: str, company_name: str = "") -> list[dict]:
    documents = []
    registrable = _get_registrable_domain(domain)
    netloc = urlparse(domain).netloc

    queries = [f"site:{netloc} annual report filetype:pdf",
               f"site:{netloc} investor presentation filetype:pdf"]
    if company_name:
        queries.append(f"{company_name} annual report filetype:pdf site:{netloc}")

    for query in queries:
        try:
            search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            resp = requests.get(search_url, timeout=10, headers=_HEADERS)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "lxml") if _has_lxml() else BeautifulSoup(resp.text, "html.parser")
            for a_tag in soup.find_all("a", href=True):
                href = _normalize_search_url(a_tag["href"])
                text = a_tag.get_text(strip=True)
                if _get_registrable_domain(href) == registrable and href.lower().endswith(".pdf"):
                    doc_type = _classify_document(text, href)
                    if doc_type:
                        period = _extract_financial_period(text + " " + href)
                        documents.append({
                            "url": _canonicalize_url(href), "title": text or href.split("/")[-1],
                            "doc_type": doc_type, "year": _get_year_from_period(period),
                            "financial_year": period.get("financial_year"),
                            "quarter": period.get("quarter"), "calendar_year": period.get("calendar_year"),
                            "file_type": "pdf", "confidence": 0.7,
                        })
            time.sleep(1)
        except Exception as exc:
            logger.debug("Search document discovery failed: %s", exc)

    seen = set()
    unique = []
    for doc in documents:
        if doc["url"] not in seen:
            seen.add(doc["url"])
            unique.append(doc)

    logger.info("Search found %d documents for %s", len(unique), registrable)
    return unique


def _scan_page_for_documents(page_url: str) -> list[dict]:
    """Scan a single page for PDF document links.

    FIX: uses get_all_anchors() instead of a raw _fetch_page + BeautifulSoup
    (lxml) call, so this survives both missing-lxml and blocked-fetch cases.
    """
    documents = []
    result = get_all_anchors(page_url)

    if not result["anchors"]:
        logger.debug("Doc scan: 0 anchors from %s | %s", page_url, result["diagnostics"])
        return documents

    for a in result["anchors"]:
        href = a["href"]
        link_text = a["text"]
        full_url = a["absolute_url"]

        is_pdf = href.lower().endswith(".pdf") or "pdf" in href.lower()
        if not is_pdf:
            continue

        doc_type = _classify_document(link_text, href)
        if not doc_type:
            combined = _normalize_for_matching(link_text + " " + href)
            if any(kw in combined for kw in REPORT_LINK_KEYWORDS):
                doc_type = "annual_report"
            else:
                continue

        period = _extract_financial_period(link_text + " " + href)
        title = link_text if link_text else href.split("/")[-1]

        documents.append({
            "url": full_url, "title": title, "doc_type": doc_type,
            "year": _get_year_from_period(period),
            "financial_year": period.get("financial_year"),
            "quarter": period.get("quarter"), "calendar_year": period.get("calendar_year"),
            "file_type": "pdf",
            "confidence": 0.9 if not result["diagnostics"]["looks_blocked"] else 0.6,
        })

    return documents


# ===========================================================================
# Document Download  (unchanged)
# ===========================================================================

def download_document(url: str, save_dir: str, filename: str = None) -> dict:
    import hashlib
    from pathlib import Path

    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)

    if not filename:
        parsed = urlparse(url)
        filename = parsed.path.split("/")[-1]
        if not filename or not filename.endswith(".pdf"):
            filename = f"document_{hash(url) % 10000:04d}.pdf"

    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    file_path = save_path / filename

    content = None
    content_type = ""

    try:
        from curl_cffi import requests as cffi_requests
        resp = cffi_requests.get(url, timeout=30, impersonate="chrome", allow_redirects=True)
        if resp.status_code == 200:
            content = resp.content
            content_type = resp.headers.get("Content-Type", "")
    except Exception as exc:
        logger.debug("curl_cffi download failed for '%s': %s", url, exc)

    if content is None:
        try:
            resp = requests.get(url, timeout=30, headers=_HEADERS, allow_redirects=True)
            resp.raise_for_status()
            content = resp.content
            content_type = resp.headers.get("Content-Type", "")
        except Exception as exc:
            logger.error("Download failed for '%s': %s", url, exc)
            return {"success": False, "file_path": None, "file_size": 0,
                    "checksum_sha256": None, "error": str(exc)}

    if not _is_valid_pdf(content, content_type):
        logger.warning("Not a valid PDF (magic bytes check failed): %s", url)
        return {"success": False, "file_path": None, "file_size": 0,
                "checksum_sha256": None, "error": "Not a valid PDF"}

    sha256 = hashlib.sha256(content).hexdigest()
    with open(file_path, "wb") as f:
        f.write(content)

    file_size = len(content)
    logger.info("Downloaded & validated: %s (%d bytes)", file_path, file_size)

    return {"success": True, "file_path": str(file_path), "file_size": file_size,
            "checksum_sha256": sha256}


# ===========================================================================
# Public API — Full Pipeline  (unchanged)
# ===========================================================================

def discover_and_collect(ticker: str) -> dict:
    from connectors.yahoo_finance import resolve_ticker

    resolved = resolve_ticker(ticker)
    logger.info("Phase 1.4 pipeline for: %s (resolved: %s)", ticker, resolved)

    result = {
        "ticker": resolved,
        "company": {"name": ""},
        "website": {"url": None, "verified": False, "confidence": 0.0, "source": "yfinance",
                     "http_status": None, "page_status": None},
        "ir": {"url": None, "confidence": None, "score": 0, "method": None,
               "http_status": None, "page_status": None, "evidence": []},
        "documents_found": [],
    }

    company_name = get_company_name(resolved)
    result["company"]["name"] = company_name

    website = get_company_website(resolved)
    if not website:
        return result

    result["website"]["url"] = website
    result["website"]["confidence"] = 0.9

    http_check = _fetch_page(website)
    result["website"]["http_status"] = http_check["status"]
    result["website"]["page_status"] = http_check["page_status"]
    result["website"]["verified"] = True
    if http_check["accessible"]:
        result["website"]["confidence"] = 1.0

    logger.info("Website: %s → %s (%s via %s)",
                website, http_check["status"], http_check["page_status"], http_check["method"])

    ir = discover_ir_page(website, company_name)
    if not ir:
        return result

    result["ir"]["url"] = ir["url"]
    result["ir"]["score"] = ir.get("score", 0)
    result["ir"]["confidence"] = ir.get("confidence", "low")
    result["ir"]["method"] = ir.get("method", "unknown")
    result["ir"]["http_status"] = ir.get("http_status")
    result["ir"]["page_status"] = ir.get("page_status")
    result["ir"]["evidence"] = ir.get("evidence", [])

    documents = discover_documents(ir["url"], website)

    if not documents and not http_check["accessible"]:
        logger.info("Direct crawl found 0 docs, trying search...")
        documents = _discover_documents_from_search(website, company_name)

    result["documents_found"] = documents

    logger.info("Pipeline complete: ticker=%s, ir=%s (score=%d), docs=%d",
                resolved, ir["url"], ir.get("score", 0), len(documents))

    return result


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ticker = sys.argv[1] if len(sys.argv) > 1 else "TCS.NS"
    result = discover_and_collect(ticker)
    print(f"\nIR URL: {result['ir']['url']} (confidence={result['ir']['confidence']})")
    print(f"Documents found: {len(result['documents_found'])}")
    for d in result["documents_found"][:10]:
        print(f"  [{d['doc_type']}] {d['title']} -> {d['url']}")