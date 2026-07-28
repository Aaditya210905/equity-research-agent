"""
Phase 1.2 - Market Data Connector Verification Script

Run from the backend/ directory:
    python -X utf8 tests/test_phase1_2.py

Tests:
    1. Market connector functions (all 6)
    2. JSON contract validation against Pydantic schemas
    3. Price history with multiple periods
    4. Multi-ticker consistency (INFY, RELIANCE.NS, TCS.NS, etc.)
    5. API endpoints (requires server running)

Start the server first:
    python -m uvicorn main:app --reload
"""

import sys
import json
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
# 1. MARKET CONNECTOR — Individual Functions
# ===================================================================
TICKER = "INFY"


def test_current_price():
    section("1a. CONNECTOR -- get_current_price")
    try:
        from connectors.market import get_current_price

        data = get_current_price(TICKER)
        log_result("Returns a dict", isinstance(data, dict))

        expected = ["current", "open", "high", "low", "previous_close"]
        missing = [k for k in expected if k not in data]
        log_result("All price keys present", len(missing) == 0,
                   f"missing: {missing}" if missing else "")

        price = data.get("current")
        log_result("current is a positive number",
                   isinstance(price, (int, float)) and price > 0,
                   f"current = {price}")

        print(f"\n  Output: {json.dumps(data, indent=2)}")
    except Exception as e:
        log_result("get_current_price", False, str(e))


def test_valuation():
    section("1b. CONNECTOR -- get_valuation")
    try:
        from connectors.market import get_valuation

        data = get_valuation(TICKER)
        log_result("Returns a dict", isinstance(data, dict))

        expected = ["market_cap", "enterprise_value", "shares_outstanding"]
        missing = [k for k in expected if k not in data]
        log_result("All valuation keys present", len(missing) == 0,
                   f"missing: {missing}" if missing else "")

        mcap = data.get("market_cap")
        log_result("market_cap is populated",
                   mcap is not None and mcap > 0,
                   f"market_cap = {mcap}")

        print(f"\n  Output: {json.dumps(data, indent=2)}")
    except Exception as e:
        log_result("get_valuation", False, str(e))


def test_multiples():
    section("1c. CONNECTOR -- get_multiples")
    try:
        from connectors.market import get_multiples

        data = get_multiples(TICKER)
        log_result("Returns a dict", isinstance(data, dict))

        expected = ["pe_ratio", "forward_pe", "peg_ratio", "price_to_book", "eps"]
        missing = [k for k in expected if k not in data]
        log_result("All multiples keys present", len(missing) == 0,
                   f"missing: {missing}" if missing else "")

        pe = data.get("pe_ratio")
        log_result("pe_ratio is populated (or null)",
                   pe is None or (isinstance(pe, (int, float)) and pe > 0),
                   f"pe_ratio = {pe}")

        print(f"\n  Output: {json.dumps(data, indent=2)}")
    except Exception as e:
        log_result("get_multiples", False, str(e))


def test_trading_statistics():
    section("1d. CONNECTOR -- get_trading_statistics")
    try:
        from connectors.market import get_trading_statistics

        data = get_trading_statistics(TICKER)
        log_result("Returns a dict", isinstance(data, dict))

        expected = ["volume", "average_volume", "beta", "dividend_yield",
                    "fifty_two_week_high", "fifty_two_week_low"]
        missing = [k for k in expected if k not in data]
        log_result("All trading keys present", len(missing) == 0,
                   f"missing: {missing}" if missing else "")

        vol = data.get("volume")
        log_result("volume is populated",
                   vol is not None and vol > 0,
                   f"volume = {vol}")

        print(f"\n  Output: {json.dumps(data, indent=2)}")
    except Exception as e:
        log_result("get_trading_statistics", False, str(e))


# ===================================================================
# 2. MARKET SNAPSHOT — Combined (single API call)
# ===================================================================

