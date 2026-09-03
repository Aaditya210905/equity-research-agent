"""
Plan Executor — Phase 5

Executes a research plan by calling each required tool and
collecting results into a unified evidence package.

The executor:
    - Iterates through the plan's required_tools
    - Calls each tool with appropriate inputs
    - Handles errors gracefully (skips failed tools)
    - Merges results into an evidence package
    - Records execution trace for auditability
"""

import logging
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Individual tool executors
# ---------------------------------------------------------------------------

def _exec_financial_engine(plan: dict) -> dict:
    """Run the financial computation engine for each company."""
    from financial_engine.engine import compute_all, financial_health_score

    results = {}
    for ticker in plan.get("companies", []):
        try:
            from services import data_service

            # Get financial statements from Yahoo Finance
            market_snap = data_service.get_market_snapshot(ticker)
            market = market_snap.model_dump() if hasattr(market_snap, "model_dump") else (market_snap or {})

            # Build normalized financial data from market data
            # Use the financial_statements key if data_service provides it
            fin_data = _build_financial_data(ticker, market)

            metrics = compute_all(fin_data)
            health = financial_health_score(fin_data)

            results[ticker] = {
                "metrics": metrics,
                "health": health,
            }
        except Exception as exc:
            logger.warning("Financial engine failed for %s: %s", ticker, exc)
            results[ticker] = {"metrics": {}, "health": {}, "error": str(exc)}

    return {"status": "success", "data": results}


def _build_financial_data(ticker: str, market_data: dict) -> dict:
    """Build normalized financial data dict for the engine.

    Tries to pull data from Yahoo Finance financial statements.
    Falls back to whatever market data is available.
    """
    import yfinance as yf

    data = {
        "income_statement": {},
        "balance_sheet": {},
        "cash_flow": {},
        "market_data": {},
    }

    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

        # Market data
        data["market_data"] = {
            "share_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "market_cap": info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
            "shares_outstanding": info.get("sharesOutstanding"),
            "dividend_per_share": info.get("dividendRate"),
        }

        # Income statement
        data["income_statement"] = {
            "revenue": info.get("totalRevenue"),
            "gross_profit": info.get("grossProfits"),
            "operating_income": info.get("operatingIncome") or info.get("ebitda"),
            "net_income": info.get("netIncomeToCommon"),
            "ebitda": info.get("ebitda"),
            "eps": info.get("trailingEps"),
        }

        # Balance sheet
        data["balance_sheet"] = {
            "total_assets": info.get("totalAssets"),
            "total_equity": info.get("bookValue") and info.get("sharesOutstanding") and (
                info["bookValue"] * info["sharesOutstanding"]
            ),
            "total_debt": info.get("totalDebt"),
            "current_assets": info.get("totalCurrentAssets"),
            "current_liabilities": info.get("totalCurrentLiabilities"),
            "cash_and_equivalents": info.get("totalCash"),
        }

        # Cash flow
        data["cash_flow"] = {
            "operating_cash_flow": info.get("operatingCashflow"),
            "capital_expenditure": None,  # Not directly in info
            "free_cash_flow": info.get("freeCashflow"),
        }

    except Exception as exc:
        logger.warning("Yahoo data fetch failed for %s: %s", ticker, exc)

    return data


def _exec_market_service(plan: dict) -> dict:
    """Fetch market data for each company."""
    results = {}
    for ticker in plan.get("companies", []):
        try:
            from services import data_service
            snap = data_service.get_market_snapshot(ticker)
            results[ticker] = snap.model_dump() if hasattr(snap, "model_dump") else (snap or {})
        except Exception as exc:
            logger.warning("Market service failed for %s: %s", ticker, exc)
            results[ticker] = {"error": str(exc)}
    return {"status": "success", "data": results}


def _exec_retriever(plan: dict) -> dict:
    """Run retrieval queries from the plan."""
    chunks = []
    queries = plan.get("retrieval_queries", [])

    if not queries:
        return {"status": "skipped", "data": {"chunks": []}}

    try:
        from retrieval.retriever import retrieve

        for query in queries[:6]:  # Limit to avoid excessive queries
            try:
                result = retrieve(
                    query=query,
                    company=plan["companies"][0] if plan.get("companies") else None,
                    top_k=5,
                )
                chunks.extend(result.get("hits", []))
            except Exception as exc:
                logger.warning("Retrieval failed for '%s': %s", query[:50], exc)

        # Deduplicate by chunk_id
        seen = set()
        unique = []
        for c in chunks:
            cid = c.get("chunk_id", id(c))
            if cid not in seen:
                seen.add(cid)
                unique.append(c)

        return {"status": "success", "data": {"chunks": unique}}

    except Exception as exc:
        logger.warning("Retriever unavailable: %s", exc)
        return {"status": "error", "data": {"chunks": []}, "error": str(exc)}


def _exec_news_service(plan: dict) -> dict:
    """Fetch recent news (lightweight — uses Yahoo Finance news)."""
    news = []
    for ticker in plan.get("companies", []):
        try:
            import yfinance as yf
            t = yf.Ticker(ticker)
            for item in (t.news or [])[:5]:
                news.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "date": item.get("providerPublishTime", ""),
                    "summary": item.get("title", ""),
                })
        except Exception as exc:
            logger.warning("News fetch failed for %s: %s", ticker, exc)
    return {"status": "success", "data": {"news": news}}


