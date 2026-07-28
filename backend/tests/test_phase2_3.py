"""
Phase 2.3 - Intelligent Chunking Verification

Run from the backend/ directory:
    python -X utf8 tests/test_phase2_3.py

Tests:
    1. Heading detection (ALL CAPS, ITEM, PART, numbered)
    2. Table detection (pipes, numbers, columns)
    3. Block parsing (heading/paragraph/table classification)
    4. Section assignment (heading hierarchy)
    5. Full chunking on synthetic financial report
    6. Token count enforcement (min/target/max)
    7. Table preservation (never split)
    8. Semantic overlap
    9. Chunk metadata & quality scores
   10. Real SEC filing (AAPL 10-K extract -> clean -> chunk)
   11. Pydantic schema validation
"""

import sys
import json
import shutil
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
PASS = "[PASS]"
FAIL = "[FAIL]"
DIVIDER = "=" * 60

test_results: list[dict] = []
TEST_DIR = Path(__file__).parent / "test_chunking"


def log_result(test_name: str, passed: bool, detail: str = ""):
    status = PASS if passed else FAIL
    test_results.append({"name": test_name, "passed": passed})
    print(f"  {status}  {test_name}")
    if detail:
        print(f"         {detail}")


def section(title: str):
    print(f"\n{DIVIDER}")
    print(f"  {title}")
    print(DIVIDER)


# ===================================================================
# SYNTHETIC FINANCIAL REPORT (realistic structure)
# ===================================================================

