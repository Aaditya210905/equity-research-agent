"""
Embedding Generator — Phase 2.4

Converts text chunks into semantic vectors using OpenAI's embedding API.

Architecture:
    Chunks
        |
        v
    Hash Check (cache.py)
        |
        ├── Cached → return vector
        |
        └── New → batch to OpenAI API
                      |
                      v
                Store in cache
                      |
                      v
                Return vector + metadata

Supports:
    - Batch processing (up to 2048 texts per API call)
    - Content-hash caching (skip unchanged chunks)
    - Embedding versioning
    - Retry with exponential backoff
    - Graceful degradation (no API key → error, not crash)
"""

import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------

EMBEDDING_MODELS = {
    "text-embedding-3-small": {"dim": 1536, "max_tokens": 8191, "batch_max": 2048},
    "text-embedding-3-large": {"dim": 3072, "max_tokens": 8191, "batch_max": 2048},
    "text-embedding-ada-002":  {"dim": 1536, "max_tokens": 8191, "batch_max": 2048},
}

DEFAULT_MODEL = "text-embedding-3-small"
EMBEDDING_VERSION = 1

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0   # seconds
RETRY_MAX_DELAY = 30.0   # seconds


# ---------------------------------------------------------------------------
# OpenAI client (lazy singleton)
# ---------------------------------------------------------------------------
_client = None


def _get_client():
    """Lazily initialize the OpenAI client."""
    global _client
    if _client is not None:
        return _client

    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai package not installed. Run: pip install openai")

    from config.settings import settings
    api_key = settings.OPENAI_API_KEY

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY not set. Add it to backend/config/.env\n"
            "Get a key at https://platform.openai.com/api-keys"
        )

    _client = OpenAI(api_key=api_key)
    logger.info("OpenAI client initialized")
    return _client


# ---------------------------------------------------------------------------
# Core embedding function (single batch)
# ---------------------------------------------------------------------------

def _embed_batch_raw(
    texts: list[str],
    model: str = DEFAULT_MODEL,
) -> list[list[float]]:
    """Call OpenAI embedding API for a batch of texts.

    Parameters
    ----------
    texts : list[str]
        Texts to embed (max 2048 per call).
    model : str
        Model identifier.

    Returns
    -------
    list[list[float]]
        One embedding vector per input text.

    Raises
    ------
    RuntimeError
        If all retries are exhausted.
    """
    client = _get_client()
    model_info = EMBEDDING_MODELS.get(model, EMBEDDING_MODELS[DEFAULT_MODEL])

    if len(texts) > model_info["batch_max"]:
        raise ValueError(
            f"Batch too large: {len(texts)} > {model_info['batch_max']}"
        )

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.embeddings.create(
                input=texts,
                model=model,
            )
            # Sort by index to preserve input order
            embeddings = [None] * len(texts)
            for item in response.data:
                embeddings[item.index] = item.embedding

            return embeddings

        except Exception as exc:
            last_error = exc
            error_name = type(exc).__name__

            # Don't retry on auth errors
            if "authentication" in str(exc).lower() or "api key" in str(exc).lower():
                raise RuntimeError(f"OpenAI authentication failed: {exc}") from exc

            delay = min(RETRY_BASE_DELAY * (2 ** (attempt - 1)), RETRY_MAX_DELAY)
            logger.warning(
                "Embedding attempt %d/%d failed (%s: %s). Retrying in %.1fs...",
                attempt, MAX_RETRIES, error_name, exc, delay,
            )
            time.sleep(delay)

    raise RuntimeError(
        f"Embedding failed after {MAX_RETRIES} retries: {last_error}"
    ) from last_error


# ---------------------------------------------------------------------------
# High-level embedding with caching
# ---------------------------------------------------------------------------

