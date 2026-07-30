"""
Cash Flow Metrics — Phase 3

Measures cash generation and capital allocation.

Metrics:
    Free Cash Flow      = Operating Cash Flow − CapEx
    OCF Ratio           = Operating Cash Flow / Net Income
    CapEx to Revenue    = Capital Expenditure / Revenue × 100
    Cash Conversion     = Free Cash Flow / Net Income × 100
    FCF Yield           = Free Cash Flow / Market Cap × 100
"""

from financial_engine import metric, safe_divide, get


def free_cash_flow(data: dict) -> dict:
    """Operating Cash Flow − Capital Expenditure."""
    ocf = get(data, "cash_flow", "operating_cash_flow")
    capex = get(data, "cash_flow", "capital_expenditure")

    if ocf is None:
        return metric(None, "$", "Operating Cash Flow − CapEx", "missing_data",
                      {"operating_cash_flow": ocf, "capital_expenditure": capex})

    # CapEx is often reported as negative; use absolute value
    capex_abs = abs(capex) if capex is not None else 0
    value = ocf - capex_abs
    return metric(value, "$", "Operating Cash Flow − CapEx", "computed",
                  {"operating_cash_flow": ocf, "capital_expenditure": capex_abs})


def ocf_ratio(data: dict) -> dict:
    """Operating Cash Flow / Net Income."""
    ocf = get(data, "cash_flow", "operating_cash_flow")
    ni = get(data, "income_statement", "net_income")
    return safe_divide(ocf, ni, "Operating Cash Flow / Net Income", "x", 1,
                       {"operating_cash_flow": ocf, "net_income": ni})


def capex_to_revenue(data: dict) -> dict:
    """Capital Expenditure / Revenue × 100."""
    capex = get(data, "cash_flow", "capital_expenditure")
    rev = get(data, "income_statement", "revenue")

    if capex is not None:
        capex = abs(capex)

    return safe_divide(capex, rev, "|CapEx| / Revenue × 100", "%", 100,
                       {"capital_expenditure": capex, "revenue": rev})


def cash_conversion(data: dict) -> dict:
    """Free Cash Flow / Net Income × 100."""
    ocf = get(data, "cash_flow", "operating_cash_flow")
    capex = get(data, "cash_flow", "capital_expenditure")
    ni = get(data, "income_statement", "net_income")

    if ocf is None or ni is None:
        return metric(None, "%", "FCF / Net Income × 100", "missing_data")
    if ni == 0:
        return metric(None, "%", "FCF / Net Income × 100", "division_by_zero")

    capex_abs = abs(capex) if capex is not None else 0
    fcf = ocf - capex_abs
    value = (fcf / ni) * 100
    return metric(value, "%", "FCF / Net Income × 100", "computed",
                  {"fcf": round(fcf, 2), "net_income": ni})


def fcf_yield(data: dict) -> dict:
    """Free Cash Flow / Market Cap × 100."""
    ocf = get(data, "cash_flow", "operating_cash_flow")
    capex = get(data, "cash_flow", "capital_expenditure")
    mcap = get(data, "market_data", "market_cap")

    if ocf is None or mcap is None:
        return metric(None, "%", "FCF / Market Cap × 100", "missing_data")
    if mcap == 0:
        return metric(None, "%", "FCF / Market Cap × 100", "division_by_zero")

    capex_abs = abs(capex) if capex is not None else 0
    fcf = ocf - capex_abs
    value = (fcf / mcap) * 100
    return metric(value, "%", "FCF / Market Cap × 100", "computed",
                  {"fcf": round(fcf, 2), "market_cap": mcap})


def compute_all(data: dict) -> dict:
    """Compute all cash flow metrics."""
    return {
        "free_cash_flow": free_cash_flow(data),
        "ocf_ratio": ocf_ratio(data),
        "capex_to_revenue": capex_to_revenue(data),
        "cash_conversion": cash_conversion(data),
        "fcf_yield": fcf_yield(data),
    }
