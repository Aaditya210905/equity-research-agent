"""
Document Ingestion Graph — LangGraph

Replaces the sequential collect_documents() with a parallel StateGraph:

    [START]
       │
    node_init   (uppercase ticker, init DB)
       │
    ┌──┼──────────────┐
    │  │              │
  yahoo  sec_edgar  bse_india   ← run in PARALLEL
    │  │              │
    └──┼──────────────┘
       │
    node_merge  (sum counts, build final dict)
       │
    [END]

The three source nodes each append a result dict to `collection_results`.
LangGraph's operator.add reducer merges them automatically.
"""

import logging
import uuid
from pathlib import Path
from typing import Generator

from langgraph.graph import StateGraph, START, END

from graph.state import IngestionState
from graph.checkpointer import get_checkpointer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

def node_init(state: IngestionState) -> dict:
    """Initialize: uppercase ticker and ensure DB is ready."""
    from models.document import initialize_db
    ticker = state["ticker"].strip().upper()
    initialize_db()
    logger.info("[Ingestion] Starting collection for '%s'", ticker)
    return {"ticker": ticker}


def node_yahoo(state: IngestionState) -> dict:
    """Collect Yahoo Finance financial statements."""
    ticker = state["ticker"]
    logger.info("[Ingestion] Yahoo Finance: collecting for '%s'", ticker)
    try:
        from services.document_service import _collect_financial_statements
        result = _collect_financial_statements(ticker)
        result["source"] = "yahoo"
        return {"collection_results": [result]}
    except Exception as exc:
        logger.error("[Ingestion] Yahoo Finance failed for '%s': %s", ticker, exc)
        return {
            "collection_results": [{"source": "yahoo", "new": 0, "existing": 0, "failed": 0, "documents": []}],
            "errors": [f"Yahoo: {exc}"],
        }


def node_sec(state: IngestionState) -> dict:
    """Collect SEC EDGAR filings (US companies only)."""
    ticker = state["ticker"]
    logger.info("[Ingestion] SEC EDGAR: collecting for '%s'", ticker)
    try:
        from services.document_service import _collect_sec_filings
        result = _collect_sec_filings(ticker)
        result["source"] = "sec"
        return {"collection_results": [result]}
    except Exception as exc:
        logger.info("[Ingestion] SEC EDGAR not available for '%s': %s", ticker, exc)
        return {
            "collection_results": [{"source": "sec", "new": 0, "existing": 0, "failed": 0, "documents": []}],
        }


def node_bse(state: IngestionState) -> dict:
    """Collect BSE India filings (Indian companies only)."""
    ticker = state["ticker"]
    logger.info("[Ingestion] BSE India: collecting for '%s'", ticker)
    try:
        from services.document_service import _collect_bse_filings
        result = _collect_bse_filings(ticker)
        result["source"] = "bse"
        return {"collection_results": [result]}
    except Exception as exc:
        logger.info("[Ingestion] BSE not available for '%s': %s", ticker, exc)
        return {
            "collection_results": [{"source": "bse", "new": 0, "existing": 0, "failed": 0, "documents": []}],
        }


def node_merge(state: IngestionState) -> dict:
    """Merge all parallel source results into the final summary dict."""
    ticker = state["ticker"]
    results = state.get("collection_results", [])

    total_new = sum(r.get("new", 0) for r in results)
    total_existing = sum(r.get("existing", 0) for r in results)
    total_failed = sum(r.get("failed", 0) for r in results)
    all_docs = []
    for r in results:
        all_docs.extend(r.get("documents", []))

    logger.info(
        "[Ingestion] Complete for '%s': %d new, %d existing, %d failed",
        ticker, total_new, total_existing, total_failed
    )

    return {
        "final_result": {
            "ticker": ticker,
            "new_documents": total_new,
            "existing_documents": total_existing,
            "failed": total_failed,
            "documents": all_docs,
            "sources": [r.get("source", "unknown") for r in results],
        }
    }


