"""
Growth Metrics — Phase 3

Measures year-over-year and multi-year growth.

Metrics:
    Revenue Growth      = (Current − Previous) / Previous × 100
    Net Income Growth   = (Current − Previous) / Previous × 100
    EPS Growth          = (Current − Previous) / Previous × 100
    EBITDA Growth       = (Current − Previous) / Previous × 100
    CAGR                = (End / Start)^(1/years) − 1

All growth functions accept two years of data (current, previous).
"""

from financial_engine import metric, safe_divide, get


def _yoy_growth(current_val, previous_val, label: str) -> dict:
    """Year-over-year growth: (Current − Previous) / |Previous| × 100."""
    formula = f"({label} Current − {label} Previous) / |{label} Previous| × 100"
    inputs = {"current": current_val, "previous": previous_val}

    if current_val is None or previous_val is None:
        return metric(None, "%", formula, "missing_data", inputs)
    if previous_val == 0:
        return metric(None, "%", formula, "division_by_zero", inputs)

    value = ((current_val - previous_val) / abs(previous_val)) * 100
    return metric(value, "%", formula, "computed", inputs)


def revenue_growth(current: dict, previous: dict) -> dict:
    """Revenue growth YoY."""
    cur = get(current, "income_statement", "revenue")
    prev = get(previous, "income_statement", "revenue")
    return _yoy_growth(cur, prev, "Revenue")


def net_income_growth(current: dict, previous: dict) -> dict:
    """Net income growth YoY."""
    cur = get(current, "income_statement", "net_income")
    prev = get(previous, "income_statement", "net_income")
    return _yoy_growth(cur, prev, "Net Income")


def eps_growth(current: dict, previous: dict) -> dict:
    """EPS growth YoY."""
    cur = get(current, "income_statement", "eps")
    prev = get(previous, "income_statement", "eps")
    return _yoy_growth(cur, prev, "EPS")


def ebitda_growth(current: dict, previous: dict) -> dict:
    """EBITDA growth YoY."""
    cur = get(current, "income_statement", "ebitda")
    prev = get(previous, "income_statement", "ebitda")
    return _yoy_growth(cur, prev, "EBITDA")


def operating_income_growth(current: dict, previous: dict) -> dict:
    """Operating income growth YoY."""
    cur = get(current, "income_statement", "operating_income")
    prev = get(previous, "income_statement", "operating_income")
    return _yoy_growth(cur, prev, "Operating Income")


def cagr(start_value: float, end_value: float, years: int) -> dict:
    """Compound Annual Growth Rate.

    CAGR = (End / Start)^(1/years) − 1
    """
    formula = "(End Value / Start Value)^(1/Years) − 1"
    inputs = {"start_value": start_value, "end_value": end_value, "years": years}

    if start_value is None or end_value is None or years is None:
        return metric(None, "%", formula, "missing_data", inputs)
    if years <= 0:
        return metric(None, "%", formula, "missing_data", inputs)
    if start_value <= 0:
        return metric(None, "%", formula, "division_by_zero", inputs)

    value = ((end_value / start_value) ** (1 / years) - 1) * 100
    return metric(value, "%", formula, "computed", inputs)


def compute_all(current: dict, previous: dict) -> dict:
    """Compute all growth metrics (requires two years of data)."""
    return {
        "revenue_growth": revenue_growth(current, previous),
        "net_income_growth": net_income_growth(current, previous),
        "eps_growth": eps_growth(current, previous),
        "ebitda_growth": ebitda_growth(current, previous),
        "operating_income_growth": operating_income_growth(current, previous),
    }
