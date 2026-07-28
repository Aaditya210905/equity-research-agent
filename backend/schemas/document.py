"""
Pydantic response schemas for document-related endpoints.

Output contract for the document pipeline — every consumer receives
the same structure regardless of document source.
"""

from typing import Optional

from pydantic import BaseModel, Field


class DocumentMeta(BaseModel):
    """Metadata for a single document in the registry."""

    document_id: str = Field(..., description="Unique document identifier")
    ticker: str = Field(..., description="Stock ticker symbol")
    company_name: Optional[str] = Field(None, description="Company name")
    doc_type: str = Field(..., description="Document type (annual_report, quarterly_report, etc.)")
    title: str = Field(..., description="Human-readable document title")
    year: Optional[int] = Field(None, description="Fiscal year")
    quarter: Optional[str] = Field(None, description="Fiscal quarter (Q1-Q4)")
    file_path: Optional[str] = Field(None, description="Local file path (relative)")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    source: str = Field(..., description="Data source (sec_edgar, yahoo_finance, etc.)")
    source_url: Optional[str] = Field(None, description="Original source URL")
    checksum_sha256: Optional[str] = Field(None, description="SHA-256 checksum")
    processing_status: str = Field("pending", description="Pipeline status")
    download_date: Optional[str] = Field(None, description="Download timestamp (ISO)")


class DocumentCollection(BaseModel):
    """Response for GET /documents/{ticker}.

    JSON contract::

        {
            "company": "INFY",
            "ticker": "INFY",
            "total_documents": 12,
            "documents": [ ... DocumentMeta ... ]
        }
    """

    company: str = Field(..., description="Company name or ticker")
    ticker: str = Field(..., description="Stock ticker symbol")
    total_documents: int = Field(..., description="Total number of documents")
    documents: list[DocumentMeta] = Field(default_factory=list, description="List of documents")


class CollectionResult(BaseModel):
    """Response for POST /documents/{ticker}/collect.

    Reports what was collected in this run.
    """

    ticker: str = Field(..., description="Stock ticker symbol")
    new_documents: int = Field(0, description="Documents newly downloaded")
    existing_documents: int = Field(0, description="Documents already in registry")
    failed: int = Field(0, description="Documents that failed to download")
    documents: list[DocumentMeta] = Field(default_factory=list, description="All documents after collection")
