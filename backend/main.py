"""
Equity Research Agent — FastAPI entry point.

Run with:
    uvicorn main:app --reload

Docs at:
    http://127.0.0.1:8000/docs   (Swagger UI)
    http://127.0.0.1:8000/redoc  (ReDoc)
"""

import logging

from fastapi import FastAPI

from api.routes import router
from config.settings import settings  # noqa: F401 — ensures .env is loaded early
from models.document import initialize_db

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Equity Research Agent",
    description=(
        "A modular backend for equity research — data sourcing, "
        "financial analysis, document collection, and (in later phases) "
        "AI-powered memo generation with a reflection / fact-checking loop."
    ),
    version="0.2.0",
)

# Mount routes
app.include_router(router)


@app.get("/", tags=["Health"])
async def root():
    """Health-check / welcome endpoint."""
    return {
        "service": "Equity Research Agent",
        "version": "0.2.0",
        "status": "running",
        "docs": "/docs",
    }


# ---------------------------------------------------------------------------
# Startup / Shutdown
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def _startup():
    # Initialize document registry database
    initialize_db()
    logger.info("Document registry initialized")
    logger.info("Equity Research Agent v0.2.0 starting up")
    logger.info("Docs available at http://%s:%s/docs", settings.HOST, settings.PORT)


@app.on_event("shutdown")
async def _shutdown():
    from models.document import close_db
    close_db()
    logger.info("Database connections closed")
