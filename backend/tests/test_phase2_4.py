"""
Phase 2.4 - Embedding Generation Pipeline Verification

Run from the backend/ directory:
    python -X utf8 tests/test_phase2_4.py

Tests (no API key required for 1-6):
    1. Content hashing (SHA-256 stability)
    2. Embedding cache (SQLite CRUD)
    3. Cache deduplication (same hash → skip)
    4. Embedder module structure
    5. Model configuration
    6. Pydantic schema validation
    7. Live embedding (requires OPENAI_API_KEY in .env)
    8. Batch processing + caching (requires API key)
    9. Full pipeline: extract → clean → chunk → embed (requires API key)
"""

import sys
import json
import os
import shutil
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
PASS = "[PASS]"
FAIL = "[FAIL]"
SKIP = "[SKIP]"
DIVIDER = "=" * 60

test_results: list[dict] = []
TEST_DIR = Path(__file__).parent / "test_embedding"


def log_result(test_name: str, passed: bool, detail: str = ""):
    status = PASS if passed else FAIL
    test_results.append({"name": test_name, "passed": passed})
    print(f"  {status}  {test_name}")
    if detail:
        print(f"         {detail}")


def log_skip(test_name: str, reason: str = ""):
    print(f"  {SKIP}  {test_name}")
    if reason:
        print(f"         {reason}")


def section(title: str):
    print(f"\n{DIVIDER}")
    print(f"  {title}")
    print(DIVIDER)


def _has_api_key() -> bool:
    from config.settings import settings
    return bool(settings.OPENAI_API_KEY)


# ===================================================================
# 1. CONTENT HASHING
# ===================================================================

def test_hashing():
    section("1. CONTENT HASHING")
    from embedding.cache import hash_text

    # Deterministic
    h1 = hash_text("Revenue increased by 14%.")
    h2 = hash_text("Revenue increased by 14%.")
    log_result("Same text → same hash", h1 == h2)

    # Different text → different hash
    h3 = hash_text("Revenue decreased by 14%.")
    log_result("Different text → different hash", h1 != h3)

    # SHA-256 format (64 hex chars)
    log_result("Hash is 64 hex chars", len(h1) == 64 and all(c in "0123456789abcdef" for c in h1))

    # Unicode stability
    h4 = hash_text("Revenue: ₹50,000 crore")
    h5 = hash_text("Revenue: ₹50,000 crore")
    log_result("Unicode hashing stable", h4 == h5)

    # Empty string
    h6 = hash_text("")
    log_result("Empty string hashes", len(h6) == 64)


# ===================================================================
# 2. EMBEDDING CACHE (CRUD)
# ===================================================================

def test_cache_crud():
    section("2. EMBEDDING CACHE (SQLite)")
    from embedding.cache import init_cache, close_cache, get_cached, put_cached, cache_stats, clear_cache

    TEST_DIR.mkdir(parents=True, exist_ok=True)
    db_path = TEST_DIR / "test_cache.db"

    try:
        init_cache(db_path)
        log_result("Cache initialized", True)

        # Put a vector
        test_hash = "a" * 64
        test_vector = [0.1, 0.2, 0.3, 0.4, 0.5]
        put_cached(test_hash, "chunk_001", test_vector, "test-model", 5, 1)
        log_result("Put cached", True)

        # Get it back
        result = get_cached(test_hash, "test-model", 1)
        log_result("Get cached returns vector", result is not None)
        log_result("Vector matches", result == test_vector)

        # Miss — wrong model
        miss = get_cached(test_hash, "different-model", 1)
        log_result("Wrong model → None", miss is None)

        # Miss — wrong version
        miss = get_cached(test_hash, "test-model", 2)
        log_result("Wrong version → None", miss is None)

        # Miss — wrong hash
        miss = get_cached("b" * 64, "test-model", 1)
        log_result("Wrong hash → None", miss is None)

        # Stats
        stats = cache_stats()
        log_result("Cache stats", stats["total_cached"] == 1,
                   f"total={stats['total_cached']}, models={stats['models']}")

        # Upsert (same hash replaces)
        put_cached(test_hash, "chunk_001", [0.9, 0.8], "test-model", 2, 1)
        result = get_cached(test_hash, "test-model", 1)
        log_result("Upsert replaces", result == [0.9, 0.8])

        # Clear
        clear_cache()
        stats = cache_stats()
        log_result("Clear cache", stats["total_cached"] == 0)

    finally:
        close_cache()
        if db_path.exists():
            os.remove(db_path)


# ===================================================================
# 3. CACHE DEDUPLICATION
# ===================================================================