def node_embed(state: IngestionState) -> dict:
    """Phase 2 pipeline: extract → clean → chunk → embed → upload to Qdrant.

    Processes every document in the final_result. Skips documents that are
    already marked as 'embedded' in the SQL database. Updates processing_status
    to 'embedded' after successful upload.
    """
    from ingestion.pdf_extractor import extract_document
    from ingestion.text_cleaner import clean_document
    from ingestion.chunker import chunk_document
    from embedding.embedder import embed_chunks
    from vector_store.qdrant_store import upload_chunks
    from models.document import Document

    BACKEND_DIR = Path(__file__).resolve().parents[1]

    final_result = state.get("final_result", {})
    all_docs = final_result.get("documents", [])
    ticker = state["ticker"]

    total_embedded = 0
    total_chunks = 0
    total_cached = 0
    total_failed = 0
    skipped = 0

    for doc in all_docs:
        doc_id = doc.get("document_id", "")
        file_path_rel = doc.get("file_path", "")
        company = doc.get("ticker", ticker)
        year = doc.get("year")
        doc_type = doc.get("doc_type", "")

        # Skip documents already fully embedded
        if doc.get("processing_status") == "embedded":
            skipped += 1
            logger.debug("[Embed] Skipping already-embedded doc: %s", doc_id)
            continue

        if not file_path_rel:
            logger.warning("[Embed] No file_path for doc %s — skipping", doc_id)
            total_failed += 1
            continue

        file_path = BACKEND_DIR / file_path_rel
        if not file_path.exists():
            logger.warning("[Embed] File not found: %s — skipping", file_path)
            total_failed += 1
            continue

        try:
            # Step 1: Extract
            logger.info("[Embed] Extracting %s (%s)", doc_id, file_path.suffix)
            extraction = extract_document(
                file_path,
                document_id=doc_id,
                company=company,
                year=year,
                source=doc_type,
            )
            if not extraction["success"] or not extraction.get("pages"):
                logger.warning("[Embed] Extraction failed for %s: %s", doc_id, extraction.get("error"))
                total_failed += 1
                continue

            # Step 2: Clean
            cleaned = clean_document(extraction["pages"])
            clean_pages = cleaned.get("pages", [])

            # Step 3: Chunk
            chunked = chunk_document(
                clean_pages,
                document_id=doc_id,
                company=company,
                year=year,
                doc_type=doc_type,
            )
            chunks = chunked.get("chunks", [])
            if not chunks:
                logger.warning("[Embed] No chunks produced for %s", doc_id)
                total_failed += 1
                continue

            logger.info("[Embed] %s → %d chunks, embedding...", doc_id, len(chunks))

            # Step 4: Embed
            embed_result = embed_chunks(chunks, use_cache=True)
            embedded_chunks = embed_result.get("chunks", [])

            # Step 5: Upload to Qdrant
            upload_result = upload_chunks(embedded_chunks)

            total_embedded += 1
            total_chunks += len(embedded_chunks)
            total_cached += embed_result.get("cached", 0)
            logger.info(
                "[Embed] Uploaded %d vectors for %s (cached=%d)",
                upload_result.get("uploaded", 0),
                doc_id,
                embed_result.get("cached", 0),
            )

            # Step 6: Mark as embedded in SQL
            try:
                db_doc = Document.get_by_id(doc_id)
                db_doc.processing_status = "embedded"
                db_doc.save()
            except Exception:
                pass  # Don't fail the whole embed if status update fails

        except Exception as exc:
            logger.error("[Embed] Failed for %s: %s", doc_id, exc, exc_info=True)
            total_failed += 1

    logger.info(
        "[Embed] Complete for '%s': %d docs embedded, %d skipped, %d failed, %d total chunks",
        ticker, total_embedded, skipped, total_failed, total_chunks,
    )

    embed_stats = {
        "docs_embedded": total_embedded,
        "docs_skipped": skipped,
        "docs_failed": total_failed,
        "total_chunks": total_chunks,
        "total_cached": total_cached,
    }

    # Merge embed_stats back into final_result so the API response includes it
    updated_final = {**final_result, "embed_stats": embed_stats}
    return {"embed_stats": embed_stats, "final_result": updated_final}


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def _build_graph():
    builder = StateGraph(IngestionState)

    builder.add_node("init", node_init)
    builder.add_node("yahoo", node_yahoo)
    builder.add_node("sec", node_sec)
    builder.add_node("bse", node_bse)
    builder.add_node("merge", node_merge)
    builder.add_node("embed", node_embed)

    # Sequential start → init
    builder.add_edge(START, "init")

    # Fan-out: init → all three sources in PARALLEL
    builder.add_edge("init", "yahoo")
    builder.add_edge("init", "sec")
    builder.add_edge("init", "bse")

    # Fan-in: all three → merge
    builder.add_edge("yahoo", "merge")
    builder.add_edge("sec", "merge")
    builder.add_edge("bse", "merge")

    # merge → embed → END
    builder.add_edge("merge", "embed")
    builder.add_edge("embed", END)

    return builder.compile(checkpointer=get_checkpointer())


_graph = None

def _get_graph():
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_ingestion(ticker: str) -> dict:
    """Run the ingestion graph synchronously and return the final result dict."""
    graph = _get_graph()
    thread_id = f"ingest-{ticker.upper()}-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "ticker": ticker,
        "collection_results": [],
        "errors": [],
        "final_result": {},
        "embed_stats": {},
    }
    final_state = graph.invoke(initial_state, config)
    return final_state["final_result"]


def stream_ingestion(ticker: str) -> Generator[dict, None, None]:
    """Stream ingestion graph node events as they complete.

    Yields dicts like: {"node": "yahoo", "data": {...}}
    """
    graph = _get_graph()
    thread_id = f"ingest-{ticker.upper()}-stream-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "ticker": ticker,
        "collection_results": [],
        "errors": [],
        "final_result": {},
        "embed_stats": {},
    }
    for event in graph.stream(initial_state, config, stream_mode="updates"):
        for node_name, node_output in event.items():
            yield {"node": node_name, "data": node_output}
