"""
Phase 3 - Financial Computation Engine Verification

Run from the backend/ directory:
    python -X utf8 tests/test_phase3.py

Tests (no dependencies required — pure Python):
    1. Profitability metrics (Margins, ROE, ROA, ROIC)
    2. Liquidity metrics (Current, Quick, Cash ratios)
    3. Solvency metrics (D/E, D/A, Interest Coverage)
    4. Growth metrics (YoY Revenue, NI, EPS, EBITDA, CAGR)
    5. Cash flow metrics (FCF, OCF Ratio, Cash Conversion)
    6. Efficiency metrics (Asset/Inventory/Receivables Turnover)
    7. Valuation metrics (P/E, EV/EBITDA, P/B, EV)
    8. Missing data handling
    9. Division by zero handling
   10. Multi-year trend analysis
   11. Peer comparison
   12. Financial health scoring
   13. Formula registry completeness
   14. Banking company (different structure)
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
PASS = "[PASS]"
FAIL = "[FAIL]"
DIVIDER = "=" * 60
test_results: list[dict] = []


def log_result(name: str, passed: bool, detail: str = ""):
    test_results.append({"name": name, "passed": passed})
    print(f"  {PASS if passed else FAIL}  {name}")
    if detail:
        print(f"         {detail}")


def section(title: str):
    print(f"\n{DIVIDER}")
    print(f"  {title}")
    print(DIVIDER)


# ---------------------------------------------------------------------------
# Test data: IT Company (TCS-like)
# ---------------------------------------------------------------------------
TCS_DATA = {
    "income_statement": {
        "revenue": 100000,
        "cost_of_revenue": 60000,
        "gross_profit": 40000,
        "operating_income": 30000,
        "net_income": 25000,
        "ebitda": 35000,
        "interest_expense": 2000,
        "eps": 50.0,
        "pretax_income": 32000,
        "tax_provision": 7000,
    },
    "balance_sheet": {
        "total_assets": 200000,
        "total_equity": 80000,
        "total_debt": 30000,
        "total_liabilities": 120000,
        "current_assets": 60000,
        "current_liabilities": 40000,
        "cash_and_equivalents": 25000,
        "inventory": 5000,
        "accounts_receivable": 20000,
        "accounts_payable": 12000,
    },
    "cash_flow": {
        "operating_cash_flow": 32000,
        "capital_expenditure": -8000,
    },
    "market_data": {
        "market_cap": 500000,
        "share_price": 1000.0,
        "shares_outstanding": 500,
        "enterprise_value": 505000,
        "dividend_per_share": 20.0,
    },
}

# Previous year for growth calculations
TCS_PREV = {
    "income_statement": {
        "revenue": 85000,
        "net_income": 20000,
        "eps": 40.0,
        "ebitda": 30000,
        "operating_income": 25000,
    },
}

# INFY for peer comparison
INFY_DATA = {
    "income_statement": {
        "revenue": 80000,
        "cost_of_revenue": 50000,
        "gross_profit": 30000,
        "operating_income": 22000,
        "net_income": 18000,
        "ebitda": 26000,
        "interest_expense": 1500,
        "eps": 45.0,
    },
    "balance_sheet": {
        "total_assets": 150000,
        "total_equity": 70000,
        "total_debt": 20000,
        "total_liabilities": 80000,
        "current_assets": 50000,
        "current_liabilities": 30000,
        "cash_and_equivalents": 20000,
        "inventory": 3000,
        "accounts_receivable": 15000,
        "accounts_payable": 8000,
    },
    "cash_flow": {
        "operating_cash_flow": 25000,
        "capital_expenditure": -6000,
    },
    "market_data": {
        "market_cap": 400000,
        "share_price": 800.0,
        "shares_outstanding": 500,
    },
}

# Banking company (HDFC Bank-like) — different structure
HDFC_DATA = {
    "income_statement": {
        "revenue": 150000,      # Interest + non-interest income
        "cost_of_revenue": None,  # Banks don't have COGS
        "gross_profit": None,
        "operating_income": 50000,
        "net_income": 40000,
        "ebitda": None,           # EBITDA not meaningful for banks
        "interest_expense": 80000,
        "eps": 80.0,
    },
    "balance_sheet": {
        "total_assets": 2000000,
        "total_equity": 200000,
        "total_debt": 1500000,    # Deposits = liabilities for banks
        "total_liabilities": 1800000,
        "current_assets": 300000,
        "current_liabilities": 200000,
        "cash_and_equivalents": 100000,
        "inventory": None,        # Banks have no inventory
        "accounts_receivable": None,
        "accounts_payable": None,
    },
    "cash_flow": {
        "operating_cash_flow": 60000,
        "capital_expenditure": -5000,
    },
    "market_data": {
        "market_cap": 800000,
        "share_price": 1600.0,
        "shares_outstanding": 500,
    },
}


# ===================================================================
# 1. PROFITABILITY
# ===================================================================

def test_profitability():
    section("1. PROFITABILITY METRICS")
    from financial_engine.profitability import compute_all

    results = compute_all(TCS_DATA)

    # Gross Margin = 40000/100000 = 40%
    gm = results["gross_margin"]
    log_result("Gross Margin = 40%",
               gm["status"] == "computed" and abs(gm["value"] - 40.0) < 0.01,
               f"{gm['value']}%")

    # Operating Margin = 30000/100000 = 30%
    om = results["operating_margin"]
    log_result("Operating Margin = 30%",
               abs(om["value"] - 30.0) < 0.01, f"{om['value']}%")

    # Net Margin = 25000/100000 = 25%
    nm = results["net_margin"]
    log_result("Net Margin = 25%",
               abs(nm["value"] - 25.0) < 0.01, f"{nm['value']}%")

    # EBITDA Margin = 35000/100000 = 35%
    em = results["ebitda_margin"]
    log_result("EBITDA Margin = 35%",
               abs(em["value"] - 35.0) < 0.01, f"{em['value']}%")

    # ROE = 25000/80000 = 31.25%
    r = results["roe"]
    log_result("ROE = 31.25%",
               abs(r["value"] - 31.25) < 0.01, f"{r['value']}%")

    # ROA = 25000/200000 = 12.5%
    r = results["roa"]
    log_result("ROA = 12.5%",
               abs(r["value"] - 12.5) < 0.01, f"{r['value']}%")

    # ROIC: NOPAT = 30000 * (1 - 7000/32000), IC = 80000 + 30000 - 25000 = 85000
    r = results["roic"]
    log_result("ROIC computed",
               r["status"] == "computed" and r["value"] > 0,
               f"{r['value']}%")

    # All have formula
    for name, m in results.items():
        log_result(f"{name} has formula",
                   len(m.get("formula", "")) > 0)


# ===================================================================
# 2. LIQUIDITY
# ===================================================================

def test_liquidity():
    section("2. LIQUIDITY METRICS")
    from financial_engine.liquidity import compute_all

    results = compute_all(TCS_DATA)

    # Current Ratio = 60000/40000 = 1.5
    cr = results["current_ratio"]
    log_result("Current Ratio = 1.5x",
               abs(cr["value"] - 1.5) < 0.01, f"{cr['value']}x")

    # Quick Ratio = (60000-5000)/40000 = 1.375
    qr = results["quick_ratio"]
    log_result("Quick Ratio = 1.375x",
               abs(qr["value"] - 1.375) < 0.01, f"{qr['value']}x")

    # Cash Ratio = 25000/40000 = 0.625
    ca = results["cash_ratio"]
    log_result("Cash Ratio = 0.625x",
               abs(ca["value"] - 0.625) < 0.01, f"{ca['value']}x")


# ===================================================================
# 3. SOLVENCY
# ===================================================================

def test_solvency():
    section("3. SOLVENCY METRICS")
    from financial_engine.solvency import compute_all

    results = compute_all(TCS_DATA)

    # D/E = 30000/80000 = 0.375
    de = results["debt_to_equity"]
    log_result("Debt/Equity = 0.375x",
               abs(de["value"] - 0.375) < 0.01, f"{de['value']}x")

    # D/A = 30000/200000 = 0.15
    da = results["debt_to_assets"]
    log_result("Debt/Assets = 0.15x",
               abs(da["value"] - 0.15) < 0.01, f"{da['value']}x")

    # Interest Coverage = 30000/2000 = 15
    ic = results["interest_coverage"]
    log_result("Interest Coverage = 15x",
               abs(ic["value"] - 15.0) < 0.01, f"{ic['value']}x")

    # Equity Multiplier = 200000/80000 = 2.5
    em = results["equity_multiplier"]
    log_result("Equity Multiplier = 2.5x",
               abs(em["value"] - 2.5) < 0.01, f"{em['value']}x")


# ===================================================================
# 4. GROWTH
# ===================================================================

def test_growth():
    section("4. GROWTH METRICS")
    from financial_engine.growth import compute_all, cagr

    results = compute_all(TCS_DATA, TCS_PREV)

    # Revenue Growth = (100000-85000)/85000 = 17.647%
    rg = results["revenue_growth"]
    log_result("Revenue Growth ≈ 17.65%",
               abs(rg["value"] - 17.6471) < 0.1, f"{rg['value']}%")

    # NI Growth = (25000-20000)/20000 = 25%
    ng = results["net_income_growth"]
    log_result("Net Income Growth = 25%",
               abs(ng["value"] - 25.0) < 0.01, f"{ng['value']}%")

    # EPS Growth = (50-40)/40 = 25%
    eg = results["eps_growth"]
    log_result("EPS Growth = 25%",
               abs(eg["value"] - 25.0) < 0.01, f"{eg['value']}%")

    # EBITDA Growth = (35000-30000)/30000 = 16.667%
    ebg = results["ebitda_growth"]
    log_result("EBITDA Growth ≈ 16.67%",
               abs(ebg["value"] - 16.6667) < 0.1, f"{ebg['value']}%")

    # CAGR: 85000 → 100000 over 2 years ≈ 8.47%
    c = cagr(85000, 100000, 2)
    log_result("CAGR (2yr) ≈ 8.47%",
               abs(c["value"] - 8.4652) < 0.1, f"{c['value']}%")

    # CAGR: 100 → 200 over 5 years ≈ 14.87%
    c2 = cagr(100, 200, 5)
    log_result("CAGR (100→200, 5yr) ≈ 14.87%",
               abs(c2["value"] - 14.8698) < 0.1, f"{c2['value']}%")


# ===================================================================
# 5. CASH FLOW
# ===================================================================

def test_cashflow():
    section("5. CASH FLOW METRICS")
    from financial_engine.cashflow import compute_all

    results = compute_all(TCS_DATA)

    # FCF = 32000 - 8000 = 24000
    fcf = results["free_cash_flow"]
    log_result("FCF = 24000",
               abs(fcf["value"] - 24000) < 1, f"${fcf['value']}")

    # OCF/NI = 32000/25000 = 1.28
    ocf = results["ocf_ratio"]
    log_result("OCF Ratio = 1.28x",
               abs(ocf["value"] - 1.28) < 0.01, f"{ocf['value']}x")

    # CapEx/Revenue = 8000/100000 = 8%
    ctr = results["capex_to_revenue"]
    log_result("CapEx/Revenue = 8%",
               abs(ctr["value"] - 8.0) < 0.01, f"{ctr['value']}%")

    # Cash Conversion = 24000/25000 = 96%
    cc = results["cash_conversion"]
    log_result("Cash Conversion = 96%",
               abs(cc["value"] - 96.0) < 0.01, f"{cc['value']}%")

    # FCF Yield = 24000/500000 = 4.8%
    fy = results["fcf_yield"]
    log_result("FCF Yield = 4.8%",
               abs(fy["value"] - 4.8) < 0.01, f"{fy['value']}%")


# ===================================================================
# 6. EFFICIENCY
# ===================================================================

def test_efficiency():
    section("6. EFFICIENCY METRICS")
    from financial_engine.efficiency import compute_all

    results = compute_all(TCS_DATA)

    # Asset Turnover = 100000/200000 = 0.5
    at = results["asset_turnover"]
    log_result("Asset Turnover = 0.5x",
               abs(at["value"] - 0.5) < 0.01, f"{at['value']}x")

    # Inventory Turnover = 60000/5000 = 12
    it = results["inventory_turnover"]
    log_result("Inventory Turnover = 12x",
               abs(it["value"] - 12.0) < 0.01, f"{it['value']}x")

    # Receivables Turnover = 100000/20000 = 5
    rt = results["receivables_turnover"]
    log_result("Receivables Turnover = 5x",
               abs(rt["value"] - 5.0) < 0.01, f"{rt['value']}x")

    # Working Capital Turnover = 100000/(60000-40000) = 5
    wc = results["working_capital_turnover"]
    log_result("WC Turnover = 5x",
               abs(wc["value"] - 5.0) < 0.01, f"{wc['value']}x")

    # Payables Turnover = 60000/12000 = 5
    pt = results["payables_turnover"]
    log_result("Payables Turnover = 5x",
               abs(pt["value"] - 5.0) < 0.01, f"{pt['value']}x")


# ===================================================================
# 7. VALUATION
# ===================================================================

def test_valuation():
    section("7. VALUATION METRICS")
    from financial_engine.valuation import compute_all, peg_ratio

    results = compute_all(TCS_DATA)

    # P/E = 1000/50 = 20
    pe = results["pe_ratio"]
    log_result("P/E = 20x",
               abs(pe["value"] - 20.0) < 0.01, f"{pe['value']}x")

    # EV/EBITDA = 505000/35000 ≈ 14.43
    ev_eb = results["ev_to_ebitda"]
    log_result("EV/EBITDA ≈ 14.43x",
               abs(ev_eb["value"] - 14.4286) < 0.1, f"{ev_eb['value']}x")

    # P/B = 500000/80000 = 6.25
    pb = results["price_to_book"]
    log_result("P/B = 6.25x",
               abs(pb["value"] - 6.25) < 0.01, f"{pb['value']}x")

    # EV = 500000 + 30000 - 25000 = 505000
    ev = results["enterprise_value"]
    log_result("EV = 505000",
               abs(ev["value"] - 505000) < 1, f"${ev['value']}")

    # Dividend Yield = 20/1000 = 2%
    dy = results["dividend_yield"]
    log_result("Dividend Yield = 2%",
               abs(dy["value"] - 2.0) < 0.01, f"{dy['value']}%")

    # P/S = 500000/100000 = 5
    ps = results["price_to_sales"]
    log_result("P/S = 5x",
               abs(ps["value"] - 5.0) < 0.01, f"{ps['value']}x")

    # PEG with growth rate
    peg = peg_ratio(TCS_DATA, eps_growth_pct=25.0)
    log_result("PEG = 0.8x (P/E=20, growth=25%)",
               abs(peg["value"] - 0.8) < 0.01, f"{peg['value']}x")


# ===================================================================
# 8. MISSING DATA HANDLING
# ===================================================================

def test_missing_data():
    section("8. MISSING DATA HANDLING")
    from financial_engine.profitability import compute_all

    empty = {"income_statement": {}, "balance_sheet": {}, "cash_flow": {}, "market_data": {}}
    results = compute_all(empty)

    for name, m in results.items():
        log_result(f"{name}: status = missing_data",
                   m["status"] == "missing_data",
                   f"value={m['value']}, status={m['status']}")
        log_result(f"{name}: value = None",
                   m["value"] is None)


# ===================================================================
# 9. DIVISION BY ZERO
# ===================================================================

def test_division_by_zero():
    section("9. DIVISION BY ZERO HANDLING")
    from financial_engine.profitability import net_margin, roe

    zero_rev = {
        "income_statement": {"net_income": 1000, "revenue": 0},
        "balance_sheet": {"total_equity": 0},
    }

    nm = net_margin(zero_rev)
    log_result("Zero revenue → division_by_zero",
               nm["status"] == "division_by_zero")

    r = roe(zero_rev)
    log_result("Zero equity → division_by_zero",
               r["status"] == "division_by_zero")

    from financial_engine.growth import cagr
    c = cagr(0, 100, 3)
    log_result("CAGR zero start → division_by_zero",
               c["status"] == "division_by_zero")

    c2 = cagr(100, 200, 0)
    log_result("CAGR zero years → missing_data",
               c2["status"] == "missing_data")


# ===================================================================
# 10. MULTI-YEAR TRENDS
# ===================================================================

def test_trends():
    section("10. MULTI-YEAR TRENDS")
    from financial_engine.engine import compute_trends

    year1 = {"year": 2023, "income_statement": {"revenue": 80000, "net_income": 18000, "eps": 36}}
    year2 = {"year": 2024, "income_statement": {"revenue": 90000, "net_income": 22000, "eps": 44}}
    year3 = {"year": 2025, "income_statement": {"revenue": 100000, "net_income": 25000, "eps": 50}}

    result = compute_trends([year1, year2, year3])

    log_result("Years correct", result["years"] == [2023, 2024, 2025])
    log_result("Revenue series", result["revenue"] == [80000, 90000, 100000])
    log_result("NI series", result["net_income"] == [18000, 22000, 25000])

    # Revenue CAGR: (100000/80000)^(1/2) - 1 ≈ 11.8%
    rc = result.get("revenue_cagr", {})
    log_result("Revenue CAGR computed",
               rc.get("status") == "computed" and abs(rc["value"] - 11.803) < 0.1,
               f"{rc.get('value')}%")

    # YoY growth series
    yoy = result.get("yoy_growth", [])
    log_result("2 YoY growth periods", len(yoy) == 2)
    if yoy:
        y1_rev = yoy[0].get("revenue_growth", {})
        log_result("2023→2024 revenue growth = 12.5%",
                   abs(y1_rev["value"] - 12.5) < 0.1,
                   f"{y1_rev['value']}%")


# ===================================================================
# 11. PEER COMPARISON
# ===================================================================

def test_peer_comparison():
    section("11. PEER COMPARISON")
    from financial_engine.engine import compare_peers

    result = compare_peers({"TCS": TCS_DATA, "INFY": INFY_DATA})

    log_result("Companies listed", result["companies"] == ["TCS", "INFY"])
    log_result("Metrics present",
               "net_margin" in result["metrics"],
               f"keys = {list(result['metrics'].keys())[:5]}...")

    # Check TCS net margin
    tcs_nm = result["metrics"]["net_margin"]["TCS"]
    log_result("TCS net margin in comparison",
               tcs_nm["status"] == "computed" and abs(tcs_nm["value"] - 25.0) < 0.1)

    # Rankings
    roe_rank = result["rankings"].get("roe", [])
    log_result("ROE ranking exists", len(roe_rank) == 2, f"ranking = {roe_rank}")

    # TCS should rank higher in ROE (31.25% vs ~25.71%)
    log_result("TCS ranks first in ROE",
               roe_rank[0] == "TCS" if roe_rank else False)

    # Debt ratios: lower is better, ranking should be reversed
    de_rank = result["rankings"].get("debt_to_equity", [])
    log_result("Debt/Equity ranking (lower is better)", len(de_rank) == 2,
               f"ranking = {de_rank}")


# ===================================================================
# 12. FINANCIAL HEALTH SCORE
# ===================================================================

def test_health_score():
    section("12. FINANCIAL HEALTH SCORE")
    from financial_engine.engine import financial_health_score

    result = financial_health_score(TCS_DATA)

    log_result("Overall score computed",
               0 <= result["overall"] <= 100,
               f"overall = {result['overall']}")
    log_result("Profitability score",
               0 <= result["profitability_score"] <= 100,
               f"{result['profitability_score']}")
    log_result("Liquidity score",
               0 <= result["liquidity_score"] <= 100,
               f"{result['liquidity_score']}")
    log_result("Solvency score",
               0 <= result["solvency_score"] <= 100,
               f"{result['solvency_score']}")
    log_result("Cash flow score",
               0 <= result["cash_flow_score"] <= 100,
               f"{result['cash_flow_score']}")

    # TCS should score well (healthy company)
    log_result("TCS scores > 50 overall",
               result["overall"] > 50,
               f"overall = {result['overall']}")


# ===================================================================
# 13. FORMULA REGISTRY
# ===================================================================

def test_formula_registry():
    section("13. FORMULA REGISTRY")
    from financial_engine.engine import FORMULA_REGISTRY

    log_result("Registry has entries",
               len(FORMULA_REGISTRY) > 30,
               f"{len(FORMULA_REGISTRY)} metrics registered")

    # Every entry has required fields
    valid = all(
        "formula" in v and "unit" in v and "category" in v
        for v in FORMULA_REGISTRY.values()
    )
    log_result("All entries have formula/unit/category", valid)

    # Check categories
    categories = set(v["category"] for v in FORMULA_REGISTRY.values())
    expected = {"profitability", "liquidity", "solvency", "growth",
                "cash_flow", "efficiency", "valuation"}
    log_result("All 7 categories present",
               expected.issubset(categories),
               f"categories = {categories}")


# ===================================================================
# 14. BANKING COMPANY
# ===================================================================

def test_banking():
    section("14. BANKING COMPANY (HDFC Bank)")
    from financial_engine.engine import compute_all

    results = compute_all(HDFC_DATA)

    # Should handle missing COGS/inventory/EBITDA gracefully
    gm = results["profitability"]["gross_margin"]
    log_result("No COGS → gross_margin missing",
               gm["status"] == "missing_data")

    em = results["profitability"]["ebitda_margin"]
    log_result("No EBITDA → ebitda_margin missing",
               em["status"] == "missing_data")

    it = results["efficiency"]["inventory_turnover"]
    log_result("No inventory → inventory_turnover missing",
               it["status"] == "missing_data")

    # But ROE should work (bank has equity)
    roe_val = results["profitability"]["roe"]
    # ROE = 40000/200000 = 20%
    log_result("Bank ROE = 20%",
               roe_val["status"] == "computed" and abs(roe_val["value"] - 20.0) < 0.1,
               f"{roe_val['value']}%")

    # Summary should show both computed and missing
    s = results["summary"]
    log_result("Summary has computed + missing",
               s["computed"] > 0 and s["missing"] > 0,
               f"computed={s['computed']}, missing={s['missing']}, total={s['total']}")

    # Engine should never crash
    log_result("Engine didn't crash on bank data", True)

    # Full engine compute count
    from financial_engine.engine import compute_all as ca
    full = ca(TCS_DATA)
    log_result(f"Total metrics: {full['summary']['total']}",
               full["summary"]["total"] >= 30,
               f"computed={full['summary']['computed']}, missing={full['summary']['missing']}")


# ===================================================================
# RUNNER
# ===================================================================

def main():
    print("\n" + "#" * 60)
    print("  PHASE 3 -- FINANCIAL COMPUTATION ENGINE")
    print("#" * 60)

    start = time.time()

    test_profitability()
    test_liquidity()
    test_solvency()
    test_growth()
    test_cashflow()
    test_efficiency()
    test_valuation()
    test_missing_data()
    test_division_by_zero()
    test_trends()
    test_peer_comparison()
    test_health_score()
    test_formula_registry()
    test_banking()

    elapsed = time.time() - start

    section("SUMMARY")
    passed = sum(1 for t in test_results if t["passed"])
    failed = sum(1 for t in test_results if not t["passed"])
    total = len(test_results)

    print(f"\n  Total:  {total}")
    print(f"  Passed: {passed} {PASS}")
    print(f"  Failed: {failed} {FAIL}")
    print(f"  Time:   {elapsed:.1f}s")

    if failed > 0:
        print(f"\n  Failed tests:")
        for t in test_results:
            if not t["passed"]:
                print(f"    {FAIL}  {t['name']}")

    print(f"\n{'#' * 60}\n")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
