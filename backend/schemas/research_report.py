"""
Pydantic schemas for equity research reports — Phase 4.
"""

from typing import Optional
from pydantic import BaseModel, Field


class ReportSection(BaseModel):
    """One section of the research report."""

    title: str = ""
    content: str = ""
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Section confidence (0–1)")
    evidence_count: int = Field(0, description="Number of evidence pieces used")


class ResearchReport(BaseModel):
    """Complete equity research report."""

    company: str = ""
    ticker: str = ""
    sector: str = ""

    executive_summary: ReportSection = Field(default_factory=ReportSection)
    business_overview: ReportSection = Field(default_factory=ReportSection)
    financial_analysis: ReportSection = Field(default_factory=ReportSection)
    risk_analysis: ReportSection = Field(default_factory=ReportSection)
    growth_opportunities: ReportSection = Field(default_factory=ReportSection)
    valuation: ReportSection = Field(default_factory=ReportSection)
    investment_thesis: ReportSection = Field(default_factory=ReportSection)

    citations: list[dict] = Field(default_factory=list, description="All citations used")
    overall_confidence: float = Field(0.0, description="Average section confidence")
    model: str = ""
    generated_at: str = ""

    financial_health_score: Optional[float] = Field(None, description="0–100 health score from engine")
    sections_generated: int = 0
    sections_failed: int = 0


class ResearchRequest(BaseModel):
    """Request body for POST /research/{ticker}."""

    sections: list[str] = Field(
        default=["executive_summary", "business_overview", "financial_analysis",
                 "risk_analysis", "growth_opportunities", "valuation", "investment_thesis"],
        description="Which sections to generate",
    )
    top_k: int = Field(15, ge=1, le=50, description="Chunks to retrieve per section query")
    include_news: bool = Field(True, description="Include recent news in analysis")
