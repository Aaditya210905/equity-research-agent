"""
Phase 2.1 - PDF Extraction Verification

Run from the backend/ directory:
    python -X utf8 tests/test_phase2_1.py

Tests:
    1. PyMuPDF & pdfplumber availability
    2. PDF extraction (synthetic multi-page PDF)
    3. HTML extraction (SEC EDGAR 10-K filing)
    4. JSON extraction (Yahoo Finance data)
    5. Auto-detection (extract_document)
    6. Error handling (missing, empty, corrupted files)
    7. Metadata attachment
    8. Real filing test (downloads AAPL 10-K from SEC EDGAR)
"""

import sys
import os
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
WARN = "[WARN]"
DIVIDER = "=" * 60

test_results: list[dict] = []
TEST_DIR = Path(__file__).parent / "test_extraction"


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


def setup():
    """Create test directory."""
    TEST_DIR.mkdir(parents=True, exist_ok=True)


def cleanup():
    """Remove test directory."""
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)


# ===================================================================
# 1. BACKEND AVAILABILITY
# ===================================================================

def test_backends():
    section("1. EXTRACTION BACKENDS")
    try:
        import fitz
        log_result("PyMuPDF (fitz) installed", True,
                   f"version = {fitz.VersionBind}")
    except ImportError:
        log_result("PyMuPDF (fitz) installed", False)

    try:
        import pdfplumber
        log_result("pdfplumber installed", True,
                   f"version = {pdfplumber.__version__}")
    except ImportError:
        log_result("pdfplumber installed", False)

    try:
        from bs4 import BeautifulSoup
        log_result("BeautifulSoup installed", True)
    except ImportError:
        log_result("BeautifulSoup installed", False)

    from ingestion.pdf_extractor import _HAS_PYMUPDF, _HAS_PDFPLUMBER, _HAS_BS4
    log_result("Extractor detects PyMuPDF", _HAS_PYMUPDF)
    log_result("Extractor detects pdfplumber", _HAS_PDFPLUMBER)
    log_result("Extractor detects BeautifulSoup", _HAS_BS4)


# ===================================================================
# 2. PDF EXTRACTION — Synthetic Multi-Page PDF
# ===================================================================

def _create_test_pdf(path: Path, num_pages: int = 20) -> Path:
    """Create a synthetic multi-page PDF for testing."""
    import fitz

    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page(width=612, height=792)  # US Letter
        # Write realistic financial report content
        text_lines = [
            f"Page {i + 1} of {num_pages}",
            "",
            f"Section {i + 1}: Financial Overview",
            "",
            f"The company reported revenue of $12.{i}B for FY2025,",
            f"representing a year-over-year growth of {10 + i}%.",
            "",
            "Key Highlights:",
            f"  - Operating margin: {20 + i}%",
            f"  - Net income: $3.{i}B",
            f"  - Earnings per share: ${2 + i * 0.1:.2f}",
            f"  - Free cash flow: $4.{i}B",
            "",
            "Management Discussion and Analysis",
            "",
            "During the fiscal year, the company continued to invest",
            "in research and development, with a focus on artificial",
            "intelligence and cloud computing services.",
        ]
        text = "\n".join(text_lines)

        # Insert text using TextWriter for proper layout
        tw = fitz.TextWriter(page.rect)
        font = fitz.Font("helv")
        y = 72  # Top margin
        for line in text_lines:
            tw.append((72, y), line, font=font, fontsize=11)
            y += 16
        tw.write_text(page)

    doc.save(str(path))
    doc.close()
    return path


