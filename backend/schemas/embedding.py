"""
Pydantic schemas for embedded chunks.

Defines the contract for vectors produced by the embedding pipeline
and consumed by the vector store / retriever.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EmbeddedChunk(BaseModel):
    """A chunk with its embedding vector and metadata."""

    chunk_id: str = Field(..., description="Unique chunk identifier")
    document_id: Optional[str] = Field(None, description="Parent document ID")
    company: Optional[str] = Field(None, description="Company ticker or name")
    year: Optional[int] = Field(None, description="Fiscal year")
    doc_type: Optional[str] = Field(None, description="Document type")

    section: Optional[str] = Field(None, description="Section heading")
    subsection: Optional[str] = Field(None, description="Sub-section heading")
    page_start: Optional[int] = Field(None, description="First page")
    page_end: Optional[int] = Field(None, description="Last page")

    text: str = Field(..., description="Original chunk text")
    token_count: int = Field(0, description="Estimated token count")
    has_heading: bool = Field(False)
    contains_table: bool = Field(False)
    quality_score: float = Field(0.0)

    # Embedding fields
    embedding: list[float] = Field(default_factory=list, description="Embedding vector")
    embedding_model: str = Field("", description="Model used to generate embedding")
    embedding_version: int = Field(1, description="Embedding pipeline version")
    embedding_dim: int = Field(0, description="Vector dimensionality")
    content_hash: str = Field("", description="SHA-256 hash of chunk text")
    embedded_at: Optional[str] = Field(None, description="ISO timestamp of embedding")


class EmbeddingResult(BaseModel):
    """Summary of an embedding batch run."""

    document_id: Optional[str] = Field(None)
    company: Optional[str] = Field(None)
    total_chunks: int = Field(0)
    embedded: int = Field(0)
    cached: int = Field(0)
    failed: int = Field(0)
    embedding_model: str = Field("")
    embedding_dim: int = Field(0)
    embedding_version: int = Field(1)
    chunks: list[EmbeddedChunk] = Field(default_factory=list)