def embed_chunks(
    chunks: list[dict],
    model: str = DEFAULT_MODEL,
    version: int = EMBEDDING_VERSION,
    use_cache: bool = True,
    batch_size: int = 100,
) -> dict:
    """Embed a list of chunks with caching and batch processing.

    This is the main entry point for embedding generation.

    Parameters
    ----------
    chunks : list[dict]
        Chunk dicts from chunker.chunk_document()["chunks"].
        Each must have "chunk_id" and "text".
    model : str
        Embedding model to use.
    version : int
        Embedding version tag.
    use_cache : bool
        Whether to check the cache before calling the API.
    batch_size : int
        Number of chunks per API batch call (max 2048).

    Returns
    -------
    dict
        EmbeddingResult-compatible dict::

            {
                "total_chunks": 150,
                "embedded": 130,
                "cached": 20,
                "failed": 0,
                "embedding_model": "text-embedding-3-small",
                "embedding_dim": 1536,
                "embedding_version": 1,
                "chunks": [ ... EmbeddedChunk dicts ... ]
            }
    """
    from embedding.cache import hash_text, get_cached, put_cached, init_cache

    if use_cache:
        init_cache()

    model_info = EMBEDDING_MODELS.get(model, EMBEDDING_MODELS[DEFAULT_MODEL])
    dim = model_info["dim"]

    results: list[dict] = []
    cached_count = 0
    embedded_count = 0
    failed_count = 0

    # Separate cached vs. uncached
    to_embed: list[tuple[int, dict, str]] = []  # (result_idx, chunk, hash)

    for chunk in chunks:
        text = chunk.get("text", "")
        chunk_id = chunk.get("chunk_id", "")
        content_hash = hash_text(text)

        # Check cache
        cached_vector = None
        if use_cache:
            cached_vector = get_cached(content_hash, model, version)

        if cached_vector is not None:
            # Cache hit
            results.append(_build_embedded_chunk(
                chunk, cached_vector, model, dim, version, content_hash,
            ))
            cached_count += 1
            logger.debug("Cache hit: %s", chunk_id)
        else:
            # Need to embed
            result_idx = len(results)
            results.append(None)  # placeholder
            to_embed.append((result_idx, chunk, content_hash))

    # Batch-embed uncached chunks
    if to_embed:
        logger.info(
            "Embedding %d chunks (batch_size=%d, model=%s, %d cached)...",
            len(to_embed), batch_size, model, cached_count,
        )

        for batch_start in range(0, len(to_embed), batch_size):
            batch = to_embed[batch_start:batch_start + batch_size]
            batch_texts = [item[1]["text"] for item in batch]

            try:
                vectors = _embed_batch_raw(batch_texts, model)

                for (result_idx, chunk, content_hash), vector in zip(batch, vectors):
                    # Store in cache
                    if use_cache:
                        put_cached(
                            content_hash,
                            chunk.get("chunk_id", ""),
                            vector,
                            model,
                            dim,
                            version,
                        )

                    results[result_idx] = _build_embedded_chunk(
                        chunk, vector, model, dim, version, content_hash,
                    )
                    embedded_count += 1

            except Exception as exc:
                logger.error("Batch embedding failed: %s", exc)
                for result_idx, chunk, content_hash in batch:
                    results[result_idx] = _build_embedded_chunk(
                        chunk, [], model, dim, version, content_hash,
                        error=str(exc),
                    )
                    failed_count += 1

    # Filter out None placeholders (shouldn't happen but safety)
    results = [r for r in results if r is not None]

    logger.info(
        "Embedding complete: %d total, %d embedded, %d cached, %d failed",
        len(results), embedded_count, cached_count, failed_count,
    )

    return {
        "document_id": chunks[0].get("document_id") if chunks else None,
        "company": chunks[0].get("company") if chunks else None,
        "total_chunks": len(results),
        "embedded": embedded_count,
        "cached": cached_count,
        "failed": failed_count,
        "embedding_model": model,
        "embedding_dim": dim,
        "embedding_version": version,
        "chunks": results,
    }


# ---------------------------------------------------------------------------
# Build embedded chunk dict
# ---------------------------------------------------------------------------

def _build_embedded_chunk(
    chunk: dict,
    vector: list[float],
    model: str,
    dim: int,
    version: int,
    content_hash: str,
    error: str = None,
) -> dict:
    """Assemble an EmbeddedChunk-compatible dict."""
    return {
        # Original chunk metadata
        "chunk_id": chunk.get("chunk_id", ""),
        "document_id": chunk.get("document_id"),
        "company": chunk.get("company"),
        "year": chunk.get("year"),
        "doc_type": chunk.get("doc_type"),
        "section": chunk.get("section"),
        "subsection": chunk.get("subsection"),
        "page_start": chunk.get("page_start"),
        "page_end": chunk.get("page_end"),
        "text": chunk.get("text", ""),
        "token_count": chunk.get("token_count", 0),
        "has_heading": chunk.get("has_heading", False),
        "contains_table": chunk.get("contains_table", False),
        "quality_score": chunk.get("quality_score", 0.0),
        # Embedding fields
        "embedding": vector,
        "embedding_model": model,
        "embedding_version": version,
        "embedding_dim": dim if vector else 0,
        "content_hash": content_hash,
        "embedded_at": datetime.now(timezone.utc).isoformat(),
    }
