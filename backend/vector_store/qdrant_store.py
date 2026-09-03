"""
Qdrant Vector Store — Phase 2.5

Manages a single Qdrant collection (`financial_documents`) that stores
all embedded chunks with full metadata payloads.

Design:
    ONE collection for all companies/documents.
    Filtering by company, year, doc_type, section via payload filters.

Modes:
    - Local persistence (default): data/qdrant/
    - In-memory (:memory:) for tests
    - Remote server (url) for production

Payload stored with every vector:
    chunk_id, document_id, company, year, doc_type,
    section, subsection, page_start, page_end,
    text, token_count, has_heading, contains_table,
    quality_score, embedding_model, content_hash
"""

import logging
import uuid as _uuid
from pathlib import Path
from typing import Optional

from qdrant_client import QdrantClient, models

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_COLLECTION = "financial_documents"

def _get_default_vector_size() -> int:
    """Return vector size based on the active embedding provider."""
    try:
        from config.settings import settings
        provider = getattr(settings, "EMBEDDING_PROVIDER", "hf").lower()
        if provider == "google":
            return 3072  # gemini-embedding-2
        return 768  # HF or Cloudflare (embeddinggemma-300m)
    except Exception:
        return 768

DEFAULT_VECTOR_SIZE = _get_default_vector_size()

# Payload keys to index for fast filtering
_INDEXED_FIELDS = {
    "company":   models.PayloadSchemaType.KEYWORD,
    "year":      models.PayloadSchemaType.INTEGER,
    "doc_type":  models.PayloadSchemaType.KEYWORD,
    "section":   models.PayloadSchemaType.KEYWORD,
    "document_id": models.PayloadSchemaType.KEYWORD,
}

# ---------------------------------------------------------------------------
# Module-level client
# ---------------------------------------------------------------------------
_client: Optional[QdrantClient] = None


def _chunk_id_to_uuid(chunk_id: str) -> str:
    """Deterministic UUID from chunk_id (reproducible, no collisions)."""
    return str(_uuid.uuid5(_uuid.NAMESPACE_DNS, chunk_id))


# ===========================================================================
# Lifecycle
# ===========================================================================

def init_store(
    path: str | Path = None,
    url: str = None,
    in_memory: bool = False,
) -> QdrantClient:
    """Initialize the Qdrant client.

    Parameters
    ----------
    path : str or Path
        Local persistence directory. Default: data/qdrant/
    url : str
        Remote Qdrant server URL (overrides path).
    in_memory : bool
        Use in-memory storage (for tests).

    Returns
    -------
    QdrantClient
    """
    global _client

    if url:
        _client = QdrantClient(url=url)
        logger.info("Qdrant connected to %s", url)
    elif in_memory:
        _client = QdrantClient(location=":memory:")
        logger.info("Qdrant initialized in-memory")
    else:
        store_path = Path(path) if path else Path(__file__).parent.parent / "data" / "qdrant"
        store_path.mkdir(parents=True, exist_ok=True)
        _client = QdrantClient(path=str(store_path))
        logger.info("Qdrant initialized at %s", store_path)

    return _client


def get_client() -> QdrantClient:
    """Get the current Qdrant client, initializing if needed."""
    if _client is None:
        init_store()
    return _client


def close_store() -> None:
    """Close the Qdrant client."""
    global _client
    if _client:
        _client.close()
        _client = None


# ===========================================================================
# Collection management
# ===========================================================================

def ensure_collection(
    name: str = DEFAULT_COLLECTION,
    vector_size: int = DEFAULT_VECTOR_SIZE,
) -> None:
    """Create the collection if it doesn't exist.

    Also creates payload indexes for fast filtering on
    company, year, doc_type, section, document_id.
    """
    client = get_client()

    # Check if collection exists
    collections = [c.name for c in client.get_collections().collections]

    if name in collections:
        logger.debug("Collection '%s' already exists", name)
        return

    client.create_collection(
        collection_name=name,
        vectors_config=models.VectorParams(
            size=vector_size,
            distance=models.Distance.COSINE,
        ),
    )
    logger.info("Created collection '%s' (dim=%d, cosine)", name, vector_size)

    # Create payload indexes for fast filtering
    for field_name, field_type in _INDEXED_FIELDS.items():
        try:
            client.create_payload_index(
                collection_name=name,
                field_name=field_name,
                field_schema=field_type,
            )
        except Exception:
            pass  # Index may already exist

    logger.info("Payload indexes created for %s", list(_INDEXED_FIELDS.keys()))


def delete_collection(name: str = DEFAULT_COLLECTION) -> None:
    """Delete a collection."""
    client = get_client()
    try:
        client.delete_collection(name)
        logger.info("Deleted collection '%s'", name)
    except Exception as exc:
        logger.warning("Could not delete collection '%s': %s", name, exc)


def collection_info(name: str = DEFAULT_COLLECTION) -> dict:
    """Get collection statistics."""
    client = get_client()
    try:
        info = client.get_collection(name)
        count = client.count(name).count
        return {
            "name": name,
            "points_count": count,
            "status": str(info.status),
            "vector_size": info.config.params.vectors.size,
            "distance": str(info.config.params.vectors.distance),
        }
    except Exception as exc:
        return {"name": name, "error": str(exc)}


# ===========================================================================
# Upload
# ===========================================================================