def test_cache_dedup():
    section("3. CACHE DEDUPLICATION")
    from embedding.cache import init_cache, close_cache, get_cached, put_cached, hash_text, cache_stats, clear_cache

    TEST_DIR.mkdir(parents=True, exist_ok=True)
    db_path = TEST_DIR / "test_dedup.db"

    try:
        init_cache(db_path)

        text = "Cloud revenue increased by 28%."
        h = hash_text(text)

        # First put
        put_cached(h, "chunk_001", [0.1] * 10, "model-a", 10, 1)

        # Second put with same hash = replace, not duplicate
        put_cached(h, "chunk_001", [0.2] * 10, "model-a", 10, 1)

        stats = cache_stats()
        log_result("No duplicate entries", stats["total_cached"] == 1)

        # Different model = separate entry
        put_cached(h, "chunk_001", [0.3] * 10, "model-b", 10, 1)
        stats = cache_stats()
        log_result("Different model = separate entry", stats["total_cached"] == 2)

    finally:
        close_cache()
        if db_path.exists():
            os.remove(db_path)


# ===================================================================
# 4. EMBEDDER MODULE STRUCTURE
# ===================================================================

def test_embedder_module():
    section("4. EMBEDDER MODULE STRUCTURE")
    from embedding import embedder

    log_result("Has EMBEDDING_MODELS", hasattr(embedder, "EMBEDDING_MODELS"))
    log_result("Has DEFAULT_MODEL", hasattr(embedder, "DEFAULT_MODEL"))
    log_result("Has EMBEDDING_VERSION", hasattr(embedder, "EMBEDDING_VERSION"))
    log_result("Has embed_chunks function", callable(getattr(embedder, "embed_chunks", None)))
    log_result("Has _embed_batch_raw function", callable(getattr(embedder, "_embed_batch_raw", None)))

    # Model config
    models = embedder.EMBEDDING_MODELS
    log_result("text-embedding-3-small defined",
               "text-embedding-3-small" in models,
               f"dim={models.get('text-embedding-3-small', {}).get('dim')}")
    log_result("text-embedding-3-large defined",
               "text-embedding-3-large" in models,
               f"dim={models.get('text-embedding-3-large', {}).get('dim')}")


# ===================================================================
# 5. MODEL CONFIGURATION
# ===================================================================

def test_model_config():
    section("5. MODEL CONFIGURATION")
    from embedding.embedder import EMBEDDING_MODELS

    for name, config in EMBEDDING_MODELS.items():
        log_result(f"{name}: dim={config['dim']}",
                   config["dim"] > 0 and config["max_tokens"] > 0)

    # Default model exists
    from embedding.embedder import DEFAULT_MODEL
    log_result("Default model is valid",
               DEFAULT_MODEL in EMBEDDING_MODELS,
               f"default = {DEFAULT_MODEL}")


# ===================================================================
# 6. PYDANTIC SCHEMA VALIDATION
# ===================================================================

def test_schemas():
    section("6. PYDANTIC SCHEMAS")
    from schemas.embedding import EmbeddedChunk, EmbeddingResult

    # EmbeddedChunk
    chunk = EmbeddedChunk(
        chunk_id="TCS_2025_RF_003",
        document_id="TCS_10K_2025",
        company="TCS",
        year=2025,
        section="Risk Factors",
        text="The company faces cybersecurity risks...",
        token_count=786,
        embedding=[0.1] * 1536,
        embedding_model="text-embedding-3-small",
        embedding_version=1,
        embedding_dim=1536,
        content_hash="a" * 64,
        embedded_at="2026-07-29T10:15:00Z",
    )
    log_result("EmbeddedChunk validates", True)
    log_result("EmbeddedChunk has embedding", len(chunk.embedding) == 1536)

    # Serialization (exclude embedding for readability)
    d = chunk.model_dump()
    log_result("model_dump works", "embedding" in d and "content_hash" in d)

    # EmbeddingResult
    result = EmbeddingResult(
        document_id="TCS_10K_2025",
        total_chunks=150,
        embedded=130,
        cached=20,
        failed=0,
        embedding_model="text-embedding-3-small",
        embedding_dim=1536,
        chunks=[chunk],
    )
    log_result("EmbeddingResult validates", True)
    log_result("EmbeddingResult serializes", len(result.model_dump_json(exclude={"chunks"})) > 50)


# ===================================================================
# 7. LIVE EMBEDDING (requires API key)
# ===================================================================

