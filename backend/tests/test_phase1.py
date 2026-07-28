"""
Phase 1.1 — Verification Script

Run from the backend/ directory:
    python tests/test_phase1.py

Tests every layer bottom-up:
    1. Settings loader
    2. Yahoo Finance connector (all 6 functions)
    3. Data service layer
    4. FastAPI endpoint (requires server running)

Color legend:
    ✅  Pass
    ❌  Fail
    ⚠️  Warning (non-critical)
"""

import sys
import json
import time
from pathlib import Path

# Ensure backend/ is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
PASS = "✅"
FAIL = "❌"
WARN = "⚠️"
DIVIDER = "═" * 60

test_results: list[dict] = []


def log_result(test_name: str, passed: bool, detail: str = ""):
    status = PASS if passed else FAIL
    test_results.append({"name": test_name, "passed": passed})
    print(f"  {status}  {test_name}")
    if detail:
        print(f"       {detail}")


def section(title: str):
    print(f"\n{DIVIDER}")
    print(f"  {title}")
    print(DIVIDER)


# ===================================================================
# 1. SETTINGS
# ===================================================================
def test_settings():
    section("1. SETTINGS LOADER")

    try:
        from config.settings import settings

        # Settings object exists and is importable
        log_result("Import settings", True)

        # Has expected fields
        fields = ["FINNHUB_API_KEY", "ALPHA_VANTAGE_API_KEY", "OPENAI_API_KEY", "NEWS_API_KEY"]
        for field in fields:
            has_field = hasattr(settings, field)
            log_result(f"Field exists: {field}", has_field)

        # Server defaults
        log_result(
            "Default HOST = 127.0.0.1",
            settings.HOST == "127.0.0.1",
            f"got: {settings.HOST}",
        )
        log_result(
            "Default PORT = 8000",
            settings.PORT == 8000,
            f"got: {settings.PORT}",
        )

    except Exception as e:
        log_result("Import settings", False, str(e))


# ===================================================================
# 2. YAHOO FINANCE CONNECTOR
# ===================================================================
TICKER = "INFY"


def test_company_profile():
    section("2a. CONNECTOR — get_company_profile")

    try:
        from connectors.yahoo_finance import get_company_profile

        profile = get_company_profile(TICKER)

        log_result("Returns a dict", isinstance(profile, dict))
        log_result(
            "Has 'ticker' key",
            "ticker" in profile,
            f"ticker = {profile.get('ticker')}",
        )
        log_result(
            "Has 'company_name' key",
            "company_name" in profile,
            f"company_name = {profile.get('company_name')}",
        )
        log_result(
            "Ticker is uppercased",
            profile.get("ticker") == TICKER.upper(),
        )

        expected_keys = [
            "ticker", "company_name", "sector", "industry",
            "country", "currency", "market_cap", "employees",
            "website", "description", "exchange",
        ]
        missing = [k for k in expected_keys if k not in profile]
        log_result(
            "All expected keys present",
            len(missing) == 0,
            f"missing: {missing}" if missing else "",
        )

        print(f"\n  📋 Sample output:")
        for k in ["ticker", "company_name", "sector", "industry", "country", "currency", "market_cap"]:
            print(f"       {k}: {profile.get(k)}")

    except Exception as e:
        log_result("get_company_profile", False, str(e))


def test_market_data():
    section("2b. CONNECTOR — get_market_data")

    try:
        from connectors.yahoo_finance import get_market_data

        data = get_market_data(TICKER)

        log_result("Returns a dict", isinstance(data, dict))

        expected_keys = [
            "ticker", "current_price", "previous_close", "open",
            "day_high", "day_low", "volume", "pe_ratio", "beta",
        ]
        missing = [k for k in expected_keys if k not in data]
        log_result(
            "All expected keys present",
            len(missing) == 0,
            f"missing: {missing}" if missing else "",
        )

        # Sanity: price should be a positive number
        price = data.get("current_price")
        log_result(
            "current_price is a positive number",
            isinstance(price, (int, float)) and price > 0,
            f"current_price = {price}",
        )

        print(f"\n  📋 Sample output:")
        for k in ["current_price", "previous_close", "volume", "pe_ratio", "beta"]:
            print(f"       {k}: {data.get(k)}")

    except Exception as e:
        log_result("get_market_data", False, str(e))


