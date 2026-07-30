"""
Phase 2.5 - Vector Database & Semantic Retrieval Verification

Run from the backend/ directory:
    python -X utf8 tests/test_phase2_5.py

Tests (all offline — no API key required):
    1. Qdrant client lifecycle (init, in-memory)
    2. Collection CRUD (create, info, delete)
    3. Upload embedded chunks
    4. Vector search (synthetic vectors, cosine similarity)
    5. Metadata filtering (company, year, doc_type, section)
    6. Similarity thresholding
    7. Re-ranking (heading + quality boost)
    8. Deduplication
    9. Context assembly (document-order sorting)
   10. Citation formatting
   11. Full retriever pipeline (query_vector mode)
   12. Pydantic schema validation
   13. Live semantic search (requires OPENAI_API_KEY)
"""

import sys
import math
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


# ---------------------------------------------------------------------------
# Synthetic test data
# ---------------------------------------------------------------------------
DIM = 1536


def _unit_vector(index: int, dim: int = DIM) -> list[float]:
    """Create a unit vector with 1.0 at `index` and small random elsewhere."""
    import random
    random.seed(42 + index)
    vec = [random.gauss(0, 0.01) for _ in range(dim)]
    vec[index % dim] = 1.0
    # Normalize
    mag = math.sqrt(sum(v * v for v in vec))
    return [v / mag for v in vec]


def _make_test_chunks() -> list[dict]:
    """Create synthetic embedded chunks with controlled vector directions."""
    chunks = []

    # --- Risk-related chunks (vectors pointing ~direction 0) ---
    for i in range(5):
        chunks.append({
            "chunk_id": f"TCS_risk_{i:03d}",
            "document_id": "TCS_10K_2025",
            "company": "TCS",
            "year": 2025,
            "doc_type": "Annual Report",
            "section": "Risk Factors",
            "subsection": f"Risk {i}",
            "page_start": 100 + i,
            "page_end": 101 + i,
            "text": f"Risk factor {i}: The company faces significant cybersecurity threats.",
            "token_count": 50,
            "has_heading": True,
            "contains_table": False,
            "quality_score": 0.9,
            "embedding": _unit_vector(0 + i),
            "embedding_model": "test-model",
            "content_hash": f"{'a' * 60}{i:04d}",
        })

    # --- Revenue-related chunks (vectors pointing ~direction 100) ---
    for i in range(5):
        chunks.append({
            "chunk_id": f"TCS_rev_{i:03d}",
            "document_id": "TCS_10K_2025",
            "company": "TCS",
            "year": 2025,
            "doc_type": "Annual Report",
            "section": "Financial Statements",
            "subsection": "Revenue",
            "page_start": 200 + i,
            "page_end": 201 + i,
            "text": f"Revenue item {i}: Cloud revenue increased by {10+i}%.",
            "token_count": 40,
            "has_heading": False,
            "contains_table": True,
            "quality_score": 0.85,
            "embedding": _unit_vector(100 + i),
            "embedding_model": "test-model",
            "content_hash": f"{'b' * 60}{i:04d}",
        })

    # --- INFY chunks (different company, vectors ~direction 200) ---
    for i in range(3):
        chunks.append({
            "chunk_id": f"INFY_risk_{i:03d}",
            "document_id": "INFY_10K_2025",
            "company": "INFY",
            "year": 2025,
            "doc_type": "Annual Report",
            "section": "Risk Factors",
            "subsection": f"Risk {i}",
            "page_start": 50 + i,
            "page_end": 51 + i,
            "text": f"Infosys risk {i}: Regulatory compliance challenges.",
            "token_count": 45,
            "has_heading": True,
            "contains_table": False,
            "quality_score": 0.88,
            "embedding": _unit_vector(200 + i),
            "embedding_model": "test-model",
            "content_hash": f"{'c' * 60}{i:04d}",
        })

    # --- 2024 chunks (different year, vectors ~direction 300) ---
    for i in range(2):
        chunks.append({
            "chunk_id": f"TCS_2024_{i:03d}",
            "document_id": "TCS_10K_2024",
            "company": "TCS",
            "year": 2024,
            "doc_type": "Annual Report",
            "section": "Business Overview",
            "page_start": 10 + i,
            "page_end": 11 + i,
            "text": f"TCS 2024 overview {i}: Digital transformation drives growth.",
            "token_count": 55,
            "has_heading": True,
            "contains_table": False,
            "quality_score": 0.92,
            "embedding": _unit_vector(300 + i),
            "embedding_model": "test-model",
            "content_hash": f"{'d' * 60}{i:04d}",
        })

    return chunks


