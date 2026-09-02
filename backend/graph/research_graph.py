"""
Research Report Graph — LangGraph

Replaces report_generator.generate_research() with a full StateGraph:

    [START]
       │
    node_plan         (classify, extract companies, select tools, gen queries)
       │
    ┌──┼──────────────────────────┐
    │  │           │              │
 financial  market_service  retriever  news   ← PARALLEL evidence gathering
    │  │           │              │
    └──┼──────────────────────────┘
       │
    node_merge_evidence   (assemble full evidence package)
       │
    node_company_info     (enrich company name/sector from data_service)
       │
    node_generate_report  (Phase 4: 7-section AI analyst)
       │
    node_extract_claims   (break report into verifiable claims)
       │
    node_verify           (check claims against evidence)
       │
    ┌──┴──────────────────────────┐
    │ (has unverified)            │ (all verified)
    │                             │
  node_revise                    END
       │
      END
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Generator

from langgraph.graph import StateGraph, START, END

from graph.state import ResearchState
from graph.checkpointer import get_checkpointer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

def node_plan(state: ResearchState) -> dict:
    from planner.planner import create_plan
    plan = create_plan(
        state["request"],
        companies=state.get("companies") or None,
        year=state.get("year"),
    )
    logger.info("[Research] Plan: type=%s, tools=%s", plan["request_type"], plan["required_tools"])
    return {"plan": plan}


def node_financial(state: ResearchState) -> dict:
    from planner.executor import _exec_financial_engine
    logger.info("[Research] Gathering financial data...")
    try:
        result = _exec_financial_engine(state["plan"])
        return {"evidence_parts": [{"type": "financial", "data": result.get("data", {}), "status": result.get("status")}]}
    except Exception as exc:
        logger.warning("[Research] Financial engine failed: %s", exc)
        return {"evidence_parts": [{"type": "financial", "data": {}, "status": "error"}], "errors": [str(exc)]}


def node_market(state: ResearchState) -> dict:
    from planner.executor import _exec_market_service
    logger.info("[Research] Gathering market data...")
    try:
        result = _exec_market_service(state["plan"])
        return {"evidence_parts": [{"type": "market", "data": result.get("data", {}), "status": result.get("status")}]}
    except Exception as exc:
        logger.warning("[Research] Market service failed: %s", exc)
        return {"evidence_parts": [{"type": "market", "data": {}, "status": "error"}], "errors": [str(exc)]}


def node_retriever(state: ResearchState) -> dict:
    from planner.executor import _exec_retriever
    logger.info("[Research] Retrieving document chunks...")
    try:
        result = _exec_retriever(state["plan"])
        return {"evidence_parts": [{"type": "retriever", "data": result.get("data", {}), "status": result.get("status")}]}
    except Exception as exc:
        logger.warning("[Research] Retriever failed: %s", exc)
        return {"evidence_parts": [{"type": "retriever", "data": {"chunks": []}, "status": "error"}], "errors": [str(exc)]}


def node_news(state: ResearchState) -> dict:
    from planner.executor import _exec_news_service
    logger.info("[Research] Fetching news...")
    try:
        result = _exec_news_service(state["plan"])
        return {"evidence_parts": [{"type": "news", "data": result.get("data", {}), "status": result.get("status")}]}
    except Exception as exc:
        logger.warning("[Research] News service failed: %s", exc)
        return {"evidence_parts": [{"type": "news", "data": {"news": []}, "status": "error"}], "errors": [str(exc)]}


def node_merge_evidence(state: ResearchState) -> dict:
    """Assemble the full evidence package from all parallel source parts."""
    plan = state["plan"]
    companies = plan.get("companies", [])
    primary = companies[0] if companies else "UNKNOWN"

    evidence = {
        "company": {"name": primary, "ticker": primary, "sector": "Unknown"},
        "market_data": {},
        "financial_metrics": {},
        "financial_health": {},
        "growth_metrics": {},
        "retrieved_evidence": [],
        "news": [],
        "peer_comparison": {},
    }

    for part in state.get("evidence_parts", []):
        ptype = part.get("type")
        data = part.get("data", {})

        if ptype == "financial" and primary in data:
            engine_data = data[primary]
            evidence["financial_metrics"] = engine_data.get("metrics", {})
            evidence["financial_health"] = engine_data.get("health", {})

        elif ptype == "market" and primary in data:
            evidence["market_data"] = data[primary]

        elif ptype == "retriever":
            evidence["retrieved_evidence"] = data.get("chunks", [])

        elif ptype == "news":
            evidence["news"] = data.get("news", [])

    logger.info("[Research] Evidence assembled: %d retrieved chunks, %d news items",
                len(evidence["retrieved_evidence"]), len(evidence["news"]))
    return {"evidence": evidence}


def node_company_info(state: ResearchState) -> dict:
    """Enrich company info from data_service."""
    plan = state["plan"]
    companies = plan.get("companies", [])
    primary = companies[0] if companies else "UNKNOWN"
    evidence = dict(state["evidence"])

    try:
        from services import data_service
        company_data = data_service.get_company_overview(primary)
        evidence["company"] = {
            "name": company_data.name or primary,
            "ticker": primary,
            "sector": company_data.sector or "Unknown",
            "industry": company_data.industry or "Unknown",
        }
    except Exception:
        pass  # keep the default from merge step

    return {"evidence": evidence}


def node_generate_report(state: ResearchState) -> dict:
    from agents.equity_analyst import generate_report
    logger.info("[Research] Generating report sections...")
    report = generate_report(state["evidence"])
    return {"report": report}


def node_extract_claims(state: ResearchState) -> dict:
    from verification.claim_extractor import extract_claims
    claims = extract_claims(state["report"])
    logger.info("[Research] Extracted %d claims", len(claims))
    return {"claims": claims}


def node_verify(state: ResearchState) -> dict:
    from verification.verifier import verify_claims
    verification = verify_claims(state["claims"], state["evidence"])
    logger.info("[Research] Verification: %d/%d verified",
                verification["verified"], verification["total_claims"])
    return {"verification": verification}


def node_revise(state: ResearchState) -> dict:
    from verification.verifier import revise_report
    logger.info("[Research] Revising %d unverified claims", state["verification"]["unverified"])
    revised = revise_report(state["report"], state["verification"])
    return {"report": revised}


# ---------------------------------------------------------------------------
# Conditional edge
# ---------------------------------------------------------------------------

def route_verification(state: ResearchState) -> str:
    if state.get("verification", {}).get("unverified", 0) > 0:
        return "revise_report"
    return END


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def _build_graph():
    builder = StateGraph(ResearchState)

    builder.add_node("plan", node_plan)
    builder.add_node("financial", node_financial)
    builder.add_node("market", node_market)
    builder.add_node("retriever", node_retriever)
    builder.add_node("news", node_news)
    builder.add_node("merge_evidence", node_merge_evidence)
    builder.add_node("company_info", node_company_info)
    builder.add_node("generate_report", node_generate_report)
    builder.add_node("extract_claims", node_extract_claims)
    builder.add_node("verify_claims", node_verify)
    builder.add_node("revise_report", node_revise)

    # plan → parallel evidence gathering (fan-out)
    builder.add_edge(START, "plan")
    builder.add_edge("plan", "financial")
    builder.add_edge("plan", "market")
    builder.add_edge("plan", "retriever")
    builder.add_edge("plan", "news")

    # parallel → merge (fan-in)
    builder.add_edge("financial", "merge_evidence")
    builder.add_edge("market", "merge_evidence")
    builder.add_edge("retriever", "merge_evidence")
    builder.add_edge("news", "merge_evidence")

    # Sequential report pipeline
    builder.add_edge("merge_evidence", "company_info")
    builder.add_edge("company_info", "generate_report")
    builder.add_edge("generate_report", "extract_claims")
    builder.add_edge("extract_claims", "verify_claims")

    # Conditional: revise if unverified claims exist
    builder.add_conditional_edges(
        "verify_claims",
        route_verification,
        {"revise_report": "revise_report", END: END},
    )
    builder.add_edge("revise_report", END)

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

def run_research(
    request: str,
    companies: list = None,
    year: int = None,
    skip_verification: bool = False,
) -> dict:
    """Run the research graph synchronously and return {report, verification, trace}."""
    graph = _get_graph()
    thread_id = f"research-{uuid.uuid4().hex}"
    config = {"configurable": {"thread_id": thread_id}}
    start_ts = datetime.now(timezone.utc).isoformat()

    initial_state = {
        "request": request,
        "companies": companies or [],
        "year": year,
        "skip_verification": skip_verification,
        "plan": {},
        "evidence_parts": [],
        "errors": [],
        "evidence": {},
        "report": {},
        "claims": [],
        "verification": {},
        "trace": {},
    }

    import time
    t0 = time.time()
    final_state = graph.invoke(initial_state, config)
    elapsed_ms = int((time.time() - t0) * 1000)

    trace = {
        "thread_id": thread_id,
        "request": request,
        "companies": companies,
        "timestamp": start_ts,
        "duration_ms": elapsed_ms,
        "errors": final_state.get("errors", []),
    }

    return {
        "report": final_state["report"],
        "verification": final_state.get("verification", {}),
        "trace": trace,
    }


def stream_research(
    request: str,
    companies: list = None,
    year: int = None,
    skip_verification: bool = False,
) -> Generator[dict, None, None]:
    """Stream research graph node events as they complete.

    Yields dicts like: {"node": "plan", "data": {...}}
    """
    graph = _get_graph()
    thread_id = f"research-stream-{uuid.uuid4().hex}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "request": request,
        "companies": companies or [],
        "year": year,
        "skip_verification": skip_verification,
        "plan": {},
        "evidence_parts": [],
        "errors": [],
        "evidence": {},
        "report": {},
        "claims": [],
        "verification": {},
        "trace": {},
    }

    for event in graph.stream(initial_state, config, stream_mode="updates"):
        for node_name, node_output in event.items():
            yield {"node": node_name, "data": node_output}