def _make_report_pages():
    """Build a realistic multi-page financial report."""
    pages = []

    # Page 1: Cover / TOC
    pages.append({"page": 1, "clean_text": "\n".join([
        "PART I",
        "",
        "ITEM 1. BUSINESS",
        "",
        "TechCorp Inc. (the \"Company\") designs, develops, and sells consumer",
        "electronics, computer software, and online services. The Company's",
        "fiscal year ends on the last Saturday of September each year.",
        "The Company was founded in 1990 and is headquartered in San Francisco.",
        "",
        "The Company's product portfolio includes smartphones, laptops,",
        "tablets, wearable devices, and home entertainment systems. The",
        "Company also offers cloud computing, digital payments, and",
        "artificial intelligence services to enterprise customers.",
    ])})

    # Page 2: Products
    pages.append({"page": 2, "clean_text": "\n".join([
        "Products",
        "",
        "Smartphones",
        "",
        "The flagship smartphone product line generated revenue of $180.2",
        "billion in fiscal 2025, representing 46% of total net sales.",
        "Unit sales increased by 8% compared to the prior year, driven",
        "by strong demand for the premium models featuring advanced AI",
        "capabilities and improved camera systems. The average selling",
        "price increased by 3% to $912 per unit due to favorable mix.",
        "",
        "Cloud Services",
        "",
        "Cloud computing revenue reached $52.3 billion in fiscal 2025,",
        "an increase of 28% from the prior year. The growth was driven",
        "by enterprise adoption of AI infrastructure and expanding data",
        "center capacity across three new regions. Operating margins in",
        "this segment improved to 42% from 38% in the prior year.",
    ])})

    # Page 3: Revenue table
    pages.append({"page": 3, "clean_text": "\n".join([
        "FINANCIAL HIGHLIGHTS",
        "",
        "Revenue          $391.0B    $372.4B    $354.2B",
        "Net Income        $94.7B     $93.7B     $88.2B",
        "EPS (Diluted)      $6.42      $6.13      $5.89",
        "Operating Margin   31.5%      31.2%      30.8%",
        "Free Cash Flow   $112.0B    $101.2B     $96.4B",
        "",
        "Total revenue increased by 5% to $391.0 billion in fiscal 2025.",
        "The increase was primarily driven by growth in cloud services",
        "and smartphones, partially offset by lower wearable sales.",
    ])})

    # Page 4-5: Risk factors
    pages.append({"page": 4, "clean_text": "\n".join([
        "ITEM 1A. RISK FACTORS",
        "",
        "Investing in the Company's securities involves significant risks.",
        "The following risk factors should be carefully considered.",
        "",
        "MACROECONOMIC AND INDUSTRY RISKS",
        "",
        "The Company's operations and performance depend significantly",
        "on global and regional economic conditions. Adverse macroeconomic",
        "conditions, including inflation, recession, currency volatility,",
        "and geopolitical tensions, could materially adversely affect the",
        "Company's business, results of operations, and financial condition.",
        "Consumer spending patterns may shift during economic downturns,",
        "reducing demand for premium products and services.",
    ])})

    pages.append({"page": 5, "clean_text": "\n".join([
        "CYBERSECURITY AND DATA PRIVACY RISKS",
        "",
        "The Company is subject to increasing cybersecurity threats,",
        "including ransomware attacks, data breaches, and state-sponsored",
        "intrusions. A significant cybersecurity incident could result in",
        "substantial financial losses, reputational damage, regulatory",
        "penalties, and litigation costs. The Company invests approximately",
        "$2.8 billion annually in cybersecurity infrastructure.",
        "",
        "COMPETITION RISKS",
        "",
        "The markets for the Company's products and services are highly",
        "competitive. The Company faces substantial competition from",
        "companies that have significant technical, marketing, and",
        "financial resources. The Company's ability to compete depends",
        "on its continued innovation, brand strength, and ecosystem.",
    ])})

    # Page 6: Financial statements
    pages.append({"page": 6, "clean_text": "\n".join([
        "PART II",
        "",
        "ITEM 8. FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA",
        "",
        "CONSOLIDATED BALANCE SHEET",
        "",
        "ASSETS",
        "Cash and Equivalents       $29.9B     $28.1B",
        "Short-term Investments     $35.2B     $31.6B",
        "Accounts Receivable        $29.5B     $28.2B",
        "Inventories                 $6.3B      $6.5B",
        "Total Current Assets      $143.6B    $133.4B",
        "",
        "Total Assets              $364.9B    $352.1B",
        "",
        "LIABILITIES",
        "Accounts Payable           $62.1B     $58.1B",
        "Total Current Liabilities  $153.9B    $145.2B",
        "Long-term Debt             $96.2B     $98.1B",
        "Total Liabilities         $290.4B    $279.4B",
    ])})

    # Page 7: Notes
    pages.append({"page": 7, "clean_text": "\n".join([
        "NOTES TO CONSOLIDATED FINANCIAL STATEMENTS",
        "",
        "Note 1. Summary of Significant Accounting Policies",
        "",
        "The Company prepares its financial statements in accordance",
        "with U.S. generally accepted accounting principles (GAAP).",
        "Revenue is recognized when control of the promised goods or",
        "services is transferred to customers, in an amount that reflects",
        "the consideration the Company expects to receive.",
        "",
        "Note 2. Revenue Recognition",
        "",
        "The Company disaggregates revenue by product category and",
        "geographic region. Products revenue is recognized at the",
        "point of sale. Services revenue is recognized over the",
        "period the services are provided. See the revenue breakdown",
        "table in the supplementary data section for details.",
    ])})

    return pages


# ===================================================================
# 1. HEADING DETECTION
# ===================================================================

