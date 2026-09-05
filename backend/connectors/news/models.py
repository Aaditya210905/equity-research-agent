from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field

Market = Literal["IN", "US"]
NewsOrigin = Literal["google-news", "yahoo", "bing"]


class Company(BaseModel):
    ticker: str
    display: str
    name: str
    market: Market
    exchange: str
    sector: str


class NewsItem(BaseModel):
    id: str
    title: str
    source: str
    url: str
    publishedAt: str | None = None
    snippet: str = ""
    thumbnail: str | None = None
    origin: NewsOrigin
    market: Market | Literal["GLOBAL"]


class Quote(BaseModel):
    ticker: str
    name: str
    exchange: str
    currency: str
    price: float
    change: float
    changePercent: float
    previousClose: float
    dayHigh: float | None = None
    dayLow: float | None = None
    volume: float | None = None
    week52High: float | None = None
    week52Low: float | None = None
    spark: list[float] = Field(default_factory=list)
    market: Market | Literal["OTHER"]
    asOf: str


class SearchHit(BaseModel):
    ticker: str
    name: str
    exchange: str
    market: Market | Literal["OTHER"]
    type: str


class ResearchBrief(BaseModel):
    headline: str
    stance: Literal["bullish", "bearish", "neutral"]
    summary: str
    catalysts: list[str]
    risks: list[str]
    watch: list[str]


class TickerRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=24, pattern=r"^[A-Z0-9^.&=-]{1,24}$")


class QuotesRequest(BaseModel):
    tickers: list[str] = Field(max_length=12)


class CompanyNewsRequest(TickerRequest):
    name: str | None = Field(default=None, max_length=80)


class MarketNewsRequest(BaseModel):
    market: Market


class SearchRequest(BaseModel):
    q: str = Field(min_length=1, max_length=40)
