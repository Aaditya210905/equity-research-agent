"""
Profitability Metrics — Phase 3

Measures how effectively a company converts revenue into profit.

Metrics:
    Gross Margin         = Gross Profit / Revenue × 100
    Operating Margin     = Operating Income / Revenue × 100
    Net Margin           = Net Income / Revenue × 100
    EBITDA Margin        = EBITDA / Revenue × 100
    ROE                  = Net Income / Total Equity × 100
    ROA                  = Net Income / Total Assets × 100
    ROIC                 = NOPAT / Invested Capital × 100
"""

from financial_engine import metric, safe_divide, get


def gross_margin(data: dict) -> dict:
    """Gross Profit / Revenue × 100."""
    gp = get(data, "income_statement", "gross_profit")
    rev = get(data, "income_statement", "revenue")
    return safe_divide(gp, rev, "Gross Profit / Revenue × 100", "%", 100,
                       {"gross_profit": gp, "revenue": rev})


def operating_margin(data: dict) -> dict:
    """Operating Income / Revenue × 100."""
    oi = get(data, "income_statement", "operating_income")
    rev = get(data, "income_statement", "revenue")
    return safe_divide(oi, rev, "Operating Income / Revenue × 100", "%", 100,
                       {"operating_income": oi, "revenue": rev})


def net_margin(data: dict) -> dict:
    """Net Income / Revenue × 100."""
    ni = get(data, "income_statement", "net_income")
    rev = get(data, "income_statement", "revenue")
    return safe_divide(ni, rev, "Net Income / Revenue × 100", "%", 100,
                       {"net_income": ni, "revenue": rev})


def ebitda_margin(data: dict) -> dict:
    """EBITDA / Revenue × 100."""
    ebitda = get(data, "income_statement", "ebitda")
    rev = get(data, "income_statement", "revenue")
    return safe_divide(ebitda, rev, "EBITDA / Revenue × 100", "%", 100,
                       {"ebitda": ebitda, "revenue": rev})


def roe(data: dict) -> dict:
    """Net Income / Total Equity × 100."""
    ni = get(data, "income_statement", "net_income")
    eq = get(data, "balance_sheet", "total_equity")
    return safe_divide(ni, eq, "Net Income / Total Equity × 100", "%", 100,
                       {"net_income": ni, "total_equity": eq})


def roa(data: dict) -> dict:
    """Net Income / Total Assets × 100."""
    ni = get(data, "income_statement", "net_income")
    ta = get(data, "balance_sheet", "total_assets")
    return safe_divide(ni, ta, "Net Income / Total Assets × 100", "%", 100,
                       {"net_income": ni, "total_assets": ta})


def roic(data: dict) -> dict:
    """NOPAT / Invested Capital × 100.

    NOPAT = Operating Income × (1 − Tax Rate)
    Tax Rate = Tax Provision / Pre-Tax Income (estimated)
    Invested Capital = Total Equity + Total Debt − Cash
    """
    oi = get(data, "income_statement", "operating_income")
    ni = get(data, "income_statement", "net_income")
    pretax = get(data, "income_statement", "pretax_income")
    tax = get(data, "income_statement", "tax_provision")
    eq = get(data, "balance_sheet", "total_equity")
    debt = get(data, "balance_sheet", "total_debt")
    cash = get(data, "balance_sheet", "cash_and_equivalents")

    if oi is None:
        return metric(None, "%", "NOPAT / Invested Capital × 100", "missing_data")

    # Estimate tax rate
    if pretax and tax and pretax != 0:
        tax_rate = tax / pretax
    elif ni is not None and oi != 0:
        tax_rate = max(0, 1 - (ni / oi))
    else:
        tax_rate = 0.25  # fallback assumption

    nopat = oi * (1 - tax_rate)

    # Invested capital
    if eq is None or debt is None:
        return metric(None, "%", "NOPAT / Invested Capital × 100", "missing_data")

    invested = eq + debt - (cash or 0)

    if invested == 0:
        return metric(None, "%", "NOPAT / Invested Capital × 100", "division_by_zero")

    value = (nopat / invested) * 100
    return metric(value, "%", "NOPAT / Invested Capital × 100", "computed",
                  {"nopat": round(nopat, 2), "invested_capital": round(invested, 2),
                   "tax_rate": round(tax_rate, 4)})


def compute_all(data: dict) -> dict:
    """Compute all profitability metrics."""
    return {
        "gross_margin": gross_margin(data),
        "operating_margin": operating_margin(data),
        "net_margin": net_margin(data),
        "ebitda_margin": ebitda_margin(data),
        "roe": roe(data),
        "roa": roa(data),
        "roic": roic(data),
    }
