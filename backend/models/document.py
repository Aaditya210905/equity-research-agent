"""
Document Registry — Peewee ORM model for tracking all collected documents.

Every downloaded or generated document gets a row in this table. The
registry tracks physical files, their source, integrity (SHA-256), and
processing status through the RAG pipeline.

Processing pipeline stages:
    pending → downloaded → verified → text_extracted → chunked → embedded → indexed
                                                                        ↘ failed

Usage:
    from models.document import Document, initialize_db

    initialize_db()                        # call once on startup
    Document.create(ticker="AAPL", ...)    # insert
    Document.select().where(...)           # query
"""

import datetime
from pathlib import Path

from peewee import (
    Model,
    SqliteDatabase,
    CharField,
    IntegerField,
    FloatField,
    DateTimeField,
    TextField,
)

# ---------------------------------------------------------------------------
# Deferred database — initialized at application startup via initialize_db()
# ---------------------------------------------------------------------------
db = SqliteDatabase(None)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DOC_TYPES = {
    "annual_report": "Annual Report",
    "quarterly_report": "Quarterly Report",
    "income_statement": "Income Statement",
    "balance_sheet": "Balance Sheet",
    "cash_flow": "Cash Flow Statement",
    "presentation": "Investor Presentation",
    "transcript": "Earnings Call Transcript",
    "announcement": "Corporate Announcement",
}

PROCESSING_STATUSES = [
    "pending",          # Registered but not yet downloaded
    "downloaded",       # File saved locally
    "verified",         # File validated (exists, non-empty, opens)
    "text_extracted",   # Text content extracted from PDF/HTML
    "chunked",          # Split into chunks for RAG
    "embedded",         # Vector embeddings generated
    "indexed",          # Added to vector database
    "failed",           # Processing failed at some stage
]


# ---------------------------------------------------------------------------
# Document model
# ---------------------------------------------------------------------------
class Document(Model):
    """A single document in the registry."""

    # --- Identity ---
    document_id = CharField(unique=True, primary_key=True)
    ticker = CharField(index=True)
    company_name = CharField(null=True)

    # --- Classification ---
    doc_type = CharField(index=True)          # key from DOC_TYPES
    title = CharField()
    year = IntegerField(null=True, index=True)
    quarter = CharField(null=True)            # "Q1", "Q2", "Q3", "Q4"

    # --- Physical file ---
    file_path = CharField(null=True)          # relative to documents/ root
    file_size = IntegerField(null=True)       # bytes
    checksum_sha256 = CharField(null=True)

    # --- Source ---
    source = CharField()                       # "sec_edgar", "yahoo_finance", etc.
    source_url = CharField(null=True)

    # --- Pipeline tracking ---
    processing_status = CharField(default="pending")
    version = IntegerField(default=1)

    # --- Timestamps ---
    download_date = DateTimeField(default=datetime.datetime.utcnow)
    updated_at = DateTimeField(default=datetime.datetime.utcnow)

    # --- Error tracking ---
    error_message = TextField(null=True)

    class Meta:
        database = db
        table_name = "documents"


# ---------------------------------------------------------------------------
# Database lifecycle
# ---------------------------------------------------------------------------
_DB_INITIALIZED = False


def initialize_db(db_path: str = None):
    """Initialize the SQLite database and create tables.

    Parameters
    ----------
    db_path : str, optional
        Full path to the SQLite file. Defaults to ``backend/data/documents.db``.
    """
    global _DB_INITIALIZED
    if _DB_INITIALIZED:
        return

    if db_path is None:
        db_path = str(Path(__file__).resolve().parent.parent / "data" / "documents.db")

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    db.init(db_path)
    db.connect(reuse_if_open=True)
    db.create_tables([Document], safe=True)
    _DB_INITIALIZED = True


def close_db():
    """Close the database connection."""
    global _DB_INITIALIZED
    if not db.is_closed():
        db.close()
    _DB_INITIALIZED = False
