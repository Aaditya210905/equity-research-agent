"""
Phase 2.2 - Text Cleaning & Normalization Verification

Run from the backend/ directory:
    python -X utf8 tests/test_phase2_2.py

Tests:
    1. Individual cleaning functions (unit tests)
    2. Frequency-based header/footer detection
    3. Broken line merging (preserves structure)
    4. Full cleaning pipeline on synthetic financial report
    5. Real SEC filing extraction + cleaning (AAPL 10-K)
    6. Processing metadata and statistics
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
TEST_DIR = Path(__file__).parent / "test_cleaning"


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
# 1. INDIVIDUAL CLEANING FUNCTIONS
# ===================================================================

def test_normalize_unicode():
    section("1a. normalize_unicode")
    from ingestion.text_cleaner import normalize_unicode

    # Decomposed e-acute -> composed
    decomposed = "caf\u0065\u0301"  # e + combining acute
    result = normalize_unicode(decomposed)
    log_result("Composes decomposed chars", "\u00e9" in result, f"'{decomposed}' -> '{result}'")

    # Preserves currency symbols
    currencies = "$100 EUR200 \u20b950,000 \u00a5300"
    result = normalize_unicode(currencies)
    log_result("Preserves currency symbols", result == currencies)

    # Preserves normal text
    normal = "Revenue increased by 14%."
    log_result("Normal text unchanged", normalize_unicode(normal) == normal)


def test_remove_control_characters():
    section("1b. remove_control_characters")
    from ingestion.text_cleaner import remove_control_characters

    # Strips null bytes
    text = "Revenue\x00 was $100M"
    result = remove_control_characters(text)
    log_result("Removes null bytes", "\x00" not in result and "Revenue" in result)

    # Preserves newlines and tabs
    text = "Line 1\nLine 2\tValue"
    result = remove_control_characters(text)
    log_result("Preserves newlines", "\n" in result)
    log_result("Preserves tabs", "\t" in result)

    # Strips bell character
    text = "Data\x07 here"
    result = remove_control_characters(text)
    log_result("Removes bell char", "\x07" not in result)


def test_remove_xbrl_artifacts():
    section("1c. remove_xbrl_artifacts")
    from ingestion.text_cleaner import remove_xbrl_artifacts

    text = "\n".join([
        "aapl-20250927",
        "false",
        "2025",
        "FY",
        "0000320193",
        "P1Y",
        "http://fasb.org/us-gaap/2025#LongTermDebtNoncurrent",
        "http://xbrl.org/2006/xbrldi",
        "",
        "APPLE INC.",
        "Revenue was $391 billion.",
        "https://www.apple.com",
    ])

    result = remove_xbrl_artifacts(text)
    log_result("Removes EDGAR file IDs", "aapl-20250927" not in result)
    log_result("Removes boolean strings", "\nfalse\n" not in result)
    log_result("Removes padded CIK", "0000320193" not in result)
    log_result("Removes duration patterns", "P1Y" not in result)
    log_result("Removes FASB URLs", "fasb.org" not in result)
    log_result("Removes XBRL URLs", "xbrl.org" not in result)
    log_result("Keeps company name", "APPLE INC." in result)
    log_result("Keeps financial data", "Revenue was $391 billion." in result)
    log_result("Removes standalone URLs", "https://www.apple.com" not in result)
    log_result("Keeps blank lines", "\n\n" in result or result.count("\n") >= 2)


def test_normalize_whitespace():
    section("1d. normalize_whitespace")
    from ingestion.text_cleaner import normalize_whitespace

    text = "Revenue   was    $100M\tand\t\tgrew   12%"
    result = normalize_whitespace(text)
    log_result("Collapses multiple spaces", "  " not in result)
    log_result("Tabs converted to space", "\t" not in result)
    log_result("Content preserved", "Revenue" in result and "$100M" in result)

    # Trailing whitespace
    text = "Line 1   \nLine 2  \n"
    result = normalize_whitespace(text)
    lines = result.split("\n")
    trailing = any(l.endswith(" ") for l in lines)
    log_result("Trailing whitespace removed", not trailing)


def test_remove_page_numbers():
    section("1e. remove_page_numbers")
    from ingestion.text_cleaner import remove_page_numbers

    text = "\n".join([
        "Revenue was $100M.",
        "154",
        "Page 155",
        "Page 12 of 300",
        "- 156 -",
        "xiv",
        "The margin improved.",
        "12345678",  # Not a page number (too many digits)
    ])
    result = remove_page_numbers(text)
    log_result("Removes plain number", "\n154\n" not in result)
    log_result("Removes 'Page N'", "Page 155" not in result)
    log_result("Removes 'Page N of M'", "Page 12 of 300" not in result)
    log_result("Removes '- N -'", "- 156 -" not in result)
    log_result("Removes roman numerals", "\nxiv\n" not in result)
    log_result("Keeps content lines", "Revenue was $100M." in result)
    log_result("Keeps long numbers", "12345678" in result)
    log_result("Keeps normal text", "margin improved" in result)


# ===================================================================
# 2. HEADER/FOOTER DETECTION (frequency-based)
# ===================================================================

def _make_synthetic_pages(num_pages=30):
    """Create realistic financial report pages with headers/footers."""
    pages = []
    for i in range(1, num_pages + 1):
        lines = [
            "INFOSYS LIMITED",
            "Annual Report 2025",
            "",
        ]

        # Vary content per page
        if i % 5 == 0:
            lines.extend([
                "RISK FACTORS",
                "",
                "The company faces several key risks including:",
                "- Cybersecurity threats",
                "- Currency fluctuation",
                f"- Market competition in {['cloud', 'AI', 'consulting'][i % 3]} services",
            ])
        elif i % 3 == 0:
            lines.extend([
                f"Revenue for Q{(i % 4) + 1} was INR {50000 + i * 100} crore,",
                f"representing a growth of {10 + i % 5}% year-over-year.",
                f"Operating margin stood at {22 + i % 3}%.",
            ])
        else:
            lines.extend([
                "The company continued to invest in digital transformation",
                f"initiatives across {i} markets globally. Client additions",
                "remained strong with several large deal wins.",
            ])

        lines.extend([
            "",
            f"Page {i}",
        ])

        pages.append({
            "page": i,
            "text": "\n".join(lines),
        })

    return pages


def test_header_detection():
    section("2a. HEADER DETECTION")
    from ingestion.text_cleaner import detect_repeated_headers

    pages = _make_synthetic_pages(30)

    headers = detect_repeated_headers(pages, top_n_lines=3, threshold=0.4)
    log_result("Returns a list", isinstance(headers, list))
    log_result("Detected headers", len(headers) > 0, f"found {len(headers)}")

    # "INFOSYS LIMITED" should be detected (appears on all pages)
    # After digit normalization it stays the same (no digits)
    has_company = any("INFOSYS" in h for h in headers)
    log_result("Detected company name header", has_company, f"headers = {headers}")

    # "Annual Report 2025" -> "Annual Report #" after normalization
    has_annual = any("Annual Report" in h for h in headers)
    log_result("Detected annual report header", has_annual)


def test_footer_detection():
    section("2b. FOOTER DETECTION")
    from ingestion.text_cleaner import detect_repeated_footers

    pages = _make_synthetic_pages(30)

    footers = detect_repeated_footers(pages, bottom_n_lines=3, threshold=0.4)
    log_result("Returns a list", isinstance(footers, list))
    log_result("Detected footers", len(footers) > 0, f"found {len(footers)}")

    # "Page N" -> "Page #" should be detected
    has_page = any("Page" in f for f in footers)
    log_result("Detected 'Page N' footer", has_page, f"footers = {footers}")


def test_header_removal():
    section("2c. HEADER/FOOTER REMOVAL")
    from ingestion.text_cleaner import (
        detect_repeated_headers, detect_repeated_footers, remove_repeated_lines,
    )

    pages = _make_synthetic_pages(30)
    headers = detect_repeated_headers(pages)
    footers = detect_repeated_footers(pages)

    # Clean one page
    sample_page = pages[0]["text"]
    cleaned = remove_repeated_lines(sample_page, headers)
    cleaned = remove_repeated_lines(cleaned, footers)

    log_result("Header removed from page", "INFOSYS LIMITED" not in cleaned)
    log_result("Content preserved", "company" in cleaned.lower() or "invest" in cleaned.lower())


# ===================================================================
# 3. BROKEN LINE MERGING
# ===================================================================

def test_broken_line_merging():
    section("3. BROKEN LINE MERGING")
    from ingestion.text_cleaner import fix_broken_lines

    # Basic merge: line ends mid-sentence, next starts lowercase
    text = "Revenue increased by 14% due to strong demand from\ncloud computing services across all geographies."
    result = fix_broken_lines(text)
    log_result("Merges broken sentence",
               "demand from cloud computing" in result,
               f"result = '{result[:80]}...'")

    # Should NOT merge headings
    text = "RISK FACTORS\nThe company faces several risks."
    result = fix_broken_lines(text)
    log_result("Preserves headings",
               "RISK FACTORS\n" in result,
               f"result = '{result}'")

    # Should NOT merge bullet points
    text = "Key highlights:\n- Revenue grew 14%\n- Margins improved"
    result = fix_broken_lines(text)
    log_result("Preserves bullet lists",
               "- Revenue grew" in result and "- Margins" in result)

    # Should NOT merge after terminal punctuation
    text = "Revenue grew 14%.\nOperating margin improved."
    result = fix_broken_lines(text)
    log_result("Doesn't merge after period",
               "14%.\n" in result or "14%.\r\n" in result or result.count("\n") >= 1)

    # Should NOT merge short lines (likely headings)
    text = "Risk Factors\nThe company faces..."
    result = fix_broken_lines(text)
    log_result("Preserves short lines (headings)",
               "Risk Factors\n" in result)

    # Should NOT merge table rows
    text = "Revenue  $100M  $90M  $80M\nProfit   $20M   $18M  $16M"
    result = fix_broken_lines(text)
    log_result("Preserves table rows",
               result.count("\n") >= 1)

    # Numbered list items
    text = "Key factors:\n1. Revenue growth\n2. Margin expansion"
    result = fix_broken_lines(text)
    log_result("Preserves numbered lists",
               "1. Revenue" in result and "2. Margin" in result)


# ===================================================================
# 4. FULL PIPELINE -- Synthetic Financial Report
# ===================================================================

def test_full_pipeline_synthetic():
    section("4. FULL PIPELINE -- Synthetic Financial Report")
    from ingestion.text_cleaner import clean_document

    pages = _make_synthetic_pages(30)

    result = clean_document(pages)

    log_result("Returns dict", isinstance(result, dict))
    log_result("Has 'pages'", "pages" in result)
    log_result("Has 'statistics'", "statistics" in result)
    log_result("Has 'cleaning_version'", result.get("cleaning_version") == "v1")

    # Pages
    cleaned_pages = result["pages"]
    log_result("Same page count", len(cleaned_pages) == 30)

    if cleaned_pages:
        p = cleaned_pages[0]
        log_result("Page has 'raw_text'", "raw_text" in p)
        log_result("Page has 'clean_text'", "clean_text" in p)
        log_result("Page has 'char_count_raw'", "char_count_raw" in p)
        log_result("Page has 'char_count_clean'", "char_count_clean" in p)
        log_result("Page has 'cleaning_version'", p.get("cleaning_version") == "v1")

        # Headers should be removed from clean text
        has_header = any("INFOSYS LIMITED" in p["clean_text"] for p in cleaned_pages)
        log_result("Headers removed from all pages", not has_header)

        # Content should be preserved
        has_content = any("invest" in p["clean_text"].lower() or
                         "revenue" in p["clean_text"].lower() or
                         "risk" in p["clean_text"].lower()
                         for p in cleaned_pages)
        log_result("Content preserved in cleaned pages", has_content)

        # Financial values preserved
        has_numbers = any("INR" in p["clean_text"] or "crore" in p["clean_text"]
                         for p in cleaned_pages)
        log_result("Financial values preserved", has_numbers)

    # Statistics
    stats = result["statistics"]
    log_result("Stats: total_pages", stats["total_pages"] == 30)
    log_result("Stats: raw_characters > 0", stats["raw_characters"] > 0,
               f"raw = {stats['raw_characters']:,}")
    log_result("Stats: clean_characters > 0", stats["clean_characters"] > 0,
               f"clean = {stats['clean_characters']:,}")
    log_result("Stats: reduction occurred",
               stats["reduction_pct"] > 0,
               f"reduction = {stats['reduction_pct']}%")
    log_result("Stats: headers detected",
               len(stats["headers_detected"]) > 0,
               f"headers = {stats['headers_detected']}")
    log_result("Stats: footers detected",
               len(stats["footers_detected"]) > 0,
               f"footers = {stats['footers_detected']}")

    print(f"\n  Cleaning statistics:")
    print(f"    Raw chars:    {stats['raw_characters']:>10,}")
    print(f"    Clean chars:  {stats['clean_characters']:>10,}")
    print(f"    Reduction:    {stats['reduction_pct']:>9}%")
    print(f"    Headers:      {stats['headers_detected']}")
    print(f"    Footers:      {stats['footers_detected']}")


# ===================================================================
# 5. REAL SEC FILING -- Extract + Clean AAPL 10-K
# ===================================================================

def test_real_filing():
    section("5. REAL SEC FILING -- AAPL 10-K Extract + Clean")
    try:
        from connectors.sec_edgar import get_annual_filings, download_filing
        from ingestion.pdf_extractor import extract_document
        from ingestion.text_cleaner import clean_document

        TEST_DIR.mkdir(parents=True, exist_ok=True)

        # Download one filing
        filings = get_annual_filings("AAPL", limit=1)
        if not filings:
            log_result("No AAPL filings", False)
            return

        filing = filings[0]
        save_dir = TEST_DIR / "real_filing"
        dl = download_filing(filing, save_dir)

        if not dl["success"]:
            log_result("Filing download", False, dl.get("error", ""))
            return

        log_result("Filing downloaded", True,
                   f"{dl['file_size']:,} bytes")

        # Extract
        extraction = extract_document(
            dl["file_path"],
            document_id="AAPL_annual_report_2025_sec",
            company="Apple Inc.",
            year=2025,
        )
        log_result("Extraction succeeded", extraction["success"],
                   f"{extraction['total_pages']} pages, {extraction['total_characters']:,} chars")

        # Clean
        cleaned = clean_document(extraction["pages"])
        stats = cleaned["statistics"]

        log_result("Cleaning succeeded", len(cleaned["pages"]) > 0)
        log_result("Character reduction occurred",
                   stats["reduction_pct"] > 0,
                   f"{stats['reduction_pct']}% reduction")
        log_result("Clean chars > 0",
                   stats["clean_characters"] > 0,
                   f"raw={stats['raw_characters']:,} -> clean={stats['clean_characters']:,}")

        # Verify content quality in cleaned text
        all_clean_text = " ".join(p["clean_text"] for p in cleaned["pages"])
        log_result("Contains 'Apple'", "Apple" in all_clean_text or "apple" in all_clean_text.lower())
        log_result("Contains 'revenue'", "revenue" in all_clean_text.lower())
        log_result("Contains 'risk'", "risk" in all_clean_text.lower())

        # XBRL artifacts should be removed
        has_fasb = "http://fasb.org" in all_clean_text
        log_result("XBRL artifacts removed", not has_fasb)

        # Headers/footers detected
        log_result("Headers analyzed",
                   isinstance(stats["headers_detected"], list))
        log_result("Footers analyzed",
                   isinstance(stats["footers_detected"], list))

        # Processing metadata on pages
        if cleaned["pages"]:
            p = cleaned["pages"][0]
            log_result("Page has raw_text", len(p.get("raw_text", "")) > 0)
            log_result("Page has clean_text", isinstance(p.get("clean_text"), str))
            log_result("Page has cleaning_version", p.get("cleaning_version") == "v1")
            log_result("Page has char_count_raw", p.get("char_count_raw", 0) > 0)
            log_result("Page has char_count_clean", isinstance(p.get("char_count_clean"), int))

        # Print sample
        if cleaned["pages"]:
            # Find a page with actual content (skip near-empty pages)
            content_pages = [p for p in cleaned["pages"]
                           if len(p["clean_text"].strip()) > 100]
            if content_pages:
                sample = content_pages[min(5, len(content_pages) - 1)]
                print(f"\n  Sample cleaned page {sample.get('page', '?')}:")
                print(f"    Raw chars:   {sample['char_count_raw']}")
                print(f"    Clean chars: {sample['char_count_clean']}")
                print(f"    Text preview:")
                preview = sample["clean_text"][:400].replace("\n", "\n    ")
                print(f"    {preview}...")

        print(f"\n  Overall statistics:")
        print(f"    Pages:        {stats['total_pages']}")
        print(f"    Raw chars:    {stats['raw_characters']:>10,}")
        print(f"    Clean chars:  {stats['clean_characters']:>10,}")
        print(f"    Reduction:    {stats['reduction_pct']:>9}%")
        print(f"    Headers:      {len(stats['headers_detected'])}")
        print(f"    Footers:      {len(stats['footers_detected'])}")

    except Exception as e:
        log_result("Real filing test", False, str(e))
        import traceback
        traceback.print_exc()


# ===================================================================
# 6. PROCESSING METADATA / MANIFEST
# ===================================================================

def test_processing_manifest():
    section("6. PROCESSING MANIFEST")
    from ingestion.text_cleaner import clean_document

    pages = _make_synthetic_pages(10)
    result = clean_document(pages)

    # Document-level manifest
    log_result("Has cleaning_version", result.get("cleaning_version") == "v1")
    log_result("Has statistics dict", isinstance(result.get("statistics"), dict))

    stats = result["statistics"]
    required_keys = [
        "total_pages", "raw_characters", "clean_characters",
        "reduction_pct", "headers_detected", "footers_detected",
        "empty_pages_after_cleaning",
    ]
    missing = [k for k in required_keys if k not in stats]
    log_result("Statistics has all required keys",
               len(missing) == 0,
               f"missing: {missing}" if missing else "")

    # Page-level manifest
    if result["pages"]:
        p = result["pages"][0]
        page_keys = ["raw_text", "clean_text", "char_count_raw",
                     "char_count_clean", "cleaning_version"]
        missing_page = [k for k in page_keys if k not in p]
        log_result("Page has all manifest keys",
                   len(missing_page) == 0,
                   f"missing: {missing_page}" if missing_page else "")

    # Original metadata preserved
    if result["pages"]:
        p = result["pages"][0]
        log_result("Original 'page' number preserved",
                   p.get("page") == 1)

    # Verify manifest is JSON serializable
    try:
        json_str = json.dumps(result["statistics"], default=str)
        log_result("Manifest is JSON serializable", len(json_str) > 20)
    except Exception as e:
        log_result("Manifest JSON serializable", False, str(e))


# ===================================================================
# 7. EDGE CASES
# ===================================================================

def test_edge_cases():
    section("7. EDGE CASES")
    from ingestion.text_cleaner import clean_document, clean_page

    # Empty document
    result = clean_document([])
    log_result("Empty document handled", result["statistics"]["total_pages"] == 0)

    # Single page (no header/footer detection possible)
    single = [{"page": 1, "text": "Just one page of content."}]
    result = clean_document(single)
    log_result("Single page handled",
               len(result["pages"]) == 1 and result["pages"][0]["clean_text"].strip() != "")

    # Page with only headers (should become near-empty after cleaning)
    header_only = "INFOSYS LIMITED\nAnnual Report 2025\nPage 42\n"
    cleaned = clean_page(header_only, ["INFOSYS LIMITED", "Annual Report #"], ["Page #"])
    log_result("Header-only page cleaned",
               len(cleaned.strip()) < len(header_only.strip()))

    # Unicode financial text preserved
    unicode_text = "Revenue: \u20b950,000 crore | Profit: \u20ac200M | \u00a5300B"
    cleaned = clean_page(unicode_text)
    log_result("Currency symbols preserved",
               "\u20b9" in cleaned and "\u20ac" in cleaned and "\u00a5" in cleaned)

    # Percentage and decimal preservation
    text = "Growth was 14.5% with EPS of $6.42 and P/E of 28.3x."
    cleaned = clean_page(text)
    log_result("Financial numbers preserved",
               "14.5%" in cleaned and "$6.42" in cleaned and "28.3x" in cleaned)


# ===================================================================
# RUNNER
# ===================================================================

def main():
    print("\n" + "#" * 60)
    print("  PHASE 2.2 -- TEXT CLEANING VERIFICATION")
    print("#" * 60)

    start = time.time()

    try:
        test_normalize_unicode()
        test_remove_control_characters()
        test_remove_xbrl_artifacts()
        test_normalize_whitespace()
        test_remove_page_numbers()
        test_header_detection()
        test_footer_detection()
        test_header_removal()
        test_broken_line_merging()
        test_full_pipeline_synthetic()
        test_real_filing()
        test_processing_manifest()
        test_edge_cases()
    finally:
        if TEST_DIR.exists():
            shutil.rmtree(TEST_DIR)

    elapsed = time.time() - start

    # Summary
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