def test_market_snapshot():
    section("2. CONNECTOR -- get_market_snapshot (combined)")
    try:
        from connectors.market import get_market_snapshot

        data = get_market_snapshot(TICKER)
        log_result("Returns a dict", isinstance(data, dict))

        # Top-level keys
        top_keys = ["ticker", "price", "valuation", "multiples", "trading"]
        missing = [k for k in top_keys if k not in data]
        log_result("All top-level keys present", len(missing) == 0,
                   f"missing: {missing}" if missing else "")

        log_result("ticker is correct",
                   data.get("ticker") == TICKER.upper(),
                   f"ticker = {data.get('ticker')}")

        # Price sub-keys
        price = data.get("price", {})
        price_keys = ["current", "open", "high", "low", "previous_close"]
        missing_p = [k for k in price_keys if k not in price]
        log_result("price has all sub-keys", len(missing_p) == 0,
                   f"missing: {missing_p}" if missing_p else "")

        # Valuation sub-keys
        val = data.get("valuation", {})
        val_keys = ["market_cap", "enterprise_value", "shares_outstanding"]
        missing_v = [k for k in val_keys if k not in val]
        log_result("valuation has all sub-keys", len(missing_v) == 0,
                   f"missing: {missing_v}" if missing_v else "")

        # Multiples sub-keys
        mult = data.get("multiples", {})
        mult_keys = ["pe_ratio", "forward_pe", "peg_ratio", "price_to_book", "eps"]
        missing_m = [k for k in mult_keys if k not in mult]
        log_result("multiples has all sub-keys", len(missing_m) == 0,
                   f"missing: {missing_m}" if missing_m else "")

        # Trading sub-keys
        trd = data.get("trading", {})
        trd_keys = ["volume", "average_volume", "beta", "dividend_yield",
                    "fifty_two_week_high", "fifty_two_week_low"]
        missing_t = [k for k in trd_keys if k not in trd]
        log_result("trading has all sub-keys", len(missing_t) == 0,
                   f"missing: {missing_t}" if missing_t else "")

        print(f"\n  Full snapshot:")
        print(f"  {json.dumps(data, indent=2)}")

    except Exception as e:
        log_result("get_market_snapshot", False, str(e))


# ===================================================================
# 3. PYDANTIC SCHEMA VALIDATION
# ===================================================================

def test_schema_validation():
    section("3. PYDANTIC SCHEMA VALIDATION")
    try:
        from connectors.market import get_market_snapshot, get_price_history
        from schemas.market import MarketSnapshot, PriceHistory, PriceRecord

        # MarketSnapshot
        raw = get_market_snapshot(TICKER)
        snapshot = MarketSnapshot(**raw)
        log_result("MarketSnapshot validates raw connector output", True)
        log_result("Serializes to JSON",
                   len(snapshot.model_dump_json()) > 50,
                   f"{len(snapshot.model_dump_json())} chars")

        # PriceRecord
        records = get_price_history(TICKER, period="1mo")
        if records:
            rec = PriceRecord(**records[0])
            log_result("PriceRecord validates raw history record", True)
            log_result("adjusted_close field present",
                       rec.adjusted_close is not None,
                       f"adjusted_close = {rec.adjusted_close}")
        else:
            log_result("PriceRecord validation", False, "No history records")

        # PriceHistory
        history = PriceHistory(
            ticker=TICKER,
            period="1mo",
            count=len(records),
            data=[PriceRecord(**r) for r in records],
        )
        log_result("PriceHistory composes correctly", True,
                   f"{history.count} records")

    except Exception as e:
        log_result("Schema validation", False, str(e))


# ===================================================================
# 4. PRICE HISTORY — Multiple Periods
# ===================================================================

def test_price_history_periods():
    section("4. PRICE HISTORY -- Multiple Periods")
    try:
        from connectors.market import get_price_history

        periods = ["1mo", "3mo", "6mo", "1y"]
        for period in periods:
            records = get_price_history(TICKER, period=period)
            has_data = isinstance(records, list) and len(records) > 0
            log_result(f"Period '{period}' returns data",
                       has_data,
                       f"{len(records)} records" if has_data else "EMPTY")

            if records:
                first = records[0]
                has_adj = "adjusted_close" in first
                log_result(f"Period '{period}' has adjusted_close", has_adj)

    except Exception as e:
        log_result("Price history periods", False, str(e))


# ===================================================================
# 5. MULTI-TICKER CONSISTENCY
# ===================================================================

