from __future__ import annotations

import asyncio
import json
import os
import re
import time
from datetime import datetime, timezone
from hashlib import md5
from typing import Any, Awaitable, Callable, TypeVar
from urllib.parse import urlencode, quote

import httpx

from .models import NewsItem, Quote, ResearchBrief, SearchHit
from .rss import parse_rss
from .universe import find_company, infer_market

T = TypeVar("T")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
TICKER_RE = re.compile(r"^[A-Z0-9^.&=-]{1,24}$", re.I)
_cache: dict[str, tuple[float, Any]] = {}


def validate_ticker(ticker: str) -> str:
    if not isinstance(ticker, str) or not 1 <= len(ticker) <= 24 or not TICKER_RE.fullmatch(ticker):
        raise ValueError("Invalid ticker")
    return ticker.upper()


def hash_id(value: str) -> str:
    # JavaScript's hash is intentionally replaced by a stable compact hash; IDs remain opaque and deterministic.
    return md5(value.encode("utf-8")).hexdigest()[:10]


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", title.lower())).strip()


def origin_label(origin: str) -> str:
    return {"google-news": "Google News", "yahoo": "Yahoo Finance", "bing": "Bing News"}[origin]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


async def cached(key: str, ttl_seconds: float, fn: Callable[[], Awaitable[T]]) -> T:
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl_seconds:
        return hit[1]
    try:
        value = await fn()
        _cache[key] = (time.time(), value)
        return value
    except Exception:
        if hit:
            return hit[1]
        raise


async def fetch_text(url: str, accept: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=9.0, follow_redirects=True, headers={"User-Agent": UA, "Accept": accept}) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
    except (httpx.HTTPError, TimeoutError):
        return None


def to_news(items: list[Any], origin: str, market: str, thumbnail: str | None = None) -> list[NewsItem]:
    result = []
    for item in items:
        if not item.title or not item.link:
            continue
        result.append(NewsItem(
            id=f"{origin}-{hash_id(item.link or item.title)}",
            title=item.title,
            source=item.source or origin_label(origin),
            url=item.link,
            publishedAt=item.published_at,
            snippet=item.snippet,
            thumbnail=thumbnail,
            origin=origin,
            market=market,
        ))
    return result


def google_news_url(query: str, market: str) -> str:
    locale = "hl=en-IN&gl=IN&ceid=IN:en" if market == "IN" else "hl=en-US&gl=US&ceid=US:en"
    return f"https://news.google.com/rss/search?q={quote(query)}&{locale}"


def bing_news_url(query: str, market: str) -> str:
    locale = "en-IN" if market == "IN" else "en-US"
    return f"https://www.bing.com/news/search?q={quote(query)}&format=rss&mkt={locale}"


def yahoo_search_url(query: str, news_count: int, quotes_count: int) -> str:
    return "https://query1.finance.yahoo.com/v1/finance/search?" + urlencode({"q": query, "newsCount": news_count, "quotesCount": quotes_count})


def yahoo_chart_url(ticker: str, range_name: str) -> str:
    return f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(ticker, safe='')}?interval=1d&range={range_name}"


def merge_news(groups: list[list[NewsItem]]) -> list[NewsItem]:
    seen: set[str] = set()
    result: list[NewsItem] = []
    for group in groups:
        for item in group:
            key = normalize_title(item.title)
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(item)
    result.sort(key=lambda item: item.publishedAt or "", reverse=True)
    return result[:40]


async def fetch_google(query: str, market: str) -> list[NewsItem]:
    xml = await fetch_text(google_news_url(query, market), "application/rss+xml, application/xml, text/xml")
    return to_news(parse_rss(xml), "google-news", market) if xml else []


async def fetch_bing(query: str, market: str) -> list[NewsItem]:
    xml = await fetch_text(bing_news_url(query, market), "application/rss+xml, application/xml, text/xml")
    return to_news(parse_rss(xml), "bing", market) if xml else []