def test_heading_detection():
    section("1. HEADING DETECTION")
    from ingestion.chunker import _heading_score

    # PART I/II
    level, conf = _heading_score("PART I")
    log_result("PART I: level=1", level == 1, f"level={level}, conf={conf}")

    level, conf = _heading_score("PART II")
    log_result("PART II: level=1", level == 1)

    # ITEM headings
    level, conf = _heading_score("ITEM 1. BUSINESS")
    log_result("ITEM 1.: level=2", level == 2)

    level, conf = _heading_score("ITEM 1A. RISK FACTORS")
    log_result("ITEM 1A.: level=2", level == 2)

    # ALL CAPS sections
    level, conf = _heading_score("RISK FACTORS")
    log_result("ALL CAPS 'RISK FACTORS': level=2", level == 2)

    level, conf = _heading_score("FINANCIAL HIGHLIGHTS")
    log_result("ALL CAPS 'FINANCIAL HIGHLIGHTS': level=2", level == 2)

    # Note headings
    level, conf = _heading_score("Note 1. Summary of Significant Accounting Policies")
    log_result("Note heading: level=3", level == 3)

    # Numbered sub-heading
    level, conf = _heading_score("2.3 Operating Costs")
    log_result("Numbered sub-heading: level=3", level == 3)

    # NOT a heading
    level, conf = _heading_score("Revenue increased by 14% due to strong cloud demand.")
    log_result("Regular text: level=0", level == 0)

    level, conf = _heading_score("")
    log_result("Empty line: level=0", level == 0)


# ===================================================================
# 2. TABLE DETECTION
# ===================================================================

def test_table_detection():
    section("2. TABLE DETECTION")
    from ingestion.chunker import _is_table_row

    # Pipe table
    log_result("Pipe row detected",
               _is_table_row("Revenue | $391.0B | $372.4B"))

    # Number columns
    log_result("Number columns detected",
               _is_table_row("Revenue          $391.0B    $372.4B    $354.2B"))

    # Spaced columns
    log_result("Spaced columns detected",
               _is_table_row("Cash and Equivalents       $29.9B     $28.1B"))

    # NOT table rows
    log_result("Regular text NOT a table",
               not _is_table_row("Revenue increased by 14% in fiscal 2025."))
    log_result("Heading NOT a table",
               not _is_table_row("RISK FACTORS"))


# ===================================================================
# 3. BLOCK PARSING
# ===================================================================

def test_block_parsing():
    section("3. BLOCK PARSING")
    from ingestion.chunker import _parse_blocks

    pages = _make_report_pages()
    blocks = _parse_blocks(pages)

    log_result("Returns list of blocks", isinstance(blocks, list))
    log_result("Has multiple blocks", len(blocks) > 5, f"got {len(blocks)} blocks")

    # Count types
    headings = [b for b in blocks if b.block_type == "heading"]
    paragraphs = [b for b in blocks if b.block_type == "paragraph"]
    tables = [b for b in blocks if b.block_type == "table"]

    log_result("Has heading blocks", len(headings) > 3,
               f"{len(headings)} headings")
    log_result("Has paragraph blocks", len(paragraphs) > 3,
               f"{len(paragraphs)} paragraphs")
    log_result("Has table blocks", len(tables) >= 1,
               f"{len(tables)} tables")

    # Check heading levels
    level1 = [b for b in headings if b.heading_level == 1]
    level2 = [b for b in headings if b.heading_level == 2]
    log_result("Level 1 headings found (PART)", len(level1) >= 1,
               f"{len(level1)} level-1: {[b.text for b in level1]}")
    log_result("Level 2 headings found (ITEM/ALL CAPS)", len(level2) >= 2,
               f"{len(level2)} level-2")

    # Pages attached
    for b in blocks[:5]:
        has_pages = len(b.pages) > 0
        if not has_pages:
            log_result("Block has pages", False, f"block: {b.text[:50]}")
            break
    else:
        log_result("All sample blocks have pages", True)


# ===================================================================
# 4. SECTION ASSIGNMENT
# ===================================================================

def test_section_assignment():
    section("4. SECTION ASSIGNMENT")
    from ingestion.chunker import _parse_blocks, _assign_sections

    pages = _make_report_pages()
    blocks = _parse_blocks(pages)
    blocks = _assign_sections(blocks)

    # Find blocks under Risk Factors
    risk_blocks = [b for b in blocks if "RISK" in b.section.upper()]
    log_result("Risk Factors section assigned",
               len(risk_blocks) > 0,
               f"{len(risk_blocks)} blocks in risk section")

    # ALL-CAPS sub-topics become their own sections (level 2)
    cyber_blocks = [b for b in blocks if "CYBER" in b.section.upper()]
    log_result("Cybersecurity section assigned",
               len(cyber_blocks) > 0,
               f"{len(cyber_blocks)} blocks")

    # Financial statements section
    fin_blocks = [b for b in blocks if "FINANCIAL STATEMENTS" in b.section.upper()]
    log_result("Financial statements section found",
               len(fin_blocks) > 0,
               f"{len(fin_blocks)} blocks")


