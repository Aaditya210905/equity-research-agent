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


from config.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model configuration (from settings)
# ---------------------------------------------------------------------------

DEFAULT_MODEL = settings.EMBEDDING_MODEL
EMBEDDING_VERSION = 1
BATCH_MAX = 2048

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0   # seconds
RETRY_MAX_DELAY = 30.0   # seconds


# ---------------------------------------------------------------------------
# Hugging Face client (lazy singleton)
# ---------------------------------------------------------------------------
_client = None


def _get_client():
    """Lazily initialize the Hugging Face Inference client."""
    global _client
    if _client is not None:
        return _client

    try:
        from huggingface_hub import InferenceClient
    except ImportError:
        raise RuntimeError("huggingface_hub package not installed. Run: pip install huggingface_hub")

    hf_token = settings.HF_TOKEN

    if not hf_token:
        raise RuntimeError(
            "HF_TOKEN not set. Add it to backend/config/.env\n"
            "Get a key at https://huggingface.co/settings/tokens"
        )

    _client = InferenceClient(
        provider="hf-inference",
        api_key=hf_token
    )
    logger.info("Hugging Face client initialized")
    return _client


# ---------------------------------------------------------------------------
# Core embedding function (single batch)
# ---------------------------------------------------------------------------

def _embed_batch_raw(
    texts: list[str],
    model: str = None,
) -> list[list[float]]:
    """Call Hugging Face embedding API for a batch of texts.

    Parameters
    ----------
    texts : list[str]
        Texts to embed (max 2048 per call).
    model : str, optional
        Model identifier. Defaults to settings.EMBEDDING_MODEL.

    Returns
    -------
    list[list[float]]
        One embedding vector per input text.

    Raises
    ------
    RuntimeError
        If all retries are exhausted.
    """
    model = model or settings.EMBEDDING_MODEL
    client = _get_client()

    if len(texts) > BATCH_MAX:
        raise ValueError(
            f"Batch too large: {len(texts)} > {BATCH_MAX}"
        )

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.feature_extraction(
                texts,
                model=model,
            )
            
            # HuggingFace feature_extraction returns a numpy array or list.
            # Convert to list of lists of floats.
            import numpy as np
            if isinstance(response, np.ndarray):
                embeddings = response.tolist()
            else:
                embeddings = response

            return embeddings

        except Exception as exc:
            last_error = exc
            error_name = type(exc).__name__

            # Don't retry on auth errors
            if "authentication" in str(exc).lower() or "token" in str(exc).lower() or "402" in str(exc):
                raise RuntimeError(f"Hugging Face authentication or billing failed: {exc}") from exc

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
    model: str = None,
    version: int = EMBEDDING_VERSION,
    use_cache: bool = True,
    batch_size: int = None,
) -> dict:
    """Embed a list of chunks with caching and batch processing.

    This is the main entry point for embedding generation.

    Parameters
    ----------
    chunks : list[dict]
        Chunk dicts from chunker.chunk_document()["chunks"].
        Each must have "chunk_id" and "text".
    model : str, optional
        Embedding model to use. Defaults to settings.EMBEDDING_MODEL.
    version : int
        Embedding version tag.
    use_cache : bool
        Whether to check the cache before calling the API.
    batch_size : int, optional
        Number of chunks per API batch call. Defaults to settings.EMBEDDING_BATCH_SIZE.

    Returns
    -------
    dict
        EmbeddingResult-compatible dict::

            {
                "total_chunks": 150,
                "embedded": 130,
                "cached": 20,
                "failed": 0,
                "embedding_model": "...",
                "embedding_dim": 1536,
                "embedding_version": 1,
                "chunks": [ ... EmbeddedChunk dicts ... ]
            }
    """
    from embedding.cache import hash_text, get_cached, put_cached

    model = model or settings.EMBEDDING_MODEL
    batch_size = batch_size or int(settings.EMBEDDING_BATCH_SIZE or 100)

    dim = 0
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
            chunk_dim = len(cached_vector)
            dim = dim or chunk_dim
            results.append(_build_embedded_chunk(
                chunk, cached_vector, model, chunk_dim, version, content_hash,
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
                    chunk_dim = len(vector) if vector else 0
                    dim = dim or chunk_dim

                    # Store in cache
                    if use_cache and vector:
                        put_cached(
                            content_hash,
                            chunk.get("chunk_id", ""),
                            vector,
                            model,
                            chunk_dim,
                            version,
                        )

                    results[result_idx] = _build_embedded_chunk(
                        chunk, vector, model, chunk_dim, version, content_hash,
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

    # Filter out None placeholders (safety)
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
    vector_dim = len(vector) if vector else (dim or 0)
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
        "embedding_dim": vector_dim,
        "content_hash": content_hash,
        "embedded_at": datetime.now(timezone.utc).isoformat(),
    }

