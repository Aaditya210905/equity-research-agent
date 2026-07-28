"""
PDF & Document Extraction Service — Phase 2.1

Converts PDF and HTML financial documents into structured page-level
text objects suitable for downstream processing (cleaning, chunking,
embedding).

Architecture:
    Document File (PDF / HTML)
        |
        v
    Open Document
        |
        v
    Extract Text (page by page)
        |
        v
    Attach Page Metadata
        |
        v
    Return Structured Output

Responsibilities:
    1. Open the document
    2. Extract text page by page
    3. Return structured page objects with metadata

Does NOT:
    - Clean text (that's text_cleaner.py)
    - Chunk text (that's the chunker)
    - Generate embeddings (that's the embedding service)

Extraction backends:
    PDF:  PyMuPDF (fitz) primary, pdfplumber fallback
    HTML: BeautifulSoup (for SEC EDGAR filings)
    JSON: Direct load (for Yahoo Finance data)
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Check available extraction backends
# ---------------------------------------------------------------------------
_HAS_PYMUPDF = False
_HAS_PDFPLUMBER = False

try:
    import fitz  # PyMuPDF
    _HAS_PYMUPDF = True
except ImportError:
    logger.warning("PyMuPDF (fitz) not installed — PDF extraction will use pdfplumber")

try:
    import pdfplumber
    _HAS_PDFPLUMBER = True
except ImportError:
    if not _HAS_PYMUPDF:
        logger.error("Neither PyMuPDF nor pdfplumber installed — PDF extraction unavailable")

try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False
    logger.warning("BeautifulSoup not installed — HTML extraction unavailable")


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------
class ExtractionError(Exception):
    """Raised when document extraction fails."""


# ---------------------------------------------------------------------------
# Result format
# ---------------------------------------------------------------------------
def _make_result(
    source_file: str,
    file_type: str,
    pages: list[dict],
    success: bool = True,
    error: str = None,
    metadata: dict = None,
) -> dict:
    """Build a standardized extraction result.

    Returns
    -------
    dict
        {
            "source_file": "annual_report.pdf",
            "file_type": "pdf",
            "total_pages": 410,
            "total_characters": 220000,
            "pages": [{page, text, char_count, ...}, ...],
            "metadata": {document_id, company, year, ...},
            "success": True,
            "error": None,
        }
    """
    total_chars = sum(p.get("char_count", 0) for p in pages)

    return {
        "source_file": str(source_file),
        "file_type": file_type,
        "total_pages": len(pages),
        "total_characters": total_chars,
        "pages": pages,
        "metadata": metadata or {},
        "success": success,
        "error": error,
    }


# ---------------------------------------------------------------------------
# PDF Extraction — PyMuPDF (primary)
# ---------------------------------------------------------------------------

def _extract_pdf_pymupdf(file_path: Path) -> list[dict]:
    """Extract text from a PDF using PyMuPDF (fitz).

    PyMuPDF is fast and handles complex layouts well. It's the
    recommended backend for financial report PDFs.
    """
    doc = fitz.open(str(file_path))
    pages: list[dict] = []

    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")

            pages.append({
                "page": page_num + 1,
                "text": text,
                "char_count": len(text),
            })
    finally:
        doc.close()

    return pages


# ---------------------------------------------------------------------------
# PDF Extraction — pdfplumber (fallback)
# ---------------------------------------------------------------------------

def _extract_pdf_pdfplumber(file_path: Path) -> list[dict]:
    """Extract text from a PDF using pdfplumber.

    pdfplumber is particularly good at extracting tables, making it
    a useful fallback for financial documents with dense tabular data.
    """
    pages: list[dict] = []

    with pdfplumber.open(str(file_path)) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""

            pages.append({
                "page": i + 1,
                "text": text,
                "char_count": len(text),
            })

    return pages


# ---------------------------------------------------------------------------
# HTML Extraction (for SEC EDGAR filings)
# ---------------------------------------------------------------------------

# Approximate characters per "page" when splitting HTML
_HTML_PAGE_SIZE = 4000


def _extract_html(file_path: Path) -> list[dict]:
    """Extract text from an HTML document (SEC EDGAR filings).

    Since HTML doesn't have natural page breaks, we split the text
    into approximate pages of ~4000 characters (roughly one printed
    page). This preserves the page-level abstraction used by the
    rest of the pipeline.
    """
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, "lxml")

    # Remove script and style elements
    for element in soup(["script", "style", "meta", "link"]):
        element.decompose()

    text = soup.get_text(separator="\n", strip=True)

    # Split into approximate pages
    pages: list[dict] = []
    lines = text.split("\n")
    current_text = ""
    page_num = 1

    for line in lines:
        current_text += line + "\n"

        if len(current_text) >= _HTML_PAGE_SIZE:
            pages.append({
                "page": page_num,
                "text": current_text.strip(),
                "char_count": len(current_text.strip()),
            })
            current_text = ""
            page_num += 1

    # Don't lose the last chunk
    if current_text.strip():
        pages.append({
            "page": page_num,
            "text": current_text.strip(),
            "char_count": len(current_text.strip()),
        })

    return pages


# ---------------------------------------------------------------------------
# JSON Extraction (for Yahoo Finance data)
# ---------------------------------------------------------------------------

def _extract_json(file_path: Path) -> list[dict]:
    """Extract text representation from a JSON financial statement.

    Converts the structured JSON into a readable text format, treating
    the entire file as a single "page".
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Build a readable text representation
    lines: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "period":
                lines.append(f"Period: {value}")
            else:
                # Format financial line items
                label = key.replace("_", " ").title()
                if isinstance(value, (int, float)):
                    lines.append(f"{label}: {value:,.2f}")
                elif value is not None:
                    lines.append(f"{label}: {value}")
    elif isinstance(data, list):
        for item in data:
            lines.append(json.dumps(item, indent=2, default=str))

    text = "\n".join(lines)

    return [{
        "page": 1,
        "text": text,
        "char_count": len(text),
    }]


