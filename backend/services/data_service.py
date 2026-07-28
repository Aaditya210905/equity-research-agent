"""
Data Service — the single entry point every higher layer uses for data.

The service does NOT know which connector is behind the scenes.
It speaks in terms of:
    - Company Profile
    - Market Snapshot
    - Price History
    - Financials (income, balance sheet, cash flow)

Diagram:
    API / Agent
        |
        v
    Data Service
        |
        +--------------------+--------------------+
        |                    |                    |
        v                    v                    v
    Company Connector   Market Connector    Yahoo Finance
    (company.py)        (market.py)        (yahoo_finance.py)
        |                    |                    |
        v                    v                    v
    yahoo_finance.py    yfinance             yfinance
"""

import logging

from connectors import yahoo_finance
from connectors import market as market_connector
from connectors import company as company_connector
from connectors.yahoo_finance import YahooFinanceError
from connectors.market import MarketDataError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Company
# ---------------------------------------------------------------------------

def get_company_overview(ticker: str) -> dict:
    """Return combined profile + market data for a ticker.

    Returns
    -------
    dict
        {
            "profile": { ... CompanyProfile fields ... },
            "market_data": { ... MarketData fields ... },
        }

    Raises
    ------
    YahooFinanceError
        If the underlying connector fails.
    """
    logger.info("Fetching company overview for '%s'", ticker)

    profile = company_connector.get_company_profile(ticker)
    market_data = yahoo_finance.get_market_data(ticker)

    return {
        "profile": profile,
        "market_data": market_data,
    }


# ---------------------------------------------------------------------------
# Market Data (Phase 1.2)
# ---------------------------------------------------------------------------

def get_market_snapshot(ticker: str) -> dict:
    """Return the full market data snapshot (price + valuation + multiples + trading).

    Returns the exact JSON contract defined in schemas/market.py.
    Uses a single API call internally.

    Returns
    -------
    dict
        {ticker, price, valuation, multiples, trading}
    """
    logger.info("Fetching market snapshot for '%s'", ticker)
    return market_connector.get_market_snapshot(ticker)


def get_price_history(ticker: str, period: str = "1y") -> dict:
    """Return historical OHLCV records with metadata.

    Returns
    -------
    dict
        {ticker, period, count, data: [{date, open, high, low, close,
        adjusted_close, volume}, ...]}
    """
    logger.info("Fetching price history for '%s' (period=%s)", ticker, period)

    records = market_connector.get_price_history(ticker, period=period)

    return {
        "ticker": ticker.strip().upper(),
        "period": period,
        "count": len(records),
        "data": records,
    }


# ---------------------------------------------------------------------------
# Financials
# ---------------------------------------------------------------------------

def get_financial_statements(ticker: str) -> dict:
    """Return all three annual financial statements.

    Returns
    -------
    dict
        {
            "income_statement": [ ... ],
            "balance_sheet": [ ... ],
            "cash_flow": [ ... ],
        }
    """
    logger.info("Fetching financial statements for '%s'", ticker)

    return {
        "income_statement": yahoo_finance.get_income_statement(ticker),
        "balance_sheet": yahoo_finance.get_balance_sheet(ticker),
        "cash_flow": yahoo_finance.get_cash_flow(ticker),
    }