def test_price_history():
    section("2c. CONNECTOR — get_price_history")

    try:
        from connectors.yahoo_finance import get_price_history

        records = get_price_history(TICKER, period="1mo")

        log_result("Returns a list", isinstance(records, list))
        log_result("Non-empty", len(records) > 0, f"got {len(records)} records")

        if records:
            first = records[0]
            expected_keys = ["date", "open", "high", "low", "close", "volume"]
            missing = [k for k in expected_keys if k not in first]
            log_result(
                "First record has OHLCV keys",
                len(missing) == 0,
                f"missing: {missing}" if missing else "",
            )
            print(f"\n  📋 First record: {first}")
            print(f"  📋 Last record:  {records[-1]}")

    except Exception as e:
        log_result("get_price_history", False, str(e))


def test_income_statement():
    section("2d. CONNECTOR — get_income_statement")

    try:
        from connectors.yahoo_finance import get_income_statement

        records = get_income_statement(TICKER)

        log_result("Returns a list", isinstance(records, list))
        log_result("Non-empty", len(records) > 0, f"got {len(records)} periods")

        if records:
            first = records[0]
            log_result("Has 'period' key", "period" in first, f"period = {first.get('period')}")
            # Check for at least some financial line items
            keys = [k for k in first.keys() if k != "period"]
            log_result(
                "Has financial line items",
                len(keys) > 5,
                f"found {len(keys)} line items",
            )
            print(f"\n  📋 Periods: {[r.get('period') for r in records]}")
            print(f"  📋 Sample keys: {keys[:5]}...")

    except Exception as e:
        log_result("get_income_statement", False, str(e))


def test_balance_sheet():
    section("2e. CONNECTOR — get_balance_sheet")

    try:
        from connectors.yahoo_finance import get_balance_sheet

        records = get_balance_sheet(TICKER)

        log_result("Returns a list", isinstance(records, list))
        log_result("Non-empty", len(records) > 0, f"got {len(records)} periods")

        if records:
            first = records[0]
            keys = [k for k in first.keys() if k != "period"]
            log_result(
                "Has balance-sheet line items",
                len(keys) > 5,
                f"found {len(keys)} line items",
            )

    except Exception as e:
        log_result("get_balance_sheet", False, str(e))


def test_cash_flow():
    section("2f. CONNECTOR — get_cash_flow")

    try:
        from connectors.yahoo_finance import get_cash_flow

        records = get_cash_flow(TICKER)

        log_result("Returns a list", isinstance(records, list))
        log_result("Non-empty", len(records) > 0, f"got {len(records)} periods")

        if records:
            first = records[0]
            keys = [k for k in first.keys() if k != "period"]
            log_result(
                "Has cash-flow line items",
                len(keys) > 5,
                f"found {len(keys)} line items",
            )

    except Exception as e:
        log_result("get_cash_flow", False, str(e))


# ===================================================================
# 3. DATA SERVICE
# ===================================================================
def test_data_service():
    section("3. DATA SERVICE — get_company_overview")

    try:
        from services.data_service import get_company_overview

        result = get_company_overview(TICKER)

        log_result("Returns a dict", isinstance(result, dict))
        log_result("Has 'profile' key", "profile" in result)
        log_result("Has 'market_data' key", "market_data" in result)

        profile = result.get("profile", {})
        market = result.get("market_data", {})

        log_result(
            "Profile has company_name",
            bool(profile.get("company_name")),
            f"company_name = {profile.get('company_name')}",
        )
        log_result(
            "Market data has current_price",
            market.get("current_price") is not None,
            f"current_price = {market.get('current_price')}",
        )

    except Exception as e:
        log_result("get_company_overview", False, str(e))


