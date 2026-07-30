"""
Pydantic schemas for RAG answer generation.
"""

from typing import Optional
from pydantic import BaseModel, Field


class Citation(BaseModel):
    """A single citation tracing an answer back to source evidence."""

    ref: int = Field(..., description="Citation number [1], [2], etc.")
    chunk_id: str = Field("", description="Source chunk identifier")
    source: str = Field("", description="Human-readable citation string")
    section: Optional[str] = Field(None, description="Document section")
    page_start: Optional[int] = Field(None)
    page_end: Optional[int] = Field(None)
    score: float = Field(0.0, description="Retrieval similarity score")
    text_preview: str = Field("", description="First 150 chars of chunk")


class RAGAnswer(BaseModel):
    """Complete RAG response with answer, citations, and confidence."""

    answer: str = Field("", description="Generated answer text")
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = Field(0.0, description="Overall confidence (0.0–1.0)")
    confidence_tier: str = Field("", description="high / medium / low / insufficient")

    question: str = Field("", description="Original question")
    question_type: str = Field("", description="factual / comparative / analytical / summarization")
    query_used: str = Field("", description="Expanded query sent to retriever")

    chunks_retrieved: int = Field(0)
    chunks_used: int = Field(0)
    model: str = Field("", description="LLM model used")
    evidence_sufficient: bool = Field(True)


class AskRequest(BaseModel):
    """Request body for POST /ask."""

    question: str = Field(..., description="Natural language question", min_length=3)
    company: str = Field(None, description="Company ticker to scope retrieval")
    year: int = Field(None, description="Fiscal year filter")
    doc_type: str = Field(None, description="Document type filter")
    top_k: int = Field(10, ge=1, le=50, description="Max chunks to retrieve")
    rewrite_query: bool = Field(False, description="Use LLM to expand the query")
