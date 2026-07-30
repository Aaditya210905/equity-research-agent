"""
Efficiency Metrics — Phase 3

Measures how effectively a company uses its assets and working capital.

Metrics:
    Asset Turnover           = Revenue / Total Assets
    Inventory Turnover       = COGS / Inventory
    Receivables Turnover     = Revenue / Accounts Receivable
    Working Capital Turnover = Revenue / Working Capital
    Payables Turnover        = COGS / Accounts Payable
"""

from financial_engine import metric, safe_divide, get


def asset_turnover(data: dict) -> dict:
    """Revenue / Total Assets."""
    rev = get(data, "income_statement", "revenue")
    ta = get(data, "balance_sheet", "total_assets")
    return safe_divide(rev, ta, "Revenue / Total Assets", "x", 1,
                       {"revenue": rev, "total_assets": ta})


def inventory_turnover(data: dict) -> dict:
    """Cost of Revenue / Inventory."""
    cogs = get(data, "income_statement", "cost_of_revenue")
    inv = get(data, "balance_sheet", "inventory")
    return safe_divide(cogs, inv, "Cost of Revenue / Inventory", "x", 1,
                       {"cost_of_revenue": cogs, "inventory": inv})


def receivables_turnover(data: dict) -> dict:
    """Revenue / Accounts Receivable."""
    rev = get(data, "income_statement", "revenue")
    ar = get(data, "balance_sheet", "accounts_receivable")
    return safe_divide(rev, ar, "Revenue / Accounts Receivable", "x", 1,
                       {"revenue": rev, "accounts_receivable": ar})


def working_capital_turnover(data: dict) -> dict:
    """Revenue / Working Capital (Current Assets − Current Liabilities)."""
    rev = get(data, "income_statement", "revenue")
    ca = get(data, "balance_sheet", "current_assets")
    cl = get(data, "balance_sheet", "current_liabilities")

    if rev is None or ca is None or cl is None:
        return metric(None, "x", "Revenue / (Current Assets − Current Liabilities)", "missing_data")

    wc = ca - cl
    if wc == 0:
        return metric(None, "x", "Revenue / (Current Assets − Current Liabilities)", "division_by_zero",
                      {"revenue": rev, "working_capital": wc})

    value = rev / wc
    return metric(value, "x", "Revenue / (Current Assets − Current Liabilities)", "computed",
                  {"revenue": rev, "working_capital": round(wc, 2)})


def payables_turnover(data: dict) -> dict:
    """Cost of Revenue / Accounts Payable."""
    cogs = get(data, "income_statement", "cost_of_revenue")
    ap = get(data, "balance_sheet", "accounts_payable")
    return safe_divide(cogs, ap, "Cost of Revenue / Accounts Payable", "x", 1,
                       {"cost_of_revenue": cogs, "accounts_payable": ap})


def compute_all(data: dict) -> dict:
    """Compute all efficiency metrics."""
    return {
        "asset_turnover": asset_turnover(data),
        "inventory_turnover": inventory_turnover(data),
        "receivables_turnover": receivables_turnover(data),
        "working_capital_turnover": working_capital_turnover(data),
        "payables_turnover": payables_turnover(data),
    }