def test_pdf_extraction():
    section("2. PDF EXTRACTION -- Synthetic PDF")
    try:
        from ingestion.pdf_extractor import extract_pdf

        num_pages = 20
        pdf_path = _create_test_pdf(TEST_DIR / "test_report.pdf", num_pages)
        log_result("Test PDF created", pdf_path.exists(),
                   f"size = {pdf_path.stat().st_size:,} bytes")

        result = extract_pdf(
            pdf_path,
            document_id="TEST_annual_report_2025",
            company="TEST_CORP",
            year=2025,
            source="test",
        )

        log_result("Extraction succeeded", result["success"])
        log_result("File type is 'pdf'", result["file_type"] == "pdf")
        log_result(f"Total pages = {num_pages}",
                   result["total_pages"] == num_pages,
                   f"got {result['total_pages']}")
        log_result("Total characters > 0",
                   result["total_characters"] > 0,
                   f"{result['total_characters']:,} chars")

        # Check individual pages
        pages = result["pages"]
        log_result("Pages is a list", isinstance(pages, list))
        log_result(f"Has {num_pages} page objects", len(pages) == num_pages)

        if pages:
            first = pages[0]
            log_result("Page 1 has 'page' key", first.get("page") == 1)
            log_result("Page 1 has 'text' key", isinstance(first.get("text"), str))
            log_result("Page 1 has 'char_count'", first.get("char_count", 0) > 0,
                       f"char_count = {first.get('char_count')}")
            log_result("Page 1 has 'document_id'",
                       first.get("document_id") == "TEST_annual_report_2025")
            log_result("Page 1 has 'company'",
                       first.get("company") == "TEST_CORP")
            log_result("Page 1 has 'year'", first.get("year") == 2025)
            log_result("Page 1 has 'source'", first.get("source") is not None)

            # Check page numbering is sequential
            page_nums = [p["page"] for p in pages]
            expected_nums = list(range(1, num_pages + 1))
            log_result("Pages are sequentially numbered",
                       page_nums == expected_nums)

            # No empty pages
            empty_pages = [p for p in pages if p["char_count"] == 0]
            log_result("No empty pages",
                       len(empty_pages) == 0,
                       f"{len(empty_pages)} empty" if empty_pages else "")

            # Content sanity check
            has_revenue = any("revenue" in p["text"].lower() for p in pages)
            log_result("Content contains 'revenue'", has_revenue)

        # Metadata
        meta = result.get("metadata", {})
        log_result("Metadata attached", meta.get("document_id") == "TEST_annual_report_2025")

    except Exception as e:
        log_result("PDF extraction", False, str(e))
        import traceback
        traceback.print_exc()


# ===================================================================
# 3. HTML EXTRACTION (SEC EDGAR)
# ===================================================================

def _create_test_html(path: Path) -> Path:
    """Create a synthetic HTML filing for testing."""
    html = """<!DOCTYPE html>
<html>
<head><title>Form 10-K Annual Report</title></head>
<body>
<h1>ANNUAL REPORT PURSUANT TO SECTION 13 OR 15(d)</h1>
<h2>PART I</h2>
<h3>ITEM 1. BUSINESS</h3>
<p>We design, manufacture, and market smartphones, personal computers,
tablets, wearables, and accessories. We also sell a variety of related
services. Our fiscal year is the 52- or 53-week period that ends on the
last Saturday of September.</p>
<p>Revenue for FY2025 was $391.0 billion, an increase of 5% from
the prior year. Operating income was $123.2 billion.</p>

<h3>ITEM 1A. RISK FACTORS</h3>
<p>The following risk factors could materially affect our business:</p>
<ul>
<li>Global economic conditions may adversely impact demand</li>
<li>Supply chain disruptions could affect product availability</li>
<li>Competition in the technology industry is intense</li>
<li>Regulatory changes may increase compliance costs</li>
</ul>

<h2>PART II</h2>
<h3>ITEM 8. FINANCIAL STATEMENTS</h3>
<table border="1">
<tr><th>Item</th><th>2025</th><th>2024</th></tr>
<tr><td>Revenue</td><td>$391.0B</td><td>$372.4B</td></tr>
<tr><td>Net Income</td><td>$94.7B</td><td>$93.7B</td></tr>
<tr><td>EPS (Diluted)</td><td>$6.42</td><td>$6.13</td></tr>
</table>

<p>The accompanying notes are an integral part of these financial statements.</p>
""" + "<p>Additional content. " * 200 + """
<p>End of report.</p>
</body>
</html>"""

    path.write_text(html, encoding="utf-8")
    return path


def test_html_extraction():
    section("3. HTML EXTRACTION -- Synthetic Filing")
    try:
        from ingestion.pdf_extractor import extract_html

        html_path = _create_test_html(TEST_DIR / "test_10k.htm")
        log_result("Test HTML created", html_path.exists())

        result = extract_html(
            html_path,
            document_id="TEST_annual_report_2025_sec",
            company="TEST_CORP",
            year=2025,
        )

        log_result("Extraction succeeded", result["success"])
        log_result("File type is 'html'", result["file_type"] == "html")
        log_result("Has pages", result["total_pages"] > 0,
                   f"{result['total_pages']} pages")
        log_result("Total characters > 0",
                   result["total_characters"] > 0,
                   f"{result['total_characters']:,} chars")

        pages = result["pages"]
        if pages:
            first = pages[0]
            log_result("Page has metadata",
                       first.get("document_id") == "TEST_annual_report_2025_sec")

            # Content checks
            all_text = " ".join(p["text"] for p in pages)
            log_result("Contains 'Revenue'", "Revenue" in all_text or "revenue" in all_text)
            log_result("Contains 'Risk Factors'", "Risk Factors" in all_text or "risk factors" in all_text.lower())

            # No script/style tags in extracted text
            log_result("No script tags in output",
                       "<script" not in all_text.lower())

    except Exception as e:
        log_result("HTML extraction", False, str(e))