# ===================================================================
# 1. QDRANT CLIENT LIFECYCLE
# ===================================================================

def test_client_lifecycle():
    section("1. QDRANT CLIENT LIFECYCLE")
    from vector_store.qdrant_store import init_store, get_client, close_store

    # In-memory init
    client = init_store(in_memory=True)
    log_result("In-memory client initialized", client is not None)

    client2 = get_client()
    log_result("get_client returns same instance", client2 is client)

    close_store()
    log_result("Client closed", True)


# ===================================================================
# 2. COLLECTION CRUD
# ===================================================================

def test_collection_crud():
    section("2. COLLECTION CRUD")
    from vector_store.qdrant_store import (
        init_store, close_store, ensure_collection, delete_collection,
        collection_info,
    )

    try:
        init_store(in_memory=True)

        # Create
        ensure_collection("test_collection", vector_size=DIM)
        log_result("Collection created", True)

        # Info
        info = collection_info("test_collection")
        log_result("Collection info returned", "points_count" in info)
        log_result("Vector size correct",
                   info.get("vector_size") == DIM,
                   f"size = {info.get('vector_size')}")
        log_result("Distance is cosine",
                   "Cosine" in str(info.get("distance", "")))

        # Idempotent create
        ensure_collection("test_collection", vector_size=DIM)
        log_result("Idempotent create", True)

        # Delete
        delete_collection("test_collection")
        info2 = collection_info("test_collection")
        log_result("Collection deleted", "error" in info2)

    finally:
        close_store()


# ===================================================================
# 3. UPLOAD
# ===================================================================

def test_upload():
    section("3. UPLOAD EMBEDDED CHUNKS")
    from vector_store.qdrant_store import (
        init_store, close_store, ensure_collection, upload_chunks,
        collection_info,
    )

    try:
        init_store(in_memory=True)
        ensure_collection("test_upload", vector_size=DIM)

        chunks = _make_test_chunks()
        result = upload_chunks(chunks, collection="test_upload")

        log_result("Upload returns dict", isinstance(result, dict))
        log_result(f"Uploaded {result['uploaded']} chunks",
                   result["uploaded"] == len(chunks),
                   f"expected {len(chunks)}")
        log_result("No skipped", result["skipped"] == 0)
        log_result("No failed", result["failed"] == 0)

        # Verify collection count
        info = collection_info("test_upload")
        log_result("Collection has correct count",
                   info.get("points_count") == len(chunks),
                   f"points = {info.get('points_count')}")

        # Upsert idempotent (upload same chunks again)
        result2 = upload_chunks(chunks, collection="test_upload")
        info2 = collection_info("test_upload")
        log_result("Upsert idempotent",
                   info2.get("points_count") == len(chunks),
                   f"points still = {info2.get('points_count')}")

        # Upload with empty embedding (should be skipped)
        bad_chunks = [{"chunk_id": "bad", "embedding": [], "text": "nothing"}]
        r3 = upload_chunks(bad_chunks, collection="test_upload")
        log_result("Empty embedding skipped", r3["skipped"] == 1)

    finally:
        close_store()


# ===================================================================
# 4. VECTOR SEARCH
# ===================================================================