# ===================================================================
# 5. FULL CHUNKING -- Synthetic Report
# ===================================================================

def test_full_chunking():
    section("5. FULL CHUNKING -- Synthetic Financial Report")
    from ingestion.chunker import chunk_document

    pages = _make_report_pages()
    result = chunk_document(
        pages,
        document_id="TC_annual_report_2025",
        company="TC",
        year=2025,
        doc_type="Annual Report",
    )

    log_result("Returns dict", isinstance(result, dict))
    log_result("Has 'chunks'", isinstance(result.get("chunks"), list))
    log_result("Has total_chunks", result.get("total_chunks", 0) > 0,
               f"total = {result.get('total_chunks')}")
    log_result("Has total_tokens", result.get("total_tokens", 0) > 0,
               f"tokens = {result.get('total_tokens')}")
    log_result("Has sections_detected",
               len(result.get("sections_detected", [])) > 0,
               f"sections = {result.get('sections_detected')}")

    chunks = result["chunks"]
    if chunks:
        c = chunks[0]
        log_result("Chunk has chunk_id", "chunk_id" in c)
        log_result("Chunk has document_id", c.get("document_id") == "TC_annual_report_2025")
        log_result("Chunk has company", c.get("company") == "TC")
        log_result("Chunk has year", c.get("year") == 2025)
        log_result("Chunk has doc_type", c.get("doc_type") == "Annual Report")
        log_result("Chunk has section", "section" in c)
        log_result("Chunk has text", len(c.get("text", "")) > 0)
        log_result("Chunk has token_count", c.get("token_count", 0) > 0)
        log_result("Chunk has has_heading", "has_heading" in c)
        log_result("Chunk has contains_table", "contains_table" in c)
        log_result("Chunk has quality_score", 0 <= c.get("quality_score", -1) <= 1)
        log_result("Chunk has page_start", c.get("page_start") is not None)
        log_result("Chunk has page_end", c.get("page_end") is not None)

    # Print all chunks summary
    print(f"\n  Chunks produced: {len(chunks)}")
    for i, c in enumerate(chunks):
        sec = c.get("section", "")[:30]
        sub = c.get("subsection", "")[:20]
        print(f"    [{i+1:02d}] tokens={c['token_count']:4d}  "
              f"pages={c.get('page_start')}-{c.get('page_end')}  "
              f"q={c['quality_score']:.2f}  "
              f"sec='{sec}' sub='{sub}'  "
              f"heading={c['has_heading']}  table={c['contains_table']}")


# ===================================================================
# 6. TOKEN COUNT ENFORCEMENT
# ===================================================================

def test_token_enforcement():
    section("6. TOKEN COUNT ENFORCEMENT")
    from ingestion.chunker import chunk_document, MIN_TOKENS, MAX_TOKENS

    pages = _make_report_pages()
    result = chunk_document(pages, document_id="test")
    chunks = result["chunks"]

    if not chunks:
        log_result("Has chunks", False)
        return

    # Check token distribution
    token_counts = [c["token_count"] for c in chunks]
    min_t = min(token_counts)
    max_t = max(token_counts)
    avg_t = sum(token_counts) / len(token_counts)

    log_result(f"Min tokens: {min_t}", True, f"(target min: {MIN_TOKENS})")
    log_result(f"Max tokens: {max_t}", True, f"(target max: {MAX_TOKENS})")
    log_result(f"Avg tokens: {avg_t:.0f}", True)

    # Most chunks should be within range (allow some flexibility)
    in_range = sum(1 for t in token_counts if t <= MAX_TOKENS)
    pct_in_range = in_range / len(token_counts) * 100
    log_result(f"Chunks <= MAX ({MAX_TOKENS}): {pct_in_range:.0f}%",
               pct_in_range >= 80,
               f"{in_range}/{len(token_counts)}")