# ===================================================================
# 4. JSON EXTRACTION
# ===================================================================

def test_json_extraction():
    section("4. JSON EXTRACTION -- Financial Statement")
    try:
        from ingestion.pdf_extractor import extract_document

        # Create test JSON financial statement
        json_data = {
            "period": "2025-09-27",
            "total_revenue": 391035000000,
            "operating_income": 123215000000,
            "net_income": 94760000000,
            "earnings_per_share": 6.42,
            "total_assets": 364980000000,
        }
        json_path = TEST_DIR / "income_statement_2025.json"
        with open(json_path, "w") as f:
            json.dump(json_data, f, indent=2)

        result = extract_document(
            json_path,
            document_id="TEST_income_statement_2025",
            company="TEST_CORP",
            year=2025,
        )

        log_result("Extraction succeeded", result["success"])
        log_result("File type is 'json'", result["file_type"] == "json")
        log_result("Has 1 page", result["total_pages"] == 1)
        log_result("Total chars > 0", result["total_characters"] > 0)

        if result["pages"]:
            text = result["pages"][0]["text"]
            log_result("Text contains revenue", "Revenue" in text or "revenue" in text.lower())

    except Exception as e:
        log_result("JSON extraction", False, str(e))


# ===================================================================
# 5. AUTO-DETECTION (extract_document)
# ===================================================================

def test_auto_detection():
    section("5. AUTO-DETECTION -- extract_document")
    try:
        from ingestion.pdf_extractor import extract_document

        # PDF detection
        pdf_result = extract_document(TEST_DIR / "test_report.pdf")
        log_result("Auto-detects PDF", pdf_result["file_type"] == "pdf")

        # HTML detection
        html_result = extract_document(TEST_DIR / "test_10k.htm")
        log_result("Auto-detects HTML", html_result["file_type"] == "html")

        # JSON detection
        json_result = extract_document(TEST_DIR / "income_statement_2025.json")
        log_result("Auto-detects JSON", json_result["file_type"] == "json")

    except Exception as e:
        log_result("Auto-detection", False, str(e))


# ===================================================================
# 6. ERROR HANDLING
# ===================================================================

def test_error_handling():
    section("6. ERROR HANDLING")
    try:
        from ingestion.pdf_extractor import extract_pdf, extract_html, extract_document

        # Missing file
        result = extract_pdf(TEST_DIR / "nonexistent.pdf")
        log_result("Missing file: success=False", not result["success"])
        log_result("Missing file: has error message",
                   result["error"] is not None and "not found" in result["error"].lower(),
                   f"error = {result['error']}")

        # Empty file
        empty_path = TEST_DIR / "empty.pdf"
        empty_path.write_bytes(b"")
        result = extract_pdf(empty_path)
        log_result("Empty file: success=False", not result["success"])
        log_result("Empty file: has error message",
                   result["error"] is not None and "empty" in result["error"].lower())

        # Non-PDF file with .pdf extension
        fake_pdf = TEST_DIR / "fake.pdf"
        fake_pdf.write_text("This is not a PDF")
        result = extract_pdf(fake_pdf)
        # PyMuPDF will fail on this — should return error gracefully
        log_result("Fake PDF: handled gracefully", isinstance(result, dict))
        if not result["success"]:
            log_result("Fake PDF: reports failure", True)
        else:
            log_result("Fake PDF: returned result", True, "may treat as text")

        # Missing HTML file
        result = extract_html(TEST_DIR / "nonexistent.html")
        log_result("Missing HTML: success=False", not result["success"])

        # Unsupported extension
        weird_path = TEST_DIR / "data.xyz"
        weird_path.write_text("unknown format")
        result = extract_document(weird_path)
        log_result("Unsupported format: success=False", not result["success"])
        log_result("Unsupported format: has error",
                   "unsupported" in result.get("error", "").lower() or
                   "no extractor" in result.get("error", "").lower())

    except Exception as e:
        log_result("Error handling", False, str(e))


# ===================================================================
# 7. METADATA ATTACHMENT
# ===================================================================

