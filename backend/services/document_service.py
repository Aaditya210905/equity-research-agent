"""
Document Service — collects, validates, catalogs, and manages documents.

Orchestrates document collection from multiple sources:
    - SEC EDGAR (10-K, 10-Q for US companies)
    - Yahoo Finance (financial statements as JSON)
    - Investor Relations pages (future)

Flow:
    Ticker
        |
        v
    Find Sources  (SEC? Yahoo? IR?)
        |
        v
    Download Files
        |
        v
    Validate  (exists, non-empty, checksum)
        |
        v
    Register in Document DB
        |
        v
    Return Document List

Does NOT parse or embed documents — that comes in Phase 2.
"""

import datetime
import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

from models.document import Document, initialize_db, DOC_TYPES
from connectors import sec_edgar, yahoo_finance
from connectors.sec_edgar import SECEdgarError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_BACKEND_DIR = Path(__file__).resolve().parent.parent
DOCUMENTS_DIR = _BACKEND_DIR / "documents"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_document_id(ticker: str, doc_type: str, year: int, quarter: str = None, source: str = "") -> str:
    """Generate a deterministic, human-readable document ID."""
    parts = [ticker.upper(), doc_type, str(year)]
    if quarter:
        parts.append(quarter)
    if source:
        parts.append(source)
    return "_".join(parts)


def _compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _doc_exists(document_id: str) -> bool:
    """Check if a document is already registered."""
    return Document.select().where(Document.document_id == document_id).exists()


def _validate_file(file_path: Path) -> bool:
    """Validate that a file is usable.

    Checks:
        - File exists
        - File size > 0
        - File is readable
    """
    if not file_path.exists():
        return False
    if file_path.stat().st_size == 0:
        return False
    try:
        with open(file_path, "rb") as f:
            f.read(64)  # Read first 64 bytes to verify readability
        return True
    except Exception:
        return False


def _register_document(
    document_id: str,
    ticker: str,
    doc_type: str,
    title: str,
    year: int = None,
    quarter: str = None,
    file_path: str = None,
    file_size: int = None,
    source: str = "",
    source_url: str = None,
    checksum_sha256: str = None,
    company_name: str = None,
    processing_status: str = "downloaded",
) -> Document:
    """Insert or update a document in the registry."""
    now = datetime.datetime.utcnow()

    doc, created = Document.get_or_create(
        document_id=document_id,
        defaults={
            "ticker": ticker.upper(),
            "company_name": company_name,
            "doc_type": doc_type,
            "title": title,
            "year": year,
            "quarter": quarter,
            "file_path": file_path,
            "file_size": file_size,
            "source": source,
            "source_url": source_url,
            "checksum_sha256": checksum_sha256,
            "processing_status": processing_status,
            "download_date": now,
            "updated_at": now,
        },
    )

    if not created:
        # Update existing record
        doc.file_path = file_path or doc.file_path
        doc.file_size = file_size or doc.file_size
        doc.checksum_sha256 = checksum_sha256 or doc.checksum_sha256
        doc.processing_status = processing_status
        doc.updated_at = now
        doc.save()

    action = "Registered" if created else "Updated"
    logger.info("%s document: %s (%s)", action, document_id, title)
    return doc


def _document_to_dict(doc: Document) -> dict:
    """Convert a Peewee Document to a serializable dict."""
    return {
        "document_id": doc.document_id,
        "ticker": doc.ticker,
        "company_name": doc.company_name,
        "doc_type": doc.doc_type,
        "title": doc.title,
        "year": doc.year,
        "quarter": doc.quarter,
        "file_path": doc.file_path,
        "file_size": doc.file_size,
        "source": doc.source,
        "source_url": doc.source_url,
        "checksum_sha256": doc.checksum_sha256,
        "processing_status": doc.processing_status,
        "download_date": doc.download_date.isoformat() if doc.download_date else None,
    }


# ---------------------------------------------------------------------------
# SEC EDGAR Collection
# ---------------------------------------------------------------------------