def test_data_service_financials():
    section("3b. DATA SERVICE — get_financial_statements")

    try:
        from services.data_service import get_financial_statements

        result = get_financial_statements(TICKER)

        log_result("Returns a dict", isinstance(result, dict))

        for key in ["income_statement", "balance_sheet", "cash_flow"]:
            data = result.get(key, [])
            log_result(
                f"'{key}' is a non-empty list",
                isinstance(data, list) and len(data) > 0,
                f"got {len(data)} periods",
            )

    except Exception as e:
        log_result("get_financial_statements", False, str(e))


# ===================================================================
# 4. PYDANTIC SCHEMAS
# ===================================================================
def test_schemas():
    section("4. PYDANTIC SCHEMAS")

    try:
        from schemas.company import CompanyProfile, MarketData, CompanyOverview
        from connectors.yahoo_finance import get_company_profile, get_market_data

        raw_profile = get_company_profile(TICKER)
        raw_market = get_market_data(TICKER)

        # Validate that raw dicts pass Pydantic validation
        profile = CompanyProfile(**raw_profile)
        log_result("CompanyProfile validates raw connector output", True)

        market = MarketData(**raw_market)
        log_result("MarketData validates raw connector output", True)

        overview = CompanyOverview(profile=profile, market_data=market)
        log_result("CompanyOverview composes correctly", True)

        # Round-trip to JSON
        json_str = overview.model_dump_json(indent=2)
        log_result("Serializes to JSON", len(json_str) > 50, f"{len(json_str)} chars")

    except Exception as e:
        log_result("Schema validation", False, str(e))


# ===================================================================
# 5. API ENDPOINT (requires server running)
# ===================================================================
def test_api_endpoint():
    section("5. FASTAPI ENDPOINT — GET /company/{ticker}")

    try:
        import httpx
    except ImportError:
        log_result("httpx installed", False, "pip install httpx")
        return

    base_url = "http://127.0.0.1:8000"

    # Health check
    try:
        r = httpx.get(f"{base_url}/", timeout=5)
        log_result("Health endpoint (GET /)", r.status_code == 200, f"status={r.status_code}")
    except httpx.ConnectError:
        print(f"\n  {WARN}  Server not running!")
        print(f"       Start it first:  python -m uvicorn main:app --reload")
        print(f"       Then re-run this script.")
        log_result("Server reachable", False, "Connection refused")
        return

    # Company endpoint
    try:
        r = httpx.get(f"{base_url}/company/{TICKER}", timeout=30)
        log_result(
            f"GET /company/{TICKER} returns 200",
            r.status_code == 200,
            f"status={r.status_code}",
        )

        if r.status_code == 200:
            data = r.json()
            log_result("Response has 'profile'", "profile" in data)
            log_result("Response has 'market_data'", "market_data" in data)
            log_result(
                "Profile company_name is populated",
                bool(data.get("profile", {}).get("company_name")),
                f"company_name = {data['profile']['company_name']}",
            )

            print(f"\n  📋 Full response:")
            print(json.dumps(data, indent=2))

    except Exception as e:
        log_result("GET /company/{ticker}", False, str(e))

    # Invalid ticker (should still return 200 — yfinance doesn't fail, just returns sparse data)
    try:
        r = httpx.get(f"{base_url}/company/ZZZINVALID999", timeout=15)
        log_result(
            "Invalid ticker doesn't crash",
            r.status_code in (200, 502),
            f"status={r.status_code}",
        )
    except Exception as e:
        log_result("Invalid ticker handling", False, str(e))


# ===================================================================
# RUNNER
# ===================================================================
def main():
    print("\n" + "█" * 60)
    print("  PHASE 1.1 — VERIFICATION SUITE")
    print(f"  Ticker: {TICKER}")
    print("█" * 60)

    start = time.time()

    # Core tests (no server needed)
    test_settings()
    test_company_profile()
    test_market_data()
    test_price_history()
    test_income_statement()
    test_balance_sheet()
    test_cash_flow()
    test_data_service()
    test_data_service_financials()
    test_schemas()

    # API test (needs server running)
    test_api_endpoint()

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

    print(f"\n{'█' * 60}\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
