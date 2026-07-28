"""
Text Cleaning & Normalization — Phase 2.2

Transforms raw extracted PDF/HTML text into clean, semantically
meaningful text while preserving financial information.

Pipeline (each step is an independent, testable function):
    Raw Page
        |
        v
    normalize_unicode()
        |
        v
    remove_control_characters()
        |
        v
    remove_xbrl_artifacts()           (SEC EDGAR filings)
        |
        v
    normalize_whitespace()
        |
        v
    remove_repeated_lines()           (detected headers/footers)
        |
        v
    remove_page_numbers()
        |
        v
    fix_broken_lines()
        |
        v
    normalize_paragraphs()
        |
        v
    Clean Page

Design rules:
    - Each function has ONE responsibility
    - Each function is independently testable
    - Financial values are NEVER modified
    - Section headings are PRESERVED
    - Bullet lists are PRESERVED
    - Tables are PRESERVED (best effort)
    - Header/footer detection is frequency-based (not hardcoded)
"""

import logging
import re
import unicodedata
from collections import Counter
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CLEANING_VERSION = "v1"

# Characters that are valid in financial text
_VALID_CONTROL = {"\n", "\r", "\t"}

# Patterns that indicate a line is a heading (should NOT be merged)
_HEADING_PATTERNS = [
    re.compile(r"^(PART|ITEM|SECTION|CHAPTER|SCHEDULE|ANNEXURE|EXHIBIT)\s", re.IGNORECASE),
    re.compile(r"^[A-Z][A-Z\s&,\-]{5,}$"),           # ALL-CAPS line (min 6 chars)
    re.compile(r"^\d+[\.\)]\s+[A-Z]"),                # Numbered heading: "1. Revenue"
    re.compile(r"^[ivxIVX]+[\.\)]\s"),                 # Roman numeral heading
    re.compile(r"^(Note|Notes)\s+\d", re.IGNORECASE),  # "Note 1", "Notes 12"
]

# Patterns that indicate a bullet/list item (should NOT be merged)
_BULLET_PATTERNS = [
    re.compile(r"^\s*[-\u2022\u2023\u25aa\u25e6\u25cf\u25cb\u25a0\u25a1\u2013\u2014\u27a2*]\s"),
    re.compile(r"^\s*\d+[\.\)]\s"),                    # "1. ", "2) "
    re.compile(r"^\s*[a-z][\.\)]\s"),                  # "a. ", "b) "
    re.compile(r"^\s*\([a-z0-9ivx]+\)\s", re.IGNORECASE),  # "(i) ", "(a) "
]

# Page number patterns
_PAGE_NUM_PATTERNS = [
    re.compile(r"^\s*-?\s*\d{1,4}\s*-?\s*$"),                   # "154", "- 154 -"
    re.compile(r"^\s*page\s+\d{1,4}(\s+of\s+\d{1,4})?\s*$", re.IGNORECASE),  # "Page 154 of 300"
    re.compile(r"^\s*[ivxlcdm]+\s*$", re.IGNORECASE),           # Roman numerals: "xiv"
]

# XBRL / inline data patterns (from SEC EDGAR HTML extraction)
_XBRL_PATTERNS = [
    re.compile(r"^https?://\S+$"),                           # Full URL lines
    re.compile(r"^http://fasb\.org/.*$"),                     # FASB namespace URLs
    re.compile(r"^http://xbrl\.org/.*$"),                     # XBRL namespace URLs
    re.compile(r"^\d{10}$"),                                  # CIK numbers (exactly 10 digits)
    re.compile(r"^P\d+[YMWD]$"),                              # Duration patterns: P1Y, P30D
    re.compile(r"^(true|false)$", re.IGNORECASE),             # Boolean strings
    re.compile(r"^[a-z]+-\d{8}$"),                            # EDGAR file identifiers: aapl-20250927
    re.compile(r"^0{5,}\d+$"),                                # Padded CIK: 0000320193
]


# ===========================================================================
# Individual Cleaning Functions
# ===========================================================================

def normalize_unicode(text: str) -> str:
    """Apply NFC Unicode normalization.

    Converts decomposed characters (e.g. e + combining accent) into their
    composed equivalents. Preserves all currency symbols, mathematical
    operators, and special characters used in financial text.
    """
    return unicodedata.normalize("NFC", text)


