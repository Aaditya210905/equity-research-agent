from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


FilingKind = Literal["annual-reports", "quarterly-reports", "announcements"]


class CompanyHit(BaseModel):
    scripCode: str
    name: str
    symbol: str
    isin: str


class StoredFile(BaseModel):
    kind: FilingKind
    relativePath: str
    fileName: str
    headline: str
    category: str
    subcategory: str
    newsId: str
    attachmentName: str
    disseminatedAt: str
    bytes: int
    saved: bool
    skipped: str | None = None


class CompanyFolder(BaseModel):
    scripCode: str
    symbol: str
    name: str
    folder: str
    fetchedAt: str
    files: list[StoredFile]
    counts: dict[str, int]
    totalBytes: int


class FetchOptions(BaseModel):
    scripCode: str
    name: str | None = None
    symbol: str | None = None
    isin: str | None = None
    annual: bool = True
    quarterly: bool = True
    announcements: bool = True
    annualLimit: int = Field(default=3, ge=1, le=8)
    quarterlyLimit: int = Field(default=8, ge=1, le=16)
    announcementLimit: int = Field(default=20, ge=1, le=40)
    announcementDays: int = Field(default=90, ge=7, le=365)

    @field_validator("scripCode")
    @classmethod
    def valid_scrip_code(cls, value: str) -> str:
        value = value.strip()
        if not value.isdigit() or not 5 <= len(value) <= 7:
            raise ValueError("A valid BSE scrip code is required")
        return value

    @model_validator(mode="after")
    def at_least_one_kind(self) -> FetchOptions:
        if not self.annual and not self.quarterly and not self.announcements:
            raise ValueError("Select at least one report type")
        return self


class FetchResult(BaseModel):
    company: CompanyFolder
    log: list[str]