# ---------------------------------------------------------------------------
# File type detection
# ---------------------------------------------------------------------------

def _detect_file_type(file_path: Path) -> str:
    """Detect document type from file extension and content.

    Returns
    -------
    str
        "pdf", "html", or "json"

    Raises
    ------
    ExtractionError
        If the file type is unsupported.
    """
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        return "pdf"
    elif suffix in (".htm", ".html"):
        return "html"
    elif suffix == ".json":
        return "json"
    else:
        # Try to detect from content
        try:
            with open(file_path, "rb") as f:
                header = f.read(16)
            if header.startswith(b"%PDF"):
                return "pdf"
            if header.lstrip().startswith((b"<", b"<!DOCTYPE", b"<html")):
                return "html"
            if header.lstrip().startswith((b"{", b"[")):
                return "json"
        except Exception:
            pass

        raise ExtractionError(f"Unsupported file type: {suffix} ({file_path.name})")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_file(file_path: Path) -> None:
    """Validate that a file can be extracted.

    Raises
    ------
    ExtractionError
        If the file is missing, empty, or unreadable.
    """
    if not file_path.exists():
        raise ExtractionError(f"File not found: {file_path}")

    if file_path.stat().st_size == 0:
        raise ExtractionError(f"File is empty: {file_path}")

    # Check readability
    try:
        with open(file_path, "rb") as f:
            f.read(64)
    except PermissionError:
        raise ExtractionError(f"Permission denied: {file_path}")
    except Exception as exc:
        raise ExtractionError(f"Cannot read file: {file_path} ({exc})")


# ===========================================================================
# Public API
# ===========================================================================

def extract_pdf(
    file_path: str | Path,
    document_id: str = None,
    company: str = None,
    year: int = None,
    source: str = None,
) -> dict:
    """Extract text from a PDF file page by page.

    Uses PyMuPDF as the primary backend, with pdfplumber as fallback.

    Parameters
    ----------
    file_path : str or Path
        Path to the PDF file.
    document_id : str, optional
        Document registry ID.
    company : str, optional
        Company name or ticker.
    year : int, optional
        Fiscal year.
    source : str, optional
        Original source identifier.

    Returns
    -------
    dict
        Standardized extraction result with pages, metadata, and status.
    """
    file_path = Path(file_path)
    metadata = {
        "document_id": document_id,
        "company": company,
        "year": year,
        "source": source,
    }

    try:
        _validate_file(file_path)
    except ExtractionError as exc:
        return _make_result(file_path.name, "pdf", [], success=False, error=str(exc), metadata=metadata)

    # Try PyMuPDF first
    if _HAS_PYMUPDF:
        try:
            logger.info("Extracting PDF with PyMuPDF: %s", file_path.name)
            pages = _extract_pdf_pymupdf(file_path)

            # Enrich pages with metadata
            for page in pages:
                page["document_id"] = document_id
                page["company"] = company
                page["year"] = year
                page["source"] = file_path.name

            return _make_result(file_path.name, "pdf", pages, metadata=metadata)

        except Exception as exc:
            logger.warning("PyMuPDF failed for %s: %s — trying pdfplumber", file_path.name, exc)

    # Fallback to pdfplumber
    if _HAS_PDFPLUMBER:
        try:
            logger.info("Extracting PDF with pdfplumber: %s", file_path.name)
            pages = _extract_pdf_pdfplumber(file_path)

            for page in pages:
                page["document_id"] = document_id
                page["company"] = company
                page["year"] = year
                page["source"] = file_path.name

            return _make_result(file_path.name, "pdf", pages, metadata=metadata)

        except Exception as exc:
            error_msg = f"Both PyMuPDF and pdfplumber failed: {exc}"
            logger.error(error_msg)
            return _make_result(file_path.name, "pdf", [], success=False, error=error_msg, metadata=metadata)

    return _make_result(
        file_path.name, "pdf", [],
        success=False,
        error="No PDF extraction backend available (install PyMuPDF or pdfplumber)",
        metadata=metadata,
    )


