"""
Financial Computation Engine — Phase 3

Pure Python financial analysis engine.
Orchestrates all metric modules and provides:
    - Single-year analysis
    - Multi-year trend analysis
    - Peer comparison
    - Financial health scoring

The engine never interacts with LLMs, databases, or documents.
It is a deterministic computation module.

Usage:
    from financial_engine.engine import compute_all, compute_growth, compare_peers

    metrics = compute_all(financial_data)
    growth  = compute_growth(current_year, previous_year)
    comparison = compare_peers({"TCS": tcs_data, "INFY": infy_data})
"""

import logging

from financial_engine import profitability, liquidity, solvency, growth, cashflow, efficiency, valuation

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Formula Registry — documents every metric for auditability
# ---------------------------------------------------------------------------
FORMULA_REGISTRY = {
    # Profitability
    "gross_margin":         {"formula": "Gross Profit / Revenue × 100",                   "unit": "%",  "category": "profitability"},
    "operating_margin":     {"formula": "Operating Income / Revenue × 100",               "unit": "%",  "category": "profitability"},
    "net_margin":           {"formula": "Net Income / Revenue × 100",                     "unit": "%",  "category": "profitability"},
    "ebitda_margin":        {"formula": "EBITDA / Revenue × 100",                         "unit": "%",  "category": "profitability"},
    "roe":                  {"formula": "Net Income / Total Equity × 100",                "unit": "%",  "category": "profitability"},
    "roa":                  {"formula": "Net Income / Total Assets × 100",                "unit": "%",  "category": "profitability"},
    "roic":                 {"formula": "NOPAT / Invested Capital × 100",                 "unit": "%",  "category": "profitability"},
    # Liquidity
    "current_ratio":        {"formula": "Current Assets / Current Liabilities",           "unit": "x",  "category": "liquidity"},
    "quick_ratio":          {"formula": "(Current Assets − Inventory) / Current Liabilities", "unit": "x", "category": "liquidity"},
    "cash_ratio":           {"formula": "Cash & Equivalents / Current Liabilities",       "unit": "x",  "category": "liquidity"},
    # Solvency
    "debt_to_equity":       {"formula": "Total Debt / Total Equity",                      "unit": "x",  "category": "solvency"},
    "debt_to_assets":       {"formula": "Total Debt / Total Assets",                      "unit": "x",  "category": "solvency"},
    "interest_coverage":    {"formula": "Operating Income / Interest Expense",            "unit": "x",  "category": "solvency"},
    "equity_multiplier":    {"formula": "Total Assets / Total Equity",                    "unit": "x",  "category": "solvency"},
    # Growth
    "revenue_growth":       {"formula": "(Revenue Cur − Revenue Prev) / |Revenue Prev| × 100", "unit": "%", "category": "growth"},
    "net_income_growth":    {"formula": "(NI Cur − NI Prev) / |NI Prev| × 100",          "unit": "%",  "category": "growth"},
    "eps_growth":           {"formula": "(EPS Cur − EPS Prev) / |EPS Prev| × 100",       "unit": "%",  "category": "growth"},
    "ebitda_growth":        {"formula": "(EBITDA Cur − EBITDA Prev) / |EBITDA Prev| × 100", "unit": "%", "category": "growth"},
    "cagr":                 {"formula": "(End / Start)^(1/Years) − 1",                   "unit": "%",  "category": "growth"},
    # Cash Flow
    "free_cash_flow":       {"formula": "Operating Cash Flow − CapEx",                    "unit": "$",  "category": "cash_flow"},
    "ocf_ratio":            {"formula": "Operating Cash Flow / Net Income",               "unit": "x",  "category": "cash_flow"},
    "capex_to_revenue":     {"formula": "|CapEx| / Revenue × 100",                        "unit": "%",  "category": "cash_flow"},
    "cash_conversion":      {"formula": "FCF / Net Income × 100",                         "unit": "%",  "category": "cash_flow"},
    "fcf_yield":            {"formula": "FCF / Market Cap × 100",                          "unit": "%",  "category": "cash_flow"},
    # Efficiency
    "asset_turnover":       {"formula": "Revenue / Total Assets",                         "unit": "x",  "category": "efficiency"},
    "inventory_turnover":   {"formula": "Cost of Revenue / Inventory",                    "unit": "x",  "category": "efficiency"},
    "receivables_turnover": {"formula": "Revenue / Accounts Receivable",                  "unit": "x",  "category": "efficiency"},
    "working_capital_turnover": {"formula": "Revenue / (Current Assets − Current Liabilities)", "unit": "x", "category": "efficiency"},
    "payables_turnover":    {"formula": "Cost of Revenue / Accounts Payable",             "unit": "x",  "category": "efficiency"},
    # Valuation
    "pe_ratio":             {"formula": "Share Price / EPS",                               "unit": "x",  "category": "valuation"},
    "peg_ratio":            {"formula": "P/E / EPS Growth Rate",                           "unit": "x",  "category": "valuation"},
    "ev_to_ebitda":         {"formula": "Enterprise Value / EBITDA",                       "unit": "x",  "category": "valuation"},
    "price_to_book":        {"formula": "Market Cap / Total Equity",                       "unit": "x",  "category": "valuation"},
    "enterprise_value":     {"formula": "Market Cap + Total Debt − Cash",                  "unit": "$",  "category": "valuation"},
    "dividend_yield":       {"formula": "DPS / Share Price × 100",                         "unit": "%",  "category": "valuation"},
    "price_to_sales":       {"formula": "Market Cap / Revenue",                            "unit": "x",  "category": "valuation"},
}


