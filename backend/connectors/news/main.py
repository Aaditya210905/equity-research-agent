from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .models import CompanyNewsRequest, MarketNewsRequest, QuotesRequest, SearchRequest, TickerRequest
from .service import cached, collect_company_news, collect_market_news, generate_brief, load_quote, validate_ticker, yahoo_search_url
from .universe import infer_market
from .service import fetch_text


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(title="Meridian News API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def ticker_or_422(value: str) -> str:
    try:
        return validate_ticker(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/getQuote")
async def get_quote(request: TickerRequest):
    ticker = ticker_or_422(request.ticker)
    quote = await load_quote(ticker)
    return {"ok": True, "quote": quote.model_dump()} if quote else {"ok": False, "error": "Quote unavailable"}


@app.post("/api/getQuotes")
async def get_quotes(request: QuotesRequest):
    tickers = [ticker_or_422(ticker) for ticker in request.tickers]
    quotes = await asyncio.gather(*(load_quote(ticker) for ticker in tickers))
    return {"quotes": [quote.model_dump() for quote in quotes if quote]}


@app.post("/api/getCompanyNews")
async def get_company_news(request: CompanyNewsRequest):
    ticker = ticker_or_422(request.ticker)
    items = await cached(f"news-v2:{ticker}", 240, lambda: collect_company_news(ticker, request.name))
    return {"items": [item.model_dump() for item in items], "sources": list(dict.fromkeys(item.origin for item in items))}


@app.post("/api/getMarketNews")
async def get_market_news(request: MarketNewsRequest):
    items = await cached(f"mkt-v2:{request.market}", 240, lambda: collect_market_news(request.market))
    return {"items": [item.model_dump() for item in items], "sources": list(dict.fromkeys(item.origin for item in items)), "market": request.market}


@app.post("/api/searchTickers")
async def search_tickers(request: SearchRequest):
    raw = await fetch_text(yahoo_search_url(request.q, 0, 8), "application/json")
    if not raw:
        return {"hits": []}
    try:
        body = json.loads(raw)
        hits = []
        for item in body.get("quotes", []):
            if not item.get("symbol") or not (item.get("quoteType") == "EQUITY" or item.get("typeDisp") == "Equity"):
                continue
            hits.append({"ticker": item["symbol"], "name": item.get("shortname") or item.get("longname") or item["symbol"], "exchange": item.get("exchDisp") or "", "market": infer_market(item["symbol"], item.get("exchDisp")), "type": item.get("typeDisp") or "Equity"})
        return {"hits": hits}
    except (ValueError, TypeError, KeyError):
        return {"hits": []}


@app.post("/api/generateBrief")
async def generate_research_brief(request: CompanyNewsRequest):
    ticker = ticker_or_422(request.ticker)
    brief, error = await generate_brief(ticker, request.name)
    return {"ok": True, "brief": brief.model_dump()} if brief else {"ok": False, "error": error}
