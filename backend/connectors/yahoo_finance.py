"""
Yahoo Finance connector — Adapter Pattern.

Translates raw yfinance objects into clean Python dictionaries.
No other module in the project should import yfinance directly.

If Yahoo Finance is ever replaced (e.g., by Polygon), only this file
changes. Every consumer still receives the same dictionary shapes.

Functions (one responsibility each):
    get_company_profile(ticker)   → company metadata
    get_market_data(ticker)       → current price & trading metrics
    get_price_history(ticker)     → historical OHLCV records
    get_income_statement(ticker)  → annual income statement
    get_balance_sheet(ticker)     → annual balance sheet
    get_cash_flow(ticker)         → annual cash-flow statement
"""

import logging
from typing import Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------
class YahooFinanceError(Exception):
    """Raised when Yahoo Finance data retrieval fails."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_RESOLVED_CACHE = {}

def resolve_ticker(ticker: str) -> str:
    """Resolve a user-entered ticker into a valid Yahoo Finance symbol.

    Tries the ticker as-is first (works for US stocks like AAPL, MSFT).
    If that returns no data, tries with .NS suffix (Indian NSE stocks
    like WIPRO → WIPRO.NS, RELIANCE → RELIANCE.NS).
    If the user already provided a suffix (e.g. WIPRO.NS), uses it directly.
    """
    ticker = ticker.strip().upper()

    if not ticker:
        raise YahooFinanceError("Ticker cannot be empty.")

    # User already specified an exchange suffix
    if "." in ticker:
        return ticker

    # Return cached resolution if available
    if ticker in _RESOLVED_CACHE:
        return _RESOLVED_CACHE[ticker]

    # Suppress yfinance internal logger spam during probing
    yf_logger = logging.getLogger("yfinance")
    old_level = yf_logger.level
    yf_logger.setLevel(logging.CRITICAL)

    try:
        # Step 1: Try ticker directly (US stocks)
        try:
            stock = yf.Ticker(ticker)
            info = stock.info or {}
            if (
                info.get("longName")
                or info.get("shortName")
                or info.get("regularMarketPrice")
                or info.get("currentPrice")
            ):
                _RESOLVED_CACHE[ticker] = ticker
                return ticker
        except Exception:
            pass

        # Step 2: Try NSE India (.NS suffix)
        nse_ticker = ticker + ".NS"
        try:
            stock = yf.Ticker(nse_ticker)
            info = stock.info or {}
            if (
                info.get("longName")
                or info.get("shortName")
                or info.get("regularMarketPrice")
                or info.get("currentPrice")
            ):
                logger.info("Resolved '%s' → '%s' (NSE India)", ticker, nse_ticker)
                _RESOLVED_CACHE[ticker] = nse_ticker
                return nse_ticker
        except Exception:
            pass
    finally:
        # Restore yfinance logger
        yf_logger.setLevel(old_level)

    # Fallback: return original ticker and let downstream handle errors
    logger.warning("Could not resolve ticker '%s', using as-is", ticker)
    _RESOLVED_CACHE[ticker] = ticker
    return ticker



def _get_stock(symbol: str) -> yf.Ticker:
    """Create a yfinance Ticker using the resolved symbol."""
    resolved = resolve_ticker(symbol)
    return yf.Ticker(resolved)


def _safe(value, default=None):
    """Return *default* if *value* is None or NaN."""
    if value is None:
        return default
    if isinstance(value, float) and pd.isna(value):
        return default
    return value


def _statement_to_records(df: pd.DataFrame) -> list[dict]:
    """Convert a yfinance financial-statement DataFrame to a list of dicts.

    Each dict represents one fiscal period. Line-item names are converted to
    snake_case keys; NaN values become None.
    """
    if df is None or df.empty:
        return []

    records: list[dict] = []
    for col in df.columns:
        period_data: dict = {"period": col.strftime("%Y-%m-%d")}
        for idx in df.index:
            key = str(idx).strip().replace(" ", "_").lower()
            val = df.loc[idx, col]
            period_data[key] = None if pd.isna(val) else round(float(val), 2)
        records.append(period_data)
    return records


# ---------------------------------------------------------------------------
# Public API — one narrow function per data type
# ---------------------------------------------------------------------------

def get_company_profile(ticker: str) -> dict:
    """Fetch normalized company profile.

    Returns
    -------
    dict
        Keys: ticker, company_name, sector, industry, country, currency,
              market_cap, employees, website, description, exchange.
    """
    try:
        stock = _get_stock(ticker)
        info: dict = stock.info

        if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
            logger.warning("No data returned for ticker '%s'", ticker)

        return {
            "ticker": ticker.strip().upper(),
            "company_name": _safe(info.get("longName")) or _safe(info.get("shortName"), "Unknown"),
            "sector": _safe(info.get("sector"), "N/A"),
            "industry": _safe(info.get("industry"), "N/A"),
            "country": _safe(info.get("country"), "N/A"),
            "currency": _safe(info.get("currency"), "N/A"),
            "market_cap": _safe(info.get("marketCap")),
            "employees": _safe(info.get("fullTimeEmployees")),
            "website": _safe(info.get("website"), "N/A"),
            "description": _safe(info.get("longBusinessSummary"), "N/A"),
            "exchange": _safe(info.get("exchange"), "N/A"),
        }
    except Exception as exc:
        logger.error("Failed to fetch company profile for '%s': %s", ticker, exc)
        raise YahooFinanceError(f"Company profile fetch failed for {ticker}") from exc


def get_market_data(ticker: str) -> dict:
    """Fetch current market / price data.

    Returns
    -------
    dict
        Keys: ticker, current_price, previous_close, open, day_high, day_low,
              volume, average_volume, fifty_two_week_high, fifty_two_week_low,
              pe_ratio, forward_pe, dividend_yield, beta.
    """
    try:
        stock = _get_stock(ticker)
        info: dict = stock.info

        return {
            "ticker": ticker.strip().upper(),
            "current_price": _safe(info.get("currentPrice")) or _safe(info.get("regularMarketPrice")),
            "previous_close": _safe(info.get("previousClose")) or _safe(info.get("regularMarketPreviousClose")),
            "open": _safe(info.get("open")) or _safe(info.get("regularMarketOpen")),
            "day_high": _safe(info.get("dayHigh")) or _safe(info.get("regularMarketDayHigh")),
            "day_low": _safe(info.get("dayLow")) or _safe(info.get("regularMarketDayLow")),
            "volume": _safe(info.get("volume")) or _safe(info.get("regularMarketVolume")),
            "average_volume": _safe(info.get("averageVolume")),
            "fifty_two_week_high": _safe(info.get("fiftyTwoWeekHigh")),
            "fifty_two_week_low": _safe(info.get("fiftyTwoWeekLow")),
            "pe_ratio": _safe(info.get("trailingPE")),
            "forward_pe": _safe(info.get("forwardPE")),
            "dividend_yield": _safe(info.get("dividendYield")),
            "beta": _safe(info.get("beta")),
        }
    except Exception as exc:
        logger.error("Failed to fetch market data for '%s': %s", ticker, exc)
        raise YahooFinanceError(f"Market data fetch failed for {ticker}") from exc


def get_price_history(ticker: str, period: str = "1y") -> list[dict]:
    """Fetch historical OHLCV price data.

    Parameters
    ----------
    ticker : str
        Stock symbol (e.g. "INFY", "AAPL").
    period : str
        yfinance period string — "1d", "5d", "1mo", "3mo", "6mo",
        "1y", "2y", "5y", "10y", "ytd", "max".

    Returns
    -------
    list[dict]
        Each dict: date, open, high, low, close, volume.
    """
    try:
        stock = _get_stock(ticker)
        hist: pd.DataFrame = stock.history(period=period)

        if hist.empty:
            logger.warning("Empty price history for '%s' (period=%s)", ticker, period)
            return []

        records: list[dict] = []
        for date, row in hist.iterrows():
            records.append({
                "date": date.strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })
        return records
    except Exception as exc:
        logger.error("Failed to fetch price history for '%s': %s", ticker, exc)
        raise YahooFinanceError(f"Price history fetch failed for {ticker}") from exc


def get_income_statement(ticker: str) -> list[dict]:
    """Fetch annual income-statement data.

    Returns
    -------
    list[dict]
        One dict per fiscal period with line-item keys in snake_case.
    """
    try:
        stock = _get_stock(ticker)
        return _statement_to_records(stock.income_stmt)
    except Exception as exc:
        logger.error("Failed to fetch income statement for '%s': %s", ticker, exc)
        raise YahooFinanceError(f"Income statement fetch failed for {ticker}") from exc


def get_balance_sheet(ticker: str) -> list[dict]:
    """Fetch annual balance-sheet data.

    Returns
    -------
    list[dict]
        One dict per fiscal period with line-item keys in snake_case.
    """
    try:
        stock = _get_stock(ticker)
        return _statement_to_records(stock.balance_sheet)
    except Exception as exc:
        logger.error("Failed to fetch balance sheet for '%s': %s", ticker, exc)
        raise YahooFinanceError(f"Balance sheet fetch failed for {ticker}") from exc


def get_cash_flow(ticker: str) -> list[dict]:
    """Fetch annual cash-flow-statement data.

    Returns
    -------
    list[dict]
        One dict per fiscal period with line-item keys in snake_case.
    """
    try:
        stock = _get_stock(ticker)
        return _statement_to_records(stock.cashflow)
    except Exception as exc:
        logger.error("Failed to fetch cash flow for '%s': %s", ticker, exc)
        raise YahooFinanceError(f"Cash flow fetch failed for {ticker}") from exc
