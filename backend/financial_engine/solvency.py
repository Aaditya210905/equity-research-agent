"""
Solvency Metrics — Phase 3

Measures a company's ability to meet long-term obligations.

Metrics:
    Debt-to-Equity     = Total Debt / Total Equity
    Debt-to-Assets     = Total Debt / Total Assets
    Interest Coverage  = Operating Income / Interest Expense
    Equity Multiplier  = Total Assets / Total Equity
"""

from financial_engine import safe_divide, get


def debt_to_equity(data: dict) -> dict:
    """Total Debt / Total Equity."""
    debt = get(data, "balance_sheet", "total_debt")
    eq = get(data, "balance_sheet", "total_equity")
    return safe_divide(debt, eq, "Total Debt / Total Equity", "x", 1,
                       {"total_debt": debt, "total_equity": eq})


def debt_to_assets(data: dict) -> dict:
    """Total Debt / Total Assets."""
    debt = get(data, "balance_sheet", "total_debt")
    ta = get(data, "balance_sheet", "total_assets")
    return safe_divide(debt, ta, "Total Debt / Total Assets", "x", 1,
                       {"total_debt": debt, "total_assets": ta})


def interest_coverage(data: dict) -> dict:
    """Operating Income / Interest Expense."""
    oi = get(data, "income_statement", "operating_income")
    ie = get(data, "income_statement", "interest_expense")
    return safe_divide(oi, ie, "Operating Income / Interest Expense", "x", 1,
                       {"operating_income": oi, "interest_expense": ie})


def equity_multiplier(data: dict) -> dict:
    """Total Assets / Total Equity."""
    ta = get(data, "balance_sheet", "total_assets")
    eq = get(data, "balance_sheet", "total_equity")
    return safe_divide(ta, eq, "Total Assets / Total Equity", "x", 1,
                       {"total_assets": ta, "total_equity": eq})


def compute_all(data: dict) -> dict:
    """Compute all solvency metrics."""
    return {
        "debt_to_equity": debt_to_equity(data),
        "debt_to_assets": debt_to_assets(data),
        "interest_coverage": interest_coverage(data),
        "equity_multiplier": equity_multiplier(data),
    }