async def fetch_yahoo_news(ticker_or_query: str, market: str) -> list[NewsItem]:
    raw = await fetch_text(yahoo_search_url(ticker_or_query, 12, 1), "application/json")
    if not raw:
        return []
    try:
        body = json.loads(raw)
        result = []
        for item in body.get("news", []):
            if not item.get("title") or not item.get("link"):
                continue
            timestamp = item.get("providerPublishTime")
            published = datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z") if timestamp else None
            resolutions = (item.get("thumbnail") or {}).get("resolutions") or []
            result.append(NewsItem(
                id=f"yahoo-{item.get('uuid') or hash_id(item.get('link') or item.get('title', ''))}",
                title=item.get("title", ""), source=item.get("publisher") or "Yahoo Finance",
                url=item.get("link", ""), publishedAt=published, snippet="",
                thumbnail=resolutions[0].get("url") if resolutions else None,
                origin="yahoo", market=market,
            ))
        return result
    except (ValueError, TypeError, KeyError, IndexError):
        return []


def company_query(ticker: str, name: str | None) -> tuple[str, str]:
    known = find_company(ticker)
    market = known.market if known else ("IN" if infer_market(ticker) == "IN" else "US")
    symbol = re.sub(r"\.(NS|BO)$", "", ticker, flags=re.I)
    label = name or (known.name if known else symbol)
    return f'"{label}" OR {symbol} (stock OR shares OR earnings)', market


def is_relevant(item: NewsItem, ticker: str, name: str | None) -> bool:
    hay = f"{item.title} {item.snippet}".lower()
    symbol = re.sub(r"\.(NS|BO)$", "", ticker, flags=re.I).lower()
    if len(symbol) >= 2 and symbol in hay:
        return True
    if not name:
        return False
    lowered_name = name.lower()
    if lowered_name in hay:
        return True
    skip = {"class", "group", "inc", "corp", "ltd", "limited", "the", "and", "company"}
    return any(word in hay for word in lowered_name.split() if len(word) > 4 and word not in skip)


async def collect_company_news(ticker: str, name: str | None = None) -> list[NewsItem]:
    query, market = company_query(ticker, name)
    google_items, bing_items, yahoo_items = await asyncio.gather(
        fetch_google(query, market), fetch_bing(query, market), fetch_yahoo_news(ticker, market)
    )
    yahoo_items = [item for item in yahoo_items if is_relevant(item, ticker, name)]
    merged = merge_news([google_items, bing_items, yahoo_items])
    focused = [item for item in merged if is_relevant(item, ticker, name)]
    return focused if len(focused) >= 4 else merged


async def collect_market_news(market: str) -> list[NewsItem]:
    query = ('NSE OR BSE OR "Nifty 50" OR "Sensex" OR "Indian stock market"' if market == "IN" else
             'NYSE OR NASDAQ OR "Wall Street" OR "S&P 500" OR "US stocks"')
    jobs = [fetch_google(query, market), fetch_bing(query, market)]
    if market == "US":
        jobs.append(fetch_yahoo_news("S&P 500 NASDAQ", market))
    return merge_news(list(await asyncio.gather(*jobs)))


