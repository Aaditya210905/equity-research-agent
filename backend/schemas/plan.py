"""
Pydantic schemas for the Research Planner — Phase 5.
"""

from typing import Optional
from pydantic import BaseModel, Field


class ResearchPlan(BaseModel):
    """Structured execution plan produced by the planner."""

    request_id: str = ""
    objective: str = ""
    request_type: str = Field(
        "",
        description="factual_query / company_analysis / comparison / risk_analysis / investment_memo",
    )
    companies: list[str] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    retrieval_queries: list[str] = Field(
        default_factory=list,
        description="Specific queries to run against the retriever",
    )
    output_format: str = Field("research_report", description="research_report / brief_answer / comparison_table")
    year: Optional[int] = None


class ToolResult(BaseModel):
    """Result from a single tool execution."""

    tool: str = ""
    status: str = Field("", description="success / error / skipped")
    data: dict = Field(default_factory=dict)
    error: str = ""
    duration_ms: int = 0


class Claim(BaseModel):
    """A single factual claim extracted from the report."""

    text: str = ""
    section: str = ""
    has_number: bool = False
    has_citation: bool = False
    verification: str = Field("pending", description="verified / unverified / revised / removed")
    supporting_evidence: str = ""


class VerificationResult(BaseModel):
    """Outcome of the claim verification process."""

    total_claims: int = 0
    verified: int = 0
    unverified: int = 0
    revised: int = 0
    removed: int = 0
    verification_rate: float = 0.0
    claims: list[Claim] = Field(default_factory=list)


class ExecutionTrace(BaseModel):
    """Full execution log for traceability."""

    request_id: str = ""
    objective: str = ""
    plan: dict = Field(default_factory=dict)
    tools_called: list[str] = Field(default_factory=list)
    tool_results: list[dict] = Field(default_factory=list)
    verification: dict = Field(default_factory=dict)
    sections_generated: int = 0
    duration_ms: int = 0
    timestamp: str = ""