def test_live_embedding():
    section("7. LIVE EMBEDDING (OpenAI API)")
    if not _has_api_key():
        log_skip("Live embedding", "OPENAI_API_KEY not set in .env — skipping")
        return

    from embedding.embedder import embed_chunks, DEFAULT_MODEL, EMBEDDING_MODELS

    expected_dim = EMBEDDING_MODELS[DEFAULT_MODEL]["dim"]

    # Simple chunks
    chunks = [
        {
            "chunk_id": "test_chunk_001",
            "text": "Revenue increased by 14% due to strong cloud demand.",
            "token_count": 12,
        },
        {
            "chunk_id": "test_chunk_002",
            "text": "The company faces significant cybersecurity risks.",
            "token_count": 10,
        },
    ]

    result = embed_chunks(chunks, use_cache=False)

    log_result("Returns dict", isinstance(result, dict))
    log_result("total_chunks = 2", result["total_chunks"] == 2)
    log_result("embedded = 2", result["embedded"] == 2)
    log_result("failed = 0", result["failed"] == 0)
    log_result(f"Model = {DEFAULT_MODEL}", result["embedding_model"] == DEFAULT_MODEL)
    log_result(f"Dimension = {expected_dim}", result["embedding_dim"] == expected_dim)

    embedded = result["chunks"]
    if embedded:
        e = embedded[0]
        log_result("Chunk has embedding vector",
                   isinstance(e["embedding"], list) and len(e["embedding"]) == expected_dim,
                   f"dim = {len(e.get('embedding', []))}")
        log_result("Chunk has content_hash", len(e.get("content_hash", "")) == 64)
        log_result("Chunk has embedded_at", e.get("embedded_at") is not None)
        log_result("Chunk has embedding_model", e.get("embedding_model") == DEFAULT_MODEL)
        log_result("Chunk preserves text", "Revenue" in e.get("text", ""))
        log_result("Chunk preserves chunk_id", e.get("chunk_id") == "test_chunk_001")

        # Vectors should be different for different texts
        if len(embedded) >= 2:
            v1 = embedded[0]["embedding"]
            v2 = embedded[1]["embedding"]
            # Compute cosine-ish check: they shouldn't be identical
            are_different = any(abs(a - b) > 0.001 for a, b in zip(v1[:10], v2[:10]))
            log_result("Different texts → different vectors", are_different)


# ===================================================================
# 8. BATCH + CACHING (requires API key)
# ===================================================================

def test_batch_caching():
    section("8. BATCH PROCESSING + CACHING")
    if not _has_api_key():
        log_skip("Batch + caching", "OPENAI_API_KEY not set — skipping")
        return

    from embedding.embedder import embed_chunks
    from embedding.cache import init_cache, close_cache, clear_cache

    TEST_DIR.mkdir(parents=True, exist_ok=True)
    db_path = TEST_DIR / "test_batch_cache.db"

    try:
        init_cache(db_path)
        clear_cache()

        chunks = [
            {"chunk_id": f"batch_{i:03d}", "text": f"Financial statement line item number {i} shows growth."}
            for i in range(5)
        ]

        # First run — all should be embedded (API call)
        r1 = embed_chunks(chunks, use_cache=True)
        log_result("First run: all embedded",
                   r1["embedded"] == 5,
                   f"embedded={r1['embedded']}, cached={r1['cached']}")

        # Second run — all should be cached (no API call)
        r2 = embed_chunks(chunks, use_cache=True)
        log_result("Second run: all cached",
                   r2["cached"] == 5,
                   f"embedded={r2['embedded']}, cached={r2['cached']}")
        log_result("No API calls on second run", r2["embedded"] == 0)

        # Vectors from cache match originals
        if r1["chunks"] and r2["chunks"]:
            v1 = r1["chunks"][0]["embedding"]
            v2 = r2["chunks"][0]["embedding"]
            log_result("Cached vector matches original",
                       v1 == v2,
                       f"v1[0]={v1[0]:.4f}, v2[0]={v2[0]:.4f}")

        # Modified chunk should miss cache
        chunks_modified = [
            {"chunk_id": "batch_000", "text": "MODIFIED: Financial statement shows decline."},
        ]
        r3 = embed_chunks(chunks_modified, use_cache=True)
        log_result("Modified text → cache miss",
                   r3["embedded"] == 1,
                   f"embedded={r3['embedded']}, cached={r3['cached']}")

    finally:
        close_cache()
        if db_path.exists():
            os.remove(db_path)


# ===================================================================
# 9. FULL PIPELINE (requires API key)
# ===================================================================