def parse_quote(raw: str) -> Quote | None:
    try:
        result = (json.loads(raw).get("chart") or {}).get("result") or []
        if not result:
            return None
        result = result[0]
        meta = result.get("meta") or {}
        price = meta.get("regularMarketPrice")
        ticker = meta.get("symbol")
        if price is None or not ticker:
            return None
        quote_rows = ((result.get("indicators") or {}).get("quote") or [{}])
        closes = [n for n in (quote_rows[0].get("close") or []) if isinstance(n, (int, float))] if quote_rows else []
        previous = meta.get("chartPreviousClose") or (closes[-2] if len(closes) >= 2 else price)
        change = price - previous
        change_percent = meta.get("regularMarketChangePercent")
        if not isinstance(change_percent, (int, float)):
            change_percent = change / previous * 100 if previous else 0
        known = find_company(ticker)
        return Quote(
            ticker=ticker, name=known.name if known else meta.get("shortName") or meta.get("longName") or ticker,
            exchange=known.exchange if known else meta.get("fullExchangeName") or meta.get("exchangeName") or "",
            currency=meta.get("currency") or "USD", price=price, change=change,
            changePercent=change_percent, previousClose=previous,
            dayHigh=meta.get("regularMarketDayHigh"), dayLow=meta.get("regularMarketDayLow"),
            volume=meta.get("regularMarketVolume"), week52High=meta.get("fiftyTwoWeekHigh"),
            week52Low=meta.get("fiftyTwoWeekLow"), spark=closes[-60:],
            market=known.market if known else infer_market(ticker, meta.get("exchangeName")),
            asOf=datetime.fromtimestamp(meta["regularMarketTime"], timezone.utc).isoformat().replace("+00:00", "Z") if meta.get("regularMarketTime") else now_iso(),
        )
    except (ValueError, TypeError, KeyError, IndexError):
        return None


async def load_quote(ticker: str) -> Quote | None:
    async def load() -> Quote | None:
        raw = await fetch_text(yahoo_chart_url(ticker, "3mo"), "application/json")
        return parse_quote(raw) if raw else None
    return await cached(f"quote:{ticker}", 30, load)


def extract_json(text: str) -> str:
    fenced = re.search(r"```json\s*([\s\S]*?)```", text, flags=re.I)
    if fenced:
        return fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if start >= 0 and end > start else text


async def generate_brief(ticker: str, name: str | None) -> tuple[ResearchBrief | None, str | None]:
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        return None, "AI is not available in this environment"
    quote, news = await asyncio.gather(
        load_quote(ticker), cached(f"news-v2:{ticker}", 240, lambda: collect_company_news(ticker, name))
    )
    headlines = "\n".join(f"{i + 1}. [{item.source}] {item.title}{f' ({item.publishedAt[:10]})' if item.publishedAt else ''}" for i, item in enumerate(news[:12]))
    prompt = f'''You are an equity research analyst covering Indian (NSE/BSE) and US (NYSE/NASDAQ) listed companies.
Write a concise research note from the quote snapshot and recent headlines. Do not invent numbers that are not in the snapshot. If headlines are thin, say so. Be specific and sober — no hype.

Company: {name or (quote.name if quote else ticker)}
Ticker: {ticker}
Market: {quote.market if quote else "unknown"}
Last price: {f"{quote.price} {quote.currency} ({quote.changePercent:.2f}%)" if quote else "unavailable"}
Day range: {quote.dayLow if quote else "n/a"} – {quote.dayHigh if quote else "n/a"}
52-week: {quote.week52Low if quote else "n/a"} – {quote.week52High if quote else "n/a"}

Headlines:
{headlines or "(none retrieved)"}

Return JSON only with headline, stance, summary, catalysts, risks, and watch.'''
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post("https://api.x.ai/v1/chat/completions", headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}, json={"model": "grok-4.5", "messages": [{"role": "user", "content": prompt}], "max_tokens": 700, "temperature": 0.3})
        if response.status_code == 403:
            return None, "Research notes are paused because Grok quota for this app is exhausted."
        if response.status_code >= 400:
            return None, f"xAI API error {response.status_code}"
        text = ((response.json().get("choices") or [{}])[0].get("message") or {}).get("content", "")
        parsed = json.loads(extract_json(text))
        if not parsed.get("headline") or not parsed.get("summary"):
            raise ValueError("incomplete")
        stance = parsed.get("stance") if parsed.get("stance") in {"bullish", "bearish"} else "neutral"
        return ResearchBrief(headline=str(parsed["headline"])[:140], stance=stance, summary=str(parsed["summary"])[:800], catalysts=[str(x) for x in parsed.get("catalysts", [])[:4]], risks=[str(x) for x in parsed.get("risks", [])[:4]], watch=[str(x) for x in parsed.get("watch", [])[:4]]), None
    except (httpx.HTTPError, TimeoutError, ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError):
        return None, "Could not parse the research note"