# ===========================================================================
# Single-year analysis
# ===========================================================================

def compute_all(data: dict) -> dict:
    """Compute all single-year financial metrics.

    Parameters
    ----------
    data : dict
        Normalized financial data with keys:
        income_statement, balance_sheet, cash_flow, market_data.

    Returns
    -------
    dict
        {
            "profitability": {...},
            "liquidity": {...},
            "solvency": {...},
            "cash_flow": {...},
            "efficiency": {...},
            "valuation": {...},
            "summary": {"computed": N, "missing": M, "total": T},
        }
    """
    results = {
        "profitability": profitability.compute_all(data),
        "liquidity": liquidity.compute_all(data),
        "solvency": solvency.compute_all(data),
        "cash_flow": cashflow.compute_all(data),
        "efficiency": efficiency.compute_all(data),
        "valuation": valuation.compute_all(data),
    }

    # Summary statistics
    computed = 0
    missing = 0
    errors = 0
    for category in results.values():
        for m in category.values():
            status = m.get("status", "")
            if status == "computed":
                computed += 1
            elif status == "missing_data":
                missing += 1
            else:
                errors += 1

    results["summary"] = {
        "computed": computed,
        "missing": missing,
        "errors": errors,
        "total": computed + missing + errors,
    }

    return results


# ===========================================================================
# Multi-year analysis
# ===========================================================================

def compute_growth(current_year: dict, previous_year: dict) -> dict:
    """Compute year-over-year growth metrics.

    Parameters
    ----------
    current_year, previous_year : dict
        Full financial data dicts for each year.

    Returns
    -------
    dict
        Growth metrics (revenue_growth, net_income_growth, etc.)
    """
    return growth.compute_all(current_year, previous_year)


def compute_trends(years_data: list[dict]) -> dict:
    """Compute multi-year trend analysis.

    Parameters
    ----------
    years_data : list[dict]
        Financial data for multiple years, ordered chronologically
        (oldest first). Each dict should have a "year" key.

    Returns
    -------
    dict
        {
            "years": [2023, 2024, 2025],
            "revenue": [80000, 90000, 100000],
            "revenue_cagr": {...},
            "net_income": [18000, 22000, 25000],
            "net_income_cagr": {...},
            "yoy_growth": [...],
        }
    """
    if len(years_data) < 2:
        return {"error": "At least 2 years of data required"}

    from financial_engine import get

    years = [d.get("year", i) for i, d in enumerate(years_data)]
    revenues = [get(d, "income_statement", "revenue") for d in years_data]
    net_incomes = [get(d, "income_statement", "net_income") for d in years_data]
    eps_values = [get(d, "income_statement", "eps") for d in years_data]

    result = {
        "years": years,
        "revenue": revenues,
        "net_income": net_incomes,
        "eps": eps_values,
    }

    # CAGR calculations
    n_years = len(years_data) - 1
    if revenues[0] and revenues[-1]:
        result["revenue_cagr"] = growth.cagr(revenues[0], revenues[-1], n_years)
    if net_incomes[0] and net_incomes[-1] and net_incomes[0] > 0:
        result["net_income_cagr"] = growth.cagr(net_incomes[0], net_incomes[-1], n_years)

    # Year-over-year growth series
    yoy = []
    for i in range(1, len(years_data)):
        yoy.append(growth.compute_all(years_data[i], years_data[i - 1]))
    result["yoy_growth"] = yoy

    return result


# ===========================================================================
# Peer comparison
# ===========================================================================