def upload_chunks(
    embedded_chunks: list[dict],
    collection: str = DEFAULT_COLLECTION,
    batch_size: int = 100,
) -> dict:
    """Upload embedded chunks to Qdrant.

    Parameters
    ----------
    embedded_chunks : list[dict]
        EmbeddedChunk dicts from embedder.embed_chunks()["chunks"].
        Each must have "chunk_id", "embedding", and metadata fields.
    collection : str
        Target collection name.
    batch_size : int
        Points per upsert call.

    Returns
    -------
    dict
        {"uploaded": N, "skipped": M, "failed": K}
    """
    client = get_client()
    ensure_collection(collection)

    uploaded = 0
    skipped = 0
    failed = 0

    points: list[models.PointStruct] = []

    for chunk in embedded_chunks:
        embedding = chunk.get("embedding", [])
        chunk_id = chunk.get("chunk_id", "")

        if not embedding or not chunk_id:
            skipped += 1
            continue

        # Build payload (everything except the vector itself)
        payload = {
            "chunk_id": chunk_id,
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
            "embedding_model": chunk.get("embedding_model", ""),
            "content_hash": chunk.get("content_hash", ""),
        }

        points.append(models.PointStruct(
            id=_chunk_id_to_uuid(chunk_id),
            vector=embedding,
            payload=payload,
        ))

        # Flush batch
        if len(points) >= batch_size:
            try:
                client.upsert(collection_name=collection, points=points)
                uploaded += len(points)
            except Exception as exc:
                logger.error("Batch upload failed: %s", exc)
                failed += len(points)
            points = []

    # Final batch
    if points:
        try:
            client.upsert(collection_name=collection, points=points)
            uploaded += len(points)
        except Exception as exc:
            logger.error("Final batch upload failed: %s", exc)
            failed += len(points)

    logger.info("Upload complete: %d uploaded, %d skipped, %d failed",
                uploaded, skipped, failed)

    return {"uploaded": uploaded, "skipped": skipped, "failed": failed}


# ===========================================================================
# Search
# ===========================================================================

def build_filter(
    company: str = None,
    year: int = None,
    doc_type: str = None,
    section: str = None,
    document_id: str = None,
) -> Optional[models.Filter]:
    """Build a Qdrant filter from metadata constraints.

    Returns None if no constraints provided.
    """
    conditions = []

    if company:
        conditions.append(models.FieldCondition(
            key="company", match=models.MatchValue(value=company),
        ))
    if year is not None:
        conditions.append(models.FieldCondition(
            key="year", match=models.MatchValue(value=year),
        ))
    if doc_type:
        conditions.append(models.FieldCondition(
            key="doc_type", match=models.MatchValue(value=doc_type),
        ))
    if section:
        conditions.append(models.FieldCondition(
            key="section", match=models.MatchValue(value=section),
        ))
    if document_id:
        conditions.append(models.FieldCondition(
            key="document_id", match=models.MatchValue(value=document_id),
        ))

    if not conditions:
        return None

    return models.Filter(must=conditions)


def search(
    query_vector: list[float],
    collection: str = DEFAULT_COLLECTION,
    top_k: int = 10,
    company: str = None,
    year: int = None,
    doc_type: str = None,
    section: str = None,
    document_id: str = None,
    min_score: float = 0.0,
) -> list[dict]:
    """Search for similar vectors with optional metadata filtering.

    Parameters
    ----------
    query_vector : list[float]
        The query embedding vector.
    collection : str
        Collection to search.
    top_k : int
        Maximum results to return.
    company, year, doc_type, section, document_id
        Metadata filters (all optional).
    min_score : float
        Minimum similarity score (0.0–1.0 for cosine).

    Returns
    -------
    list[dict]
        Retrieval results sorted by score descending::

            [{
                "chunk_id": "TCS_RF_003",
                "score": 0.94,
                "text": "...",
                "company": "TCS",
                "year": 2025,
                "section": "Risk Factors",
                "page_start": 119,
                "page_end": 120,
                ...
            }]
    """
    client = get_client()
    qfilter = build_filter(company, year, doc_type, section, document_id)

    response = client.query_points(
        collection_name=collection,
        query=query_vector,
        limit=top_k,
        query_filter=qfilter,
        score_threshold=min_score if min_score > 0 else None,
    )

    results = []
    for hit in response.points:
        payload = hit.payload or {}
        results.append({
            "chunk_id": payload.get("chunk_id", ""),
            "score": round(hit.score, 4),
            "text": payload.get("text", ""),
            "document_id": payload.get("document_id"),
            "company": payload.get("company"),
            "year": payload.get("year"),
            "doc_type": payload.get("doc_type"),
            "section": payload.get("section"),
            "subsection": payload.get("subsection"),
            "page_start": payload.get("page_start"),
            "page_end": payload.get("page_end"),
            "token_count": payload.get("token_count", 0),
            "has_heading": payload.get("has_heading", False),
            "contains_table": payload.get("contains_table", False),
            "quality_score": payload.get("quality_score", 0.0),
        })

    return results


# ===========================================================================
# Delete
# ===========================================================================

def delete_by_document(
    document_id: str,
    collection: str = DEFAULT_COLLECTION,
) -> None:
    """Delete all vectors for a document."""
    client = get_client()
    client.delete(
        collection_name=collection,
        points_selector=models.FilterSelector(
            filter=models.Filter(must=[
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(value=document_id),
                ),
            ]),
        ),
    )
    logger.info("Deleted vectors for document '%s'", document_id)
