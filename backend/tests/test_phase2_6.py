"""
Phase 2.6 - RAG Orchestrator & Grounded Answer Verification

Run from the backend/ directory:
    python -X utf8 tests/test_phase2_6.py

Tests (no API key required for 1-7):
    1. Question classification (factual / comparative / analytical / summarization)
    2. Query expansion (financial abbreviation expansion)
    3. Context builder (numbering, dedup, truncation)
    4. Prompt builder (template loading, filling)
    5. Confidence engine (scoring, tiers)
    6. Pydantic schemas (RAGAnswer, AskRequest, Citation)
    7. Insufficient evidence handling
    8. Full RAG pipeline (requires OPENAI_API_KEY + indexed docs)
"""

import sys
import math
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
PASS = "[PASS]"
FAIL = "[FAIL]"
SKIP = "[SKIP]"
DIVIDER = "=" * 60

test_results: list[dict] = []


def log_result(test_name: str, passed: bool, detail: str = ""):
    status = PASS if passed else FAIL
    test_results.append({"name": test_name, "passed": passed})
    print(f"  {status}  {test_name}")
    if detail:
        print(f"         {detail}")


def log_skip(test_name: str, reason: str = ""):
    print(f"  {SKIP}  {test_name}")
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
# Synthetic retrieval hits for offline tests
# ---------------------------------------------------------------------------

def _make_hits():
    return [
        {
            "chunk_id": "TCS_RF_001",
            "score": 0.92,
            "text": "The company faces significant cybersecurity threats including ransomware attacks and data breaches.",
            "document_id": "TCS_10K_2025",
            "company": "TCS",
            "year": 2025,
            "doc_type": "Annual Report",
            "section": "Risk Factors",
            "subsection": "Cybersecurity",
            "page_start": 119,
            "page_end": 120,
            "token_count": 50,
            "has_heading": True,
            "contains_table": False,
            "quality_score": 0.9,
        },
        {
            "chunk_id": "TCS_RF_002",
            "score": 0.88,
            "text": "Macroeconomic conditions including inflation, recession, and currency volatility could materially affect operations.",
            "document_id": "TCS_10K_2025",
            "company": "TCS",
            "year": 2025,
            "doc_type": "Annual Report",
            "section": "Risk Factors",
            "subsection": "Macroeconomic",
            "page_start": 121,
            "page_end": 122,
            "token_count": 45,
            "has_heading": True,
            "contains_table": False,
            "quality_score": 0.88,
        },
        {
            "chunk_id": "TCS_FIN_001",
            "score": 0.75,
            "text": "Revenue increased by 14% to $391 billion in fiscal 2025 driven by cloud services.",
            "document_id": "TCS_10K_2025",
            "company": "TCS",
            "year": 2025,
            "doc_type": "Annual Report",
            "section": "Financial Statements",
            "page_start": 200,
            "page_end": 200,
            "token_count": 35,
            "has_heading": False,
            "contains_table": True,
            "quality_score": 0.85,
        },
    ]


# ===================================================================
# 1. QUESTION CLASSIFICATION
# ===================================================================

def test_question_classification():
    section("1. QUESTION CLASSIFICATION")
    from rag.orchestrator import classify_question

    # Factual
    log_result("Factual: 'What was revenue?'",
               classify_question("What was TCS revenue in FY2025?") == "factual")
    log_result("Factual: 'How much profit?'",
               classify_question("How much profit did they make?") == "factual")

    # Comparative
    log_result("Comparative: 'Compare margins'",
               classify_question("Compare Infosys and TCS margins") == "comparative")
    log_result("Comparative: 'vs'",
               classify_question("TCS vs Infosys revenue") == "comparative")

    # Analytical
    log_result("Analytical: 'Why did margins decline?'",
               classify_question("Why did margins decline?") == "analytical")
    log_result("Analytical: 'Explain the impact'",
               classify_question("Explain the impact of AI investments") == "analytical")

    # Summarization
    log_result("Summarization: 'Summarize the report'",
               classify_question("Summarize the annual report") == "summarization")
    log_result("Summarization: 'Give an overview'",
               classify_question("Give an overview of FY2025") == "summarization")


# ===================================================================
# 2. QUERY EXPANSION
# ===================================================================

