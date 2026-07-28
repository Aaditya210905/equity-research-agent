"""
Pydantic response schemas for market-data endpoints.

These models define the JSON contract that every consumer
(API, agents, frontend) relies on. The structure is:

    MarketSnapshot
    ├── PriceSnapshot     (current, open, high, low, previous_close)
    ├── Valuation         (market_cap, enterprise_value, shares_outstanding)
    ├── Multiples         (pe_ratio, forward_pe, peg_ratio, price_to_book, eps)
    └── TradingStatistics (volume, beta, dividend_yield, 52-week range)

Plus:
    PriceRecord           (single OHLCV row for historical data)
    PriceHistory          (list of PriceRecords with metadata)
"""

from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Sub-models — one per data category
# ---------------------------------------------------------------------------

class PriceSnapshot(BaseModel):
    """Current session price data."""

    current: Optional[float] = Field(None, description="Latest traded price")
    open: Optional[float] = Field(None, description="Session open price")
    high: Optional[float] = Field(None, description="Session high")
    low: Optional[float] = Field(None, description="Session low")
    previous_close: Optional[float] = Field(None, description="Previous session close")


class Valuation(BaseModel):
    """Company valuation metrics."""

    market_cap: Optional[float] = Field(None, description="Market capitalization")
    enterprise_value: Optional[float] = Field(None, description="Enterprise value (market cap + debt - cash)")
    shares_outstanding: Optional[float] = Field(None, description="Total shares outstanding")


class Multiples(BaseModel):
    """Financial multiples / ratios."""

    pe_ratio: Optional[float] = Field(None, description="Trailing P/E ratio")
    forward_pe: Optional[float] = Field(None, description="Forward P/E ratio")
    peg_ratio: Optional[float] = Field(None, description="PEG ratio (PE / growth)")
    price_to_book: Optional[float] = Field(None, description="Price-to-book ratio")
    eps: Optional[float] = Field(None, description="Trailing earnings per share")


class TradingStatistics(BaseModel):
    """Trading volume and risk metrics."""

    volume: Optional[int] = Field(None, description="Current session volume")
    average_volume: Optional[int] = Field(None, description="Average daily volume")
    beta: Optional[float] = Field(None, description="Beta coefficient (volatility vs market)")
    dividend_yield: Optional[float] = Field(None, description="Annual dividend yield (decimal)")
    fifty_two_week_high: Optional[float] = Field(None, description="52-week high price")
    fifty_two_week_low: Optional[float] = Field(None, description="52-week low price")


# ---------------------------------------------------------------------------
# Combined market snapshot
# ---------------------------------------------------------------------------

class MarketSnapshot(BaseModel):
    """Complete market data response for GET /market/{ticker}.

    JSON contract::

        {
            "ticker": "INFY",
            "price":     { ... },
            "valuation": { ... },
            "multiples": { ... },
            "trading":   { ... }
        }
    """

    ticker: str = Field(..., description="Stock ticker symbol")
    price: PriceSnapshot = Field(..., description="Current price snapshot")
    valuation: Valuation = Field(..., description="Valuation metrics")
    multiples: Multiples = Field(..., description="Financial multiples")
    trading: TradingStatistics = Field(..., description="Trading statistics")


# ---------------------------------------------------------------------------
# Historical price data
# ---------------------------------------------------------------------------

class PriceRecord(BaseModel):
    """Single OHLCV record for a trading day."""

    date: str = Field(..., description="Trading date (YYYY-MM-DD)")
    open: float = Field(..., description="Opening price")
    high: float = Field(..., description="Session high")
    low: float = Field(..., description="Session low")
    close: float = Field(..., description="Closing price")
    adjusted_close: float = Field(..., description="Adjusted closing price")
    volume: int = Field(..., description="Trading volume")


class PriceHistory(BaseModel):
    """Historical price data response for GET /market/{ticker}/history."""

    ticker: str = Field(..., description="Stock ticker symbol")
    period: str = Field(..., description="Time period requested")
    count: int = Field(..., description="Number of records returned")
    data: list[PriceRecord] = Field(..., description="OHLCV price records")
