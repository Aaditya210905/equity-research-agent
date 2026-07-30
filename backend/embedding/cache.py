"""
Embedding Cache — Phase 2.4

Avoids regenerating embeddings for chunks whose text hasn't changed.

Strategy:
    Chunk text  →  SHA-256 hash  →  Lookup in cache
        ↓                              ↓
    Hash exists?  ──yes──>  Return cached vector
        ↓ no
    Call embedding API  →  Store in cache  →  Return vector

Cache is stored as a SQLite database for durability and simplicity.
Survives process restarts, crashes, and incremental re-processing.
"""

import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default cache location
# ---------------------------------------------------------------------------
_DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent / "data"
_DEFAULT_CACHE_DB = _DEFAULT_CACHE_DIR / "embedding_cache.db"

# Module-level connection
_conn: Optional[sqlite3.Connection] = None


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def hash_text(text: str) -> str:
    """Compute a stable SHA-256 hash for a chunk's text content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Cache lifecycle
# ---------------------------------------------------------------------------

def init_cache(db_path: str | Path = None) -> None:
    """Initialize the embedding cache database.

    Creates the cache table if it doesn't exist. Safe to call multiple times.
    """
    global _conn
    db_path = Path(db_path) if db_path else _DEFAULT_CACHE_DB
    db_path.parent.mkdir(parents=True, exist_ok=True)

    _conn = sqlite3.connect(str(db_path), check_same_thread=False)
    _conn.execute("PRAGMA journal_mode=WAL")

    _conn.execute("""
        CREATE TABLE IF NOT EXISTS embedding_cache (
            content_hash      TEXT NOT NULL,
            chunk_id          TEXT NOT NULL,
            embedding         TEXT NOT NULL,
            embedding_model   TEXT NOT NULL,
            embedding_dim     INTEGER NOT NULL,
            embedding_version INTEGER DEFAULT 1,
            created_at        TEXT NOT NULL,
            PRIMARY KEY (content_hash, embedding_model, embedding_version)
        )
    """)
    _conn.commit()
    logger.info("Embedding cache initialized at %s", db_path)


def close_cache() -> None:
    """Close the cache database connection."""
    global _conn
    if _conn:
        _conn.close()
        _conn = None


def _ensure_conn():
    """Auto-initialize if not already done."""
    if _conn is None:
        init_cache()


# ---------------------------------------------------------------------------
# Cache operations
# ---------------------------------------------------------------------------

def get_cached(content_hash: str, model: str, version: int = 1) -> Optional[list[float]]:
    """Look up a cached embedding by content hash, model, and version.

    Returns
    -------
    list[float] or None
        The cached embedding vector, or None if not found.
    """
    _ensure_conn()
    row = _conn.execute(
        """SELECT embedding FROM embedding_cache
           WHERE content_hash = ?
             AND embedding_model = ?
             AND embedding_version = ?""",
        (content_hash, model, version),
    ).fetchone()

    if row:
        return json.loads(row[0])
    return None


def put_cached(
    content_hash: str,
    chunk_id: str,
    embedding: list[float],
    model: str,
    dim: int,
    version: int = 1,
) -> None:
    """Store an embedding in the cache.

    Uses INSERT OR REPLACE so re-processing the same chunk is idempotent.
    """
    _ensure_conn()
    _conn.execute(
        """INSERT OR REPLACE INTO embedding_cache
           (content_hash, chunk_id, embedding, embedding_model,
            embedding_dim, embedding_version, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            content_hash,
            chunk_id,
            json.dumps(embedding),
            model,
            dim,
            version,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    _conn.commit()


def cache_stats() -> dict:
    """Return cache statistics."""
    _ensure_conn()
    total = _conn.execute("SELECT COUNT(*) FROM embedding_cache").fetchone()[0]
    models = _conn.execute(
        "SELECT DISTINCT embedding_model FROM embedding_cache"
    ).fetchall()
    return {
        "total_cached": total,
        "models": [m[0] for m in models],
    }


def clear_cache() -> None:
    """Clear all cached embeddings."""
    _ensure_conn()
    _conn.execute("DELETE FROM embedding_cache")
    _conn.commit()
    logger.info("Embedding cache cleared")
