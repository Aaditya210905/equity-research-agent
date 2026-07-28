"""
Intelligent Financial Document Chunker — Phase 2.3

Converts cleaned documents into semantically meaningful chunks that
preserve business context and maximize retrieval quality.

Strategy:
    Clean Pages
        |
        v
    Parse Blocks  (heading / paragraph / table / blank)
        |
        v
    Assign Sections  (using heading hierarchy)
        |
        v
    Build Chunks  (group blocks to target size)
        |
        v
    Add Overlap   (semantic: last paragraph, not arbitrary chars)
        |
        v
    Score Quality
        |
        v
    Structured Chunks with Rich Metadata

Key rules:
    - Never split first. Understand structure first.
    - Chunks represent complete ideas, not arbitrary lengths.
    - Tables are never split.
    - Headings stay with their content.
    - Token counts target 700-900 (min 300, max 1200).
    - Semantic overlap: repeat last paragraph, not last N chars.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Token targets
# ---------------------------------------------------------------------------
MIN_TOKENS = 300
TARGET_TOKENS = 800
MAX_TOKENS = 1200
OVERLAP_MAX_TOKENS = 150  # Max tokens for overlap context


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    """Estimate token count for embedding models.

    Uses ~4 characters per token, a standard approximation for
    English text with models like OpenAI, Cohere, or sentence-transformers.
    """
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Heading detection
# ---------------------------------------------------------------------------

# (level, pattern, min_confidence)
_HEADING_RULES: list[tuple[int, re.Pattern, float]] = [
    # Level 1: Major divisions
    (1, re.compile(r"^PART\s+[IVXLC]+\b", re.IGNORECASE), 0.95),

    # Level 2: Items / Sections
    (2, re.compile(r"^ITEM\s+\d+[A-Z]?\.?\s", re.IGNORECASE), 0.95),
    (2, re.compile(r"^SECTION\s+\d+", re.IGNORECASE), 0.90),
    (2, re.compile(r"^SCHEDULE\s+[IVXLC\d]+", re.IGNORECASE), 0.85),
    (2, re.compile(r"^(ANNEXURE|EXHIBIT)\s+[A-Z\d]", re.IGNORECASE), 0.85),

    # Level 2: ALL-CAPS section headings (6–80 chars)
    (2, re.compile(r"^[A-Z][A-Z\s&,\-\'/()]{4,79}$"), 0.75),

    # Level 3: Note headings (financial statements)
    (3, re.compile(r"^(Note|Notes)\s+\d", re.IGNORECASE), 0.85),

    # Level 3: Numbered sub-headings (1.1, 2.3, etc.)
    (3, re.compile(r"^\d+\.\d+\.?\s+[A-Z]"), 0.70),
]


def _heading_score(line: str) -> tuple[int, float]:
    """Score a line as a potential heading.

    Returns (level, confidence). Level 0 means not a heading.
    """
    stripped = line.strip()
    if not stripped or len(stripped) > 120:
        return (0, 0.0)

    # Too long for a heading
    if len(stripped) > 80 and not stripped.startswith(("ITEM ", "PART ", "SECTION ")):
        return (0, 0.0)

    for level, pattern, confidence in _HEADING_RULES:
        if pattern.match(stripped):
            return (level, confidence)

    return (0, 0.0)


# ---------------------------------------------------------------------------
# Table detection
# ---------------------------------------------------------------------------

def _is_table_row(line: str) -> bool:
    """Heuristic: is this line part of a table?"""
    stripped = line.strip()
    if not stripped:
        return False

    # Pipe-separated
    if "|" in stripped and stripped.count("|") >= 2:
        return True

    # Multiple dollar/currency/number groups with spacing
    number_groups = re.findall(r"[\$\u20b9\u20ac\u00a5]?\s*[\d,]+\.?\d*", stripped)
    if len(number_groups) >= 3:
        return True

    # Multiple column-like spacing (3+ spaces between content)
    columns = re.findall(r"\S+\s{3,}", stripped)
    if len(columns) >= 2:
        return True

    return False


# ---------------------------------------------------------------------------
# Block data structure
# ---------------------------------------------------------------------------

@dataclass
class Block:
    """A contiguous block of text: heading, paragraph, or table."""

    text: str
    pages: list[int] = field(default_factory=list)
    block_type: str = "paragraph"      # "heading", "paragraph", "table"
    heading_level: int = 0
    section: str = ""
    subsection: str = ""


# ---------------------------------------------------------------------------
# Pass 1: Parse cleaned pages into typed blocks
# ---------------------------------------------------------------------------

def _parse_blocks(cleaned_pages: list[dict]) -> list[Block]:
    """Convert cleaned pages into a sequence of typed blocks.

    Classifies each line as heading, table row, or text, then groups
    consecutive same-type lines into blocks.
    """
    blocks: list[Block] = []
    current_lines: list[str] = []
    current_type: str = "paragraph"
    current_pages: list[int] = []

    def _flush():
        nonlocal current_lines, current_type, current_pages
        if not current_lines:
            return
        text = "\n".join(current_lines).strip()
        if text:
            blocks.append(Block(
                text=text,
                pages=sorted(set(current_pages)) if current_pages else [],
                block_type=current_type,
            ))
        current_lines = []
        current_pages = []

    for page_data in cleaned_pages:
        page_num = page_data.get("page", 0)
        text = page_data.get("clean_text", page_data.get("text", ""))

        for line in text.split("\n"):
            stripped = line.strip()

            # Blank line: flush current block
            if not stripped:
                _flush()
                current_type = "paragraph"
                continue

            # Check heading
            level, confidence = _heading_score(stripped)
            if level > 0 and confidence >= 0.70:
                _flush()
                blocks.append(Block(
                    text=stripped,
                    pages=[page_num],
                    block_type="heading",
                    heading_level=level,
                ))
                current_type = "paragraph"
                continue

            # Check table
            if _is_table_row(stripped):
                if current_type != "table":
                    _flush()
                    current_type = "table"
                current_lines.append(stripped)
                if page_num not in current_pages:
                    current_pages.append(page_num)
                continue

            # Regular text
            if current_type == "table":
                _flush()
                current_type = "paragraph"
            current_lines.append(stripped)
            if page_num not in current_pages:
                current_pages.append(page_num)

    _flush()
    return blocks


# ---------------------------------------------------------------------------
# Pass 2: Assign section/subsection from heading hierarchy
# ---------------------------------------------------------------------------

def _assign_sections(blocks: list[Block]) -> list[Block]:
    """Walk through blocks and assign section/subsection from headings."""
    current_section = ""
    current_subsection = ""

    for block in blocks:
        if block.block_type == "heading":
            if block.heading_level <= 2:
                current_section = block.text
                current_subsection = ""
            else:
                current_subsection = block.text
            block.section = current_section
            block.subsection = current_subsection
        else:
            block.section = current_section
            block.subsection = current_subsection

    return blocks


# ---------------------------------------------------------------------------
# Pass 3: Build chunks from blocks
# ---------------------------------------------------------------------------

def _build_chunks(blocks: list[Block]) -> list[dict]:
    """Accumulate blocks into chunks respecting token targets.

    Rules:
        - Start a new chunk at each level-1 or level-2 heading
        - Keep tables intact (one chunk per table, possibly with heading)
        - Accumulate paragraphs until target tokens, then emit
        - Semantic overlap: repeat last paragraph into next chunk
    """
    chunks: list[dict] = []

    # Accumulator state
    parts: list[str] = []
    pages: set[int] = set()
    tokens: int = 0
    section: str = ""
    subsection: str = ""
    has_heading: bool = False
    has_table: bool = False
    last_paragraph: str = ""  # For semantic overlap

    def _emit():
        nonlocal parts, pages, tokens, has_heading, has_table, last_paragraph
        if not parts:
            return

        text = "\n\n".join(parts)
        if not text.strip():
            parts = []
            pages = set()
            tokens = 0
            has_heading = False
            has_table = False
            return

        sorted_pages = sorted(pages) if pages else []
        chunks.append({
            "section": section,
            "subsection": subsection,
            "page_start": sorted_pages[0] if sorted_pages else None,
            "page_end": sorted_pages[-1] if sorted_pages else None,
            "text": text,
            "token_count": estimate_tokens(text),
            "has_heading": has_heading,
            "contains_table": has_table,
        })

        # Save last paragraph for overlap
        last_paragraph = parts[-1] if parts else ""

        parts = []
        pages = set()
        tokens = 0
        has_heading = False
        has_table = False

    def _start_with_overlap():
        """Begin a new chunk with semantic overlap from the previous."""
        nonlocal parts, tokens
        if last_paragraph and estimate_tokens(last_paragraph) <= OVERLAP_MAX_TOKENS:
            parts = [last_paragraph]
            tokens = estimate_tokens(last_paragraph)
        else:
            parts = []
            tokens = 0

    for block in blocks:
        block_tokens = estimate_tokens(block.text)

        # --- Heading block ---
        if block.block_type == "heading":
            # Level 1-2 headings always start a new chunk
            if block.heading_level <= 2:
                _emit()
                section = block.section
                subsection = block.subsection
                parts = [block.text]
                pages = set(block.pages)
                tokens = block_tokens
                has_heading = True
                continue

            # Level 3+ heading: start new chunk if current is big enough
            if tokens >= MIN_TOKENS:
                _emit()
                _start_with_overlap()

            section = block.section
            subsection = block.subsection
            parts.append(block.text)
            pages.update(block.pages)
            tokens += block_tokens
            has_heading = True
            continue

        # --- Table block ---
        if block.block_type == "table":
            # If current chunk already has enough content, emit first
            if tokens >= MIN_TOKENS:
                _emit()
                _start_with_overlap()

            # Add table (always keep intact)
            parts.append(block.text)
            pages.update(block.pages)
            tokens += block_tokens
            has_table = True

            # If table made chunk large, emit it
            if tokens >= TARGET_TOKENS:
                _emit()
            continue

        # --- Paragraph block ---
        # Would adding this exceed max?
        if tokens + block_tokens > MAX_TOKENS and tokens >= MIN_TOKENS:
            _emit()
            _start_with_overlap()
            section = block.section
            subsection = block.subsection

        parts.append(block.text)
        pages.update(block.pages)
        tokens += block_tokens
        section = block.section or section
        subsection = block.subsection or subsection

        # Reached target? Emit if next block would push over
        if tokens >= TARGET_TOKENS:
            _emit()
            _start_with_overlap()
            section = block.section or section
            subsection = block.subsection or subsection

    # Final chunk
    _emit()

    return chunks


# ---------------------------------------------------------------------------
# Pass 4: Split oversized chunks at sentence boundaries
# ---------------------------------------------------------------------------

def _split_oversized(chunks: list[dict]) -> list[dict]:
    """Split any chunk that exceeds MAX_TOKENS at sentence boundaries."""
    result: list[dict] = []

    for chunk in chunks:
        if chunk["token_count"] <= MAX_TOKENS:
            result.append(chunk)
            continue

        # Need to split
        text = chunk["text"]
        sentences = re.split(r"(?<=[.!?])\s+", text)

        current_sentences: list[str] = []
        current_tokens = 0

        for sentence in sentences:
            sent_tokens = estimate_tokens(sentence)

            if current_tokens + sent_tokens > MAX_TOKENS and current_sentences:
                # Emit sub-chunk
                sub_text = " ".join(current_sentences)
                sub = dict(chunk)
                sub["text"] = sub_text
                sub["token_count"] = estimate_tokens(sub_text)
                result.append(sub)
                current_sentences = []
                current_tokens = 0

            current_sentences.append(sentence)
            current_tokens += sent_tokens

        if current_sentences:
            sub_text = " ".join(current_sentences)
            sub = dict(chunk)
            sub["text"] = sub_text
            sub["token_count"] = estimate_tokens(sub_text)
            result.append(sub)

    return result


# ---------------------------------------------------------------------------
# Pass 5: Merge undersized chunks
# ---------------------------------------------------------------------------

def _merge_undersized(chunks: list[dict]) -> list[dict]:
    """Merge chunks below MIN_TOKENS with their neighbor."""
    if len(chunks) <= 1:
        return chunks

    result: list[dict] = []
    i = 0

    while i < len(chunks):
        chunk = dict(chunks[i])

        # If this chunk is too small and there's a next chunk in same section
        while (chunk["token_count"] < MIN_TOKENS
               and i + 1 < len(chunks)
               and chunks[i + 1].get("section") == chunk.get("section")):
            next_chunk = chunks[i + 1]
            chunk["text"] = chunk["text"] + "\n\n" + next_chunk["text"]
            chunk["token_count"] = estimate_tokens(chunk["text"])
            chunk["page_end"] = next_chunk.get("page_end") or chunk.get("page_end")
            chunk["has_heading"] = chunk.get("has_heading") or next_chunk.get("has_heading")
            chunk["contains_table"] = chunk.get("contains_table") or next_chunk.get("contains_table")
            if next_chunk.get("subsection"):
                chunk["subsection"] = next_chunk["subsection"]
            i += 1

        result.append(chunk)
        i += 1

    return result


# ---------------------------------------------------------------------------
# Quality scoring
# ---------------------------------------------------------------------------

def _quality_score(chunk: dict) -> float:
    """Calculate a quality score for a chunk (0.0 - 1.0)."""
    score = 0.7  # Base

    tokens = chunk.get("token_count", 0)

    # Token count in sweet spot
    if MIN_TOKENS <= tokens <= MAX_TOKENS:
        score += 0.15
    elif tokens < 100:
        score -= 0.3
    elif tokens < MIN_TOKENS:
        score -= 0.1
    elif tokens > MAX_TOKENS:
        score -= 0.15

    # Has section context
    if chunk.get("section"):
        score += 0.05

    # Has heading
    if chunk.get("has_heading"):
        score += 0.05

    # Has page references
    if chunk.get("page_start") is not None:
        score += 0.05

    return round(min(1.0, max(0.0, score)), 2)


# ===========================================================================
# Public API
# ===========================================================================

def chunk_document(
    cleaned_pages: list[dict],
    document_id: str = None,
    company: str = None,
    year: int = None,
    doc_type: str = None,
) -> dict:
    """Chunk a cleaned document into semantically meaningful pieces.

    This is the main entry point. The algorithm:
        1. Parse pages into typed blocks (heading / paragraph / table)
        2. Assign section hierarchy from headings
        3. Build chunks by accumulating blocks to target token count
        4. Split oversized chunks at sentence boundaries
        5. Merge undersized chunks with neighbors
        6. Score quality and assign metadata

    Parameters
    ----------
    cleaned_pages : list[dict]
        Cleaned page objects from text_cleaner.clean_document()["pages"].
        Each dict must have "clean_text" (or "text") and "page" keys.
    document_id : str, optional
        Parent document ID.
    company, year, doc_type : optional
        Metadata attached to every chunk.

    Returns
    -------
    dict
        ChunkingResult-compatible dict::

            {
                "document_id": "AAPL_annual_report_2025_sec",
                "company": "AAPL",
                "total_chunks": 45,
                "total_tokens": 36000,
                "avg_chunk_tokens": 800,
                "sections_detected": ["BUSINESS", "RISK FACTORS", ...],
                "chunks": [ ... ChunkMeta dicts ... ]
            }
    """
    if not cleaned_pages:
        return {
            "document_id": document_id,
            "company": company,
            "total_chunks": 0,
            "total_tokens": 0,
            "avg_chunk_tokens": 0.0,
            "sections_detected": [],
            "chunks": [],
        }

    logger.info("Chunking document: %d pages, document_id=%s",
                len(cleaned_pages), document_id)

    # Pass 1: Parse into blocks
    blocks = _parse_blocks(cleaned_pages)
    logger.debug("Parsed %d blocks", len(blocks))

    # Pass 2: Assign sections
    blocks = _assign_sections(blocks)

    # Collect detected sections
    sections = []
    for b in blocks:
        if b.block_type == "heading" and b.heading_level <= 2 and b.text not in sections:
            sections.append(b.text)

    # Pass 3: Build chunks
    raw_chunks = _build_chunks(blocks)

    # Pass 4: Split oversized
    raw_chunks = _split_oversized(raw_chunks)

    # Pass 5: Merge undersized
    raw_chunks = _merge_undersized(raw_chunks)

    # Pass 6: Finalize — assign IDs, metadata, quality scores
    finalized: list[dict] = []
    total_tokens = 0

    for i, chunk in enumerate(raw_chunks):
        chunk_id = f"{document_id or 'doc'}_chunk_{i + 1:03d}"

        quality = _quality_score(chunk)

        finalized.append({
            "chunk_id": chunk_id,
            "document_id": document_id,
            "company": company,
            "year": year,
            "doc_type": doc_type,
            "section": chunk.get("section"),
            "subsection": chunk.get("subsection"),
            "page_start": chunk.get("page_start"),
            "page_end": chunk.get("page_end"),
            "text": chunk["text"],
            "token_count": chunk["token_count"],
            "has_heading": chunk.get("has_heading", False),
            "contains_table": chunk.get("contains_table", False),
            "quality_score": quality,
        })
        total_tokens += chunk["token_count"]

    avg_tokens = total_tokens / len(finalized) if finalized else 0.0

    logger.info(
        "Chunking complete: %d chunks, %d total tokens, %.0f avg tokens, "
        "%d sections detected",
        len(finalized), total_tokens, avg_tokens, len(sections),
    )

    return {
        "document_id": document_id,
        "company": company,
        "total_chunks": len(finalized),
        "total_tokens": total_tokens,
        "avg_chunk_tokens": round(avg_tokens, 1),
        "sections_detected": sections,
        "chunks": finalized,
    }
