"""
Pydantic response schemas for company-related endpoints.

These models serve as the contract between the backend and any consumer
(frontend, CLI, other services). They also power FastAPI's automatic
OpenAPI documentation and response validation.
"""

from typing import Optional

from pydantic import BaseModel, Field


class CompanyProfile(BaseModel):
    """Normalized company profile — source-agnostic."""

    ticker: str = Field(..., description="Stock ticker symbol")
    company_name: str = Field(..., description="Full legal company name")
    sector: Optional[str] = Field(None, description="Business sector (e.g. Technology)")
    industry: Optional[str] = Field(None, description="Specific industry classification")
    country: Optional[str] = Field(None, description="Country of incorporation")
    currency: Optional[str] = Field(None, description="Primary trading currency")
    market_cap: Optional[float] = Field(None, description="Market capitalization in local currency")
    employees: Optional[int] = Field(None, description="Full-time employee count")
    website: Optional[str] = Field(None, description="Company website URL")
    description: Optional[str] = Field(None, description="Business summary / description")
    exchange: Optional[str] = Field(None, description="Stock exchange identifier")


class MarketData(BaseModel):
    """Current market / price snapshot."""

    ticker: str = Field(..., description="Stock ticker symbol")
    current_price: Optional[float] = Field(None, description="Latest traded price")
    previous_close: Optional[float] = Field(None, description="Previous session close")
    open: Optional[float] = Field(None, description="Current session open")
    day_high: Optional[float] = Field(None, description="Session high")
    day_low: Optional[float] = Field(None, description="Session low")
    volume: Optional[int] = Field(None, description="Session volume")
    average_volume: Optional[int] = Field(None, description="Average daily volume")
    fifty_two_week_high: Optional[float] = Field(None, description="52-week high")
    fifty_two_week_low: Optional[float] = Field(None, description="52-week low")
    pe_ratio: Optional[float] = Field(None, description="Trailing P/E ratio")
    forward_pe: Optional[float] = Field(None, description="Forward P/E ratio")
    dividend_yield: Optional[float] = Field(None, description="Dividend yield (decimal)")
    beta: Optional[float] = Field(None, description="Beta coefficient")


class CompanyOverview(BaseModel):
    """Combined response for GET /company/{ticker}.

    Merges the profile and live market data into a single payload.
    """

    profile: CompanyProfile
    market_data: MarketData
