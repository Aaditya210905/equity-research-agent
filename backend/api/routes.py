"""
API routes for the Equity Research Agent.

Phase 1.1:
    GET  /company/{ticker}            -> CompanyOverview

Phase 1.2:
    GET  /market/{ticker}             -> MarketSnapshot
    GET  /market/{ticker}/history     -> PriceHistory

Phase 1.3:
    POST /documents/{ticker}/collect  -> CollectionResult
    GET  /documents/{ticker}          -> DocumentCollection
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from connectors.yahoo_finance import YahooFinanceError
from connectors.market import MarketDataError
from schemas.company import CompanyOverview
from schemas.market import MarketSnapshot, PriceHistory
from schemas.document import DocumentCollection, CollectionResult
from services import data_service, document_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Company endpoints (Phase 1.1)
# ---------------------------------------------------------------------------

@router.get(
    "/company/{ticker}",
    response_model=CompanyOverview,
    tags=["Company"],
    summary="Get company overview",
    description="Returns normalized company profile and live market data for the given ticker.",
)
async def get_company(ticker: str):
    """Fetch company profile + market data from Yahoo Finance."""
    try:
        overview = data_service.get_company_overview(ticker)
        return overview
    except YahooFinanceError as exc:
        logger.error("Connector error for ticker '%s': %s", ticker, exc)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to retrieve data for '{ticker.upper()}' from Yahoo Finance.",
        )
    except Exception as exc:
        logger.error("Unexpected error for ticker '%s': %s", ticker, exc)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while processing '{ticker.upper()}'.",
        )


# ---------------------------------------------------------------------------
# Market endpoints (Phase 1.2)
# ---------------------------------------------------------------------------

@router.get(
    "/market/{ticker}",
    response_model=MarketSnapshot,
    tags=["Market"],
    summary="Get market data snapshot",
    description=(
        "Returns structured market data: current price, valuation, "
        "financial multiples, and trading statistics."
    ),
)
async def get_market_snapshot(ticker: str):
    """Fetch the full market data snapshot."""
    try:
        snapshot = data_service.get_market_snapshot(ticker)
        return snapshot
    except MarketDataError as exc:
        logger.error("Market connector error for '%s': %s", ticker, exc)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to retrieve market data for '{ticker.upper()}'.",
        )
    except Exception as exc:
        logger.error("Unexpected error for ticker '%s': %s", ticker, exc)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while processing '{ticker.upper()}'.",
        )


@router.get(
    "/market/{ticker}/history",
    response_model=PriceHistory,
    tags=["Market"],
    summary="Get price history",
    description=(
        "Returns historical OHLCV price data for the given ticker. "
        "Supported periods: 1mo, 3mo, 6mo, 1y, 5y, max."
    ),
)
async def get_price_history(
    ticker: str,
    period: str = Query(
        default="1y",
        description="Time period: 1mo, 3mo, 6mo, 1y, 5y, max",
        pattern="^(1mo|3mo|6mo|1y|5y|max)$",
    ),
):
    """Fetch historical OHLCV price data."""
    try:
        history = data_service.get_price_history(ticker, period=period)
        return history
    except MarketDataError as exc:
        logger.error("Price history error for '%s': %s", ticker, exc)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to retrieve price history for '{ticker.upper()}'.",
        )
    except Exception as exc:
        logger.error("Unexpected error for ticker '%s': %s", ticker, exc)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while processing '{ticker.upper()}'.",
        )


# ---------------------------------------------------------------------------
# Document endpoints (Phase 1.3)
# ---------------------------------------------------------------------------

@router.post(
    "/documents/{ticker}/collect",
    response_model=CollectionResult,
    tags=["Documents"],
    summary="Collect documents for a company",
    description=(
        "Triggers document collection from all available sources "
        "(SEC EDGAR, Yahoo Finance). Downloads files, validates them, "
        "and registers metadata in the document database."
    ),
)
async def collect_documents(ticker: str):
    """Trigger document collection for a ticker.

    Flow:
        1. Fetch financial statements from Yahoo Finance -> save as JSON
        2. Download SEC filings (10-K, 10-Q) for US companies
        3. Validate & register everything in the document database
    """
    try:
        result = document_service.collect_documents(ticker)
        return result
    except Exception as exc:
        logger.error("Document collection error for '%s': %s", ticker, exc)
        raise HTTPException(
            status_code=500,
            detail=f"Document collection failed for '{ticker.upper()}': {str(exc)}",
        )


@router.get(
    "/documents/{ticker}",
    response_model=DocumentCollection,
    tags=["Documents"],
    summary="List company documents",
    description=(
        "Returns all documents registered for a company. "
        "Optionally filter by document type or year."
    ),
)
async def get_documents(
    ticker: str,
    doc_type: str = Query(
        default=None,
        description="Filter by document type (annual_report, quarterly_report, income_statement, etc.)",
    ),
    year: int = Query(
        default=None,
        description="Filter by fiscal year",
    ),
):
    """List all registered documents for a company."""
    try:
        docs = document_service.get_company_documents(ticker, doc_type=doc_type, year=year)
        return docs
    except Exception as exc:
        logger.error("Document listing error for '%s': %s", ticker, exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve documents for '{ticker.upper()}'.",
        )
