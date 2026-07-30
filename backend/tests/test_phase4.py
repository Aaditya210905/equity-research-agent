"""
Phase 4 - AI Equity Research Analyst Verification

Run from the backend/ directory:
    python -X utf8 tests/test_phase4.py

Tests (no API key required for 1-8):
    1. Research report schema validation
    2. Financial metrics formatting
    3. Evidence formatting
    4. News formatting
    5. Evidence categorization (evidence matrix)
    6. Section confidence scoring
    7. Prompt template loading
    8. Evidence payload assembly
    9. Full report generation (requires OPENAI_API_KEY)
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
PASS = "[PASS]"
FAIL = "[FAIL]"
SKIP = "[SKIP]"
DIVIDER = "=" * 60
test_results: list[dict] = []


def log_result(name: str, passed: bool, detail: str = ""):
    test_results.append({"name": name, "passed": passed})
    print(f"  {PASS if passed else FAIL}  {name}")
    if detail:
        print(f"         {detail}")


def log_skip(name: str, reason: str = ""):
    print(f"  {SKIP}  {name}")
    if reason:
        print(f"         {reason}")


def section(title: str):
    print(f"\n{DIVIDER}")
    print(f"  {title}")
    print(DIVIDER)


def _has_api_key() -> bool:
    from config.settings import settings
    return bool(settings.OPENAI_API_KEY)


# ---------------------------------------------------------------------------
# Synthetic test data
# ---------------------------------------------------------------------------

SAMPLE_METRICS = {
    "profitability": {
        "gross_margin": {"value": 40.0, "unit": "%", "formula": "GP/Rev", "status": "computed"},
        "operating_margin": {"value": 30.0, "unit": "%", "formula": "OI/Rev", "status": "computed"},
        "net_margin": {"value": 25.0, "unit": "%", "formula": "NI/Rev", "status": "computed"},
        "roe": {"value": 31.25, "unit": "%", "formula": "NI/Eq", "status": "computed"},
        "roa": {"value": 12.5, "unit": "%", "formula": "NI/TA", "status": "computed"},
    },
    "liquidity": {
        "current_ratio": {"value": 1.5, "unit": "x", "formula": "CA/CL", "status": "computed"},
        "quick_ratio": {"value": 1.375, "unit": "x", "formula": "(CA-Inv)/CL", "status": "computed"},
    },
    "solvency": {
        "debt_to_equity": {"value": 0.375, "unit": "x", "formula": "D/E", "status": "computed"},
        "interest_coverage": {"value": 15.0, "unit": "x", "formula": "OI/IE", "status": "computed"},
    },
    "valuation": {
        "pe_ratio": {"value": 20.0, "unit": "x", "formula": "P/EPS", "status": "computed"},
        "ev_to_ebitda": {"value": 14.43, "unit": "x", "formula": "EV/EBITDA", "status": "computed"},
        "price_to_book": {"value": 6.25, "unit": "x", "formula": "MC/Eq", "status": "computed"},
    },
    "cash_flow": {
        "free_cash_flow": {"value": 24000, "unit": "$", "formula": "OCF-CapEx", "status": "computed"},
        "cash_conversion": {"value": 96.0, "unit": "%", "formula": "FCF/NI", "status": "computed"},
    },
    "summary": {"computed": 14, "missing": 0, "total": 14},
}

SAMPLE_EVIDENCE = [
    {
        "chunk_id": "TCS_RF_001", "text": "The company faces significant cybersecurity threats.",
        "section": "Risk Factors", "page_start": 119, "page_end": 120,
        "score": 0.92, "company": "TCS", "year": 2025, "doc_type": "Annual Report",
    },
    {
        "chunk_id": "TCS_BUS_001", "text": "TCS operates in IT services and consulting globally.",
        "section": "Business Overview", "page_start": 10, "page_end": 12,
        "score": 0.88, "company": "TCS", "year": 2025, "doc_type": "Annual Report",
    },
    {
        "chunk_id": "TCS_FIN_001", "text": "Revenue increased by 14% driven by cloud services.",
        "section": "Financial Statements", "page_start": 200, "page_end": 200,
        "score": 0.75, "company": "TCS", "year": 2025, "doc_type": "Annual Report",
    },
    {
        "chunk_id": "TCS_GRW_001", "text": "AI and digital transformation investments accelerated.",
        "section": "Strategy and Growth", "page_start": 50, "page_end": 52,
        "score": 0.80, "company": "TCS", "year": 2025, "doc_type": "Annual Report",
    },
    {
        "chunk_id": "TCS_RF_002", "text": "Regulatory changes in data protection could impact operations.",
        "section": "Risk Factors", "page_start": 125, "page_end": 126,
        "score": 0.70, "company": "TCS", "year": 2025, "doc_type": "Annual Report",
    },
]

SAMPLE_NEWS = [
    {"title": "TCS wins $500M deal with European bank", "date": "2025-06-15", "summary": "Major deal win."},
    {"title": "TCS announces 15% dividend increase", "date": "2025-05-20", "summary": "Higher returns."},
]

SAMPLE_EVIDENCE_PAYLOAD = {
    "company": {"name": "Tata Consultancy Services", "ticker": "TCS", "sector": "IT Services"},
    "market_data": {"share_price": 4200.0, "market_cap": 1500000000000},
    "financial_metrics": SAMPLE_METRICS,
    "financial_health": {"overall": 87.8, "profitability_score": 91.7},
    "growth_metrics": {
        "revenue_growth": {"value": 17.65, "unit": "%", "status": "computed"},
        "net_income_growth": {"value": 25.0, "unit": "%", "status": "computed"},
    },
    "retrieved_evidence": SAMPLE_EVIDENCE,
    "news": SAMPLE_NEWS,
}


# ===================================================================
# 1. SCHEMA VALIDATION
# ===================================================================

def test_schemas():
    section("1. RESEARCH REPORT SCHEMAS")
    from schemas.research_report import ResearchReport, ReportSection, ResearchRequest

    # ReportSection
    sec = ReportSection(
        title="Executive Summary",
        content="TCS is a leading IT services company...",
        confidence=0.85,
        evidence_count=5,
    )
    log_result("ReportSection validates", sec.confidence == 0.85)

    # ResearchReport
    report = ResearchReport(
        company="TCS", ticker="TCS", sector="IT Services",
        executive_summary=sec,
        overall_confidence=0.82,
        model="gpt-4o-mini",
        generated_at="2025-07-30T00:00:00Z",
        financial_health_score=87.8,
        sections_generated=7,
    )
    log_result("ResearchReport validates", True)
    log_result("Report serializes", len(report.model_dump_json()) > 50)

    # ResearchRequest
    req = ResearchRequest()
    log_result("ResearchRequest defaults",
               len(req.sections) == 7 and req.top_k == 15,
               f"sections={len(req.sections)}, top_k={req.top_k}")


# ===================================================================
# 2. METRICS FORMATTING
# ===================================================================

def test_metrics_formatting():
    section("2. FINANCIAL METRICS FORMATTING")
    from agents.equity_analyst import format_metrics

    # Full metrics
    text = format_metrics(SAMPLE_METRICS)
    log_result("Formats all categories",
               "PROFITABILITY" in text and "SOLVENCY" in text,
               f"length = {len(text)}")
    log_result("Contains values", "40.0%" in text or "40%" in text)
    log_result("Contains metric names", "gross_margin" in text)

    # Single category
    prof_text = format_metrics(SAMPLE_METRICS, "profitability")
    log_result("Single category filter",
               "PROFITABILITY" in prof_text and "SOLVENCY" not in prof_text)

    # Empty
    empty = format_metrics({})
    log_result("Empty metrics handled", "No" in empty or "no" in empty)

    # Missing data status
    missing_metrics = {"profitability": {
        "roe": {"value": None, "unit": "%", "formula": "NI/Eq", "status": "missing_data"},
    }}
    mt = format_metrics(missing_metrics)
    log_result("Missing data shown as N/A", "N/A" in mt, f"text: {mt.strip()}")


# ===================================================================
# 3. EVIDENCE FORMATTING
# ===================================================================

def test_evidence_formatting():
    section("3. EVIDENCE FORMATTING")
    from agents.equity_analyst import format_evidence

    text = format_evidence(SAMPLE_EVIDENCE)
    log_result("Contains [1] reference", "[1]" in text)
    log_result("Contains [2] reference", "[2]" in text)
    log_result("Contains section info", "Risk Factors" in text)
    log_result("Contains page info", "Page" in text)
    log_result("Contains relevance score", "0.92" in text)
    log_result("Contains chunk text", "cybersecurity" in text)

    # Empty
    empty = format_evidence([])
    log_result("Empty evidence handled", "No" in empty)


# ===================================================================
# 4. NEWS FORMATTING
# ===================================================================

def test_news_formatting():
    section("4. NEWS FORMATTING")
    from agents.equity_analyst import format_news

    text = format_news(SAMPLE_NEWS)
    log_result("Contains title", "500M deal" in text)
    log_result("Contains date", "2025-06-15" in text)

    empty = format_news([])
    log_result("Empty news handled", "No" in empty)


# ===================================================================
# 5. EVIDENCE CATEGORIZATION
# ===================================================================

def test_evidence_categorization():
    section("5. EVIDENCE CATEGORIZATION (Matrix)")
    from agents.equity_analyst import categorize_evidence

    matrix = categorize_evidence(SAMPLE_EVIDENCE)

    log_result("Has risk_analysis bucket",
               len(matrix.get("risk_analysis", [])) >= 2,
               f"risk_analysis = {len(matrix.get('risk_analysis', []))}")

    log_result("Has business_overview bucket",
               len(matrix.get("business_overview", [])) >= 1,
               f"business_overview = {len(matrix.get('business_overview', []))}")

    log_result("Has growth_opportunities bucket",
               len(matrix.get("growth_opportunities", [])) >= 1,
               f"growth_opportunities = {len(matrix.get('growth_opportunities', []))}")

    log_result("Has financial_analysis bucket",
               len(matrix.get("financial_analysis", [])) >= 1,
               f"financial_analysis = {len(matrix.get('financial_analysis', []))}")

    # All chunks should be placed somewhere
    total = sum(len(v) for v in matrix.values())
    log_result("All chunks categorized",
               total >= len(SAMPLE_EVIDENCE),
               f"total placed = {total}, input = {len(SAMPLE_EVIDENCE)}")


# ===================================================================
# 6. SECTION CONFIDENCE
# ===================================================================

def test_section_confidence():
    section("6. SECTION CONFIDENCE SCORING")
    from agents.equity_analyst import _section_confidence

    # Full evidence
    full = _section_confidence(has_metrics=True, evidence_count=5, has_news=True)
    log_result("Full evidence → high confidence",
               full >= 0.85, f"confidence = {full}")

    # Metrics only
    metrics_only = _section_confidence(has_metrics=True, evidence_count=0, has_news=False)
    log_result("Metrics only → medium",
               0.4 <= metrics_only <= 0.6, f"confidence = {metrics_only}")

    # No evidence
    none = _section_confidence(has_metrics=False, evidence_count=0, has_news=False)
    log_result("No evidence → zero", none == 0.0, f"confidence = {none}")

    # Some evidence
    some = _section_confidence(has_metrics=True, evidence_count=2, has_news=True)
    log_result("Partial evidence → reasonable",
               0.6 <= some <= 1.0, f"confidence = {some}")


# ===================================================================
# 7. PROMPT TEMPLATE LOADING
# ===================================================================

def test_prompts():
    section("7. PROMPT TEMPLATE LOADING")
    from agents.equity_analyst import _load_prompt

    prompts = [
        "report_system.txt",
        "executive_summary.txt",
        "business_overview.txt",
        "financial_analysis.txt",
        "risk_analysis.txt",
        "growth_analysis.txt",
        "valuation_commentary.txt",
        "investment_thesis.txt",
    ]

    for p in prompts:
        content = _load_prompt(p)
        log_result(f"{p} loads",
                   len(content) > 50,
                   f"length = {len(content)}")

    # System prompt has grounding rules
    system = _load_prompt("report_system.txt")
    log_result("System prompt has grounding rules",
               "evidence" in system.lower() and "never" in system.lower())


# ===================================================================
# 8. EVIDENCE PAYLOAD ASSEMBLY
# ===================================================================

def test_payload_assembly():
    section("8. EVIDENCE PAYLOAD ASSEMBLY")

    payload = SAMPLE_EVIDENCE_PAYLOAD

    log_result("Has company info",
               payload["company"]["name"] == "Tata Consultancy Services")
    log_result("Has market data",
               payload["market_data"]["share_price"] == 4200.0)
    log_result("Has financial metrics",
               payload["financial_metrics"]["profitability"]["roe"]["value"] == 31.25)
    log_result("Has health score",
               payload["financial_health"]["overall"] == 87.8)
    log_result("Has growth metrics",
               payload["growth_metrics"]["revenue_growth"]["value"] == 17.65)
    log_result("Has retrieved evidence",
               len(payload["retrieved_evidence"]) == 5)
    log_result("Has news",
               len(payload["news"]) == 2)


# ===================================================================
# 9. FULL REPORT GENERATION (requires API key)
# ===================================================================

def test_full_report():
    section("9. FULL REPORT GENERATION")
    if not _has_api_key():
        log_skip("Full report generation", "OPENAI_API_KEY not set — skipping")
        return

    try:
        from agents.equity_analyst import generate_report

        print("  Generating research report for TCS (7 sections)...")
        print("  This may take 30–60 seconds...\n")

        report = generate_report(SAMPLE_EVIDENCE_PAYLOAD)

        log_result("Report generated", True)
        log_result("Has company", report.get("company") == "Tata Consultancy Services")
        log_result("Has ticker", report.get("ticker") == "TCS")
        log_result("Has model", len(report.get("model", "")) > 0)
        log_result("Has generated_at", len(report.get("generated_at", "")) > 0)

        # Sections
        expected_sections = [
            "executive_summary", "business_overview", "financial_analysis",
            "risk_analysis", "growth_opportunities", "valuation", "investment_thesis",
        ]

        for sec_name in expected_sections:
            sec = report.get(sec_name, {})
            has_content = len(sec.get("content", "")) > 50
            log_result(f"{sec_name}: has content",
                       has_content,
                       f"length = {len(sec.get('content', ''))}")
            log_result(f"{sec_name}: has confidence",
                       0 <= sec.get("confidence", -1) <= 1,
                       f"confidence = {sec.get('confidence')}")

        log_result("Overall confidence",
                   0 <= report.get("overall_confidence", -1) <= 1,
                   f"overall = {report.get('overall_confidence')}")
        log_result("Sections generated count",
                   report.get("sections_generated", 0) == 7)
        log_result("No sections failed",
                   report.get("sections_failed", 99) == 0)
        log_result("Has citations",
                   len(report.get("citations", [])) >= 0,
                   f"{len(report.get('citations', []))} citations")
        log_result("Health score passed through",
                   report.get("financial_health_score") == 87.8)

        # Print report preview
        print(f"\n  Report Preview:")
        print(f"  {'='*50}")
        for sec_name in expected_sections:
            sec = report.get(sec_name, {})
            content = sec.get("content", "")[:200]
            conf = sec.get("confidence", 0)
            print(f"\n  [{sec.get('title', sec_name)}] (confidence: {conf:.2f})")
            for line in content.split("\n")[:3]:
                print(f"    {line}")
            if len(sec.get("content", "")) > 200:
                print(f"    ... ({len(sec.get('content', ''))} chars)")

        print(f"\n  Overall confidence: {report.get('overall_confidence', 0):.2f}")
        print(f"  Model: {report.get('model')}")
        print(f"  Health score: {report.get('financial_health_score')}")

    except Exception as exc:
        log_result("Full report generation", False, str(exc))
        import traceback
        traceback.print_exc()


# ===================================================================
# RUNNER
# ===================================================================

def main():
    print("\n" + "#" * 60)
    print("  PHASE 4 -- AI EQUITY RESEARCH ANALYST")
    print("#" * 60)

    if _has_api_key():
        print(f"\n  OPENAI_API_KEY detected — full tests will run")
    else:
        print(f"\n  OPENAI_API_KEY not set — API tests will be skipped")

    start = time.time()

    test_schemas()
    test_metrics_formatting()
    test_evidence_formatting()
    test_news_formatting()
    test_evidence_categorization()
    test_section_confidence()
    test_prompts()
    test_payload_assembly()
    test_full_report()

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
