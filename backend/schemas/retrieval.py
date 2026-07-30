"""
Pydantic schemas for retrieval results.
"""

from typing import Optional
from pydantic import BaseModel, Field


class RetrievalHit(BaseModel):
    """A single retrieval result with score and citation metadata."""

    chunk_id: str = Field(..., description="Chunk identifier")
    score: float = Field(..., description="Similarity score (0–1 for cosine)")
    text: str = Field("", description="Chunk text content")

    # Citation metadata
    document_id: Optional[str] = None
    company: Optional[str] = None
    year: Optional[int] = None
    doc_type: Optional[str] = None
    section: Optional[str] = None
    subsection: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None

    # Quality
    token_count: int = 0
    has_heading: bool = False
    contains_table: bool = False
    quality_score: float = 0.0

    # Computed
    relevance: str = Field("", description="Relevance tier: excellent/good/fair/low")

    def citation(self) -> str:
        """Build a human-readable citation string."""
        parts = []
        if self.company:
            parts.append(self.company)
        if self.doc_type:
            parts.append(self.doc_type)
        if self.year:
            parts.append(str(self.year))
        if self.section:
            parts.append(self.section)
        if self.page_start:
            if self.page_end and self.page_end != self.page_start:
                parts.append(f"Pages {self.page_start}–{self.page_end}")
            else:
                parts.append(f"Page {self.page_start}")
        return ", ".join(parts) if parts else "Unknown source"


class RetrievalResponse(BaseModel):
    """Response from a retrieval query."""

    query: str = Field("", description="Original query text")
    total_hits: int = Field(0, description="Total results returned")
    hits: list[RetrievalHit] = Field(default_factory=list)
    filters_applied: dict = Field(default_factory=dict, description="Metadata filters used")
    min_score_used: float = Field(0.0)
