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

    builder.add_edge("merge", END)

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
    }
    for event in graph.stream(initial_state, config, stream_mode="updates"):
        for node_name, node_output in event.items():
            yield {"node": node_name, "data": node_output}
