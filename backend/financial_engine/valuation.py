"""
Valuation Metrics — Phase 3

Market-based valuation ratios.

Metrics:
    P/E Ratio           = Share Price / EPS
    PEG Ratio           = P/E / EPS Growth Rate
    EV/EBITDA           = Enterprise Value / EBITDA
    Price-to-Book       = Market Cap / Total Equity
    Enterprise Value    = Market Cap + Total Debt − Cash
    Dividend Yield      = Dividend Per Share / Share Price × 100
    Price-to-Sales      = Market Cap / Revenue
"""

from financial_engine import metric, safe_divide, get


def pe_ratio(data: dict) -> dict:
    """Share Price / EPS."""
    price = get(data, "market_data", "share_price")
    eps = get(data, "income_statement", "eps")
    return safe_divide(price, eps, "Share Price / EPS", "x", 1,
                       {"share_price": price, "eps": eps})


def peg_ratio(data: dict, eps_growth_pct: float = None) -> dict:
    """P/E Ratio / EPS Growth Rate.

    eps_growth_pct should be a percentage (e.g. 15.0 for 15%).
    """
    price = get(data, "market_data", "share_price")
    eps = get(data, "income_statement", "eps")

    if price is None or eps is None or eps == 0:
        return metric(None, "x", "P/E / EPS Growth Rate", "missing_data")

    pe = price / eps

    if eps_growth_pct is None or eps_growth_pct == 0:
        return metric(None, "x", "P/E / EPS Growth Rate", "missing_data",
                      {"pe": round(pe, 2), "eps_growth_pct": eps_growth_pct})

    value = pe / eps_growth_pct
    return metric(value, "x", "P/E / EPS Growth Rate", "computed",
                  {"pe": round(pe, 2), "eps_growth_pct": eps_growth_pct})


def ev_to_ebitda(data: dict) -> dict:
    """Enterprise Value / EBITDA."""
    # Calculate EV if not provided
    ev = get(data, "market_data", "enterprise_value")
    if ev is None:
        mcap = get(data, "market_data", "market_cap")
        debt = get(data, "balance_sheet", "total_debt")
        cash = get(data, "balance_sheet", "cash_and_equivalents")
        if mcap is not None:
            ev = mcap + (debt or 0) - (cash or 0)

    ebitda = get(data, "income_statement", "ebitda")
    return safe_divide(ev, ebitda, "Enterprise Value / EBITDA", "x", 1,
                       {"enterprise_value": ev, "ebitda": ebitda})


def price_to_book(data: dict) -> dict:
    """Market Cap / Total Equity."""
    mcap = get(data, "market_data", "market_cap")
    eq = get(data, "balance_sheet", "total_equity")
    return safe_divide(mcap, eq, "Market Cap / Total Equity", "x", 1,
                       {"market_cap": mcap, "total_equity": eq})


def enterprise_value(data: dict) -> dict:
    """Market Cap + Total Debt − Cash & Equivalents."""
    mcap = get(data, "market_data", "market_cap")
    debt = get(data, "balance_sheet", "total_debt")
    cash = get(data, "balance_sheet", "cash_and_equivalents")

    if mcap is None:
        return metric(None, "$", "Market Cap + Total Debt − Cash", "missing_data")

    value = mcap + (debt or 0) - (cash or 0)
    return metric(value, "$", "Market Cap + Total Debt − Cash", "computed",
                  {"market_cap": mcap, "total_debt": debt or 0,
                   "cash_and_equivalents": cash or 0})


def dividend_yield(data: dict) -> dict:
    """Dividend Per Share / Share Price × 100."""
    dps = get(data, "market_data", "dividend_per_share")
    price = get(data, "market_data", "share_price")
    return safe_divide(dps, price, "Dividend Per Share / Share Price × 100", "%", 100,
                       {"dividend_per_share": dps, "share_price": price})


def price_to_sales(data: dict) -> dict:
    """Market Cap / Revenue."""
    mcap = get(data, "market_data", "market_cap")
    rev = get(data, "income_statement", "revenue")
    return safe_divide(mcap, rev, "Market Cap / Revenue", "x", 1,
                       {"market_cap": mcap, "revenue": rev})


def compute_all(data: dict) -> dict:
    """Compute all valuation metrics."""
    return {
        "pe_ratio": pe_ratio(data),
        "ev_to_ebitda": ev_to_ebitda(data),
        "price_to_book": price_to_book(data),
        "enterprise_value": enterprise_value(data),
        "dividend_yield": dividend_yield(data),
        "price_to_sales": price_to_sales(data),
    }