def test_metadata():
    section("7. METADATA ATTACHMENT")
    try:
        from ingestion.pdf_extractor import extract_pdf

        result = extract_pdf(
            TEST_DIR / "test_report.pdf",
            document_id="META_TEST_001",
            company="Meta Corp",
            year=2025,
            source="unit_test",
        )

        log_result("Extraction succeeded", result["success"])

        # Check metadata on result
        meta = result.get("metadata", {})
        log_result("Result metadata: document_id",
                   meta.get("document_id") == "META_TEST_001")
        log_result("Result metadata: company",
                   meta.get("company") == "Meta Corp")
        log_result("Result metadata: year",
                   meta.get("year") == 2025)

        # Check metadata on every page
        if result["pages"]:
            all_have_id = all(p.get("document_id") == "META_TEST_001" for p in result["pages"])
            all_have_company = all(p.get("company") == "Meta Corp" for p in result["pages"])
            all_have_year = all(p.get("year") == 2025 for p in result["pages"])
            all_have_source = all(p.get("source") is not None for p in result["pages"])

            log_result("All pages have document_id", all_have_id)
            log_result("All pages have company", all_have_company)
            log_result("All pages have year", all_have_year)
            log_result("All pages have source", all_have_source)

    except Exception as e:
        log_result("Metadata attachment", False, str(e))


# ===================================================================
# 8. REAL SEC FILING (downloads from EDGAR)
# ===================================================================

def test_real_filing():
    section("8. REAL SEC FILING -- AAPL 10-K")
    try:
        from connectors.sec_edgar import get_annual_filings, download_filing
        from ingestion.pdf_extractor import extract_document

        # Get one annual filing
        filings = get_annual_filings("AAPL", limit=1)
        if not filings:
            log_result("No AAPL filings found", False)
            return

        filing = filings[0]
        log_result("Filing found", True,
                   f"{filing['form']} from {filing['filing_date']}")

        # Download it
        save_dir = TEST_DIR / "real_filings"
        dl = download_filing(filing, save_dir)
        log_result("Filing downloaded", dl["success"],
                   f"size = {dl.get('file_size', 0):,} bytes")

        if not dl["success"]:
            return

        file_path = Path(dl["file_path"])

        # Extract it
        result = extract_document(
            file_path,
            document_id="AAPL_annual_report_2025_sec",
            company="Apple Inc.",
            year=2025,
        )

        log_result("Extraction succeeded", result["success"])
        log_result(f"File type: {result['file_type']}",
                   result["file_type"] in ("pdf", "html"))
        log_result(f"Pages extracted: {result['total_pages']}",
                   result["total_pages"] > 10,
                   f"{result['total_pages']} pages")
        log_result(f"Characters extracted: {result['total_characters']:,}",
                   result["total_characters"] > 100000,
                   f"{result['total_characters']:,} chars")

        # Verify content quality
        all_text = " ".join(p["text"] for p in result["pages"])
        has_apple = "apple" in all_text.lower()
        has_revenue = "revenue" in all_text.lower()
        has_risk = "risk" in all_text.lower()

        log_result("Contains 'Apple'", has_apple)
        log_result("Contains 'revenue'", has_revenue)
        log_result("Contains 'risk'", has_risk)

        # No empty pages (allow some — real PDFs can have blank pages)
        non_empty = [p for p in result["pages"] if p["char_count"] > 10]
        empty_pct = (result["total_pages"] - len(non_empty)) / max(result["total_pages"], 1) * 100
        log_result(f"Non-empty pages: {len(non_empty)}/{result['total_pages']}",
                   len(non_empty) > result["total_pages"] * 0.8,
                   f"{empty_pct:.0f}% empty")

        # All pages have metadata
        all_have_meta = all(
            p.get("document_id") and p.get("company")
            for p in result["pages"]
        )
        log_result("All pages have metadata", all_have_meta)

        # Print sample content
        if result["pages"]:
            sample = result["pages"][0]["text"][:300]
            print(f"\n  Sample (page 1, first 300 chars):")
            print(f"  {sample[:300]}...")

    except Exception as e:
        log_result("Real filing test", False, str(e))
        import traceback
        traceback.print_exc()


# ===================================================================
# RUNNER
# ===================================================================

def main():
    print("\n" + "#" * 60)
    print("  PHASE 2.1 -- PDF EXTRACTION VERIFICATION")
    print("#" * 60)

    start = time.time()
    setup()

    try:
        test_backends()
        test_pdf_extraction()
        test_html_extraction()
        test_json_extraction()
        test_auto_detection()
        test_error_handling()
        test_metadata()
        test_real_filing()
    finally:
        cleanup()

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
