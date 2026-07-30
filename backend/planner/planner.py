"""
Research Planner — Phase 5

Converts a user request into a structured execution plan.
The planner:
    1. Classifies the request type
    2. Identifies required companies
    3. Selects necessary tools
    4. Generates retrieval queries
    5. Outputs a structured ResearchPlan

The planner is DETERMINISTIC for common request types.
No LLM call needed for planning — this keeps it fast, testable, and reliable.
"""

import logging
import re
import uuid
from typing import Optional

from planner.tool_registry import get_tools_for_request_type

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Request type classification (rule-based, no LLM)
# ---------------------------------------------------------------------------

_REQUEST_PATTERNS = {
    "comparison": [
        r"\bcompare\b", r"\bvs\.?\b", r"\bversus\b", r"\bdifference\b",
        r"\bbetter\s+than\b", r"\bcompared\s+to\b",
    ],
    "risk_analysis": [
        r"\brisk", r"\bthreat", r"\bconcern", r"\bdanger",
        r"\bchallenge", r"\bvulnerab",
    ],
    "investment_memo": [
        r"\binvestment\s+memo", r"\bresearch\s+report", r"\bfull\s+analysis",
        r"\bcomplete\s+report", r"\bequity\s+research", r"\binvestment\s+thesis",
        r"\bwrite\s+a\s+report", r"\banalyze\s+.*\s+from\s+an\s+investment",
    ],
    "factual_query": [
        r"\bwhat\s+is\b", r"\bwhat\s+was\b", r"\bhow\s+much\b",
        r"\bcurrent\s+price\b", r"\broe\b", r"\broa\b", r"\beps\b",
        r"\bmarket\s+cap\b", r"\brevenue\b", r"\bprofit\b",
    ],
    # "company_analysis" is the default for anything with a ticker
}


def classify_request(request: str) -> str:
    """Classify a user request into a request type."""
    req_lower = request.lower().strip()

    for rtype, patterns in _REQUEST_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, req_lower):
                return rtype

    return "company_analysis"


# ---------------------------------------------------------------------------
# Company extraction (rule-based)
# ---------------------------------------------------------------------------

# Common ticker patterns
_TICKER_PATTERN = re.compile(r"\b([A-Z]{2,5})\b")

_KNOWN_COMPANIES = {
    "tcs": "TCS", "infosys": "INFY", "infy": "INFY", "wipro": "WIPRO",
    "reliance": "RELIANCE", "hdfc": "HDFCBANK", "apple": "AAPL", "aapl": "AAPL",
    "google": "GOOGL", "googl": "GOOGL", "microsoft": "MSFT", "msft": "MSFT",
    "tesla": "TSLA", "tsla": "TSLA", "amazon": "AMZN", "amzn": "AMZN",
    "hcltech": "HCLTECH", "hcl": "HCLTECH",
}

# Words that look like tickers but aren't
_TICKER_STOPWORDS = {
    "AI", "IT", "US", "UK", "EU", "CEO", "CFO", "CTO", "ROE", "ROA",
    "EPS", "FCF", "IPO", "ESG", "PE", "PEG", "DCF", "SEC", "WHAT",
    "THE", "AND", "FOR", "FROM", "HOW", "WHY", "NOT", "ARE", "WAS",
}


def extract_companies(request: str) -> list[str]:
    """Extract company tickers from a user request."""
    companies = []

    # Check known company names
    req_lower = request.lower()
    for name, ticker in _KNOWN_COMPANIES.items():
        if name in req_lower and ticker not in companies:
            companies.append(ticker)

    # Check for uppercase ticker patterns
    for match in _TICKER_PATTERN.finditer(request):
        ticker = match.group(1)
        if ticker not in _TICKER_STOPWORDS and ticker not in companies:
            companies.append(ticker)

    return companies


# ---------------------------------------------------------------------------
# Retrieval query generation
# ---------------------------------------------------------------------------

_RETRIEVAL_TEMPLATES = {
    "company_analysis": [
        "{company} business overview revenue operations",
        "{company} financial performance growth",
        "{company} risk factors challenges",
        "{company} strategy growth opportunities",
    ],
    "risk_analysis": [
        "{company} risk factors regulatory compliance",
        "{company} cybersecurity threats vulnerabilities",
        "{company} competitive risks market threats",
        "{company} financial risks debt exposure",
    ],
    "investment_memo": [
        "{company} business overview revenue model",
        "{company} financial performance margins profitability",
        "{company} risk factors",
        "{company} growth strategy AI digital transformation",
        "{company} competitive position market share",
    ],
    "comparison": [
        "{company} financial performance revenue margins",
        "{company} growth strategy competitive position",
    ],
}


def _generate_queries(request_type: str, companies: list[str]) -> list[str]:
    """Generate retrieval queries for each company."""
    templates = _RETRIEVAL_TEMPLATES.get(request_type, ["{company} overview"])
    queries = []
    for company in companies:
        for tmpl in templates:
            queries.append(tmpl.format(company=company))
    return queries


# ===========================================================================
# Public API
# ===========================================================================

def create_plan(
    request: str,
    companies: list[str] = None,
    year: int = None,
) -> dict:
    """Create a structured research plan from a user request.

    Parameters
    ----------
    request : str
        Natural language research request.
    companies : list[str], optional
        Override auto-detected companies.
    year : int, optional
        Fiscal year filter.

    Returns
    -------
    dict (ResearchPlan-compatible)
    """
    request_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"

    # Step 1: Classify
    request_type = classify_request(request)

    # Step 2: Extract companies
    if companies is None:
        companies = extract_companies(request)
    if not companies:
        companies = []

    # Step 3: Select tools
    required_tools = get_tools_for_request_type(request_type)

    # Step 4: Generate retrieval queries
    retrieval_queries = _generate_queries(request_type, companies)

    plan = {
        "request_id": request_id,
        "objective": request,
        "request_type": request_type,
        "companies": companies,
        "required_tools": required_tools,
        "retrieval_queries": retrieval_queries,
        "output_format": "research_report" if request_type != "factual_query" else "brief_answer",
        "year": year,
    }

    logger.info("Plan created: type=%s, companies=%s, tools=%s",
                request_type, companies, required_tools)

    return plan