def test_vector_search():
    section("4. VECTOR SEARCH (Cosine Similarity)")
    from vector_store.qdrant_store import (
        init_store, close_store, ensure_collection, upload_chunks, search,
    )

    try:
        init_store(in_memory=True)
        ensure_collection("test_search", vector_size=DIM)
        upload_chunks(_make_test_chunks(), collection="test_search")

        # Query with risk-like vector → should find risk chunks first
        query = _unit_vector(0)  # Matches risk direction
        results = search(query, collection="test_search", top_k=5)

        log_result("Search returns results", len(results) > 0,
                   f"got {len(results)}")
        log_result("Results have scores", all("score" in r for r in results))
        log_result("Results sorted by score",
                   all(results[i]["score"] >= results[i+1]["score"]
                       for i in range(len(results)-1)))

        # Top result should be TCS risk chunk (same vector direction)
        top = results[0]
        log_result("Top result is risk-related",
                   "risk" in top.get("chunk_id", "").lower(),
                   f"top = {top.get('chunk_id')}, score = {top.get('score')}")
        log_result("Top result has text", len(top.get("text", "")) > 0)
        log_result("Top result has metadata",
                   top.get("company") == "TCS" and top.get("section") == "Risk Factors")

        # Query with revenue-like vector → should find revenue chunks first
        query2 = _unit_vector(100)
        results2 = search(query2, collection="test_search", top_k=5)
        top2 = results2[0]
        log_result("Revenue query finds revenue chunk",
                   "rev" in top2.get("chunk_id", "").lower(),
                   f"top = {top2.get('chunk_id')}, score = {top2.get('score')}")

    finally:
        close_store()


# ===================================================================
# 5. METADATA FILTERING
# ===================================================================

def test_metadata_filtering():
    section("5. METADATA FILTERING")
    from vector_store.qdrant_store import (
        init_store, close_store, ensure_collection, upload_chunks, search,
    )

    try:
        init_store(in_memory=True)
        ensure_collection("test_filter", vector_size=DIM)
        upload_chunks(_make_test_chunks(), collection="test_filter")

        query = _unit_vector(0)

        # Filter by company
        results_tcs = search(query, collection="test_filter", top_k=20, company="TCS")
        all_tcs = all(r["company"] == "TCS" for r in results_tcs)
        log_result("Company filter: only TCS", all_tcs,
                   f"{len(results_tcs)} results, all TCS = {all_tcs}")

        results_infy = search(query, collection="test_filter", top_k=20, company="INFY")
        all_infy = all(r["company"] == "INFY" for r in results_infy)
        log_result("Company filter: only INFY", all_infy,
                   f"{len(results_infy)} results")

        # Filter by year
        results_2024 = search(query, collection="test_filter", top_k=20, year=2024)
        all_2024 = all(r["year"] == 2024 for r in results_2024)
        log_result("Year filter: only 2024", all_2024,
                   f"{len(results_2024)} results")

        # Filter by section
        results_risk = search(query, collection="test_filter", top_k=20,
                             section="Risk Factors")
        all_risk = all(r["section"] == "Risk Factors" for r in results_risk)
        log_result("Section filter: only Risk Factors", all_risk,
                   f"{len(results_risk)} results")

        # Combined filters
        results_combo = search(query, collection="test_filter", top_k=20,
                              company="TCS", year=2025,
                              section="Risk Factors")
        valid = all(r["company"] == "TCS" and r["year"] == 2025
                    and r["section"] == "Risk Factors" for r in results_combo)
        log_result("Combined filter (TCS + 2025 + Risk)", valid,
                   f"{len(results_combo)} results")

        # Filter by document_id
        results_doc = search(query, collection="test_filter", top_k=20,
                            document_id="INFY_10K_2025")
        all_doc = all(r["document_id"] == "INFY_10K_2025" for r in results_doc)
        log_result("Document ID filter", all_doc,
                   f"{len(results_doc)} results")

    finally:
        close_store()


# ===================================================================
# 6. SIMILARITY THRESHOLDING
# ===================================================================