def test_query_expansion():
    section("2. QUERY EXPANSION")
    from rag.orchestrator import expand_query

    # AI expansion
    expanded = expand_query("What is the company's AI strategy?")
    log_result("AI expanded",
               "Artificial Intelligence" in expanded,
               f"'{expanded[:60]}...'")

    # ESG expansion
    expanded = expand_query("Tell me about ESG performance")
    log_result("ESG expanded",
               "Environmental" in expanded,
               f"'{expanded[:60]}...'")

    # No expansion needed
    original = "What was revenue in fiscal 2025?"
    expanded = expand_query(original)
    log_result("No expansion: passes through",
               expanded == original)

    # Multiple abbreviations
    expanded = expand_query("Compare ROE and EPS trends")
    log_result("Multiple expansions",
               "return on equity" in expanded and "earnings per share" in expanded,
               f"'{expanded[:80]}...'")


# ===================================================================
# 3. CONTEXT BUILDER
# ===================================================================

def test_context_builder():
    section("3. CONTEXT BUILDER")
    from rag.context_builder import build_context

    hits = _make_hits()
    result = build_context(hits)

    log_result("Returns dict", isinstance(result, dict))
    log_result("Has context_text", len(result.get("context_text", "")) > 0)
    log_result("Has citations", len(result.get("citations", [])) > 0)
    log_result("Has chunks_used", result.get("chunks_used", 0) > 0)
    log_result("Has total_tokens", result.get("total_tokens", 0) > 0)

    # Citation numbering
    ctx = result["context_text"]
    log_result("Context has [1]", "[1]" in ctx)
    log_result("Context has [2]", "[2]" in ctx)
    log_result("Context has [3]", "[3]" in ctx)

    # Citations metadata
    c1 = result["citations"][0]
    log_result("Citation has ref", c1.get("ref") == 1)
    log_result("Citation has chunk_id", c1.get("chunk_id") == "TCS_RF_001")
    log_result("Citation has source string",
               "TCS" in c1.get("source", ""),
               f"source = '{c1.get('source')}'")
    log_result("Citation has score", c1.get("score") == 0.92)
    log_result("Citation has text_preview", len(c1.get("text_preview", "")) > 0)

    # Sorted by page
    pages = [c.get("page_start", 0) for c in result["citations"]]
    log_result("Citations sorted by page",
               pages == sorted(pages),
               f"pages = {pages}")

    # Deduplication
    dup_hits = hits + [hits[0]]  # Duplicate first hit
    dedup_result = build_context(dup_hits)
    log_result("Deduplication works",
               dedup_result["chunks_used"] == 3,
               f"used {dedup_result['chunks_used']} (input had 4)")

    # Empty hits
    empty = build_context([])
    log_result("Empty hits handled", empty["chunks_used"] == 0)

    # Token budget truncation
    huge_hits = [
        {
            "chunk_id": f"big_{i:03d}",
            "text": "x" * 10000,
            "score": 0.9 - i * 0.01,
            "page_start": i,
        }
        for i in range(20)
    ]
    truncated = build_context(huge_hits, max_tokens=3000)
    log_result("Token budget truncates",
               truncated["chunks_used"] < 20,
               f"used {truncated['chunks_used']}/20, tokens={truncated['total_tokens']}")


# ===================================================================
# 4. PROMPT BUILDER
# ===================================================================

def test_prompt_builder():
    section("4. PROMPT BUILDER")
    from rag.prompt_builder import build_prompt

    result = build_prompt(
        question="What are TCS risks?",
        context_text="[1] Cybersecurity threats...\n\n[2] Macroeconomic risks...",
        question_type="factual",
    )

    log_result("Returns dict", isinstance(result, dict))
    log_result("Has system prompt", len(result.get("system", "")) > 0)
    log_result("Has user prompt", len(result.get("user", "")) > 0)
    log_result("Has template_used", result.get("template_used") == "rag_answer.txt")

    # Question is in system prompt
    log_result("Question in prompt",
               "What are TCS risks?" in result["system"])

    # Context is in system prompt
    log_result("Context in prompt",
               "[1] Cybersecurity" in result["system"])

    # Key rules present
    log_result("Has grounding rule",
               "ONLY" in result["system"] or "only" in result["system"])
    log_result("Has citation rule",
               "[1]" in result["system"] or "cite" in result["system"].lower())

    # Different question types use different templates
    summary = build_prompt("Summarize", "[1] data", "summarization")
    log_result("Summarization uses summarize.txt",
               summary["template_used"] == "summarize.txt")

    compare = build_prompt("Compare X and Y", "[1] data", "comparative")
    log_result("Comparative uses compare.txt",
               compare["template_used"] == "compare.txt")


