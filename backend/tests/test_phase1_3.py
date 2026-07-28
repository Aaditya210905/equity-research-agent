"""
Phase 1.3 - Financial Statements & Document Pipeline Verification

Run from the backend/ directory:
    python -X utf8 tests/test_phase1_3.py

Tests (no server required for 1-5):
    1. Document registry (Peewee model)
    2. SEC EDGAR connector (CIK lookup, filing discovery)
    3. Yahoo Finance financial statements -> JSON storage
    4. Document service (full collection pipeline)
    5. Validation rules
    6. API endpoints (requires server running)

Start the server first for API tests:
    python -m uvicorn main:app --reload
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
# 1. DOCUMENT REGISTRY (Peewee model)
# ===================================================================

def test_document_registry():
    section("1. DOCUMENT REGISTRY")
    try:
        from models.document import Document, initialize_db, close_db, DOC_TYPES, PROCESSING_STATUSES

        # Use a test database
        test_db_path = str(Path(__file__).parent / "test_documents.db")
        initialize_db(test_db_path)
        log_result("Database initialized", True)

        # DOC_TYPES defined
        log_result("DOC_TYPES has entries", len(DOC_TYPES) >= 5,
                   f"{len(DOC_TYPES)} types")

        # PROCESSING_STATUSES defined
        log_result("PROCESSING_STATUSES has stages", len(PROCESSING_STATUSES) >= 6,
                   f"{len(PROCESSING_STATUSES)} stages")

        # Create a document
        doc = Document.create(
            document_id="TEST_annual_report_2024_test",
            ticker="TEST",
            company_name="Test Corp",
            doc_type="annual_report",
            title="Test Annual Report 2024",
            year=2024,
            file_path="documents/TEST/annual_reports/test.pdf",
            file_size=1024,
            source="test",
            processing_status="downloaded",
        )
        log_result("Document created", doc is not None)

        # Query it back
        fetched = Document.get_by_id("TEST_annual_report_2024_test")
        log_result("Document retrieved", fetched.ticker == "TEST")
        log_result("Document type correct", fetched.doc_type == "annual_report")
        log_result("Year correct", fetched.year == 2024)

        # Update processing status
        fetched.processing_status = "verified"
        fetched.save()
        refreshed = Document.get_by_id("TEST_annual_report_2024_test")
        log_result("Processing status updated", refreshed.processing_status == "verified")

        # Query by ticker
        docs = list(Document.select().where(Document.ticker == "TEST"))
        log_result("Query by ticker works", len(docs) >= 1)

        # Cleanup
        Document.delete().where(Document.ticker == "TEST").execute()
        close_db()

        # Remove test db
        try:
            os.remove(test_db_path)
        except Exception:
            pass

        log_result("Cleanup successful", True)

    except Exception as e:
        log_result("Document registry", False, str(e))


# ===================================================================
# 2. SEC EDGAR CONNECTOR
# ===================================================================

def test_sec_edgar_cik():
    section("2a. SEC EDGAR -- CIK Resolution")
    try:
        from connectors.sec_edgar import resolve_cik, SECEdgarError

        # Valid US ticker
        result = resolve_cik("AAPL")
        log_result("resolve_cik('AAPL') returns dict", isinstance(result, dict))
        log_result("Has 'cik' key", "cik" in result, f"cik = {result.get('cik')}")
        log_result("Has 'name' key", "name" in result, f"name = {result.get('name')}")
        log_result("CIK is 10-digit padded", len(result.get("cik", "")) == 10)

        # Another ticker
        msft = resolve_cik("MSFT")
        log_result("resolve_cik('MSFT') works", "cik" in msft,
                   f"name = {msft.get('name')}")

        # Non-US ticker should raise
        try:
            resolve_cik("RELIANCE.NS")
            log_result("Non-US ticker raises SECEdgarError", False,
                       "Should have raised")
        except SECEdgarError:
            log_result("Non-US ticker raises SECEdgarError", True)

    except Exception as e:
        log_result("SEC EDGAR CIK", False, str(e))


def test_sec_edgar_filings():
    section("2b. SEC EDGAR -- Filing Discovery")
    try:
        from connectors.sec_edgar import get_annual_filings, get_quarterly_filings

        # Annual filings
        annual = get_annual_filings("AAPL", limit=3)
        log_result("get_annual_filings returns list", isinstance(annual, list))
        log_result("Has filings", len(annual) > 0, f"found {len(annual)} 10-K filings")

        if annual:
            f = annual[0]
            log_result("Filing has 'form'", "form" in f, f"form = {f.get('form')}")
            log_result("Filing has 'filing_date'", "filing_date" in f,
                       f"date = {f.get('filing_date')}")
            log_result("Filing has 'doc_url'", "doc_url" in f)
            log_result("Filing has 'doc_type'", f.get("doc_type") == "annual_report")
            print(f"\n  Latest 10-K: {f.get('filing_date')} - {f.get('primary_doc')}")

        # Quarterly filings
        quarterly = get_quarterly_filings("AAPL", limit=4)
        log_result("get_quarterly_filings returns list", isinstance(quarterly, list))
        log_result("Has quarterly filings", len(quarterly) > 0,
                   f"found {len(quarterly)} 10-Q filings")

    except Exception as e:
        log_result("SEC EDGAR filings", False, str(e))


# ===================================================================
# 3. YAHOO FINANCE FINANCIAL STATEMENTS -> JSON
# ===================================================================

def test_yahoo_financial_statements():
    section("3. YAHOO FINANCE -- Financial Statements")
    try:
        from connectors.yahoo_finance import (
            get_income_statement, get_balance_sheet, get_cash_flow,
        )

        ticker = "AAPL"

        income = get_income_statement(ticker)
        log_result("Income statement returns list", isinstance(income, list))
        log_result("Income statement non-empty", len(income) > 0,
                   f"{len(income)} periods")

        balance = get_balance_sheet(ticker)
        log_result("Balance sheet returns list", isinstance(balance, list))
        log_result("Balance sheet non-empty", len(balance) > 0,
                   f"{len(balance)} periods")

        cash = get_cash_flow(ticker)
        log_result("Cash flow returns list", isinstance(cash, list))
        log_result("Cash flow non-empty", len(cash) > 0,
                   f"{len(cash)} periods")

        # Verify JSON serializable
        if income:
            json_str = json.dumps(income[0], default=str)
            log_result("Income statement JSON serializable", len(json_str) > 50)

    except Exception as e:
        log_result("Yahoo financial statements", False, str(e))


# ===================================================================
# 4. DOCUMENT SERVICE -- Full Collection Pipeline
# ===================================================================

def test_document_collection_us():
    section("4a. DOCUMENT SERVICE -- US Company (AAPL)")
    try:
        from models.document import initialize_db, Document, close_db, db
        from services.document_service import collect_documents, get_company_documents, DOCUMENTS_DIR

        # Use test database
        test_db_path = str(Path(__file__).parent / "test_collect.db")

        # Reset the module-level flag to force re-init
        import models.document
        models.document._DB_INITIALIZED = False
        if not db.is_closed():
            db.close()

        initialize_db(test_db_path)

        ticker = "AAPL"
        result = collect_documents(ticker)

        log_result("Returns dict", isinstance(result, dict))
        log_result("Has 'ticker'", result.get("ticker") == "AAPL")
        log_result("Has 'new_documents'", "new_documents" in result,
                   f"new = {result.get('new_documents')}")
        log_result("Has 'documents' list", isinstance(result.get("documents"), list))

        total = result.get("new_documents", 0) + result.get("existing_documents", 0)
        log_result("Collected documents", total > 0, f"total = {total}")

        # Check document types
        doc_types = set(d.get("doc_type") for d in result.get("documents", []))
        print(f"\n  Document types found: {doc_types}")

        has_financials = bool(doc_types & {"income_statement", "balance_sheet", "cash_flow"})
        log_result("Has financial statements", has_financials)

        has_sec = bool(doc_types & {"annual_report", "quarterly_report"})
        log_result("Has SEC filings", has_sec)

        # Verify files exist on disk
        docs_on_disk = list(DOCUMENTS_DIR.rglob("*"))
        actual_files = [f for f in docs_on_disk if f.is_file()]
        log_result("Files exist on disk", len(actual_files) > 0,
                   f"{len(actual_files)} files")

        # Query from database
        db_docs = get_company_documents(ticker)
        log_result("get_company_documents works",
                   db_docs.get("total_documents", 0) > 0,
                   f"{db_docs.get('total_documents')} in registry")

        # Second collection should find existing docs
        result2 = collect_documents(ticker)
        log_result("Re-collection finds existing docs",
                   result2.get("existing_documents", 0) > 0,
                   f"existing = {result2.get('existing_documents')}")

        # Cleanup
        close_db()
        models.document._DB_INITIALIZED = False
        try:
            os.remove(test_db_path)
        except Exception:
            pass

        # Clean up downloaded files
        aapl_dir = DOCUMENTS_DIR / "AAPL"
        if aapl_dir.exists():
            shutil.rmtree(aapl_dir)

    except Exception as e:
        log_result("Document collection (US)", False, str(e))
        import traceback
        traceback.print_exc()


def test_document_collection_non_us():
    section("4b. DOCUMENT SERVICE -- Non-US Company (INFY)")
    try:
        from models.document import initialize_db, close_db, db
        from services.document_service import collect_documents, DOCUMENTS_DIR
        import models.document

        # Use test database
        test_db_path = str(Path(__file__).parent / "test_collect_infy.db")
        models.document._DB_INITIALIZED = False
        if not db.is_closed():
            db.close()
        initialize_db(test_db_path)

        ticker = "INFY"
        result = collect_documents(ticker)

        log_result("Returns dict", isinstance(result, dict))
        log_result("Has 'ticker'", result.get("ticker") == "INFY")

        total = result.get("new_documents", 0) + result.get("existing_documents", 0)
        log_result("Collected documents (at least financials)", total > 0,
                   f"total = {total}")

        # INFY is US-listed (ADR), so may have SEC filings too
        doc_types = set(d.get("doc_type") for d in result.get("documents", []))
        has_financials = bool(doc_types & {"income_statement", "balance_sheet", "cash_flow"})
        log_result("Has financial statements from Yahoo", has_financials)
        print(f"\n  Document types: {doc_types}")

        # Cleanup
        close_db()
        models.document._DB_INITIALIZED = False
        try:
            os.remove(test_db_path)
        except Exception:
            pass
        infy_dir = DOCUMENTS_DIR / "INFY"
        if infy_dir.exists():
            shutil.rmtree(infy_dir)

    except Exception as e:
        log_result("Document collection (non-US)", False, str(e))


# ===================================================================
# 5. VALIDATION RULES
# ===================================================================

def test_validation():
    section("5. VALIDATION RULES")
    try:
        from services.document_service import _validate_file

        # Create a test file
        test_dir = Path(__file__).parent / "test_validation"
        test_dir.mkdir(exist_ok=True)

        # Valid file
        valid_file = test_dir / "valid.txt"
        valid_file.write_text("test content")
        log_result("Valid file passes", _validate_file(valid_file))

        # Empty file
        empty_file = test_dir / "empty.txt"
        empty_file.write_text("")
        log_result("Empty file fails", not _validate_file(empty_file))

        # Non-existent file
        log_result("Missing file fails", not _validate_file(test_dir / "nope.txt"))

        # Cleanup
        shutil.rmtree(test_dir)
        log_result("Validation cleanup", True)

    except Exception as e:
        log_result("Validation", False, str(e))


# ===================================================================
# 6. DOCUMENT SCHEMAS (Pydantic)
# ===================================================================

def test_schemas():
    section("6. PYDANTIC SCHEMAS")
    try:
        from schemas.document import DocumentMeta, DocumentCollection, CollectionResult

        # DocumentMeta
        meta = DocumentMeta(
            document_id="AAPL_annual_report_2024_sec",
            ticker="AAPL",
            doc_type="annual_report",
            title="10-K - Apple Inc. (2024)",
            source="sec_edgar",
            year=2024,
        )
        log_result("DocumentMeta validates", True)
        log_result("DocumentMeta serializes", len(meta.model_dump_json()) > 20)

        # DocumentCollection
        collection = DocumentCollection(
            company="Apple Inc.",
            ticker="AAPL",
            total_documents=1,
            documents=[meta],
        )
        log_result("DocumentCollection validates", True)

        # CollectionResult
        result = CollectionResult(
            ticker="AAPL",
            new_documents=5,
            existing_documents=3,
            failed=0,
            documents=[meta],
        )
        log_result("CollectionResult validates", True)

    except Exception as e:
        log_result("Document schemas", False, str(e))


# ===================================================================
# 7. API ENDPOINTS (requires server running)
# ===================================================================

def test_api_collect():
    section("7a. API -- POST /documents/{ticker}/collect")
    try:
        import httpx
    except ImportError:
        log_result("httpx installed", False, "pip install httpx")
        return

    base_url = "http://127.0.0.1:8000"

    try:
        httpx.get(f"{base_url}/", timeout=5)
    except httpx.ConnectError:
        print(f"\n  {WARN}  Server not running!")
        print(f"         Start it:  python -m uvicorn main:app --reload")
        log_result("Server reachable", False, "Connection refused")
        return

    # Collect documents for AAPL
    try:
        r = httpx.post(f"{base_url}/documents/AAPL/collect", timeout=120)
        log_result("POST /documents/AAPL/collect returns 200",
                   r.status_code == 200, f"status={r.status_code}")

        if r.status_code == 200:
            data = r.json()
            log_result("Has 'ticker'", data.get("ticker") == "AAPL")
            log_result("Has 'new_documents'", "new_documents" in data,
                       f"new={data.get('new_documents')}")
            log_result("Has 'documents' list",
                       isinstance(data.get("documents"), list),
                       f"count={len(data.get('documents', []))}")

            print(f"\n  Collection result:")
            print(f"    New:      {data.get('new_documents')}")
            print(f"    Existing: {data.get('existing_documents')}")
            print(f"    Failed:   {data.get('failed')}")

    except Exception as e:
        log_result("POST /documents/AAPL/collect", False, str(e))


def test_api_list():
    section("7b. API -- GET /documents/{ticker}")
    try:
        import httpx
    except ImportError:
        return

    base_url = "http://127.0.0.1:8000"

    try:
        r = httpx.get(f"{base_url}/documents/AAPL", timeout=30)
        log_result("GET /documents/AAPL returns 200",
                   r.status_code == 200, f"status={r.status_code}")

        if r.status_code == 200:
            data = r.json()
            log_result("Has 'company'", "company" in data)
            log_result("Has 'total_documents'", "total_documents" in data,
                       f"total={data.get('total_documents')}")
            log_result("Has 'documents' list",
                       isinstance(data.get("documents"), list))

            # Show document summary
            if data.get("documents"):
                print(f"\n  Documents for {data.get('ticker')}:")
                for d in data["documents"][:5]:
                    print(f"    - [{d.get('doc_type')}] {d.get('title')} ({d.get('processing_status')})")
                if len(data["documents"]) > 5:
                    print(f"    ... and {len(data['documents']) - 5} more")

    except Exception as e:
        log_result("GET /documents/AAPL", False, str(e))

    # Filter by type
    try:
        r = httpx.get(f"{base_url}/documents/AAPL?doc_type=annual_report", timeout=30)
        if r.status_code == 200:
            data = r.json()
            types = set(d["doc_type"] for d in data.get("documents", []))
            log_result("Filter by doc_type works",
                       types <= {"annual_report"},
                       f"types found: {types}")
    except Exception as e:
        log_result("Filter by doc_type", False, str(e))


# ===================================================================
# RUNNER
# ===================================================================

def main():
    print("\n" + "#" * 60)
    print("  PHASE 1.3 -- DOCUMENT PIPELINE VERIFICATION")
    print("#" * 60)

    start = time.time()

    # Core tests (no server needed)
    test_document_registry()
    test_sec_edgar_cik()
    test_sec_edgar_filings()
    test_yahoo_financial_statements()
    test_validation()
    test_schemas()
    test_document_collection_us()
    test_document_collection_non_us()

    # API tests (needs server)
    test_api_collect()
    test_api_list()

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
