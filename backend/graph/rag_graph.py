"""
RAG Ask Graph — LangGraph

Replaces the sequential ask() orchestrator with a StateGraph:

    [START]
       │
    classify       (factual / comparative / analytical / summarization)
       │
    expand         (financial term expansion)
       │
    retrieve       (vector search in Qdrant)
       │
    build_context  (numbered citations, token budget)
       │
    ┌──┴──────────────────────┐
    │ (no evidence)           │ (has evidence)
    │                         │
 respond_insufficient    build_prompt
                              │
                         generate_answer
                              │
                         compute_confidence
                              │
                           respond
                              │
                            [END]
"""

import logging
import uuid
from typing import Generator

from langgraph.graph import StateGraph, START, END

from graph.state import RAGState
from graph.checkpointer import get_checkpointer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

def node_classify(state: RAGState) -> dict:
    from rag.orchestrator import classify_question
    qtype = classify_question(state["question"])
    logger.info("[RAG] Question type: %s", qtype)
    return {"question_type": qtype}


def node_expand(state: RAGState) -> dict:
    from rag.orchestrator import expand_query, rewrite_query_with_llm
    if state.get("rewrite_query"):
        query = rewrite_query_with_llm(state["question"], company=state.get("company"))
    else:
        query = expand_query(state["question"])
    logger.info("[RAG] Query: '%s'", query[:100])
    return {"query_used": query}


def node_retrieve(state: RAGState) -> dict:
    from retrieval.retriever import retrieve
    kwargs = {
        "query": state["query_used"],
        "top_k": state.get("top_k", 10),
        "min_score": 0.0,
    }
    company = state.get("company")
    if company and company.strip().lower() not in ("string", "none", "null", ""):
        kwargs["company"] = company.strip().upper()
    year = state.get("year")
    if year and year > 1900:
        kwargs["year"] = year
    doc_type = state.get("doc_type")
    if doc_type and doc_type.strip().lower() not in ("string", "none", "null", ""):
        kwargs["doc_type"] = doc_type.strip().lower()
    if state.get("collection"):
        kwargs["collection"] = state["collection"]

    result = retrieve(**kwargs)
    hits = result.get("hits", [])
    logger.info("[RAG] Retrieved %d chunks", len(hits))
    return {"hits": hits}


def node_build_context(state: RAGState) -> dict:
    from rag.context_builder import build_context
    ctx = build_context(state["hits"])
    return {
        "context_text": ctx["context_text"],
        "citations": ctx["citations"],
        "chunks_used": ctx["chunks_used"],
    }


def node_build_prompt(state: RAGState) -> dict:
    from rag.prompt_builder import build_prompt
    prompt = build_prompt(state["question"], state["context_text"], state["question_type"])
    return {"prompt": prompt}


def node_generate(state: RAGState) -> dict:
    from rag.orchestrator import _generate_answer
    from config.settings import settings
    model = getattr(settings, "LLM_MODEL", "gpt-4o-mini")
    answer = _generate_answer(state["prompt"]["system"], state["prompt"]["user"], model)
    return {"answer": answer}


def node_compute_confidence(state: RAGState) -> dict:
    from rag.confidence import compute_confidence
    scores = [h.get("score", 0.0) for h in state["hits"][:state["chunks_used"]]]
    conf = compute_confidence(scores, state["chunks_used"], state.get("top_k", 10))
    return {"confidence": conf}


def node_respond(state: RAGState) -> dict:
    from config.settings import settings
    model = getattr(settings, "LLM_MODEL", "gpt-4o-mini")
    conf = state["confidence"]
    return {
        "response": {
            "answer": state["answer"],
            "citations": state["citations"],
            "confidence": conf["score"],
            "confidence_tier": conf["tier"],
            "question": state["question"],
            "question_type": state["question_type"],
            "query_used": state["query_used"],
            "chunks_retrieved": len(state["hits"]),
            "chunks_used": state["chunks_used"],
            "model": model,
            "evidence_sufficient": conf["evidence_sufficient"],
        }
    }


