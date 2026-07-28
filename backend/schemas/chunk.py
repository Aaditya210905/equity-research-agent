"""
Pydantic schemas for document chunks.

Defines the contract for chunks emitted by the intelligent chunker
and consumed by the embedding + retrieval pipeline.
"""

from typing import Optional

from pydantic import BaseModel, Field


class ChunkMeta(BaseModel):
    """A single semantically meaningful chunk of a financial document."""

    chunk_id: str = Field(..., description="Unique chunk identifier")
    document_id: Optional[str] = Field(None, description="Parent document registry ID")
    company: Optional[str] = Field(None, description="Company ticker or name")
    year: Optional[int] = Field(None, description="Fiscal year")
    doc_type: Optional[str] = Field(None, description="Document type (Annual Report, etc.)")

    section: Optional[str] = Field(None, description="Major section heading")
    subsection: Optional[str] = Field(None, description="Sub-section heading")
    page_start: Optional[int] = Field(None, description="First page of chunk")
    page_end: Optional[int] = Field(None, description="Last page of chunk")

    text: str = Field(..., description="Chunk text content")
    token_count: int = Field(0, description="Estimated token count")
    has_heading: bool = Field(False, description="Whether chunk starts with a heading")
    contains_table: bool = Field(False, description="Whether chunk contains tabular data")
    quality_score: float = Field(0.0, description="Chunk quality score (0.0-1.0)")


class ChunkingResult(BaseModel):
    """Response for document chunking operation."""

    document_id: Optional[str] = Field(None, description="Source document ID")
    company: Optional[str] = Field(None, description="Company ticker")
    total_chunks: int = Field(0, description="Number of chunks produced")
    total_tokens: int = Field(0, description="Total tokens across all chunks")
    avg_chunk_tokens: float = Field(0.0, description="Average tokens per chunk")
    sections_detected: list[str] = Field(default_factory=list, description="Section headings found")
    chunks: list[ChunkMeta] = Field(default_factory=list, description="List of chunks")
