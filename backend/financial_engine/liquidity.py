"""
Liquidity Metrics — Phase 3

Measures a company's ability to meet short-term obligations.

Metrics:
    Current Ratio    = Current Assets / Current Liabilities
    Quick Ratio      = (Current Assets − Inventory) / Current Liabilities
    Cash Ratio       = Cash & Equivalents / Current Liabilities
"""

from financial_engine import safe_divide, get, metric


def current_ratio(data: dict) -> dict:
    """Current Assets / Current Liabilities."""
    ca = get(data, "balance_sheet", "current_assets")
    cl = get(data, "balance_sheet", "current_liabilities")
    return safe_divide(ca, cl, "Current Assets / Current Liabilities", "x", 1,
                       {"current_assets": ca, "current_liabilities": cl})


def quick_ratio(data: dict) -> dict:
    """(Current Assets − Inventory) / Current Liabilities."""
    ca = get(data, "balance_sheet", "current_assets")
    inv = get(data, "balance_sheet", "inventory") or 0
    cl = get(data, "balance_sheet", "current_liabilities")

    if ca is None or cl is None:
        return metric(None, "x", "(Current Assets − Inventory) / Current Liabilities", "missing_data")
    if cl == 0:
        return metric(None, "x", "(Current Assets − Inventory) / Current Liabilities", "division_by_zero")

    value = (ca - inv) / cl
    return metric(value, "x", "(Current Assets − Inventory) / Current Liabilities", "computed",
                  {"current_assets": ca, "inventory": inv, "current_liabilities": cl})


def cash_ratio(data: dict) -> dict:
    """Cash & Equivalents / Current Liabilities."""
    cash = get(data, "balance_sheet", "cash_and_equivalents")
    cl = get(data, "balance_sheet", "current_liabilities")
    return safe_divide(cash, cl, "Cash & Equivalents / Current Liabilities", "x", 1,
                       {"cash_and_equivalents": cash, "current_liabilities": cl})


def compute_all(data: dict) -> dict:
    """Compute all liquidity metrics."""
    return {
        "current_ratio": current_ratio(data),
        "quick_ratio": quick_ratio(data),
        "cash_ratio": cash_ratio(data),
    }