def test_thresholding():
    section("6. SIMILARITY THRESHOLDING")
    from vector_store.qdrant_store import (
        init_store, close_store, ensure_collection, upload_chunks, search,
    )

    try:
        init_store(in_memory=True)
        ensure_collection("test_thresh", vector_size=DIM)
        upload_chunks(_make_test_chunks(), collection="test_thresh")

        query = _unit_vector(0)

        # No threshold → get all
        all_results = search(query, collection="test_thresh", top_k=20)
        log_result("No threshold returns many results",
                   len(all_results) > 5,
                   f"got {len(all_results)}")

        # High threshold → fewer results
        high_results = search(query, collection="test_thresh", top_k=20,
                             min_score=0.5)
        log_result("High threshold filters results",
                   len(high_results) <= len(all_results),
                   f"got {len(high_results)} (threshold=0.5)")

        # Very high threshold → even fewer
        very_high = search(query, collection="test_thresh", top_k=20,
                          min_score=0.9)
        log_result("Very high threshold (0.9)",
                   len(very_high) <= len(high_results),
                   f"got {len(very_high)}")

        # All returned scores above threshold
        if high_results:
            above = all(r["score"] >= 0.5 for r in high_results)
            log_result("All scores >= threshold", above)

    finally:
        close_store()


# ===================================================================
# 7. RE-RANKING
# ===================================================================

def test_reranking():
    section("7. RE-RANKING")
    from retrieval.retriever import _rerank

    results = [
        {"score": 0.80, "has_heading": False, "quality_score": 0.7,
         "contains_table": False, "section": None, "chunk_id": "no_heading"},
        {"score": 0.78, "has_heading": True, "quality_score": 0.9,
         "contains_table": False, "section": "Risk Factors", "chunk_id": "with_heading"},
        {"score": 0.82, "has_heading": False, "quality_score": 0.6,
         "contains_table": True, "section": None, "chunk_id": "table_chunk"},
    ]

    reranked = _rerank(results)

    log_result("Re-ranking returns list", isinstance(reranked, list))
    log_result("Same number of results", len(reranked) == 3)

    # The chunk with heading + high quality + section should be boosted
    ids = [r["chunk_id"] for r in reranked]
    log_result("Heading chunk boosted to top",
               ids[0] == "with_heading",
               f"order = {ids}")


# ===================================================================
# 8. DEDUPLICATION
# ===================================================================

def test_deduplication():
    section("8. DEDUPLICATION")
    from retrieval.retriever import _deduplicate

    results = [
        {"chunk_id": "a", "text": "Revenue increased by 14%.", "score": 0.9},
        {"chunk_id": "a", "text": "Revenue increased by 14%.", "score": 0.85},  # dup id
        {"chunk_id": "b", "text": "Revenue increased by 14%.", "score": 0.80},  # dup text
        {"chunk_id": "c", "text": "Risk factors are significant.", "score": 0.75},
    ]

    deduped = _deduplicate(results)

    log_result("Dedup removes duplicates",
               len(deduped) == 2,
               f"got {len(deduped)}, expected 2")
    ids = [r["chunk_id"] for r in deduped]
    log_result("Keeps first occurrence", "a" in ids and "c" in ids,
               f"ids = {ids}")


# ===================================================================
# 9. CONTEXT ASSEMBLY
# ===================================================================

def test_context_assembly():
    section("9. CONTEXT ASSEMBLY (Document-Order)")
    from retrieval.retriever import _assemble_context

    results = [
        {"document_id": "doc1", "page_start": 50, "chunk_id": "c", "score": 0.8},
        {"document_id": "doc1", "page_start": 10, "chunk_id": "a", "score": 0.9},
        {"document_id": "doc2", "page_start": 5, "chunk_id": "d", "score": 0.7},
        {"document_id": "doc1", "page_start": 30, "chunk_id": "b", "score": 0.85},
    ]

    assembled = _assemble_context(results)
    pages = [r["page_start"] for r in assembled if r["document_id"] == "doc1"]
    log_result("Same-doc chunks sorted by page",
               pages == sorted(pages),
               f"pages = {pages}")

    # doc1 should come before doc2 (doc1 appeared first)
    doc_ids = [r["document_id"] for r in assembled]
    first_doc2 = doc_ids.index("doc2")
    log_result("Document order preserved",
               all(d == "doc1" for d in doc_ids[:first_doc2]))


# ===================================================================
# 10. CITATION FORMATTING
# ===================================================================