def node_respond_insufficient(state: RAGState) -> dict:
    from rag.confidence import compute_confidence
    from config.settings import settings
    model = getattr(settings, "LLM_MODEL", "gpt-4o-mini")
    conf = compute_confidence([], 0, state.get("top_k", 10))
    return {
        "response": {
            "answer": (
                "The available documents do not contain sufficient information "
                "to answer this question. Please ensure relevant documents have "
                "been indexed for this company."
            ),
            "citations": [],
            "confidence": conf["score"],
            "confidence_tier": conf["tier"],
            "question": state["question"],
            "question_type": state["question_type"],
            "query_used": state.get("query_used", state["question"]),
            "chunks_retrieved": len(state.get("hits", [])),
            "chunks_used": 0,
            "model": model,
            "evidence_sufficient": False,
        }
    }


# ---------------------------------------------------------------------------
# Conditional edge
# ---------------------------------------------------------------------------

def route_evidence(state: RAGState) -> str:
    """Route to insufficient-evidence handler if context is empty."""
    if not state.get("context_text", "").strip():
        return "respond_insufficient"
    return "build_prompt"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def _build_graph():
    builder = StateGraph(RAGState)

    builder.add_node("classify", node_classify)
    builder.add_node("expand", node_expand)
    builder.add_node("retrieve", node_retrieve)
    builder.add_node("build_context", node_build_context)
    builder.add_node("build_prompt", node_build_prompt)
    builder.add_node("generate_answer", node_generate)
    builder.add_node("compute_confidence", node_compute_confidence)
    builder.add_node("respond", node_respond)
    builder.add_node("respond_insufficient", node_respond_insufficient)

    builder.add_edge(START, "classify")
    builder.add_edge("classify", "expand")
    builder.add_edge("expand", "retrieve")
    builder.add_edge("retrieve", "build_context")

    # Conditional: has evidence ΓåÆ full pipeline; empty ΓåÆ short-circuit
    builder.add_conditional_edges(
        "build_context",
        route_evidence,
        {"build_prompt": "build_prompt", "respond_insufficient": "respond_insufficient"},
    )

    builder.add_edge("build_prompt", "generate_answer")
    builder.add_edge("generate_answer", "compute_confidence")
    builder.add_edge("compute_confidence", "respond")
    builder.add_edge("respond", END)
    builder.add_edge("respond_insufficient", END)

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

def run_rag(
    question: str,
    company: str = None,
    year: int = None,
    doc_type: str = None,
    collection: str = None,
    top_k: int = 10,
    rewrite_query: bool = False,
) -> dict:
    """Run the RAG graph synchronously and return the response dict."""
    graph = _get_graph()
    thread_id = f"rag-{uuid.uuid4().hex}"
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "question": question,
        "company": company,
        "year": year,
        "doc_type": doc_type,
        "collection": collection,
        "top_k": top_k,
        "rewrite_query": rewrite_query,
        "question_type": "",
        "query_used": "",
        "hits": [],
        "context_text": "",
        "citations": [],
        "chunks_used": 0,
        "prompt": {},
        "answer": "",
        "confidence": {},
        "response": {},
    }
    final_state = graph.invoke(initial_state, config)
    return final_state["response"]


def stream_rag(
    question: str,
    company: str = None,
    year: int = None,
    doc_type: str = None,
    collection: str = None,
    top_k: int = 10,
    rewrite_query: bool = False,
) -> Generator[dict, None, None]:
    """Stream RAG graph node events as they complete.

    Yields dicts like: {"node": "classify", "data": {...}}
    """
    graph = _get_graph()
    thread_id = f"rag-stream-{uuid.uuid4().hex}"
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "question": question,
        "company": company,
        "year": year,
        "doc_type": doc_type,
        "collection": collection,
        "top_k": top_k,
        "rewrite_query": rewrite_query,
        "question_type": "",
        "query_used": "",
        "hits": [],
        "context_text": "",
        "citations": [],
        "chunks_used": 0,
        "prompt": {},
        "answer": "",
        "confidence": {},
        "response": {},
    }
    for event in graph.stream(initial_state, config, stream_mode="updates"):
        for node_name, node_output in event.items():
            yield {"node": node_name, "data": node_output}