def _collect_sec_filings(ticker: str, annual_limit: int = 3, quarterly_limit: int = 4) -> dict:
    """Download and register SEC filings for a US-listed company.

    Returns
    -------
    dict
        {"new": int, "existing": int, "failed": int, "documents": list}
    """
    result = {"new": 0, "existing": 0, "failed": 0, "documents": []}
    ticker_upper = ticker.strip().upper()
    company_dir = DOCUMENTS_DIR / ticker_upper

    # --- Annual filings (10-K) ---
    try:
        annual_filings = sec_edgar.get_annual_filings(ticker, limit=annual_limit)
    except SECEdgarError as exc:
        logger.warning("No SEC filings for '%s': %s", ticker, exc)
        return result

    for filing in annual_filings:
        year = int(filing["filing_date"][:4])
        doc_id = _make_document_id(ticker_upper, "annual_report", year, source="sec")
        save_dir = company_dir / "annual_reports"

        if _doc_exists(doc_id):
            result["existing"] += 1
            doc = Document.get_by_id(doc_id)
            result["documents"].append(_document_to_dict(doc))
            continue

        dl = sec_edgar.download_filing(filing, save_dir)
        if dl["success"]:
            file_path = dl["file_path"]
            rel_path = str(Path(file_path).relative_to(_BACKEND_DIR))
            status = "verified" if _validate_file(Path(file_path)) else "downloaded"

            doc = _register_document(
                document_id=doc_id,
                ticker=ticker_upper,
                doc_type="annual_report",
                title=f"{filing['form']} — {filing['company_name']} ({year})",
                year=year,
                file_path=rel_path,
                file_size=dl["file_size"],
                source="sec_edgar",
                source_url=filing["doc_url"],
                checksum_sha256=dl["checksum_sha256"],
                company_name=filing["company_name"],
                processing_status=status,
            )
            result["new"] += 1
            result["documents"].append(_document_to_dict(doc))
        else:
            result["failed"] += 1

    # --- Quarterly filings (10-Q) ---
    try:
        quarterly_filings = sec_edgar.get_quarterly_filings(ticker, limit=quarterly_limit)
    except SECEdgarError:
        quarterly_filings = []

    for filing in quarterly_filings:
        year = int(filing["filing_date"][:4])
        # Derive quarter from report date
        if filing.get("report_date"):
            month = int(filing["report_date"][5:7])
            quarter = f"Q{(month - 1) // 3 + 1}"
        else:
            quarter = None

        doc_id = _make_document_id(
            ticker_upper, "quarterly_report", year,
            quarter=quarter, source="sec",
        )
        save_dir = company_dir / "quarterly_reports"

        if _doc_exists(doc_id):
            result["existing"] += 1
            doc = Document.get_by_id(doc_id)
            result["documents"].append(_document_to_dict(doc))
            continue

        dl = sec_edgar.download_filing(filing, save_dir)
        if dl["success"]:
            file_path = dl["file_path"]
            rel_path = str(Path(file_path).relative_to(_BACKEND_DIR))
            status = "verified" if _validate_file(Path(file_path)) else "downloaded"

            doc = _register_document(
                document_id=doc_id,
                ticker=ticker_upper,
                doc_type="quarterly_report",
                title=f"{filing['form']} — {filing['company_name']} ({year} {quarter or ''})",
                year=year,
                quarter=quarter,
                file_path=rel_path,
                file_size=dl["file_size"],
                source="sec_edgar",
                source_url=filing["doc_url"],
                checksum_sha256=dl["checksum_sha256"],
                company_name=filing["company_name"],
                processing_status=status,
            )
            result["new"] += 1
            result["documents"].append(_document_to_dict(doc))
        else:
            result["failed"] += 1

    return result


# ---------------------------------------------------------------------------
# Yahoo Finance Financial Statements Collection
# ---------------------------------------------------------------------------

