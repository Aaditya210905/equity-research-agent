"""
Company Profile connector — company identity and metadata.

Delegates to the Yahoo Finance adapter for now. If we add Finnhub or
NSE as a company-info source later, only this file changes.

Architecture:
    Data Service  ->  Company Connector  ->  yahoo_finance.py  ->  yfinance
"""

import logging

from connectors import yahoo_finance
from connectors.yahoo_finance import YahooFinanceError

logger = logging.getLogger(__name__)


def get_company_profile(ticker: str) -> dict:
    """Fetch normalized company profile.

    Returns
    -------
    dict
        {ticker, company_name, sector, industry, country, currency,
         market_cap, employees, website, description, exchange}
    """
    logger.info("Fetching company profile for '%s'", ticker)
    return yahoo_finance.get_company_profile(ticker)
