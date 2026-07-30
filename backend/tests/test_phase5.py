"""
Phase 5 - Research Planner, Tool Calling & Reflection Verification

Run from the backend/ directory:
    python -X utf8 tests/test_phase5.py

Tests (no API key required for 1-9):
    1. Request classification
    2. Company extraction
    3. Plan creation
    4. Tool registry
    5. Tool selection per request type
    6. Retrieval query generation
    7. Claim extraction (from synthetic report)
    8. Claim verification (against synthetic evidence)
    9. Report revision
   10. Schema validation
   11. Full end-to-end pipeline (requires OPENAI_API_KEY)
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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
# Synthetic report for verification tests
# ---------------------------------------------------------------------------
MOCK_REPORT = {
    "executive_summary": {
        "content": (
            "TCS is a leading IT services company with strong financial health. "
            "Revenue grew by 14% to $100 billion in fiscal 2025 [1]. "
            "The company maintains a net margin of 25.0% and ROE of 31.25% [2]. "
            "Key risks include cybersecurity threats and regulatory changes."
        ),
        "confidence": 0.85,
    },
    "financial_analysis": {
        "content": (
            "Operating margin stands at 30.0%, indicating strong operational efficiency. "
            "Free cash flow reached $24 billion with a cash conversion ratio of 96%. "
            "The current ratio of 1.5x suggests adequate liquidity [3]. "
            "Debt-to-equity of 0.375x reflects a conservative capital structure."
        ),
        "confidence": 0.90,
    },
    "risk_analysis": {
        "content": (
            "The company faces significant cybersecurity threats [1]. "
            "Regulatory changes in data protection could impact operations [5]. "
            "Macroeconomic volatility poses revenue uncertainty."
        ),
        "confidence": 0.80,
    },
    "growth_opportunities": {
        "content": "AI and digital transformation investments accelerated. Cloud revenue is growing.",
        "confidence": 0.75,
    },
    "business_overview": {"content": "TCS operates globally in IT consulting.", "confidence": 0.70},
    "valuation": {"content": "P/E ratio of 20.0x. EV/EBITDA is 14.43x.", "confidence": 0.80},
    "investment_thesis": {
        "content": "Bull case: Strong margins and growth. Bear case: cybersecurity risks.",
        "confidence": 0.75,
    },
}

MOCK_EVIDENCE = {
    "financial_metrics": {
        "profitability": {
            "net_margin": {"value": 25.0, "unit": "%", "status": "computed"},
            "operating_margin": {"value": 30.0, "unit": "%", "status": "computed"},
            "roe": {"value": 31.25, "unit": "%", "status": "computed"},
        },
        "liquidity": {
            "current_ratio": {"value": 1.5, "unit": "x", "status": "computed"},
        },
        "solvency": {
            "debt_to_equity": {"value": 0.375, "unit": "x", "status": "computed"},
        },
        "cash_flow": {
            "free_cash_flow": {"value": 24000, "unit": "$", "status": "computed"},
            "cash_conversion": {"value": 96.0, "unit": "%", "status": "computed"},
        },
        "valuation": {
            "pe_ratio": {"value": 20.0, "unit": "x", "status": "computed"},
            "ev_to_ebitda": {"value": 14.43, "unit": "x", "status": "computed"},
        },
    },
    "retrieved_evidence": [
        {"text": "Revenue increased by 14% to $100 billion.", "section": "Financial"},
        {"text": "The company faces significant cybersecurity threats.", "section": "Risk Factors"},
        {"text": "Regulatory changes in data protection could impact operations.", "section": "Risk Factors"},
    ],
    "market_data": {"share_price": 4200.0, "market_cap": 1500000000000},
    "news": [],
}


# ===================================================================
# 1. REQUEST CLASSIFICATION
# ===================================================================

def test_classification():
    section("1. REQUEST CLASSIFICATION")
    from planner.planner import classify_request

    tests = [
        ("What is TCS ROE?", "factual_query"),
        ("Analyze TCS", "company_analysis"),
        ("Compare TCS and Infosys", "comparison"),
        ("What are TCS risks?", "risk_analysis"),
        ("Write a complete investment memo for TCS", "investment_memo"),
        ("Generate equity research report for Infosys", "investment_memo"),
        ("How does Reliance AI strategy look?", "company_analysis"),
        ("TCS vs Infosys margins", "comparison"),
    ]

    for request, expected in tests:
        result = classify_request(request)
        log_result(f"'{request[:40]}...' → {expected}",
                   result == expected,
                   f"got: {result}")


# ===================================================================
# 2. COMPANY EXTRACTION
# ===================================================================

def test_extraction():
    section("2. COMPANY EXTRACTION")
    from planner.planner import extract_companies

    # Known company names
    log_result("Extracts 'TCS'",
               "TCS" in extract_companies("Analyze TCS"))
    log_result("Extracts 'Infosys' → INFY",
               "INFY" in extract_companies("What about Infosys?"))
    log_result("Extracts 'Apple' → AAPL",
               "AAPL" in extract_companies("Tell me about Apple"))

    # Multiple companies
    result = extract_companies("Compare TCS and Infosys")
    log_result("Multiple: TCS + INFY",
               "TCS" in result and "INFY" in result,
               f"found: {result}")

    # Ticker patterns
    result = extract_companies("What about MSFT?")
    log_result("Ticker pattern: MSFT",
               "MSFT" in result)

    # Should NOT extract common words
    result = extract_companies("How much AI investment?")
    log_result("Filters stopwords (AI not a ticker)",
               "AI" not in result, f"found: {result}")


# ===================================================================
# 3. PLAN CREATION
# ===================================================================

def test_plan_creation():
    section("3. PLAN CREATION")
    from planner.planner import create_plan

    plan = create_plan("Analyze TCS from an investment perspective")

    log_result("Has request_id", len(plan["request_id"]) > 0)
    log_result("Has objective", "TCS" in plan["objective"])
    # "from an investment perspective" correctly maps to investment_memo
    log_result("Type: investment_memo", plan["request_type"] == "investment_memo")
    log_result("Companies: [TCS]", plan["companies"] == ["TCS"])
    log_result("Has required_tools", len(plan["required_tools"]) > 0)
    log_result("Has retrieval_queries", len(plan["retrieval_queries"]) > 0)
    log_result("Output: research_report", plan["output_format"] == "research_report")

    # Factual query
    fq = create_plan("What is AAPL market cap?")
    log_result("Factual → brief_answer", fq["output_format"] == "brief_answer")
    log_result("Factual has fewer tools",
               len(fq["required_tools"]) <= len(plan["required_tools"]),
               f"tools: {fq['required_tools']}")

    # Comparison
    comp = create_plan("Compare TCS and Infosys")
    log_result("Comparison: 2 companies",
               len(comp["companies"]) == 2,
               f"companies: {comp['companies']}")
    log_result("Comparison has peer_comparison tool",
               "peer_comparison" in comp["required_tools"])


# ===================================================================
# 4. TOOL REGISTRY
# ===================================================================

def test_registry():
    section("4. TOOL REGISTRY")
    from planner.tool_registry import TOOL_REGISTRY, list_tools, get_tool

    log_result("Registry has 6 tools",
               len(TOOL_REGISTRY) == 6,
               f"count = {len(TOOL_REGISTRY)}")
    log_result("list_tools() works",
               len(list_tools()) == 6)

    # Every tool has required fields
    for name, tool in TOOL_REGISTRY.items():
        has_fields = all(k in tool for k in ("name", "description", "serves", "inputs"))
        log_result(f"{name}: has all fields", has_fields)

    # Lookup
    fe = get_tool("financial_engine")
    log_result("get_tool works", fe is not None and fe["name"] == "financial_engine")


# ===================================================================
# 5. TOOL SELECTION
# ===================================================================

def test_tool_selection():
    section("5. TOOL SELECTION PER REQUEST TYPE")
    from planner.tool_registry import get_tools_for_request_type

    # Factual query → financial_engine + market_service
    fq = get_tools_for_request_type("factual_query")
    log_result("factual_query tools",
               "financial_engine" in fq and "market_service" in fq,
               f"tools: {fq}")

    # Company analysis → everything except peer_comparison
    ca = get_tools_for_request_type("company_analysis")
    log_result("company_analysis has retriever",
               "retriever" in ca)
    log_result("company_analysis has financial_engine",
               "financial_engine" in ca)

    # Comparison → includes peer_comparison
    comp = get_tools_for_request_type("comparison")
    log_result("comparison has peer_comparison",
               "peer_comparison" in comp)

    # Investment memo → most tools
    im = get_tools_for_request_type("investment_memo")
    log_result("investment_memo has ≥4 tools",
               len(im) >= 4,
               f"tools: {im}")


# ===================================================================
# 6. RETRIEVAL QUERIES
# ===================================================================

def test_queries():
    section("6. RETRIEVAL QUERY GENERATION")
    from planner.planner import create_plan

    plan = create_plan("Analyze TCS risks and growth")
    queries = plan["retrieval_queries"]

    log_result("Queries generated", len(queries) > 0, f"count = {len(queries)}")
    log_result("Queries contain company name",
               any("TCS" in q for q in queries))
    log_result("Risk queries generated",
               any("risk" in q.lower() for q in queries))


# ===================================================================
# 7. CLAIM EXTRACTION
# ===================================================================

def test_claim_extraction():
    section("7. CLAIM EXTRACTION")
    from verification.claim_extractor import extract_claims

    claims = extract_claims(MOCK_REPORT)

    log_result("Claims extracted", len(claims) > 0, f"count = {len(claims)}")

    # Should find claims with numbers
    number_claims = [c for c in claims if c["has_number"]]
    log_result("Number claims found",
               len(number_claims) >= 3,
               f"count = {len(number_claims)}")

    # Should detect citations
    cited = [c for c in claims if c["has_citation"]]
    log_result("Cited claims found",
               len(cited) >= 2,
               f"count = {len(cited)}")

    # Each claim has section
    log_result("Claims have sections",
               all(c.get("section") for c in claims))

    # All start as "pending"
    log_result("All start as pending",
               all(c["verification"] == "pending" for c in claims))

    # Preview
    for c in claims[:3]:
        print(f"         [{c['section']}] '{c['text'][:60]}...'")


# ===================================================================
# 8. CLAIM VERIFICATION
# ===================================================================

def test_verification():
    section("8. CLAIM VERIFICATION")
    from verification.claim_extractor import extract_claims
    from verification.verifier import verify_claims

    claims = extract_claims(MOCK_REPORT)
    result = verify_claims(claims, MOCK_EVIDENCE)

    log_result("Has total_claims", result["total_claims"] > 0)
    log_result("Has verified count", result["verified"] >= 0)
    log_result("Has verification_rate",
               0 <= result["verification_rate"] <= 1,
               f"rate = {result['verification_rate']}")

    # Most claims should be verified (we have matching evidence)
    log_result("Most claims verified",
               result["verification_rate"] >= 0.5,
               f"verified {result['verified']}/{result['total_claims']}")

    # Check specific verification
    verified = [c for c in result["claims"] if c["verification"] == "verified"]
    log_result("Verified claims have evidence",
               all(c.get("supporting_evidence") for c in verified[:3]))

    # Print verification summary
    print(f"\n         Verification: {result['verified']}/{result['total_claims']} "
          f"({result['verification_rate']*100:.0f}%)")
    print(f"         Unverified: {result['unverified']}")


# ===================================================================
# 9. REPORT REVISION
# ===================================================================

def test_revision():
    section("9. REPORT REVISION")
    from verification.verifier import revise_report
    import copy

    # Case 1: All verified → no changes
    report1 = copy.deepcopy(MOCK_REPORT)
    verified_all = {"claims": [], "unverified": 0}
    revised1 = revise_report(report1, verified_all)
    log_result("All verified → no revision",
               "no revision" in revised1.get("_revision_notes", "").lower())

    # Case 2: Unverified claims → disclaimers added
    report2 = copy.deepcopy(MOCK_REPORT)
    unverified = {
        "claims": [
            {"text": "Fake number 999%", "section": "financial_analysis",
             "has_number": True, "verification": "unverified"},
        ],
        "unverified": 1,
    }
    revised2 = revise_report(report2, unverified)
    fin = revised2.get("financial_analysis", {})
    log_result("Disclaimer added to section",
               "could not be fully verified" in fin.get("content", ""))
    log_result("Confidence reduced",
               fin.get("confidence", 1.0) < 0.90,
               f"confidence = {fin.get('confidence')}")


# ===================================================================
# 10. SCHEMA VALIDATION
# ===================================================================

def test_schemas():
    section("10. SCHEMA VALIDATION")
    from schemas.plan import ResearchPlan, ToolResult, Claim, VerificationResult, ExecutionTrace

    plan = ResearchPlan(
        request_id="REQ-001",
        objective="Analyze TCS",
        request_type="company_analysis",
        companies=["TCS"],
        required_tools=["financial_engine", "retriever"],
    )
    log_result("ResearchPlan validates", True)

    tr = ToolResult(tool="financial_engine", status="success", duration_ms=150)
    log_result("ToolResult validates", True)

    claim = Claim(text="Revenue grew 14%", section="financial", has_number=True)
    log_result("Claim validates", True)

    vr = VerificationResult(total_claims=10, verified=8, unverified=2, verification_rate=0.8)
    log_result("VerificationResult validates", True)

    trace = ExecutionTrace(
        request_id="REQ-001",
        tools_called=["financial_engine", "retriever"],
        duration_ms=4500,
    )
    log_result("ExecutionTrace validates", True)
    log_result("All schemas serialize", len(trace.model_dump_json()) > 10)


# ===================================================================
# 11. FULL E2E PIPELINE (requires API key)
# ===================================================================

def test_full_pipeline():
    section("11. FULL END-TO-END PIPELINE")
    if not _has_api_key():
        log_skip("Full pipeline", "OPENAI_API_KEY not set — skipping")
        return

    try:
        from report.report_generator import generate_research

        print("  Running full pipeline: 'Analyze AAPL from an investment perspective'")
        print("  This may take 60–120 seconds...\n")

        result = generate_research(
            "Analyze AAPL from an investment perspective",
            companies=["AAPL"],
            skip_verification=False,
        )

        report = result.get("report", {})
        verification = result.get("verification", {})
        trace = result.get("trace", {})

        log_result("Report generated",
                   report.get("sections_generated", 0) > 0,
                   f"sections = {report.get('sections_generated')}")
        log_result("Has trace",
                   len(trace.get("tools_called", [])) > 0,
                   f"tools = {trace.get('tools_called')}")
        log_result("Has duration",
                   trace.get("duration_ms", 0) > 0,
                   f"duration = {trace.get('duration_ms')}ms")

        if verification:
            log_result("Verification ran",
                       verification.get("total_claims", 0) > 0,
                       f"claims = {verification.get('total_claims')}")
            log_result("Verification rate",
                       verification.get("verification_rate", 0) > 0,
                       f"rate = {verification.get('verification_rate')}")

        # Print trace summary
        print(f"\n  Trace:")
        print(f"    Request: {trace.get('objective', '')[:60]}")
        print(f"    Tools: {trace.get('tools_called', [])}")
        print(f"    Duration: {trace.get('duration_ms')}ms")
        if trace.get("verification"):
            v = trace["verification"]
            print(f"    Verification: {v.get('verified', '?')}/{v.get('claims', '?')} claims")

    except Exception as exc:
        log_result("Full pipeline", False, str(exc))
        import traceback
        traceback.print_exc()


# ===================================================================
# RUNNER
# ===================================================================

def main():
    print("\n" + "#" * 60)
    print("  PHASE 5 -- PLANNER, TOOLS & REFLECTION")
    print("#" * 60)

    if _has_api_key():
        print(f"\n  OPENAI_API_KEY detected — full tests will run")
    else:
        print(f"\n  OPENAI_API_KEY not set — API tests will be skipped")

    start = time.time()

    test_classification()
    test_extraction()
    test_plan_creation()
    test_registry()
    test_tool_selection()
    test_queries()
    test_claim_extraction()
    test_verification()
    test_revision()
    test_schemas()
    test_full_pipeline()

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