def _collect_financial_statements(ticker: str) -> dict:
    """Save Yahoo Finance financial statements as JSON and register them.

    Returns
    -------
    dict
        {"new": int, "existing": int, "failed": int, "documents": list}
    """
    result = {"new": 0, "existing": 0, "failed": 0, "documents": []}
    ticker_upper = ticker.strip().upper()
    company_dir = DOCUMENTS_DIR / ticker_upper / "financial_statements"
    company_dir.mkdir(parents=True, exist_ok=True)

    statement_types = {
        "income_statement": yahoo_finance.get_income_statement,
        "balance_sheet": yahoo_finance.get_balance_sheet,
        "cash_flow": yahoo_finance.get_cash_flow,
    }

    for stmt_type, fetch_fn in statement_types.items():
        try:
            records = fetch_fn(ticker)
            if not records:
                logger.warning("No %s data for '%s'", stmt_type, ticker)
                continue

            # Save each period as a separate document
            for record in records:
                period = record.get("period", "unknown")
                year = int(period[:4]) if period != "unknown" else 0
                doc_id = _make_document_id(ticker_upper, stmt_type, year, source="yahoo")

                if _doc_exists(doc_id):
                    result["existing"] += 1
                    doc = Document.get_by_id(doc_id)
                    result["documents"].append(_document_to_dict(doc))
                    continue

                # Save as JSON file
                filename = f"{stmt_type}_{year}.json"
                file_path = company_dir / filename

                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(record, f, indent=2, default=str)

                rel_path = str(file_path.relative_to(_BACKEND_DIR))
                file_size = file_path.stat().st_size
                checksum = _compute_sha256(file_path)

                doc = _register_document(
                    document_id=doc_id,
                    ticker=ticker_upper,
                    doc_type=stmt_type,
                    title=f"{DOC_TYPES.get(stmt_type, stmt_type)} — {ticker_upper} ({year})",
                    year=year,
                    file_path=rel_path,
                    file_size=file_size,
                    source="yahoo_finance",
                    checksum_sha256=checksum,
                    processing_status="verified",
                )
                result["new"] += 1
                result["documents"].append(_document_to_dict(doc))

        except Exception as exc:
            logger.error("Failed to collect %s for '%s': %s", stmt_type, ticker, exc)
            result["failed"] += 1

    return result


# ===========================================================================
# Public API
# ===========================================================================

def collect_documents(ticker: str) -> dict:
    """Collect all available documents for a company.

    Tries all available sources:
        1. Financial statements from Yahoo Finance
        2. SEC EDGAR filings (10-K, 10-Q) for US companies

    Parameters
    ----------
    ticker : str
        Stock ticker symbol.

    Returns
    -------
    dict
        CollectionResult-compatible dict:
        {ticker, new_documents, existing_documents, failed, documents}
    """
    initialize_db()
    ticker_upper = ticker.strip().upper()

    logger.info("Collecting documents for '%s'...", ticker_upper)

    total_new = 0
    total_existing = 0
    total_failed = 0
    all_documents: list[dict] = []

    # 1. Yahoo Finance financial statements (works for any ticker)
    try:
        fin_result = _collect_financial_statements(ticker)
        total_new += fin_result["new"]
        total_existing += fin_result["existing"]
        total_failed += fin_result["failed"]
        all_documents.extend(fin_result["documents"])
    except Exception as exc:
        logger.error("Financial statements collection failed for '%s': %s", ticker, exc)

    # 2. SEC EDGAR (US companies only — fails gracefully for non-US)
    try:
        sec_result = _collect_sec_filings(ticker)
        total_new += sec_result["new"]
        total_existing += sec_result["existing"]
        total_failed += sec_result["failed"]
        all_documents.extend(sec_result["documents"])
    except Exception as exc:
        logger.info("SEC EDGAR not available for '%s' (likely non-US): %s", ticker, exc)

    logger.info(
        "Collection complete for '%s': %d new, %d existing, %d failed",
        ticker_upper, total_new, total_existing, total_failed,
    )

    return {
        "ticker": ticker_upper,
        "new_documents": total_new,
        "existing_documents": total_existing,
        "failed": total_failed,
        "documents": all_documents,
    }


def get_company_documents(
    ticker: str,
    doc_type: str = None,
    year: int = None,
) -> dict:
    """Retrieve all registered documents for a company from the database.

    Parameters
    ----------
    ticker : str
        Stock ticker symbol.
    doc_type : str, optional
        Filter by document type.
    year : int, optional
        Filter by fiscal year.

    Returns
    -------
    dict
        DocumentCollection-compatible dict.
    """
    initialize_db()
    ticker_upper = ticker.strip().upper()

    query = Document.select().where(Document.ticker == ticker_upper)

    if doc_type:
        query = query.where(Document.doc_type == doc_type)
    if year:
        query = query.where(Document.year == year)

    query = query.order_by(Document.year.desc(), Document.doc_type)

    documents = [_document_to_dict(doc) for doc in query]

    # Get company name from first document if available
    company_name = ticker_upper
    if documents and documents[0].get("company_name"):
        company_name = documents[0]["company_name"]

    return {
        "company": company_name,
        "ticker": ticker_upper,
        "total_documents": len(documents),
        "documents": documents,
    }


def get_document(document_id: str) -> Optional[dict]:
    """Retrieve a single document's metadata by ID.

    Returns
    -------
    dict or None
        Document metadata dict, or None if not found.
    """
    initialize_db()
    try:
        doc = Document.get_by_id(document_id)
        return _document_to_dict(doc)
    except Document.DoesNotExist:
        return None