def remove_control_characters(text: str) -> str:
    """Remove non-printable control characters.

    Preserves newlines, carriage returns, and tabs — everything else
    in the C0/C1 control character range is stripped.
    """
    chars = []
    for ch in text:
        if ch in _VALID_CONTROL:
            chars.append(ch)
        elif unicodedata.category(ch).startswith("C"):
            continue  # Skip control chars
        else:
            chars.append(ch)
    return "".join(chars)


def remove_xbrl_artifacts(text: str) -> str:
    """Remove XBRL/iXBRL inline artifacts from SEC EDGAR filings.

    SEC filings extracted from HTML often contain namespace URIs,
    CIK numbers, boolean flags, and duration patterns from inline
    XBRL markup that leaked into the text layer.
    """
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned.append(line)
            continue

        is_xbrl = any(pattern.match(stripped) for pattern in _XBRL_PATTERNS)
        if not is_xbrl:
            cleaned.append(line)

    return "\n".join(cleaned)


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace: collapse multiple spaces, clean tabs.

    - Multiple consecutive spaces -> single space
    - Tabs -> single space
    - Trailing whitespace removed per line
    - Preserves intentional blank lines (normalized to single blank)
    """
    lines = text.split("\n")
    normalized = []
    for line in lines:
        # Replace tabs with spaces
        line = line.replace("\t", " ")
        # Collapse multiple spaces
        line = re.sub(r" {2,}", " ", line)
        # Strip trailing whitespace
        line = line.rstrip()
        normalized.append(line)
    return "\n".join(normalized)


def remove_page_numbers(text: str) -> str:
    """Remove standalone page number lines.

    Detects and removes lines that are solely page numbers in various
    formats: plain digits, "Page N", "Page N of M", roman numerals.
    Does NOT remove numbers that are part of larger content.
    """
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned.append(line)
            continue

        is_page_num = any(p.match(stripped) for p in _PAGE_NUM_PATTERNS)
        if not is_page_num:
            cleaned.append(line)

    return "\n".join(cleaned)


# ---------------------------------------------------------------------------
# Frequency-Based Header/Footer Detection
# ---------------------------------------------------------------------------

def detect_repeated_headers(
    pages: list[dict],
    top_n_lines: int = 3,
    threshold: float = 0.4,
    min_pages: int = 5,
) -> list[str]:
    """Detect repeated header lines using frequency analysis.

    Examines the first ``top_n_lines`` of each page. Any line that
    appears on more than ``threshold`` fraction of pages (and at least
    ``min_pages``) is classified as a header.

    Parameters
    ----------
    pages : list[dict]
        List of page dicts, each with a "text" key.
    top_n_lines : int
        Number of lines to check at the top of each page.
    threshold : float
        Fraction of pages a line must appear on to be a header (0.0-1.0).
    min_pages : int
        Minimum absolute count to classify as a header.

    Returns
    -------
    list[str]
        Detected header strings (stripped).
    """
    if len(pages) < min_pages:
        return []

    required_count = max(min_pages, int(len(pages) * threshold))
    line_counts: Counter = Counter()

    for page in pages:
        text = page.get("text", "")
        lines = text.strip().split("\n")

        seen_on_page: set[str] = set()
        for line in lines[:top_n_lines]:
            stripped = line.strip()
            if stripped and stripped not in seen_on_page:
                # Normalize for comparison: strip digits that might be page numbers
                normalized = re.sub(r"\d+", "#", stripped)
                seen_on_page.add(normalized)
                line_counts[normalized] += 1

    headers = []
    for pattern, count in line_counts.items():
        if count >= required_count:
            headers.append(pattern)
            logger.debug("Detected header (count=%d/%d): '%s'", count, len(pages), pattern)

    if headers:
        logger.info("Detected %d header patterns across %d pages", len(headers), len(pages))

    return headers


def detect_repeated_footers(
    pages: list[dict],
    bottom_n_lines: int = 3,
    threshold: float = 0.4,
    min_pages: int = 5,
) -> list[str]:
    """Detect repeated footer lines using frequency analysis.

    Same logic as header detection but examines the last ``bottom_n_lines``
    of each page.
    """
    if len(pages) < min_pages:
        return []

    required_count = max(min_pages, int(len(pages) * threshold))
    line_counts: Counter = Counter()

    for page in pages:
        text = page.get("text", "")
        lines = text.strip().split("\n")

        seen_on_page: set[str] = set()
        for line in lines[-bottom_n_lines:]:
            stripped = line.strip()
            if stripped and stripped not in seen_on_page:
                normalized = re.sub(r"\d+", "#", stripped)
                seen_on_page.add(normalized)
                line_counts[normalized] += 1

    footers = []
    for pattern, count in line_counts.items():
        if count >= required_count:
            footers.append(pattern)
            logger.debug("Detected footer (count=%d/%d): '%s'", count, len(pages), pattern)

    if footers:
        logger.info("Detected %d footer patterns across %d pages", len(footers), len(pages))

    return footers


def remove_repeated_lines(text: str, patterns: list[str]) -> str:
    """Remove lines that match detected header/footer patterns.

    Comparison is done after normalizing digits to '#' so that
    'Page 154' matches the pattern 'Page #'.
    """
    if not patterns:
        return text

    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned.append(line)
            continue

        normalized = re.sub(r"\d+", "#", stripped)
        if normalized in patterns:
            continue  # Skip this header/footer line

        cleaned.append(line)

    return "\n".join(cleaned)


# ---------------------------------------------------------------------------
# Broken Line Merging
# ---------------------------------------------------------------------------

def _is_heading(line: str) -> bool:
    """Check if a line looks like a section heading."""
    stripped = line.strip()
    if not stripped:
        return False
    return any(p.match(stripped) for p in _HEADING_PATTERNS)


def _is_bullet(line: str) -> bool:
    """Check if a line is a bullet point or list item."""
    stripped = line.strip()
    if not stripped:
        return False
    return any(p.match(stripped) for p in _BULLET_PATTERNS)


def _is_table_row(line: str) -> bool:
    """Heuristic check for table rows.

    A line is likely a table row if it contains multiple number-like
    tokens separated by spaces or has many pipe/tab separators.
    """
    stripped = line.strip()
    if not stripped:
        return False

    # Contains pipe separators
    if "|" in stripped:
        return True

    # Multiple dollar/number groups
    number_groups = re.findall(r"[\$\u20b9]?\s*[\d,]+\.?\d*", stripped)
    if len(number_groups) >= 3:
        return True

    return False


def _should_merge(current: str, next_line: str) -> bool:
    """Decide whether two consecutive lines should be merged.

    Rules:
        Merge when current line ends mid-sentence and next starts lowercase.
        Never merge headings, bullets, table rows, or blank lines.
    """
    c = current.rstrip()
    n = next_line.strip()

    # Nothing to merge
    if not c or not n:
        return False

    # Current line ends with terminal punctuation -> don't merge
    if c[-1] in ".!?;:":
        return False

    # Current line is too short (likely a heading)
    if len(c.strip()) < 20:
        return False

    # Next line is a heading or bullet -> don't merge
    if _is_heading(n) or _is_bullet(n):
        return False

    # Either line looks like a table row -> don't merge
    if _is_table_row(c) or _is_table_row(n):
        return False

    # Next line starts with lowercase -> likely continuation
    if n[0].islower():
        return True

    # Current line ends with a hyphen (word break: "oper-\nating")
    if c.endswith("-") and n[0].islower():
        return True

    return False


def fix_broken_lines(text: str) -> str:
    """Merge lines that were broken by PDF page width.

    Reconstructs sentences that were split across lines during PDF
    extraction. Preserves headings, bullet lists, and table structures.

    Before:
        Revenue increased by
        14% due to strong
        cloud demand.

    After:
        Revenue increased by 14% due to strong cloud demand.
    """
    lines = text.split("\n")
    result: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Try to merge with subsequent lines
        while i + 1 < len(lines) and _should_merge(line, lines[i + 1]):
            next_line = lines[i + 1].strip()

            # Handle hyphenated word breaks: "oper-" + "ating" -> "operating"
            if line.rstrip().endswith("-") and next_line and next_line[0].islower():
                line = line.rstrip()[:-1] + next_line
            else:
                line = line.rstrip() + " " + next_line

            i += 1

        result.append(line)
        i += 1

    return "\n".join(result)


# ---------------------------------------------------------------------------
# Paragraph Normalization
# ---------------------------------------------------------------------------

def normalize_paragraphs(text: str) -> str:
    """Normalize paragraph spacing and remove excessive blank lines.

    - Collapse 3+ consecutive blank lines into 2 (paragraph break)
    - Remove leading/trailing blank lines
    - Preserve single blank lines between paragraphs
    """
    # Collapse runs of 3+ blank lines into exactly 2
    text = re.sub(r"\n{4,}", "\n\n\n", text)

    # Remove leading/trailing whitespace
    text = text.strip()

    return text


# ===========================================================================
# High-Level API
# ===========================================================================

def clean_page(
    text: str,
    headers: Optional[list[str]] = None,
    footers: Optional[list[str]] = None,
) -> str:
    """Apply the full cleaning pipeline to a single page's text.

    Steps (in order):
        1. Unicode normalization
        2. Remove control characters
        3. Remove XBRL artifacts
        4. Normalize whitespace
        5. Remove detected headers
        6. Remove detected footers
        7. Remove page numbers
        8. Fix broken lines
        9. Normalize paragraphs

    Parameters
    ----------
    text : str
        Raw extracted text for one page.
    headers : list[str], optional
        Patterns to remove (from detect_repeated_headers).
    footers : list[str], optional
        Patterns to remove (from detect_repeated_footers).

    Returns
    -------
    str
        Cleaned text.
    """
    text = normalize_unicode(text)
    text = remove_control_characters(text)
    text = remove_xbrl_artifacts(text)
    text = normalize_whitespace(text)
    text = remove_repeated_lines(text, headers or [])
    text = remove_repeated_lines(text, footers or [])
    text = remove_page_numbers(text)
    text = fix_broken_lines(text)
    text = normalize_paragraphs(text)
    return text


def clean_document(pages: list[dict]) -> dict:
    """Clean all pages in a document with automatic header/footer detection.

    This is the main entry point. It:
        1. Detects headers and footers using frequency analysis
        2. Cleans every page
        3. Returns cleaned pages with processing metadata

    Parameters
    ----------
    pages : list[dict]
        Raw page objects from pdf_extractor.extract_document().
        Each dict must have "page" and "text" keys.

    Returns
    -------
    dict
        {
            "pages": [
                {
                    "page": 84,
                    "raw_text": "...",
                    "clean_text": "...",
                    "char_count_raw": 4200,
                    "char_count_clean": 3800,
                    "cleaning_version": "v1",
                    ... (original metadata preserved)
                },
                ...
            ],
            "statistics": {
                "total_pages": 386,
                "raw_characters": 1842057,
                "clean_characters": 1698412,
                "reduction_pct": 7.8,
                "headers_detected": [...],
                "footers_detected": [...],
                "empty_pages_after_cleaning": 2
            },
            "cleaning_version": "v1"
        }
    """
    if not pages:
        return {
            "pages": [],
            "statistics": {
                "total_pages": 0,
                "raw_characters": 0,
                "clean_characters": 0,
                "reduction_pct": 0.0,
                "headers_detected": [],
                "footers_detected": [],
                "empty_pages_after_cleaning": 0,
            },
            "cleaning_version": CLEANING_VERSION,
        }

    logger.info("Cleaning document with %d pages...", len(pages))

    # Step 1: Detect headers and footers across all pages
    headers = detect_repeated_headers(pages)
    footers = detect_repeated_footers(pages)

    # Step 2: Clean each page
    cleaned_pages: list[dict] = []
    total_raw = 0
    total_clean = 0
    empty_count = 0

    for page_data in pages:
        raw_text = page_data.get("text", "")
        total_raw += len(raw_text)

        clean_text = clean_page(raw_text, headers, footers)
        total_clean += len(clean_text)

        if not clean_text.strip():
            empty_count += 1

        # Build cleaned page dict — preserve all original metadata
        cleaned = {}
        for key, value in page_data.items():
            if key == "text":
                continue  # Replace with raw/clean split
            if key == "char_count":
                continue  # Replace with raw/clean counts
            cleaned[key] = value

        cleaned["raw_text"] = raw_text
        cleaned["clean_text"] = clean_text
        cleaned["char_count_raw"] = len(raw_text)
        cleaned["char_count_clean"] = len(clean_text)
        cleaned["cleaning_version"] = CLEANING_VERSION

        cleaned_pages.append(cleaned)

    reduction_pct = ((total_raw - total_clean) / total_raw * 100) if total_raw > 0 else 0.0

    # Readable header/footer names (un-normalize the '#' back for display)
    header_display = headers[:]
    footer_display = footers[:]

    logger.info(
        "Cleaning complete: %d pages, %d->%d chars (%.1f%% reduction), "
        "%d headers, %d footers detected",
        len(pages), total_raw, total_clean, reduction_pct,
        len(headers), len(footers),
    )

    return {
        "pages": cleaned_pages,
        "statistics": {
            "total_pages": len(pages),
            "raw_characters": total_raw,
            "clean_characters": total_clean,
            "reduction_pct": round(reduction_pct, 1),
            "headers_detected": header_display,
            "footers_detected": footer_display,
            "empty_pages_after_cleaning": empty_count,
        },
        "cleaning_version": CLEANING_VERSION,
    }
