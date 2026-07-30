"""
Financial Engine — Phase 3

Pure Python financial computation engine.
LLMs explain numbers. Python computes numbers.

All modules use these helpers for standardized output.
"""


def metric(
    value,
    unit: str,
    formula: str,
    status: str = "computed",
    inputs: dict = None,
) -> dict:
    """Create a standardized MetricResult.

    Every metric in the engine returns this structure:
        {
            "value": 31.25,
            "unit": "%",
            "formula": "Net Income / Total Equity × 100",
            "status": "computed",
            "inputs": {"net_income": 25000, "total_equity": 80000},
        }

    Status values:
        "computed"        — successfully calculated
        "missing_data"    — one or more required inputs were None
        "division_by_zero" — denominator was zero
        "anomaly"         — value outside expected range (flagged for review)
    """
    if value is not None:
        value = round(float(value), 4)
    return {
        "value": value,
        "unit": unit,
        "formula": formula,
        "status": status,
        "inputs": inputs or {},
    }


def safe_divide(
    numerator,
    denominator,
    formula: str,
    unit: str = "%",
    multiply: float = 100.0,
    inputs: dict = None,
) -> dict:
    """Safely divide two values, handling None and zero.

    Parameters
    ----------
    numerator, denominator : float or None
    formula : str — human-readable formula
    unit : str — "%", "x", "$", etc.
    multiply : float — multiply result by this (100 for percentages, 1 for ratios)
    inputs : dict — input values for auditability
    """
    if numerator is None or denominator is None:
        return metric(None, unit, formula, "missing_data", inputs)
    if denominator == 0:
        return metric(None, unit, formula, "division_by_zero", inputs)
    value = (numerator / denominator) * multiply
    return metric(value, unit, formula, "computed", inputs)


def get(data: dict, *keys):
    """Safely extract a value from nested dict.

    Usage:
        get(data, "income_statement", "revenue")
        get(data, "revenue")  # flat dict
    """
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current