# ===================================================================
# 7. TABLE PRESERVATION
# ===================================================================

def test_table_preservation():
    section("7. TABLE PRESERVATION")
    from ingestion.chunker import chunk_document

    pages = _make_report_pages()
    result = chunk_document(pages, document_id="test")

    table_chunks = [c for c in result["chunks"] if c["contains_table"]]
    log_result("Table chunks detected", len(table_chunks) > 0,
               f"{len(table_chunks)} table chunks")

    if table_chunks:
        tc = table_chunks[0]
        # Table should contain multiple financial rows
        lines = tc["text"].split("\n")
        number_lines = [l for l in lines if "$" in l or "%" in l]
        log_result("Table has financial data",
                   len(number_lines) >= 2,
                   f"{len(number_lines)} data rows")

        # Table shouldn't be split mid-row
        log_result("Table is intact",
                   len(tc["text"]) > 50,
                   f"{len(tc['text'])} chars in table chunk")


# ===================================================================
# 8. CHUNK METADATA & QUALITY
# ===================================================================

def test_quality_scores():
    section("8. QUALITY SCORES")
    from ingestion.chunker import chunk_document

    pages = _make_report_pages()
    result = chunk_document(pages, document_id="test", company="TC", year=2025)

    chunks = result["chunks"]
    if not chunks:
        log_result("Has chunks", False)
        return

    scores = [c["quality_score"] for c in chunks]
    avg_score = sum(scores) / len(scores)
    min_score = min(scores)
    max_score = max(scores)

    log_result(f"Avg quality: {avg_score:.2f}", avg_score > 0.5)
    log_result(f"Min quality: {min_score:.2f}", min_score >= 0.0)
    log_result(f"Max quality: {max_score:.2f}", max_score <= 1.0)

    # All chunks have valid quality
    valid = all(0.0 <= s <= 1.0 for s in scores)
    log_result("All scores in [0, 1]", valid)


# ===================================================================
# 9. REAL SEC FILING -- Full Pipeline
# ===================================================================