def test_citation():
    section("10. CITATION FORMATTING")
    from schemas.retrieval import RetrievalHit

    hit = RetrievalHit(
        chunk_id="TCS_RF_003",
        score=0.94,
        text="The company faces cybersecurity risks...",
        company="TCS",
        year=2025,
        doc_type="Annual Report",
        section="Risk Factors",
        page_start=119,
        page_end=120,
    )

    citation = hit.citation()
    log_result("Citation has company", "TCS" in citation)
    log_result("Citation has year", "2025" in citation)
    log_result("Citation has section", "Risk Factors" in citation)
    log_result("Citation has pages", "119" in citation and "120" in citation)
    log_result("Citation is readable",
               len(citation) > 10,
               f"'{citation}'")

    # Single page
    hit2 = RetrievalHit(chunk_id="x", score=0.5, company="INFY", page_start=42)
    c2 = hit2.citation()
    log_result("Single page citation", "Page 42" in c2, f"'{c2}'")

    # Minimal
    hit3 = RetrievalHit(chunk_id="x", score=0.5)
    c3 = hit3.citation()
    log_result("Minimal citation", c3 == "Unknown source", f"'{c3}'")


# ===================================================================
# 11. FULL RETRIEVER PIPELINE (query_vector mode)
# ===================================================================

def test_retriever_pipeline():
    section("11. FULL RETRIEVER PIPELINE (Vector Mode)")
    from vector_store.qdrant_store import (
        init_store, close_store, ensure_collection, upload_chunks,
    )
    from retrieval.retriever import retrieve

    try:
        init_store(in_memory=True)
        ensure_collection("test_retriever", vector_size=DIM)
        upload_chunks(_make_test_chunks(), collection="test_retriever")

        # Risk query
        risk_query = _unit_vector(0)
        result = retrieve(
            query_vector=risk_query,
            top_k=5,
            company="TCS",
            collection="test_retriever",
        )

        log_result("Returns dict", isinstance(result, dict))
        log_result("Has 'hits'", isinstance(result.get("hits"), list))
        log_result("Has total_hits", result.get("total_hits", 0) > 0,
                   f"total = {result.get('total_hits')}")

        hits = result["hits"]
        if hits:
            h = hits[0]
            log_result("Hit has chunk_id", "chunk_id" in h)
            log_result("Hit has score", "score" in h)
            log_result("Hit has text", len(h.get("text", "")) > 0)
            log_result("Hit has relevance tier", h.get("relevance") in
                       ("excellent", "good", "fair", "low"))
            log_result("Hit has company", h.get("company") == "TCS")

        log_result("Filters recorded",
                   result.get("filters_applied", {}).get("company") == "TCS")

        # Revenue query with section filter
        rev_query = _unit_vector(100)
        result2 = retrieve(
            query_vector=rev_query,
            top_k=3,
            section="Financial Statements",
            collection="test_retriever",
        )
        if result2["hits"]:
            log_result("Revenue query finds financial chunks",
                       result2["hits"][0].get("section") == "Financial Statements",
                       f"section = {result2['hits'][0].get('section')}")

        # Print summary
        print(f"\n  Retrieval summary:")
        for h in hits[:5]:
            print(f"    [{h['chunk_id']}] score={h['score']:.4f}  "
                  f"rel={h['relevance']:9s}  sec='{h.get('section', '')}'")

    finally:
        close_store()


# ===================================================================
# 12. PYDANTIC SCHEMA VALIDATION
# ===================================================================

def test_schema_validation():
    section("12. PYDANTIC SCHEMA VALIDATION")
    from schemas.retrieval import RetrievalHit, RetrievalResponse

    hit = RetrievalHit(
        chunk_id="test",
        score=0.85,
        text="Test text",
        company="TCS",
        relevance="excellent",
    )
    log_result("RetrievalHit validates", True)

    response = RetrievalResponse(
        query="test query",
        total_hits=1,
        hits=[hit],
        filters_applied={"company": "TCS"},
        min_score_used=0.6,
    )
    log_result("RetrievalResponse validates", True)

    j = response.model_dump_json()
    log_result("Serializes to JSON", len(j) > 50)