def extract_html(
    file_path: str | Path,
    document_id: str = None,
    company: str = None,
    year: int = None,
    source: str = None,
) -> dict:
    """Extract text from an HTML document (SEC EDGAR filings).

    Parameters
    ----------
    file_path : str or Path
        Path to the HTML file.
    document_id, company, year, source
        Metadata to attach to each page.

    Returns
    -------
    dict
        Standardized extraction result.
    """
    file_path = Path(file_path)
    metadata = {
        "document_id": document_id,
        "company": company,
        "year": year,
        "source": source,
    }

    try:
        _validate_file(file_path)
    except ExtractionError as exc:
        return _make_result(file_path.name, "html", [], success=False, error=str(exc), metadata=metadata)

    if not _HAS_BS4:
        return _make_result(
            file_path.name, "html", [],
            success=False,
            error="BeautifulSoup not installed",
            metadata=metadata,
        )

    try:
        logger.info("Extracting HTML: %s", file_path.name)
        pages = _extract_html(file_path)

        for page in pages:
            page["document_id"] = document_id
            page["company"] = company
            page["year"] = year
            page["source"] = file_path.name

        return _make_result(file_path.name, "html", pages, metadata=metadata)

    except Exception as exc:
        error_msg = f"HTML extraction failed: {exc}"
        logger.error(error_msg)
        return _make_result(file_path.name, "html", [], success=False, error=error_msg, metadata=metadata)


def extract_document(
    file_path: str | Path,
    document_id: str = None,
    company: str = None,
    year: int = None,
    source: str = None,
) -> dict:
    """Extract text from any supported document type.

    Auto-detects the file type (PDF, HTML, JSON) and routes to the
    appropriate extraction backend.

    Parameters
    ----------
    file_path : str or Path
        Path to the document.
    document_id, company, year, source
        Metadata to attach to each extracted page.

    Returns
    -------
    dict
        Standardized extraction result::

            {
                "source_file": "annual_report.pdf",
                "file_type": "pdf",
                "total_pages": 410,
                "total_characters": 220000,
                "pages": [
                    {
                        "page": 1,
                        "text": "...",
                        "char_count": 3200,
                        "document_id": "AAPL_annual_report_2024_sec",
                        "company": "AAPL",
                        "year": 2024,
                        "source": "annual_report.pdf"
                    },
                    ...
                ],
                "metadata": {...},
                "success": True,
                "error": None
            }
    """
    file_path = Path(file_path)
    metadata = {
        "document_id": document_id,
        "company": company,
        "year": year,
        "source": source,
    }

    # Validate
    try:
        _validate_file(file_path)
    except ExtractionError as exc:
        return _make_result(file_path.name, "unknown", [], success=False, error=str(exc), metadata=metadata)

    # Detect type
    try:
        file_type = _detect_file_type(file_path)
    except ExtractionError as exc:
        return _make_result(file_path.name, "unknown", [], success=False, error=str(exc), metadata=metadata)

    # Route to appropriate extractor
    if file_type == "pdf":
        return extract_pdf(file_path, document_id, company, year, source)
    elif file_type == "html":
        return extract_html(file_path, document_id, company, year, source)
    elif file_type == "json":
        try:
            logger.info("Extracting JSON: %s", file_path.name)
            pages = _extract_json(file_path)

            for page in pages:
                page["document_id"] = document_id
                page["company"] = company
                page["year"] = year
                page["source"] = file_path.name

            return _make_result(file_path.name, "json", pages, metadata=metadata)
        except Exception as exc:
            return _make_result(file_path.name, "json", [], success=False, error=str(exc), metadata=metadata)

    return _make_result(file_path.name, file_type, [], success=False, error=f"No extractor for {file_type}", metadata=metadata)
