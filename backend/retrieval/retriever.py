"""
Semantic Retriever — Phase 2.5

Retrieves the most relevant chunks for a given query by combining:
    1. Query embedding (via embedder)
    2. Vector search (via Qdrant)
    3. Metadata filtering
    4. Similarity thresholding
    5. Re-ranking (quality + score boost)
    6. Citation formatting

Pipeline:
    Query Text
        |
        v
    Embed Query  (or accept pre-computed vector)
        |
        v
    Vector Search  (Qdrant, top_k * 2 for re-ranking headroom)
        |
        v
    Apply Threshold
        |
        v
    Re-rank  (boost headings, quality, section match)
        |
        v
    Deduplicate  (near-identical text)
        |
        v
    Assemble Context  (sort by document order)
        |
        v
    Return Citation-Ready Results
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Relevance tiers
# ---------------------------------------------------------------------------
SCORE_EXCELLENT = 0.85
SCORE_GOOD = 0.75
SCORE_FAIR = 0.60


def _relevance_tier(score: float) -> str:
    """Classify a similarity score into a relevance tier."""
    if score >= SCORE_EXCELLENT:
        return "excellent"
    elif score >= SCORE_GOOD:
        return "good"
    elif score >= SCORE_FAIR:
        return "fair"
    return "low"


# ---------------------------------------------------------------------------
# Query embedding helper
# ---------------------------------------------------------------------------

def _embed_query(query: str, model: str = None) -> list[float]:
    """Embed a single query string."""
    from embedding.embedder import _embed_batch_raw, DEFAULT_MODEL
    model = model or DEFAULT_MODEL
    vectors = _embed_batch_raw([query], model=model)
    return vectors[0]


# ---------------------------------------------------------------------------
# Re-ranking
# ---------------------------------------------------------------------------

def _rerank(results: list[dict]) -> list[dict]:
    """Re-rank search results by combining vector score with metadata signals.

    Boosting rules:
        +0.02  chunk has a heading (more self-contained)
        +0.01  chunk quality_score > 0.8
        -0.01  chunk contains_table (tables are less semantically searchable)
        +0.02  chunk has section metadata (better citation)

    This is a lightweight re-ranker. A cross-encoder (e.g. ms-marco)
    can be plugged in here for production use.
    """
    for r in results:
        adjusted = r["score"]
        if r.get("has_heading"):
            adjusted += 0.02
        if r.get("quality_score", 0) > 0.8:
            adjusted += 0.01
        if r.get("contains_table"):
            adjusted -= 0.01
        if r.get("section"):
            adjusted += 0.02
        r["_rerank_score"] = round(min(1.0, adjusted), 4)

    results.sort(key=lambda r: r["_rerank_score"], reverse=True)

    # Clean up internal key
    for r in results:
        r.pop("_rerank_score", None)

    return results


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _deduplicate(results: list[dict], threshold: float = 0.95) -> list[dict]:
    """Remove near-duplicate results (same text / same chunk_id)."""
    seen_ids: set[str] = set()
    seen_text_prefixes: set[str] = set()
    unique: list[dict] = []

    for r in results:
        cid = r.get("chunk_id", "")
        if cid in seen_ids:
            continue

        # Check text prefix similarity (first 200 chars)
        prefix = r.get("text", "")[:200]
        if prefix in seen_text_prefixes:
            continue

        seen_ids.add(cid)
        seen_text_prefixes.add(prefix)
        unique.append(r)

    return unique


# ---------------------------------------------------------------------------
# Context assembly
# ---------------------------------------------------------------------------

def _assemble_context(results: list[dict]) -> list[dict]:
    """Sort results by document order for coherent context.

    Groups by document_id, then sorts by page_start within each group.
    Preserves the re-ranked order across different documents.
    """
    # Group by document
    from collections import defaultdict
    by_doc: dict[str, list[dict]] = defaultdict(list)
    doc_order: list[str] = []

    for r in results:
        doc_id = r.get("document_id") or "unknown"
        if doc_id not in doc_order:
            doc_order.append(doc_id)
        by_doc[doc_id].append(r)

    # Sort within each document by page
    assembled: list[dict] = []
    for doc_id in doc_order:
        chunks = by_doc[doc_id]
        chunks.sort(key=lambda c: c.get("page_start") or 0)
        assembled.extend(chunks)

    return assembled


# ===========================================================================
# Public API
# ===========================================================================

def retrieve(
    query: str = None,
    query_vector: list[float] = None,
    top_k: int = 10,
    company: str = None,
    year: int = None,
    doc_type: str = None,
    section: str = None,
    document_id: str = None,
    min_score: float = 0.0,
    rerank: bool = True,
    deduplicate: bool = True,
    embedding_model: str = None,
    collection: str = None,
) -> dict:
    """Retrieve the most relevant chunks for a query.

    Provide either ``query`` (text, will be embedded) or ``query_vector``
    (pre-computed embedding). Using ``query_vector`` allows testing
    without an OpenAI API key.

    Parameters
    ----------
    query : str
        Natural language question (will be embedded).
    query_vector : list[float]
        Pre-computed query embedding (skips embedding step).
    top_k : int
        Maximum results to return.
    company, year, doc_type, section, document_id
        Metadata filters.
    min_score : float
        Minimum similarity score (0.0–1.0).
    rerank : bool
        Apply lightweight re-ranking.
    deduplicate : bool
        Remove near-duplicate results.
    embedding_model : str
        Model for query embedding (default from config).
    collection : str
        Qdrant collection to search.

    Returns
    -------
    dict
        RetrievalResponse-compatible dict::

            {
                "query": "What are TCS risks?",
                "total_hits": 5,
                "hits": [
                    {
                        "chunk_id": "TCS_RF_003",
                        "score": 0.94,
                        "text": "...",
                        "relevance": "excellent",
                        ...
                    }
                ],
                "filters_applied": {"company": "TCS"},
                "min_score_used": 0.6
            }
    """
    from vector_store.qdrant_store import search as qdrant_search, DEFAULT_COLLECTION

    collection = collection or DEFAULT_COLLECTION

    # Embed query if needed
    if query_vector is None:
        if query is None:
            raise ValueError("Provide either 'query' or 'query_vector'")
        query_vector = _embed_query(query, model=embedding_model)

    query_text = query or ""

    # Search with headroom for re-ranking
    search_k = top_k * 2 if rerank else top_k

    results = qdrant_search(
        query_vector=query_vector,
        collection=collection,
        top_k=search_k,
        company=company,
        year=year,
        doc_type=doc_type,
        section=section,
        document_id=document_id,
        min_score=min_score,
    )

    # Re-rank
    if rerank and results:
        results = _rerank(results)

    # Deduplicate
    if deduplicate and results:
        results = _deduplicate(results)

    # Trim to requested top_k
    results = results[:top_k]

    # Assemble context (sort by document order)
    results = _assemble_context(results)

    # Add relevance tiers
    for r in results:
        r["relevance"] = _relevance_tier(r["score"])

    # Build filters dict for response
    filters_applied = {}
    if company:
        filters_applied["company"] = company
    if year is not None:
        filters_applied["year"] = year
    if doc_type:
        filters_applied["doc_type"] = doc_type
    if section:
        filters_applied["section"] = section
    if document_id:
        filters_applied["document_id"] = document_id

    return {
        "query": query_text,
        "total_hits": len(results),
        "hits": results,
        "filters_applied": filters_applied,
        "min_score_used": min_score,
    }