def compare_peers(companies: dict[str, dict]) -> dict:
    """Compare financial metrics across multiple companies.

    Parameters
    ----------
    companies : dict[str, dict]
        {company_name: financial_data_dict}

    Returns
    -------
    dict
        {
            "companies": ["TCS", "INFY", "HCLTECH"],
            "metrics": {
                "roe": {"TCS": {...}, "INFY": {...}, "HCLTECH": {...}},
                "net_margin": {"TCS": {...}, "INFY": {...}, ...},
                ...
            },
            "rankings": {
                "roe": ["TCS", "INFY", "HCLTECH"],
                ...
            }
        }
    """
    company_names = list(companies.keys())
    all_metrics: dict[str, dict] = {}

    # Compute metrics for each company
    company_results = {}
    for name, data in companies.items():
        company_results[name] = compute_all(data)

    # Flatten into per-metric comparison
    categories = ["profitability", "liquidity", "solvency", "cash_flow", "efficiency", "valuation"]
    for category in categories:
        for name in company_names:
            cat_metrics = company_results[name].get(category, {})
            for metric_name, metric_val in cat_metrics.items():
                if metric_name not in all_metrics:
                    all_metrics[metric_name] = {}
                all_metrics[metric_name][name] = metric_val

    # Rankings (sort by value descending for each metric)
    rankings = {}
    for metric_name, company_vals in all_metrics.items():
        ranked = []
        for name, m in company_vals.items():
            val = m.get("value")
            if val is not None:
                ranked.append((name, val))
        # Higher is generally better (except debt ratios)
        reverse = metric_name not in ("debt_to_equity", "debt_to_assets", "pe_ratio", "ev_to_ebitda")
        ranked.sort(key=lambda x: x[1], reverse=reverse)
        rankings[metric_name] = [name for name, _ in ranked]

    return {
        "companies": company_names,
        "metrics": all_metrics,
        "rankings": rankings,
    }


# ===========================================================================
# Financial Health Score
# ===========================================================================

def financial_health_score(data: dict) -> dict:
    """Compute a transparent financial health score.

    Scoring is rule-based and fully auditable (no LLM involvement).

    Categories (each 0–100):
        Profitability:  based on margins and returns
        Liquidity:      based on current/quick ratios
        Solvency:       based on debt ratios and interest coverage
        Cash Flow:      based on FCF yield and cash conversion

    Returns
    -------
    dict
        {
            "overall": 72.5,
            "profitability_score": 85.0,
            "liquidity_score": 70.0,
            "solvency_score": 65.0,
            "cash_flow_score": 70.0,
            "breakdown": {...},
        }
    """
    metrics = compute_all(data)

    def _val(category: str, name: str):
        return (metrics.get(category, {}).get(name, {}).get("value"))

    # --- Profitability score (0–100) ---
    prof_signals = []

    nm = _val("profitability", "net_margin")
    if nm is not None:
        prof_signals.append(min(100, max(0, nm * 3)))  # 33% margin → 100

    roe_val = _val("profitability", "roe")
    if roe_val is not None:
        prof_signals.append(min(100, max(0, roe_val * 4)))  # 25% ROE → 100

    roa_val = _val("profitability", "roa")
    if roa_val is not None:
        prof_signals.append(min(100, max(0, roa_val * 8)))  # 12.5% ROA → 100

    prof_score = sum(prof_signals) / len(prof_signals) if prof_signals else 0

    # --- Liquidity score (0–100) ---
    liq_signals = []

    cr = _val("liquidity", "current_ratio")
    if cr is not None:
        liq_signals.append(min(100, max(0, cr * 50)))  # 2.0 → 100

    qr = _val("liquidity", "quick_ratio")
    if qr is not None:
        liq_signals.append(min(100, max(0, qr * 66.7)))  # 1.5 → 100

    liq_score = sum(liq_signals) / len(liq_signals) if liq_signals else 0

    # --- Solvency score (0–100) ---
    solv_signals = []

    dte = _val("solvency", "debt_to_equity")
    if dte is not None:
        solv_signals.append(min(100, max(0, 100 - dte * 50)))  # 0 debt → 100, 2x → 0

    ic = _val("solvency", "interest_coverage")
    if ic is not None:
        solv_signals.append(min(100, max(0, ic * 10)))  # 10x → 100

    solv_score = sum(solv_signals) / len(solv_signals) if solv_signals else 0

    # --- Cash flow score (0–100) ---
    cf_signals = []

    cc = _val("cash_flow", "cash_conversion")
    if cc is not None:
        cf_signals.append(min(100, max(0, cc)))  # 100% conversion → 100

    fy = _val("cash_flow", "fcf_yield")
    if fy is not None:
        cf_signals.append(min(100, max(0, fy * 15)))  # ~6.7% yield → 100

    cf_score = sum(cf_signals) / len(cf_signals) if cf_signals else 0

    # --- Overall (weighted average) ---
    weights = {"profitability": 0.30, "liquidity": 0.20, "solvency": 0.25, "cash_flow": 0.25}
    scores = {
        "profitability": prof_score,
        "liquidity": liq_score,
        "solvency": solv_score,
        "cash_flow": cf_score,
    }

    overall = sum(scores[k] * weights[k] for k in weights)

    return {
        "overall": round(overall, 1),
        "profitability_score": round(prof_score, 1),
        "liquidity_score": round(liq_score, 1),
        "solvency_score": round(solv_score, 1),
        "cash_flow_score": round(cf_score, 1),
        "breakdown": scores,
    }
