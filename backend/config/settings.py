"""
Central configuration for the Equity Research Agent.

Usage:
    from config.settings import settings

    key = settings.FINNHUB_API_KEY

All modules import `settings` from this file.
Never call os.getenv() directly in application code.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Load .env from the config/ directory (co-located with this file)
# ---------------------------------------------------------------------------
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_env_path)


# ---------------------------------------------------------------------------
# Settings schema
# ---------------------------------------------------------------------------
class Settings(BaseModel):
    """Validated, typed application configuration."""

    # --- API Keys (populated from .env) ---
    FINNHUB_API_KEY: str = Field(
        default="",
        description="Finnhub API key for supplementary market data",
    )
    ALPHA_VANTAGE_API_KEY: str = Field(
        default="",
        description="Alpha Vantage API key for fundamental data",
    )
    OPENAI_API_KEY: str = Field(
        default="",
        description="OpenAI API key for LLM calls (added in later phases)",
    )
    NEWS_API_KEY: str = Field(
        default="",
        description="News API key for financial news retrieval",
    )

    # --- Server ---
    HOST: str = Field(default="127.0.0.1", description="FastAPI server host")
    PORT: int = Field(default=8000, description="FastAPI server port")
    DEBUG: bool = Field(default=True, description="Enable debug / reload mode")

    # --- Yahoo Finance ---
    YAHOO_FINANCE_USER_AGENT: str = Field(
        default="EquityResearchAgent/1.0",
        description="User-Agent header for Yahoo Finance requests",
    )

    # --- SEC EDGAR ---
    SEC_USER_AGENT: str = Field(
        default="EquityResearchAgent/1.0 contact@example.com",
        description="User-Agent header for SEC EDGAR (required by SEC)",
    )

    # --- Document Storage (Phase 1.3) ---
    DOCUMENTS_DIR: str = Field(
        default="documents",
        description="Root directory for downloaded documents",
    )
    DATA_DIR: str = Field(
        default="data",
        description="Directory for SQLite database and other data files",
    )

    # --- Embedding (Phase 2.4) ---
    EMBEDDING_MODEL: str = Field(
        default="text-embedding-3-small",
        description="OpenAI embedding model to use",
    )
    EMBEDDING_BATCH_SIZE: int = Field(
        default=100,
        description="Number of chunks per embedding API batch call",
    )

    # --- Future configuration slots (uncomment as phases are added) ---
    # REDIS_URL: str = Field(default="redis://localhost:6379/0")
    # VECTOR_DB_URL: str = Field(default="")
    # ANTHROPIC_API_KEY: str = Field(default="")


# ---------------------------------------------------------------------------
# Build & export singleton
# ---------------------------------------------------------------------------
def _load_settings() -> Settings:
    """Construct Settings from environment variables."""
    return Settings(
        FINNHUB_API_KEY=os.getenv("FINNHUB_API_KEY", ""),
        ALPHA_VANTAGE_API_KEY=os.getenv("ALPHA_VANTAGE_API_KEY", ""),
        OPENAI_API_KEY=os.getenv("OPENAI_API_KEY", ""),
        NEWS_API_KEY=os.getenv("NEWS_API_KEY", ""),
    )


settings = _load_settings()
