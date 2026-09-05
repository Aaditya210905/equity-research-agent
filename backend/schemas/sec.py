from pydantic import BaseModel, Field, field_validator

class CompanyHit(BaseModel):
    cik: str
    name: str
    ticker: str

class FetchOptions(BaseModel):
    ticker: str
    annual: bool = True
    quarterly: bool = True
    annualLimit: int = Field(default=3, ge=1, le=8)
    quarterlyLimit: int = Field(default=8, ge=1, le=16)

    @field_validator("ticker")
    @classmethod
    def valid_ticker(cls, value: str) -> str:
        return value.strip().upper()

class FetchResult(BaseModel):
    company: dict
    log: list[str]