def test_multi_ticker():
    section("5. MULTI-TICKER CONSISTENCY")

    tickers = ["INFY", "RELIANCE.NS", "TCS.NS", "ICICIBANK.NS", "SBIN.NS", "HDFCBANK.NS"]

    try:
        from connectors.market import get_market_snapshot

        expected_top_keys = {"ticker", "price", "valuation", "multiples", "trading"}

        for t in tickers:
            try:
                data = get_market_snapshot(t)
                has_all_keys = set(data.keys()) >= expected_top_keys
                price = data.get("price", {}).get("current")
                log_result(
                    f"{t:15s} -- schema valid, price={price}",
                    has_all_keys and price is not None,
                )
            except Exception as e:
                log_result(f"{t:15s} -- fetch", False, str(e))

    except Exception as e:
        log_result("Multi-ticker test", False, str(e))


# ===================================================================
# 6. API ENDPOINTS (requires server running)
# ===================================================================

def test_api_market_snapshot():
    section("6a. API ENDPOINT -- GET /market/{ticker}")

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
        print(f"         Then re-run this script.")
        log_result("Server reachable", False, "Connection refused")
        return

    # Market snapshot
    try:
        r = httpx.get(f"{base_url}/market/{TICKER}", timeout=30)
        log_result(f"GET /market/{TICKER} returns 200",
                   r.status_code == 200,
                   f"status={r.status_code}")

        if r.status_code == 200:
            data = r.json()
            log_result("Response has 'ticker'", "ticker" in data)
            log_result("Response has 'price'", "price" in data)
            log_result("Response has 'valuation'", "valuation" in data)
            log_result("Response has 'multiples'", "multiples" in data)
            log_result("Response has 'trading'", "trading" in data)

            print(f"\n  Full response:")
            print(f"  {json.dumps(data, indent=2)}")

    except Exception as e:
        log_result("GET /market/{ticker}", False, str(e))


def test_api_price_history():
    section("6b. API ENDPOINT -- GET /market/{ticker}/history")

    try:
        import httpx
    except ImportError:
        return

    base_url = "http://127.0.0.1:8000"

    try:
        r = httpx.get(f"{base_url}/market/{TICKER}/history?period=1mo", timeout=30)
        log_result(f"GET /market/{TICKER}/history?period=1mo returns 200",
                   r.status_code == 200,
                   f"status={r.status_code}")

        if r.status_code == 200:
            data = r.json()
            log_result("Response has 'ticker'", "ticker" in data)
            log_result("Response has 'period'", "period" in data)
            log_result("Response has 'count'", "count" in data)
            log_result("Response has 'data' list",
                       "data" in data and isinstance(data["data"], list))

            count = data.get("count", 0)
            log_result(f"Has {count} records", count > 0)

            if data.get("data"):
                first = data["data"][0]
                log_result("Record has adjusted_close",
                           "adjusted_close" in first,
                           f"first record: {first}")

    except Exception as e:
        log_result("GET /market/{ticker}/history", False, str(e))

    # Invalid period should return 422
    try:
        r = httpx.get(f"{base_url}/market/{TICKER}/history?period=invalid", timeout=10)
        log_result("Invalid period returns 422",
                   r.status_code == 422,
                   f"status={r.status_code}")
    except Exception as e:
        log_result("Invalid period test", False, str(e))


def test_api_multi_ticker():
    section("6c. API ENDPOINT -- Multi-ticker consistency")

    try:
        import httpx
    except ImportError:
        return

    base_url = "http://127.0.0.1:8000"

    tickers = ["INFY", "RELIANCE.NS", "TCS.NS"]
    for t in tickers:
        try:
            r = httpx.get(f"{base_url}/market/{t}", timeout=30)
            if r.status_code == 200:
                data = r.json()
                has_all = all(k in data for k in ["ticker", "price", "valuation", "multiples", "trading"])
                log_result(f"GET /market/{t} -- valid schema", has_all)
            else:
                log_result(f"GET /market/{t}", False, f"status={r.status_code}")
        except Exception as e:
            log_result(f"GET /market/{t}", False, str(e))


# ===================================================================
# RUNNER
# ===================================================================
def main():
    print("\n" + "#" * 60)
    print("  PHASE 1.2 -- MARKET DATA CONNECTOR VERIFICATION")
    print(f"  Primary ticker: {TICKER}")
    print("#" * 60)

    start = time.time()

    # Core tests (no server needed)
    test_current_price()
    test_valuation()
    test_multiples()
    test_trading_statistics()
    test_market_snapshot()
    test_schema_validation()
    test_price_history_periods()
    test_multi_ticker()

    # API tests (needs server running)
    test_api_market_snapshot()
    test_api_price_history()
    test_api_multi_ticker()

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