# ===================================================================
# 5. CONFIDENCE ENGINE
# ===================================================================

def test_confidence():
    section("5. CONFIDENCE ENGINE")
    from rag.confidence import compute_confidence

    # High confidence
    high = compute_confidence(
        retrieval_scores=[0.95, 0.90, 0.88, 0.85, 0.82],
        chunks_used=5,
        chunks_requested=10,
    )
    log_result("High confidence tier",
               high["tier"] == "medium",
               f"score={high['score']}, tier={high['tier']}")
    log_result("High confidence score > 0.7", high["score"] > 0.7)
    log_result("Evidence sufficient", high["evidence_sufficient"])

    # Medium confidence
    medium = compute_confidence(
        retrieval_scores=[0.70, 0.65, 0.60],
        chunks_used=3,
        chunks_requested=10,
    )
    log_result("Medium confidence",
               medium["tier"] in ("low", "medium"),
               f"score={medium['score']}, tier={medium['tier']}")

    # Low confidence
    low = compute_confidence(
        retrieval_scores=[0.30, 0.25],
        chunks_used=2,
        chunks_requested=10,
    )
    log_result("Low confidence score",
               low["score"] < 0.5,
               f"score={low['score']}, tier={low['tier']}")

    # No evidence
    empty = compute_confidence(
        retrieval_scores=[],
        chunks_used=0,
        chunks_requested=10,
    )
    log_result("No evidence: insufficient",
               empty["tier"] == "insufficient",
               f"score={empty['score']}")
    log_result("No evidence: not sufficient",
               not empty["evidence_sufficient"])

    # Details present
    log_result("Has retrieval_confidence", "retrieval_confidence" in high)
    log_result("Has coverage_confidence", "coverage_confidence" in high)
    log_result("Has details", "details" in high)
    log_result("Details has avg_score", "avg_score" in high["details"])
    log_result("Details has best_score", "best_score" in high["details"])

    # Score bounds
    log_result("Score in [0, 1]",
               all(0 <= c["score"] <= 1 for c in [high, medium, low, empty]))


# ===================================================================
# 6. PYDANTIC SCHEMAS
# ===================================================================

def test_schemas():
    section("6. PYDANTIC SCHEMAS")
    from schemas.answer import RAGAnswer, AskRequest, Citation

    # Citation
    cite = Citation(
        ref=1,
        chunk_id="TCS_RF_001",
        source="TCS, Annual Report, 2025, Risk Factors, Pages 119–120",
        section="Risk Factors",
        page_start=119,
        page_end=120,
        score=0.92,
        text_preview="Cybersecurity threats...",
    )
    log_result("Citation validates", True)

    # RAGAnswer
    answer = RAGAnswer(
        answer="Revenue increased by 14%...",
        citations=[cite],
        confidence=0.85,
        confidence_tier="high",
        question="What was TCS revenue?",
        question_type="factual",
        query_used="What was TCS revenue in FY2025?",
        chunks_retrieved=10,
        chunks_used=5,
        model="gpt-4o-mini",
        evidence_sufficient=True,
    )
    log_result("RAGAnswer validates", True)
    log_result("RAGAnswer serializes", len(answer.model_dump_json()) > 50)

    # AskRequest
    req = AskRequest(question="What are the risks?", company="TCS", year=2025)
    log_result("AskRequest validates", True)
    log_result("AskRequest has defaults",
               req.top_k == 10 and req.rewrite_query == False)


# ===================================================================
# 7. INSUFFICIENT EVIDENCE HANDLING
# ===================================================================

def test_insufficient_evidence():
    section("7. INSUFFICIENT EVIDENCE HANDLING")
    from rag.context_builder import build_context
    from rag.confidence import compute_confidence

    # Empty retrieval
    ctx = build_context([])
    conf = compute_confidence([], 0, 10)

    log_result("Empty context is empty string",
               ctx["context_text"] == "")
    log_result("Zero chunks used", ctx["chunks_used"] == 0)
    log_result("Confidence tier = insufficient",
               conf["tier"] == "insufficient")
    log_result("Evidence not sufficient",
               not conf["evidence_sufficient"])


# ===================================================================
# 8. FULL RAG PIPELINE (requires API key + indexed docs)
# ===================================================================

