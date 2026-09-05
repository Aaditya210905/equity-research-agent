"""
News connector — wraps the newspython sub-package.

Aggregates company and market news from Google News RSS, Bing News RSS,
and Yahoo Finance with deduplication, relevance filtering, and caching.
"""

import asyncio
import logging
from typing import Optional

from connectors.news.service import (
    collect_company_news,
    collect_market_news,
)

logger = logging.getLogger(__name__)


class NewsConnectorError(Exception):
    """Raised when news retrieval fails."""


async def get_company_news_async(
    ticker: str, name: Optional[str] = None
) -> list[dict]:
    """Fetch recent news for a company (async).

    Parameters
    ----------
    ticker : str
        Stock symbol (e.g. "TCS", "AAPL", "RELIANCE.NS").
    name : str, optional
        Company name for better relevance filtering.

    Returns
    -------
    list[dict]
        Each record follows the NewsItem schema from newspython.
    """
    try:
        items = await collect_company_news(ticker, name)
        return [item.model_dump() for item in items]
    except Exception as exc:
        logger.error("News fetch failed for '%s': %s", ticker, exc)
        return []


async def get_market_news_async(market: str = "IN") -> list[dict]:
    """Fetch market-wide news (async).

    Parameters
    ----------
    market : str
        "IN" for Indian markets, "US" for US markets.

    Returns
    -------
    list[dict]
        Each record follows the NewsItem schema.
    """
    try:
        items = await collect_market_news(market)
        return [item.model_dump() for item in items]
    except Exception as exc:
        logger.error("Market news fetch failed for '%s': %s", market, exc)
        return []


def get_company_news(ticker: str, name: Optional[str] = None) -> list[dict]:
    """Fetch recent news for a company (sync wrapper).

    For use in non-async contexts. Prefer get_company_news_async in routes.
    """
    try:
        return asyncio.run(get_company_news_async(ticker, name))
    except RuntimeError:
        # Already in an event loop — create a new one
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(get_company_news_async(ticker, name))
        finally:
            loop.close()