def test_full_pipeline():
    section("9. FULL PIPELINE -- Extract → Clean → Chunk → Embed")
    if not _has_api_key():
        log_skip("Full pipeline", "OPENAI_API_KEY not set — skipping")
        return

    try:
        from connectors.sec_edgar import get_annual_filings, download_filing
        from ingestion.pdf_extractor import extract_document
        from ingestion.text_cleaner import clean_document
        from ingestion.chunker import chunk_document
        from embedding.embedder import embed_chunks, EMBEDDING_MODELS, DEFAULT_MODEL
        from embedding.cache import init_cache, close_cache, clear_cache

        TEST_DIR.mkdir(parents=True, exist_ok=True)
        db_path = TEST_DIR / "test_pipeline_cache.db"

        try:
            init_cache(db_path)
            clear_cache()

            # Download
            filings = get_annual_filings("AAPL", limit=1)
            dl = download_filing(filings[0], TEST_DIR / "pipeline")
            log_result("Downloaded", dl["success"], f"{dl['file_size']:,} bytes")

            # Extract
            extraction = extract_document(dl["file_path"], document_id="AAPL_10K", company="AAPL", year=2025)
            log_result("Extracted", extraction["success"], f"{extraction['total_pages']} pages")

            # Clean
            cleaned = clean_document(extraction["pages"])
            log_result("Cleaned", cleaned["statistics"]["clean_characters"] > 0)

            # Chunk
            chunked = chunk_document(cleaned["pages"], document_id="AAPL_10K", company="AAPL", year=2025)
            total_chunks = chunked["total_chunks"]
            log_result("Chunked", total_chunks > 0, f"{total_chunks} chunks")

            # Embed (only first 10 chunks to save API cost)
            sample_chunks = chunked["chunks"][:10]
            result = embed_chunks(sample_chunks, use_cache=True)

            expected_dim = EMBEDDING_MODELS[DEFAULT_MODEL]["dim"]
            log_result("Embedded", result["embedded"] + result["cached"] > 0,
                       f"embedded={result['embedded']}, cached={result['cached']}, failed={result['failed']}")
            log_result(f"Dimension = {expected_dim}", result["embedding_dim"] == expected_dim)

            # Verify vectors
            if result["chunks"]:
                e = result["chunks"][0]
                log_result("Vector has correct dim",
                           len(e["embedding"]) == expected_dim)
                log_result("Has content_hash", len(e["content_hash"]) == 64)
                log_result("Has embedded_at", e["embedded_at"] is not None)
                log_result("Preserves company", e["company"] == "AAPL")
                log_result("Preserves year", e["year"] == 2025)
                log_result("Has section metadata", "section" in e)

                print(f"\n  Pipeline summary:")
                print(f"    Pages:     {extraction['total_pages']}")
                print(f"    Chunks:    {total_chunks}")
                print(f"    Embedded:  {result['embedded']}")
                print(f"    Cached:    {result['cached']}")
                print(f"    Model:     {result['embedding_model']}")
                print(f"    Dimension: {result['embedding_dim']}")

        finally:
            close_cache()
            if db_path.exists():
                os.remove(db_path)

    except Exception as exc:
        log_result("Full pipeline", False, str(exc))
        import traceback
        traceback.print_exc()


# ===================================================================
# RUNNER
# ===================================================================

def main():
    print("\n" + "#" * 60)
    print("  PHASE 2.4 -- EMBEDDING PIPELINE VERIFICATION")
    print("#" * 60)

    if _has_api_key():
        print(f"\n  OPENAI_API_KEY detected — full tests will run")
    else:
        print(f"\n  OPENAI_API_KEY not set — API tests will be skipped")
        print(f"  Set it in backend/config/.env to run full tests")

    start = time.time()

    TEST_DIR.mkdir(parents=True, exist_ok=True)
    try:
        test_hashing()
        test_cache_crud()
        test_cache_dedup()
        test_embedder_module()
        test_model_config()
        test_schemas()
        test_live_embedding()
        test_batch_caching()
        test_full_pipeline()
    finally:
        if TEST_DIR.exists():
            shutil.rmtree(TEST_DIR)

    elapsed = time.time() - start

    section("SUMMARY")
    passed = sum(1 for t in test_results if t["passed"])
    failed = sum(1 for t in test_results if not t["passed"])
    total = len(test_results)

    print(f"\n  Total:  {total}")
    print(f"  Passed: {passed} {PASS}")
    print(f"  Failed: {failed} {FAIL}")
    print(f"  Time:   {elapsed:.1f}s")

    if failed > 0:
        print(f"\n  Failed tests:")
        for t in test_results:
            if not t["passed"]:
                print(f"    {FAIL}  {t['name']}")

    print(f"\n{'#' * 60}\n")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
