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
# Logging — console + file (logs/ folder, rotated daily)
# ---------------------------------------------------------------------------
import os
from logging.handlers import TimedRotatingFileHandler

_LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(_LOG_DIR, exist_ok=True)

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Console handler
_console = logging.StreamHandler()
_console.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))

# File handler — one file per day, keeps 30 days
_file = TimedRotatingFileHandler(
    filename=os.path.join(_LOG_DIR, "app.log"),
    when="midnight",
    interval=1,
    backupCount=30,
    encoding="utf-8",
)
_file.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
_file.suffix = "%Y-%m-%d"

logging.basicConfig(
    level=logging.INFO,
    handlers=[_console, _file],
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
