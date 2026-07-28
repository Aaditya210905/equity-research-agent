"""
News connector — stub for Phase 1.2.

Will be implemented in a later phase using RSS feeds (cleanest legal path)
and optionally News API for broader coverage.

Planned sources:
    - Google News RSS (filtered by company name)
    - Moneycontrol RSS
    - Economic Times RSS
    - LiveMint RSS
    - News API (with API key)
"""

import logging

logger = logging.getLogger(__name__)


class NewsConnectorError(Exception):
    """Raised when news retrieval fails."""


def get_company_news(ticker: str, days: int = 7) -> list[dict]:
    """Fetch recent news for a company.

    Parameters
    ----------
    ticker : str
        Stock symbol.
    days : int
        Look-back window in days (default 7).

    Returns
    -------
    list[dict]
        Each record: {title, source, url, published_date, summary}.

    Note
    ----
    Stub — returns empty list until implemented in a later phase.
    """
    logger.info("News connector not yet implemented (ticker=%s)", ticker)
    return []
