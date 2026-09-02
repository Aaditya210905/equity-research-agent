"""
SQLite Checkpointer Singleton

Provides a shared SqliteSaver instance for all LangGraph graphs.
Checkpoints are stored in backend/data/checkpoints.db — this lets
graphs resume from where they left off after a crash (e.g., if the
LLM fails mid-report, re-running with the same thread_id picks up
from the last completed node).
"""

import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_checkpointer = None
_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "checkpoints.db"


def get_checkpointer():
    """Return the shared SqliteSaver checkpointer (lazy singleton)."""
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    try:
        from langgraph.checkpoint.sqlite import SqliteSaver

        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        _checkpointer = SqliteSaver(conn)
        logger.info("LangGraph checkpointer initialized at %s", _DB_PATH)
    except Exception as exc:
        logger.warning("Could not initialize SQLite checkpointer: %s — running without checkpointing", exc)
        from langgraph.checkpoint.memory import MemorySaver
        _checkpointer = MemorySaver()

    return _checkpointer