# ===================================================================
# 13. LIVE SEMANTIC SEARCH (requires API key)
# ===================================================================

def test_live_semantic():
    section("13. LIVE SEMANTIC SEARCH")
    if not _has_api_key():
        log_skip("Live semantic", "OPENAI_API_KEY not set — skipping")
        return

    try:
        from connectors.sec_edgar import get_annual_filings, download_filing
        from ingestion.pdf_extractor import extract_document
        from ingestion.text_cleaner import clean_document
        from ingestion.chunker import chunk_document
        from embedding.embedder import embed_chunks
        from embedding.cache import init_cache, close_cache, clear_cache
        from vector_store.qdrant_store import (
            init_store, close_store, ensure_collection, upload_chunks,
            collection_info,
        )
        from retrieval.retriever import retrieve

        import tempfile, shutil
        tmp = Path(tempfile.mkdtemp())

        try:
            init_store(in_memory=True)
            ensure_collection()
            init_cache(tmp / "cache.db")
            clear_cache()

            # Download + Extract + Clean + Chunk (AAPL 10-K)
            filings = get_annual_filings("AAPL", limit=1)
            dl = download_filing(filings[0], tmp / "filing")
            extraction = extract_document(dl["file_path"],
                                         document_id="AAPL_10K", company="AAPL", year=2025)
            cleaned = clean_document(extraction["pages"])
            chunked = chunk_document(cleaned["pages"],
                                    document_id="AAPL_10K", company="AAPL",
                                    year=2025, doc_type="Annual Report")

            # Embed first 20 chunks (cost control)
            sample = chunked["chunks"][:20]
            embedded = embed_chunks(sample, use_cache=True)
            log_result("Embedded chunks", embedded["embedded"] + embedded["cached"] > 0,
                       f"embedded={embedded['embedded']}, cached={embedded['cached']}")

            # Upload
            upload_result = upload_chunks(embedded["chunks"])
            log_result("Uploaded to Qdrant", upload_result["uploaded"] > 0,
                       f"{upload_result['uploaded']} points")

            info = collection_info()
            log_result("Collection populated",
                       info.get("points_count", 0) > 0,
                       f"points = {info.get('points_count')}")

            # Semantic query
            result = retrieve(query="What are Apple's biggest business risks?",
                            top_k=5, company="AAPL")
            log_result("Semantic query returns results",
                       result["total_hits"] > 0,
                       f"hits = {result['total_hits']}")

            if result["hits"]:
                top = result["hits"][0]
                log_result("Top hit has score",
                           top["score"] > 0,
                           f"score = {top['score']}")
                log_result("Top hit has text",
                           len(top["text"]) > 0,
                           f"preview: '{top['text'][:60]}...'")
                log_result("Top hit has relevance",
                           top["relevance"] in ("excellent", "good", "fair", "low"))

                print(f"\n  Query: 'What are Apple's biggest business risks?'")
                for h in result["hits"][:3]:
                    print(f"    score={h['score']:.4f}  rel={h['relevance']}  "
                          f"sec='{h.get('section', '')[:30]}'")
                    print(f"      '{h['text'][:80]}...'")

        finally:
            close_cache()
            close_store()
            shutil.rmtree(tmp, ignore_errors=True)

    except Exception as exc:
        log_result("Live semantic search", False, str(exc))
        import traceback
        traceback.print_exc()


# ===================================================================
# RUNNER
# ===================================================================

def main():
    print("\n" + "#" * 60)
    print("  PHASE 2.5 -- VECTOR DB & RETRIEVAL VERIFICATION")
    print("#" * 60)

    if _has_api_key():
        print(f"\n  OPENAI_API_KEY detected — full tests will run")
    else:
        print(f"\n  OPENAI_API_KEY not set — API tests will be skipped")

    start = time.time()

    test_client_lifecycle()
    test_collection_crud()
    test_upload()
    test_vector_search()
    test_metadata_filtering()
    test_thresholding()
    test_reranking()
    test_deduplication()
    test_context_assembly()
    test_citation()
    test_retriever_pipeline()
    test_schema_validation()
    test_live_semantic()

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
