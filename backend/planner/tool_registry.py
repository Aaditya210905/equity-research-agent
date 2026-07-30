"""
Tool Registry — Phase 5

Central registry of all tools available to the research planner.
Each tool has a name, description, and the request types it serves.

The planner uses this registry to decide which tools to invoke.
The executor uses it to find the function to call.
"""

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOL_REGISTRY = {
    "financial_engine": {
        "name": "financial_engine",
        "description": "Compute financial ratios and metrics (margins, ROE, ROIC, etc.)",
        "serves": ["factual_query", "company_analysis", "comparison", "investment_memo"],
        "inputs": ["ticker"],
    },
    "market_service": {
        "name": "market_service",
        "description": "Current stock price, market cap, P/E, and trading data",
        "serves": ["factual_query", "company_analysis", "comparison", "investment_memo"],
        "inputs": ["ticker"],
    },
    "retriever": {
        "name": "retriever",
        "description": "Retrieve evidence from indexed annual reports and SEC filings",
        "serves": ["company_analysis", "risk_analysis", "investment_memo"],
        "inputs": ["query", "company"],
    },
    "news_service": {
        "name": "news_service",
        "description": "Fetch recent news about the company",
        "serves": ["company_analysis", "risk_analysis", "investment_memo"],
        "inputs": ["ticker"],
    },
    "peer_comparison": {
        "name": "peer_comparison",
        "description": "Compare financial metrics across multiple companies",
        "serves": ["comparison"],
        "inputs": ["tickers"],
    },
    "health_scorer": {
        "name": "health_scorer",
        "description": "Compute a financial health score (0–100) from metrics",
        "serves": ["company_analysis", "comparison", "investment_memo"],
        "inputs": ["financial_data"],
    },
}


def get_tools_for_request_type(request_type: str) -> list[str]:
    """Return tool names needed for a given request type."""
    return [
        name
        for name, tool in TOOL_REGISTRY.items()
        if request_type in tool["serves"]
    ]


def get_tool(name: str) -> dict:
    """Look up a tool by name."""
    return TOOL_REGISTRY.get(name)


def list_tools() -> list[str]:
    """Return all registered tool names."""
    return list(TOOL_REGISTRY.keys())
