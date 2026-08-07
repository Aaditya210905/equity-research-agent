"""
Market Data connector — structured market information for equity analysis.

Provides all market-related data that future AI agents need:
    - Current price snapshot
    - Company valuation metrics
    - Financial multiples
    - Trading statistics
    - Historical OHLCV price data

Architecture:
    Data Service
        |
        v
    Market Connector  <-- this file
        |
        v
    Yahoo Finance (yfinance)
        |
        v
    Standardized JSON

The connector returns the exact JSON contract that every downstream
consumer (agents, service layer, API) relies on. If the data source
changes from Yahoo to Polygon or NSE, only this file is modified.

Functions (one responsibility each):
    get_current_price(ticker)        -> price snapshot
    get_valuation(ticker)            -> market cap, EV, shares
    get_multiples(ticker)            -> PE, PEG, P/B, EPS
    get_trading_statistics(ticker)   -> volume, beta, dividends, 52-week
    get_market_snapshot(ticker)      -> ALL of the above (single API call)
    get_price_history(ticker, period)-> historical OHLCV records
"""

import logging

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------
class MarketDataError(Exception):
    """Raised when market data retrieval fails."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _fetch_info(symbol: str) -> dict:
    """Fetch the raw info dict from yfinance. Single HTTP call."""
    from connectors.yahoo_finance import resolve_ticker
    resolved = resolve_ticker(symbol)
    stock = yf.Ticker(resolved)
    info = stock.info or {}
    return info


def _safe(value, default=None):
    """Return *default* if *value* is None or NaN."""
    if value is None:
        return default
    if isinstance(value, float) and pd.isna(value):
        return default
    return value


# ---------------------------------------------------------------------------
# Individual data extractors (each makes its own API call)
# ---------------------------------------------------------------------------

def get_current_price(ticker: str) -> dict:
    """Fetch current price snapshot.

    Returns
    -------
    dict
        {current, open, high, low, previous_close}
    """
    try:
        info = _fetch_info(ticker)
        return {
            "current": _safe(info.get("currentPrice")) or _safe(info.get("regularMarketPrice")),
            "open": _safe(info.get("open")) or _safe(info.get("regularMarketOpen")),
            "high": _safe(info.get("dayHigh")) or _safe(info.get("regularMarketDayHigh")),
            "low": _safe(info.get("dayLow")) or _safe(info.get("regularMarketDayLow")),
            "previous_close": _safe(info.get("previousClose")) or _safe(info.get("regularMarketPreviousClose")),
        }
    except Exception as exc:
        logger.error("Failed to fetch price for '%s': %s", ticker, exc)
        raise MarketDataError(f"Price fetch failed for {ticker}") from exc


def get_valuation(ticker: str) -> dict:
    """Fetch company valuation metrics.

    Returns
    -------
    dict
        {market_cap, enterprise_value, shares_outstanding}
    """
    try:
        info = _fetch_info(ticker)
        return {
            "market_cap": _safe(info.get("marketCap")),
            "enterprise_value": _safe(info.get("enterpriseValue")),
            "shares_outstanding": _safe(info.get("sharesOutstanding")),
        }
    except Exception as exc:
        logger.error("Failed to fetch valuation for '%s': %s", ticker, exc)
        raise MarketDataError(f"Valuation fetch failed for {ticker}") from exc


def get_multiples(ticker: str) -> dict:
    """Fetch financial multiples / ratios.

    Returns
    -------
    dict
        {pe_ratio, forward_pe, peg_ratio, price_to_book, eps}
    """
    try:
        info = _fetch_info(ticker)
        return {
            "pe_ratio": _safe(info.get("trailingPE")),
            "forward_pe": _safe(info.get("forwardPE")),
            "peg_ratio": _safe(info.get("pegRatio")),
            "price_to_book": _safe(info.get("priceToBook")),
            "eps": _safe(info.get("trailingEps")),
        }
    except Exception as exc:
        logger.error("Failed to fetch multiples for '%s': %s", ticker, exc)
        raise MarketDataError(f"Multiples fetch failed for {ticker}") from exc


def get_trading_statistics(ticker: str) -> dict:
    """Fetch trading statistics.

    Returns
    -------
    dict
        {volume, average_volume, beta, dividend_yield,
         fifty_two_week_high, fifty_two_week_low}
    """
    try:
        info = _fetch_info(ticker)
        return {
            "volume": _safe(info.get("volume")) or _safe(info.get("regularMarketVolume")),
            "average_volume": _safe(info.get("averageVolume")),
            "beta": _safe(info.get("beta")),
            "dividend_yield": _safe(info.get("dividendYield")),
            "fifty_two_week_high": _safe(info.get("fiftyTwoWeekHigh")),
            "fifty_two_week_low": _safe(info.get("fiftyTwoWeekLow")),
        }
    except Exception as exc:
        logger.error("Failed to fetch trading stats for '%s': %s", ticker, exc)
        raise MarketDataError(f"Trading stats fetch failed for {ticker}") from exc


# ---------------------------------------------------------------------------
# Combined snapshot — ONE API call for everything
# ---------------------------------------------------------------------------

def get_market_snapshot(ticker: str) -> dict:
    """Fetch the complete market data snapshot in a single API call.

    This is the primary function consumers should use. It fetches
    ``stock.info`` once and splits the data into four categories.

    Returns
    -------
    dict
        The full JSON contract::

            {
                "ticker": "INFY",
                "price":     { current, open, high, low, previous_close },
                "valuation": { market_cap, enterprise_value, shares_outstanding },
                "multiples": { pe_ratio, forward_pe, peg_ratio, price_to_book, eps },
                "trading":   { volume, average_volume, beta, dividend_yield,
                               fifty_two_week_high, fifty_two_week_low },
            }
    """
    try:
        info = _fetch_info(ticker)
        normalized_ticker = ticker.strip().upper()

        return {
            "ticker": normalized_ticker,

            "currency": _safe(info.get("currency")),

            "price": {
                "current": _safe(info.get("currentPrice")) or _safe(info.get("regularMarketPrice")),
                "open": _safe(info.get("open")) or _safe(info.get("regularMarketOpen")),
                "high": _safe(info.get("dayHigh")) or _safe(info.get("regularMarketDayHigh")),
                "low": _safe(info.get("dayLow")) or _safe(info.get("regularMarketDayLow")),
                "previous_close": _safe(info.get("previousClose")) or _safe(info.get("regularMarketPreviousClose")),
            },

            "valuation": {
                "market_cap": _safe(info.get("marketCap")),
                "enterprise_value": _safe(info.get("enterpriseValue")),
                "shares_outstanding": _safe(info.get("sharesOutstanding")),
            },

            "multiples": {
                "pe_ratio": _safe(info.get("trailingPE")),
                "forward_pe": _safe(info.get("forwardPE")),
                "peg_ratio": _safe(info.get("pegRatio")),
                "price_to_book": _safe(info.get("priceToBook")),
                "eps": _safe(info.get("trailingEps")),
            },

            "trading": {
                "volume": _safe(info.get("volume")) or _safe(info.get("regularMarketVolume")),
                "average_volume": _safe(info.get("averageVolume")),
                "beta": _safe(info.get("beta")),
                "dividend_yield": _safe(info.get("dividendYield")),
                "fifty_two_week_high": _safe(info.get("fiftyTwoWeekHigh")),
                "fifty_two_week_low": _safe(info.get("fiftyTwoWeekLow")),
            },
        }
    except Exception as exc:
        logger.error("Failed to fetch market snapshot for '%s': %s", ticker, exc)
        raise MarketDataError(f"Market snapshot fetch failed for {ticker}") from exc


# ---------------------------------------------------------------------------
# Historical price data
# ---------------------------------------------------------------------------

def get_price_history(ticker: str, period: str = "1y") -> list[dict]:
    """Fetch historical OHLCV price data.

    Parameters
    ----------
    ticker : str
        Stock symbol (e.g. "INFY", "AAPL", "RELIANCE.NS").
    period : str
        One of: "1mo", "3mo", "6mo", "1y", "5y", "max".

    Returns
    -------
    list[dict]
        Each record: {date, open, high, low, close, adjusted_close, volume}.
        ``adjusted_close`` equals ``close`` in modern yfinance (auto-adjusted).
    """
    try:
        from connectors.yahoo_finance import resolve_ticker
        symbol = resolve_ticker(ticker)
        stock = yf.Ticker(symbol)
        hist: pd.DataFrame = stock.history(period=period)

        if hist.empty:
            logger.warning("Empty price history for '%s' (period=%s)", symbol, period)
            return []

        records: list[dict] = []
        for date, row in hist.iterrows():
            records.append({
                "date": date.strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "adjusted_close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })
        return records
    except Exception as exc:
        logger.error("Failed to fetch price history for '%s': %s", ticker, exc)
        raise MarketDataError(f"Price history fetch failed for {ticker}") from exc
