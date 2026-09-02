"""
Shared LangGraph State Definitions

Three TypedDicts — one per pipeline:
    IngestionState   → Document collection (Phase 1)
    RAGState         → Ask / Q&A (Phase 2.6)
    ResearchState    → Full research report (Phase 5)
"""

import operator
from typing import Annotated, Optional
from typing_extensions import TypedDict


# ---------------------------------------------------------------------------
# Graph 1 — Document Ingestion
# ---------------------------------------------------------------------------

class IngestionState(TypedDict):
    """State for the document ingestion pipeline."""
    ticker: str

    # Parallel source results — each node appends one dict; operator.add merges them
    collection_results: Annotated[list[dict], operator.add]
    errors: Annotated[list[str], operator.add]

    # Assembled final result (written by merge node)
    final_result: dict


# ---------------------------------------------------------------------------
# Graph 2 — RAG Ask
# ---------------------------------------------------------------------------

class RAGState(TypedDict):
    """State for the RAG question-answering pipeline."""
    # Inputs
    question: str
    company: Optional[str]
    year: Optional[int]
    doc_type: Optional[str]
    collection: Optional[str]
    top_k: int
    rewrite_query: bool

    # Computed progressively through nodes
    question_type: str
    query_used: str
    hits: list[dict]
    context_text: str
    citations: list[dict]
    chunks_used: int
    prompt: dict
    answer: str
    confidence: dict

    # Final assembled response
    response: dict


# ---------------------------------------------------------------------------
# Graph 3 — Research Report
# ---------------------------------------------------------------------------

class ResearchState(TypedDict):
    """State for the full research report pipeline."""
    # Inputs
    request: str
    companies: list[str]
    year: Optional[int]
    skip_verification: bool

    # Plan (written by plan node)
    plan: dict

    # Parallel evidence parts — each evidence node appends one dict
    evidence_parts: Annotated[list[dict], operator.add]
    errors: Annotated[list[str], operator.add]

    # Merged full evidence package (written by merge node)
    evidence: dict

    # Report pipeline
    report: dict
    claims: list[dict]
    verification: dict
    trace: dict
