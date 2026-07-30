"""
Context Builder — Phase 2.6

Assembles retrieved chunks into a coherent, citation-numbered context
block that the LLM can reason over.

Pipeline:
    Retrieved Hits
        |
        v
    Remove Duplicates
        |
        v
    Sort by Document Order (page number)
        |
        v
    Number Citations  [1], [2], ...
        |
        v
    Format Context Block
        |
        v
    Truncate if Over Token Budget
        |
        v
    {context_text, citations, chunks_used, total_tokens}
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Max context tokens to feed LLM (leaves room for prompt + answer)
DEFAULT_MAX_CONTEXT_TOKENS = 6000


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return max(1, len(text) // 4)


def _build_source_string(hit: dict) -> str:
    """Build a human-readable source string from a hit."""
    parts = []
    if hit.get("company"):
        parts.append(hit["company"])
    if hit.get("doc_type"):
        parts.append(hit["doc_type"])
    if hit.get("year"):
        parts.append(str(hit["year"]))
    if hit.get("section"):
        parts.append(hit["section"])
    if hit.get("page_start"):
        if hit.get("page_end") and hit["page_end"] != hit["page_start"]:
            parts.append(f"Pages {hit['page_start']}–{hit['page_end']}")
        else:
            parts.append(f"Page {hit['page_start']}")
    return ", ".join(parts) if parts else "Unknown source"


def build_context(
    hits: list[dict],
    max_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
) -> dict:
    """Build LLM context from retrieved chunks.

    Parameters
    ----------
    hits : list[dict]
        Retrieval hits from retriever.retrieve()["hits"].
    max_tokens : int
        Maximum context token budget.

    Returns
    -------
    dict
        {
            "context_text": "[1] Revenue increased...\n\n[2] Risk factors...",
            "citations": [
                {"ref": 1, "chunk_id": "...", "source": "...", ...},
                ...
            ],
            "chunks_used": 5,
            "total_tokens": 4200,
        }
    """
    if not hits:
        return {
            "context_text": "",
            "citations": [],
            "chunks_used": 0,
            "total_tokens": 0,
        }

    # --- Step 1: Deduplicate by chunk_id ---
    seen: set[str] = set()
    unique: list[dict] = []
    for hit in hits:
        cid = hit.get("chunk_id", "")
        if cid and cid in seen:
            continue
        seen.add(cid)
        unique.append(hit)

    # --- Step 2: Sort by document then page ---
    unique.sort(key=lambda h: (
        h.get("document_id") or "",
        h.get("page_start") or 0,
    ))

    # --- Step 3: Build numbered context blocks ---
    context_parts: list[str] = []
    citations: list[dict] = []
    total_tokens = 0

    for i, hit in enumerate(unique, start=1):
        text = hit.get("text", "").strip()
        if not text:
            continue

        block = f"[{i}] {text}"
        block_tokens = _estimate_tokens(block)

        # Check token budget
        if total_tokens + block_tokens > max_tokens:
            logger.debug("Context budget reached at chunk %d/%d", i, len(unique))
            break

        context_parts.append(block)
        total_tokens += block_tokens

        # Build citation metadata
        source = _build_source_string(hit)
        citations.append({
            "ref": i,
            "chunk_id": hit.get("chunk_id", ""),
            "source": source,
            "section": hit.get("section"),
            "page_start": hit.get("page_start"),
            "page_end": hit.get("page_end"),
            "score": hit.get("score", 0.0),
            "text_preview": text[:150],
        })

    context_text = "\n\n".join(context_parts)

    logger.info("Context built: %d chunks, %d tokens",
                len(citations), total_tokens)

    return {
        "context_text": context_text,
        "citations": citations,
        "chunks_used": len(citations),
        "total_tokens": total_tokens,
    }