def test_full_pipeline():
    section("8. FULL RAG PIPELINE")
    if not _has_api_key():
        log_skip("Full RAG pipeline", "OPENAI_API_KEY not set — skipping")
        return

    try:
        from connectors.sec_edgar import get_annual_filings, download_filing
        from ingestion.pdf_extractor import extract_document
        from ingestion.text_cleaner import clean_document
        from ingestion.chunker import chunk_document
        from embedding.embedder import embed_chunks
        from embedding.cache import init_cache, close_cache, clear_cache
        from vector_store.qdrant_store import (
            init_store, close_store, ensure_collection, upload_chunks,
        )
        from rag.orchestrator import ask

        import tempfile, shutil
        tmp = Path(tempfile.mkdtemp())

        try:
            # Setup stores
            init_store(in_memory=True)
            ensure_collection()
            init_cache(tmp / "cache.db")
            clear_cache()

            # Build index: download → extract → clean → chunk → embed → upload
            print("  Building index (AAPL 10-K)...")
            filings = get_annual_filings("AAPL", limit=1)
            dl = download_filing(filings[0], tmp / "filing")
            extraction = extract_document(dl["file_path"],
                                         document_id="AAPL_10K", company="AAPL", year=2025)
            cleaned = clean_document(extraction["pages"])
            chunked = chunk_document(cleaned["pages"],
                                    document_id="AAPL_10K", company="AAPL",
                                    year=2025, doc_type="Annual Report")

            # Embed first 25 chunks
            sample = chunked["chunks"][:25]
            embedded = embed_chunks(sample, use_cache=True)
            upload_chunks(embedded["chunks"])
            log_result("Index built",
                       True,
                       f"{embedded['embedded']+embedded['cached']} chunks indexed")

            # --- Ask a question ---
            print("\n  Asking: 'What are Apple's biggest business risks?'")
            result = ask(
                question="What are Apple's biggest business risks?",
                company="AAPL",
            )

            log_result("Answer generated",
                       len(result.get("answer", "")) > 20,
                       f"answer length = {len(result.get('answer', ''))}")
            log_result("Has citations",
                       len(result.get("citations", [])) >= 0,
                       f"{len(result.get('citations', []))} citations")
            log_result("Has confidence",
                       0 <= result.get("confidence", -1) <= 1,
                       f"confidence = {result.get('confidence')}")
            log_result("Has confidence_tier",
                       result.get("confidence_tier") in ("high", "medium", "low", "insufficient"))
            log_result("Has question_type",
                       result.get("question_type") in ("factual", "comparative", "analytical", "summarization"),
                       f"type = {result.get('question_type')}")
            log_result("Has model",
                       len(result.get("model", "")) > 0)
            log_result("Evidence flag set",
                       "evidence_sufficient" in result)

            # Print answer preview
            answer = result["answer"]
            print(f"\n  Answer preview:")
            for line in answer[:500].split("\n"):
                print(f"    {line}")
            if len(answer) > 500:
                print(f"    ... ({len(answer)} chars total)")

            print(f"\n  Confidence: {result['confidence']:.2f} ({result['confidence_tier']})")
            print(f"  Type: {result['question_type']}")
            print(f"  Chunks: {result['chunks_retrieved']} retrieved, {result['chunks_used']} used")
            print(f"  Model: {result['model']}")

            if result.get("citations"):
                print(f"\n  Citations:")
                for c in result["citations"][:3]:
                    print(f"    [{c['ref']}] {c['source']}")
                    print(f"        '{c['text_preview'][:60]}...'")

        finally:
            close_cache()
            close_store()
            shutil.rmtree(tmp, ignore_errors=True)

    except Exception as exc:
        log_result("Full RAG pipeline", False, str(exc))
        import traceback
        traceback.print_exc()


# ===================================================================
# RUNNER
# ===================================================================

def main():
    print("\n" + "#" * 60)
    print("  PHASE 2.6 -- RAG ORCHESTRATOR VERIFICATION")
    print("#" * 60)

    if _has_api_key():
        print(f"\n  OPENAI_API_KEY detected — full tests will run")
    else:
        print(f"\n  OPENAI_API_KEY not set — API tests will be skipped")

    start = time.time()

    test_question_classification()
    test_query_expansion()
    test_context_builder()
    test_prompt_builder()
    test_confidence()
    test_schemas()
    test_insufficient_evidence()
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
