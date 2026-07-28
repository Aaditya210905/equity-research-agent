"""
SEC EDGAR connector — download 10-K, 10-Q, and 8-K filings.

SEC EDGAR is completely free, requires no API key, and covers 20M+ filings
back to 1994. The only requirement is a descriptive User-Agent header.

Architecture:
    Document Service  ->  SEC EDGAR Connector  ->  EDGAR REST API
                                                      |
                                                      v
                                               Local file storage

Key endpoints used:
    - Company tickers:  https://www.sec.gov/files/company_tickers.json
    - Submissions:      https://data.sec.gov/submissions/CIK{cik}.json
    - Filing documents: https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{doc}
    - Company facts:    https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json
"""

import hashlib
import logging
import time
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SEC_HEADERS = {
    "User-Agent": "EquityResearchAgent/1.0 contact@example.com",
    "Accept-Encoding": "gzip, deflate",
}

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"

# Map filing form types to our document types
FORM_TO_DOC_TYPE = {
    "10-K": "annual_report",
    "10-K/A": "annual_report",
    "20-F": "annual_report",      # Foreign private issuers
    "10-Q": "quarterly_report",
    "10-Q/A": "quarterly_report",
    "8-K": "announcement",
    "8-K/A": "announcement",
}

# Respect SEC rate limits (max 10 req/s, we'll be conservative)
_REQUEST_DELAY = 0.15  # seconds between requests


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------
class SECEdgarError(Exception):
    """Raised when SEC EDGAR operations fail."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
_CIK_CACHE: dict[str, dict] = {}  # ticker -> {cik, name}


def _rate_limit():
    """Simple rate limiter — sleep between requests."""
    time.sleep(_REQUEST_DELAY)


def _sec_get(url: str, timeout: float = 30.0) -> httpx.Response:
    """Make a GET request to SEC with proper headers and rate limiting."""
    _rate_limit()
    try:
        response = httpx.get(url, headers=SEC_HEADERS, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
        return response
    except httpx.HTTPStatusError as exc:
        logger.error("SEC EDGAR HTTP error %s for %s", exc.response.status_code, url)
        raise SECEdgarError(f"HTTP {exc.response.status_code} from SEC EDGAR") from exc
    except httpx.RequestError as exc:
        logger.error("SEC EDGAR request error for %s: %s", url, exc)
        raise SECEdgarError(f"Request failed: {exc}") from exc


def _compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


# ---------------------------------------------------------------------------
# CIK Resolution
# ---------------------------------------------------------------------------

def resolve_cik(ticker: str) -> dict:
    """Look up the SEC CIK number for a given ticker.

    Returns
    -------
    dict
        {"cik": "0000320193", "name": "Apple Inc.", "ticker": "AAPL"}

    Raises
    ------
    SECEdgarError
        If the ticker is not found in SEC's database (likely not a US company).
    """
    ticker_upper = ticker.strip().upper()

    # Check cache
    if ticker_upper in _CIK_CACHE:
        return _CIK_CACHE[ticker_upper]

    logger.info("Resolving CIK for '%s' from SEC...", ticker_upper)
    response = _sec_get(COMPANY_TICKERS_URL)
    data = response.json()

    # Build full cache on first call
    for entry in data.values():
        t = str(entry["ticker"]).upper()
        _CIK_CACHE[t] = {
            "cik": str(entry["cik_str"]).zfill(10),
            "name": entry["title"],
            "ticker": t,
        }

    if ticker_upper not in _CIK_CACHE:
        raise SECEdgarError(
            f"Ticker '{ticker_upper}' not found in SEC EDGAR. "
            f"This is likely not a US-listed company."
        )

    return _CIK_CACHE[ticker_upper]


# ---------------------------------------------------------------------------
# Filing Discovery
# ---------------------------------------------------------------------------

def get_filings_list(
    ticker: str,
    form_types: Optional[list[str]] = None,
    limit: int = 10,
) -> list[dict]:
    """Get a list of available SEC filings for a company.

    Parameters
    ----------
    ticker : str
        US stock ticker (e.g. "AAPL", "MSFT").
    form_types : list[str], optional
        Filter by form types (e.g. ["10-K", "10-Q"]). Default: all mapped types.
    limit : int
        Maximum filings to return per form type.

    Returns
    -------
    list[dict]
        Each dict: {form, filing_date, report_date, accession, primary_doc,
                    primary_doc_description, doc_url, doc_type}
    """
    if form_types is None:
        form_types = list(FORM_TO_DOC_TYPE.keys())

    company = resolve_cik(ticker)
    cik = company["cik"]

    logger.info("Fetching filings for %s (CIK=%s)...", ticker, cik)
    response = _sec_get(SUBMISSIONS_URL.format(cik=cik))
    submissions = response.json()

    recent = submissions.get("filings", {}).get("recent", {})

    forms = recent.get("form", [])
    filing_dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    primary_descs = recent.get("primaryDocDescription", [])

    filings: list[dict] = []
    counts: dict[str, int] = {ft: 0 for ft in form_types}

    for i, form in enumerate(forms):
        if form not in form_types:
            continue
        if counts[form] >= limit:
            continue

        accession_clean = accessions[i].replace("-", "")
        doc_url = f"{ARCHIVES_BASE}/{cik.lstrip('0')}/{accession_clean}/{primary_docs[i]}"

        filings.append({
            "form": form,
            "filing_date": filing_dates[i],
            "report_date": report_dates[i] if i < len(report_dates) else None,
            "accession": accessions[i],
            "primary_doc": primary_docs[i],
            "primary_doc_description": primary_descs[i] if i < len(primary_descs) else "",
            "doc_url": doc_url,
            "doc_type": FORM_TO_DOC_TYPE.get(form, "announcement"),
            "cik": cik,
            "company_name": company["name"],
        })
        counts[form] += 1

    logger.info("Found %d filings for %s", len(filings), ticker)
    return filings


def get_annual_filings(ticker: str, limit: int = 5) -> list[dict]:
    """Get annual report filings (10-K, 20-F)."""
    return get_filings_list(ticker, form_types=["10-K", "10-K/A", "20-F"], limit=limit)


def get_quarterly_filings(ticker: str, limit: int = 8) -> list[dict]:
    """Get quarterly report filings (10-Q)."""
    return get_filings_list(ticker, form_types=["10-Q", "10-Q/A"], limit=limit)


# ---------------------------------------------------------------------------
# Filing Download
# ---------------------------------------------------------------------------

def download_filing(
    filing: dict,
    save_dir: Path,
) -> dict:
    """Download a single SEC filing to a local directory.

    Parameters
    ----------
    filing : dict
        A filing dict from get_filings_list().
    save_dir : Path
        Directory to save the file into.

    Returns
    -------
    dict
        {file_path, file_size, checksum_sha256, success}
    """
    doc_url = filing["doc_url"]
    filename = filing["primary_doc"]

    # Make filename more descriptive
    form = filing["form"].replace("/", "-")
    date = filing["filing_date"]
    safe_name = f"{form}_{date}_{filename}"

    save_dir.mkdir(parents=True, exist_ok=True)
    file_path = save_dir / safe_name

    # Skip if already downloaded
    if file_path.exists() and file_path.stat().st_size > 0:
        logger.info("File already exists: %s", file_path)
        return {
            "file_path": str(file_path),
            "file_size": file_path.stat().st_size,
            "checksum_sha256": _compute_sha256(file_path),
            "success": True,
            "already_existed": True,
        }

    logger.info("Downloading %s -> %s", doc_url, file_path)
    try:
        response = _sec_get(doc_url, timeout=60.0)

        with open(file_path, "wb") as f:
            f.write(response.content)

        file_size = file_path.stat().st_size
        checksum = _compute_sha256(file_path)

        logger.info("Downloaded %s (%d bytes, sha256=%s...)", safe_name, file_size, checksum[:12])
        return {
            "file_path": str(file_path),
            "file_size": file_size,
            "checksum_sha256": checksum,
            "success": True,
            "already_existed": False,
        }

    except Exception as exc:
        logger.error("Failed to download %s: %s", doc_url, exc)
        # Clean up partial file
        if file_path.exists():
            file_path.unlink()
        return {
            "file_path": None,
            "file_size": 0,
            "checksum_sha256": None,
            "success": False,
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Structured financial data (XBRL)
# ---------------------------------------------------------------------------

def get_company_facts(ticker: str) -> dict:
    """Fetch structured XBRL financial data from SEC EDGAR.

    Returns the full company-facts JSON, which contains every XBRL-tagged
    financial data point across all filings.

    Returns
    -------
    dict
        Raw company-facts JSON from SEC EDGAR.
    """
    company = resolve_cik(ticker)
    cik = company["cik"]

    logger.info("Fetching XBRL company facts for %s (CIK=%s)...", ticker, cik)
    response = _sec_get(COMPANY_FACTS_URL.format(cik=cik))
    return response.json()