def _exec_peer_comparison(plan: dict) -> dict:
    """Run peer comparison across companies."""
    companies = plan.get("companies", [])
    if len(companies) < 2:
        return {"status": "skipped", "data": {}}

    try:
        from financial_engine.engine import compare_peers

        company_data = {}
        for ticker in companies:
            fin_data = _build_financial_data(ticker, {})
            company_data[ticker] = fin_data

        comparison = compare_peers(company_data)
        return {"status": "success", "data": comparison}

    except Exception as exc:
        logger.warning("Peer comparison failed: %s", exc)
        return {"status": "error", "data": {}, "error": str(exc)}


def _exec_health_scorer(plan: dict) -> dict:
    """Compute financial health scores."""
    # This is handled within financial_engine execution
    return {"status": "skipped", "data": {}}


# ---------------------------------------------------------------------------
# Tool dispatch map
# ---------------------------------------------------------------------------

_TOOL_EXECUTORS = {
    "financial_engine": _exec_financial_engine,
    "market_service": _exec_market_service,
    "retriever": _exec_retriever,
    "news_service": _exec_news_service,
    "peer_comparison": _exec_peer_comparison,
    "health_scorer": _exec_health_scorer,
}


# ===========================================================================
# Public API
# ===========================================================================

def execute_plan(plan: dict) -> dict:
    """Execute a research plan and collect all evidence.

    Parameters
    ----------
    plan : dict
        ResearchPlan from planner.create_plan().

    Returns
    -------
    dict
        {
            "evidence": {
                "company": {...},
                "market_data": {...},
                "financial_metrics": {...},
                "financial_health": {...},
                "growth_metrics": {},
                "retrieved_evidence": [...],
                "news": [...],
                "peer_comparison": {...},
            },
            "trace": {
                "request_id": "...",
                "tools_called": [...],
                "tool_results": [...],
                "duration_ms": 1234,
                ...
            }
        }
    """
    start = time.time()
    request_id = plan.get("request_id", "unknown")
    companies = plan.get("companies", [])
    primary = companies[0] if companies else "UNKNOWN"

    tools_called = []
    tool_results = []

    # Execute each tool
    for tool_name in plan.get("required_tools", []):
        executor = _TOOL_EXECUTORS.get(tool_name)
        if not executor:
            logger.warning("No executor for tool '%s'", tool_name)
            continue

        logger.info("[%s] Executing tool: %s", request_id, tool_name)
        t0 = time.time()

        try:
            result = executor(plan)
            dur = int((time.time() - t0) * 1000)
            tools_called.append(tool_name)
            tool_results.append({
                "tool": tool_name,
                "status": result.get("status", "success"),
                "duration_ms": dur,
                "error": result.get("error", ""),
            })
        except Exception as exc:
            dur = int((time.time() - t0) * 1000)
            result = {"status": "error", "data": {}}
            tool_results.append({
                "tool": tool_name, "status": "error",
                "duration_ms": dur, "error": str(exc),
            })
            logger.error("[%s] Tool '%s' crashed: %s", request_id, tool_name, exc)

    # --- Enrich company info from data_service ---
    try:
        from services import data_service
        company_data = data_service.get_company_overview(primary)
        company_info = {
            "name": company_data.name or primary,
            "ticker": primary,
            "sector": company_data.sector or "Unknown",
            "industry": company_data.industry or "Unknown",
        }
    except Exception:
        company_info = {"name": primary, "ticker": primary, "sector": "Unknown"}

    # --- Assemble evidence package ---
    evidence = {
        "company": company_info,
        "market_data": {},
        "financial_metrics": {},
        "financial_health": {},
        "growth_metrics": {},
        "retrieved_evidence": [],
        "news": [],
        "peer_comparison": {},
    }

    # Merge tool results into evidence (using cached results)
    cached_data = {}
    for tool_name in tools_called:
        executor_fn = _TOOL_EXECUTORS.get(tool_name)
        if not executor_fn:
            continue

        try:
            if tool_name not in cached_data:
                cached_data[tool_name] = executor_fn(plan)
            data = cached_data[tool_name].get("data", {})
        except Exception:
            continue

        if tool_name == "financial_engine" and primary in data:
            engine_data = data[primary]
            evidence["financial_metrics"] = engine_data.get("metrics", {})
            evidence["financial_health"] = engine_data.get("health", {})

        elif tool_name == "market_service" and primary in data:
            evidence["market_data"] = data[primary]

        elif tool_name == "retriever":
            evidence["retrieved_evidence"] = data.get("chunks", [])

        elif tool_name == "news_service":
            evidence["news"] = data.get("news", [])

        elif tool_name == "peer_comparison":
            evidence["peer_comparison"] = data

    elapsed = int((time.time() - start) * 1000)

    trace = {
        "request_id": request_id,
        "objective": plan.get("objective", ""),
        "plan": plan,
        "tools_called": tools_called,
        "tool_results": tool_results,
        "duration_ms": elapsed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    logger.info("[%s] Execution complete: %d tools in %dms",
                request_id, len(tools_called), elapsed)

    return {"evidence": evidence, "trace": trace}
