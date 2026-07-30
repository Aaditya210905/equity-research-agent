"""
Report Generator — Phase 5

End-to-end research report generation:

    User Request
        |
        v
    1. Planner → creates structured plan
        |
        v
    2. Executor → calls tools, collects evidence
        |
        v
    3. Analyst → generates 7-section report
        |
        v
    4. Claim Extractor → breaks report into claims
        |
        v
    5. Verifier → checks every claim against evidence
        |
        v
    6. Reviser → adds disclaimers for unverified claims
        |
        v
    Final Verified Report + Execution Trace

This is the Chief Research Officer — the single entry point for
producing a verified equity research report.
"""

import logging
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def generate_research(
    request: str,
    companies: list[str] = None,
    year: int = None,
    skip_verification: bool = False,
) -> dict:
    """Generate a complete, verified equity research report.

    This is the top-level orchestrator that coordinates:
        Planning → Execution → Generation → Verification → Revision

    Parameters
    ----------
    request : str
        Natural language research request (e.g., "Analyze TCS from an investment perspective").
    companies : list[str], optional
        Override auto-detected company tickers.
    year : int, optional
        Fiscal year filter.
    skip_verification : bool
        Skip claim verification (faster but less reliable).

    Returns
    -------
    dict
        {
            "report": {...},            # Full research report
            "verification": {...},      # Claim verification results
            "trace": {...},             # Execution trace
        }
    """
    from planner.planner import create_plan
    from planner.executor import execute_plan
    from agents.equity_analyst import generate_report
    from verification.claim_extractor import extract_claims
    from verification.verifier import verify_claims, revise_report

    start = time.time()

    # --- Step 1: Plan ---
    logger.info("Step 1: Creating research plan")
    plan = create_plan(request, companies=companies, year=year)
    logger.info("Plan: type=%s, tools=%s", plan["request_type"], plan["required_tools"])

    # --- Step 2: Execute tools & collect evidence ---
    logger.info("Step 2: Executing plan (%d tools)", len(plan["required_tools"]))
    execution = execute_plan(plan)
    evidence = execution["evidence"]
    trace = execution["trace"]

    # --- Step 3: Generate report ---
    logger.info("Step 3: Generating report")
    report = generate_report(evidence)
    trace["sections_generated"] = report.get("sections_generated", 0)

    # --- Step 4 & 5: Verify (optional) ---
    verification = {}
    if not skip_verification:
        logger.info("Step 4: Extracting claims")
        claims = extract_claims(report)

        logger.info("Step 5: Verifying %d claims", len(claims))
        verification = verify_claims(claims, evidence)
        trace["verification"] = {
            "claims": verification["total_claims"],
            "verified": verification["verified"],
            "unverified": verification["unverified"],
            "verification_rate": verification["verification_rate"],
        }

        # --- Step 6: Revise ---
        if verification["unverified"] > 0:
            logger.info("Step 6: Revising %d unverified claims", verification["unverified"])
            report = revise_report(report, verification)
    else:
        trace["verification"] = {"skipped": True}

    elapsed = int((time.time() - start) * 1000)
    trace["duration_ms"] = elapsed
    trace["timestamp"] = datetime.now(timezone.utc).isoformat()

    logger.info("Research complete in %dms", elapsed)

    return {
        "report": report,
        "verification": verification,
        "trace": trace,
    }