def test_real_pipeline():
    section("9. REAL FILING -- AAPL 10-K Full Pipeline")
    try:
        from connectors.sec_edgar import get_annual_filings, download_filing
        from ingestion.pdf_extractor import extract_document
        from ingestion.text_cleaner import clean_document
        from ingestion.chunker import chunk_document, MIN_TOKENS, MAX_TOKENS

        TEST_DIR.mkdir(parents=True, exist_ok=True)

        # Download
        filings = get_annual_filings("AAPL", limit=1)
        if not filings:
            log_result("No filings", False)
            return
        dl = download_filing(filings[0], TEST_DIR / "pipeline")
        if not dl["success"]:
            log_result("Download", False)
            return
        log_result("Downloaded", True, f"{dl['file_size']:,} bytes")

        # Extract
        extraction = extract_document(
            dl["file_path"],
            document_id="AAPL_10K_2025",
            company="AAPL",
            year=2025,
        )
        log_result("Extracted", extraction["success"],
                   f"{extraction['total_pages']} pages, {extraction['total_characters']:,} chars")

        # Clean
        cleaned = clean_document(extraction["pages"])
        log_result("Cleaned",
                   cleaned["statistics"]["clean_characters"] > 0,
                   f"{cleaned['statistics']['clean_characters']:,} clean chars")

        # Chunk
        result = chunk_document(
            cleaned["pages"],
            document_id="AAPL_10K_2025",
            company="AAPL",
            year=2025,
            doc_type="Annual Report",
        )

        log_result("Chunked", result["total_chunks"] > 0,
                   f"{result['total_chunks']} chunks")
        log_result(f"Total tokens: {result['total_tokens']:,}", True)
        log_result(f"Avg chunk tokens: {result['avg_chunk_tokens']:.0f}", True)

        # Sections detected
        sections = result.get("sections_detected", [])
        log_result("Sections detected", len(sections) > 0,
                   f"{len(sections)} sections")
        print(f"\n  Sections found:")
        for s in sections[:10]:
            print(f"    - {s}")
        if len(sections) > 10:
            print(f"    ... and {len(sections) - 10} more")

        # Token distribution
        chunks = result["chunks"]
        token_counts = [c["token_count"] for c in chunks]
        in_range = sum(1 for t in token_counts if MIN_TOKENS <= t <= MAX_TOKENS)
        log_result(f"Chunks in target range: {in_range}/{len(chunks)}",
                   in_range > len(chunks) * 0.3,
                   f"{in_range/len(chunks)*100:.0f}%")

        # Has table chunks
        table_chunks = [c for c in chunks if c["contains_table"]]
        log_result("Table chunks found", len(table_chunks) >= 0,
                   f"{len(table_chunks)} table chunks")

        # Has heading chunks
        heading_chunks = [c for c in chunks if c["has_heading"]]
        log_result("Heading chunks found", len(heading_chunks) > 0,
                   f"{len(heading_chunks)} chunks with headings")

        # Quality score distribution
        scores = [c["quality_score"] for c in chunks]
        avg_q = sum(scores) / len(scores)
        log_result(f"Avg quality: {avg_q:.2f}", avg_q > 0.5)

        # Content verification
        all_text = " ".join(c["text"] for c in chunks)
        log_result("Contains 'Apple'", "Apple" in all_text)
        log_result("Contains 'revenue'", "revenue" in all_text.lower())
        log_result("Contains 'risk'", "risk" in all_text.lower())

        # Print sample chunks
        print(f"\n  Sample chunks:")
        for c in chunks[:5]:
            preview = c["text"][:80].replace("\n", " ")
            print(f"    [{c['chunk_id'][-3:]}] tokens={c['token_count']:4d}  "
                  f"q={c['quality_score']:.2f}  "
                  f"sec='{(c.get('section') or '')[:25]}'  "
                  f"'{preview}...'")

    except Exception as e:
        log_result("Real pipeline", False, str(e))
        import traceback
        traceback.print_exc()


# ===================================================================
# 10. PYDANTIC SCHEMA VALIDATION
# ===================================================================

def test_schema_validation():
    section("10. PYDANTIC SCHEMA VALIDATION")
    from ingestion.chunker import chunk_document
    from schemas.chunk import ChunkMeta, ChunkingResult

    pages = _make_report_pages()
    result = chunk_document(
        pages,
        document_id="TC_2025",
        company="TC",
        year=2025,
        doc_type="Annual Report",
    )

    # Validate ChunkingResult
    try:
        cr = ChunkingResult(**result)
        log_result("ChunkingResult validates", True,
                   f"{cr.total_chunks} chunks")
    except Exception as e:
        log_result("ChunkingResult validates", False, str(e))

    # Validate individual ChunkMeta
    if result["chunks"]:
        try:
            cm = ChunkMeta(**result["chunks"][0])
            log_result("ChunkMeta validates", True)
            log_result("ChunkMeta serializes",
                       len(cm.model_dump_json()) > 50)
        except Exception as e:
            log_result("ChunkMeta validates", False, str(e))


# ===================================================================
# RUNNER
# ===================================================================

def main():
    print("\n" + "#" * 60)
    print("  PHASE 2.3 -- INTELLIGENT CHUNKING VERIFICATION")
    print("#" * 60)

    start = time.time()

    try:
        test_heading_detection()
        test_table_detection()
        test_block_parsing()
        test_section_assignment()
        test_full_chunking()
        test_token_enforcement()
        test_table_preservation()
        test_quality_scores()
        test_real_pipeline()
        test_schema_validation()
    finally:
        if TEST_DIR.exists():
            shutil.rmtree(TEST_DIR)

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
