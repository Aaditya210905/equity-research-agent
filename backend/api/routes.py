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

Phase 1.4 (BSE filings):
    GET  /bse/search                  -> list[CompanyHit]
    POST /bse/filings/fetch           -> FetchResult
    GET  /bse/filings                 -> list[CompanyFolder]
    GET  /bse/file/{file_path}        -> PDF FileResponse

Phase 2.6:
    POST /ask                         -> RAGAnswer

Phase 4:
    POST /research/{ticker}           -> ResearchReport
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from connectors.yahoo_finance import YahooFinanceError
from connectors.market import MarketDataError
from schemas.company import CompanyOverview
from schemas.market import MarketSnapshot, PriceHistory
from schemas.document import DocumentCollection, CollectionResult
from schemas.answer import RAGAnswer, AskRequest
from schemas.research_report import ResearchReport, ResearchRequest
from services import data_service, document_service

from fastapi.responses import FileResponse
from connectors.bse import search_companies
from services.bse_service import ingest_company
from schemas.bse import FetchOptions
from services.bse_storage import list_company_folders, resolve_under_root

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

# ---------------------------------------------------------------------------
# Phase 1.4 — BSE Filings (annual reports, quarterly results, announcements)
# ---------------------------------------------------------------------------

@router.get(
    "/bse/search",
    tags=["BSE Filings"],
    summary="Search BSE-listed companies",
    description="Search for a company by name or symbol and get its BSE scrip code.",
)
async def bse_search(query: str = Query(min_length=2, max_length=80)):
    """Search BSE for a company to get its scrip code."""
    try:
        return await search_companies(query)
    except Exception as exc:
        logger.error("BSE search error: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))


@router.post(
    "/bse/filings/fetch",
    tags=["BSE Filings"],
    summary="Fetch BSE filings for a company",
    description=(
        "Fetches and saves annual reports, quarterly results, and corporate "
        "announcements from BSE India for the given scrip code."
    ),
)
async def bse_fetch_filings(options: FetchOptions):
    """Fetch and store BSE filings (annual reports, quarterly, announcements)."""
    try:
        return await ingest_company(options)
    except Exception as exc:
        logger.error("BSE fetch error for scrip '%s': %s", options.scripCode, exc)
        raise HTTPException(status_code=502, detail=str(exc))


@router.get(
    "/bse/filings",
    tags=["BSE Filings"],
    summary="List all fetched BSE filings",
    description="Returns a list of all companies whose filings have been downloaded.",
)
async def bse_list_filings():
    """List all BSE company filing folders that have been fetched."""
    return list_company_folders()


@router.get(
    "/bse/file/{file_path:path}",
    tags=["BSE Filings"],
    summary="Serve a downloaded BSE PDF",
    description="Serves a previously downloaded PDF filing by its relative path.",
)
async def bse_serve_file(file_path: str):
    """Serve a downloaded BSE PDF by relative path."""
    try:
        path = resolve_under_root(file_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, media_type="application/pdf", filename=path.name)

# ---------------------------------------------------------------------------
# RAG endpoint (Phase 2.6)
# ---------------------------------------------------------------------------

@router.post(
    "/ask",
    response_model=RAGAnswer,
    tags=["RAG"],
    summary="Ask a financial research question",
    description=(
        "Answers a question using retrieved evidence from indexed financial "
        "documents. Returns a grounded answer with citations and a confidence score. "
        "Requires documents to be indexed in the vector store."
    ),
)
async def ask_question(request: AskRequest):
    """Answer a question using the RAG pipeline.

    Flow:
        1. Classify question type
        2. Expand / rewrite query
        3. Retrieve relevant chunks from vector DB
        4. Build context with citations
        5. Generate answer via LLM
        6. Compute confidence score
    """
    try:
        from rag.orchestrator import ask

        result = ask(
            question=request.question,
            company=request.company,
            year=request.year,
            doc_type=request.doc_type,
            top_k=request.top_k,
            rewrite_query=request.rewrite_query,
        )
        return result
    except RuntimeError as exc:
        logger.error("RAG configuration error: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("RAG error: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process question: {str(exc)}",
        )


# ---------------------------------------------------------------------------
# Research Report endpoint (Phase 5 — full pipeline)
# ---------------------------------------------------------------------------

@router.post(
    "/research/{ticker}",
    tags=["Research"],
    summary="Generate verified equity research report",
    description=(
        "Generates a professional equity research report using the full pipeline: "
        "Planner → Tool Execution → Report Generation → Claim Verification → Revision. "
        "Returns the verified report, verification results, and a full execution trace."
    ),
)
async def generate_research_report(ticker: str, request: ResearchRequest = None):
    """Generate a full, verified equity research report.

    Pipeline:
        1. Planner creates structured execution plan
        2. Executor calls financial engine, retriever, market service, news
        3. Analyst generates 7-section report
        4. Claim extractor + verifier checks every factual claim
        5. Reviser adds disclaimers for unverified claims
    """
    try:
        from report.report_generator import generate_research

        result = generate_research(
            request=f"Generate a comprehensive equity research report for {ticker.upper()}",
            companies=[ticker.upper()],
        )

        return result

    except RuntimeError as exc:
        logger.error("Research config error for '%s': %s", ticker, exc)
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error("Research error for '%s': %s", ticker, exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate research report for '{ticker.upper()}'.",
        )
