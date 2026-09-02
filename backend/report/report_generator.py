"""
Report Generator — Phase 5 (LangGraph)

Delegates to the LangGraph Research Report Graph:

    User Request
        │
        v
    1. Plan Node          → classify, extract companies, select tools, gen queries
        │
        v  (parallel)
    2. Evidence Nodes     → financial_engine | market_service | retriever | news
        │
        v
    3. Merge Node         → assemble full evidence package
        │
        v
    4. Company Info Node  → enrich company name/sector
        │
        v
    5. Report Node        → Phase 4 AI analyst: 7 sections
        │
        v
    6. Claims Node        → break report into verifiable claims
        │
        v
    7. Verify Node        → check every claim against evidence
        │
        v  (conditional)
    8. Revise Node        → add disclaimers for unverified claims
        │
        v
    Final Verified Report + Execution Trace
"""

import logging

logger = logging.getLogger(__name__)


def generate_research(
    request: str,
    companies: list[str] = None,
    year: int = None,
    skip_verification: bool = False,
) -> dict:
    """Generate a complete, verified equity research report.

    Delegates to the LangGraph Research Report Graph. The graph runs
    evidence gathering in parallel (financial engine, market service,
    retriever, and news) and supports checkpointing + streaming.

    Parameters
    ----------
    request : str
        Natural language research request.
    companies : list[str], optional
        Override auto-detected company tickers.
    year : int, optional
        Fiscal year filter.
    skip_verification : bool
        Skip claim verification (faster but less reliable).

    Returns
    -------
    dict
        {
            "report": {...},        # Full research report
            "verification": {...},  # Claim verification results
            "trace": {...},         # Execution trace
        }
    """
    from graph.research_graph import run_research
    return run_research(
        request=request,
        companies=companies,
        year=year,
        skip_verification=skip_verification,
    )
