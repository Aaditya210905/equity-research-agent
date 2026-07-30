"""
RAG Orchestrator — Phase 2.6

The conductor of the entire RAG pipeline. Coordinates:

    User Question
        |
        v
    1. Classify Question Type
        |
        v
    2. Rewrite Query (optional)
        |
        v
    3. Retrieve Chunks (via retriever)
        |
        v
    4. Build Context (numbered citations)
        |
        v
    5. Build Prompt (template-based)
        |
        v
    6. Call LLM (GPT-4o-mini)
        |
        v
    7. Compute Confidence
        |
        v
    8. Return Grounded Answer + Citations

The orchestrator does NOT perform retrieval, embeddings, or calculations.
It only coordinates components.
"""

import logging
import re
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Question classification patterns
# ---------------------------------------------------------------------------

_QUESTION_PATTERNS = {
    "comparative": [
        r"\bcompare\b", r"\bversus\b", r"\bvs\.?\b", r"\bdifference\s+between\b",
        r"\bcompared\s+to\b", r"\bbetter\s+than\b", r"\bworse\s+than\b",
    ],
    "summarization": [
        r"\bsummar", r"\boverview\b", r"\bbrief\b", r"\bhighlight",
        r"\bkey\s+points?\b", r"\bwhat\s+does\s+the\s+report\s+say\b",
    ],
    "analytical": [
        r"\bwhy\b", r"\bhow\s+did\b", r"\bexplain\b", r"\breason",
        r"\bcause\b", r"\bimpact\b", r"\bimplication", r"\banalyz",
    ],
    # "factual" is the default
}


def classify_question(question: str) -> str:
    """Classify a question into: factual, comparative, analytical, summarization."""
    q_lower = question.lower().strip()

    for qtype, patterns in _QUESTION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, q_lower):
                return qtype

    return "factual"


# ---------------------------------------------------------------------------
# Query rewriting (rule-based financial term expansion)
# ---------------------------------------------------------------------------

_FINANCIAL_EXPANSIONS = {
    r"\bAI\b": "Artificial Intelligence AI Machine Learning Generative AI",
    r"\bESG\b": "Environmental Social Governance ESG sustainability climate",
    r"\bM&A\b": "mergers acquisitions M&A",
    r"\bCAPEX\b": "capital expenditure CAPEX capital spending",
    r"\bOPEX\b": "operating expenditure OPEX operating costs",
    r"\bR&D\b": "research development R&D innovation",
    r"\bROE\b": "return on equity ROE",
    r"\bROA\b": "return on assets ROA",
    r"\bEBITDA\b": "EBITDA earnings before interest taxes depreciation amortization",
    r"\bEPS\b": "earnings per share EPS",
    r"\bP/E\b": "price to earnings PE ratio valuation",
    r"\bNPL\b": "non-performing loans NPL bad loans asset quality",
}


def expand_query(question: str) -> str:
    """Expand financial abbreviations in the query for better retrieval."""
    expanded = question
    for pattern, replacement in _FINANCIAL_EXPANSIONS.items():
        if re.search(pattern, expanded):
            expanded = re.sub(pattern, replacement, expanded, count=1)
    return expanded


def rewrite_query_with_llm(question: str, company: str = None) -> str:
    """Use the LLM to expand a query into a comprehensive search query.

    This adds latency but improves retrieval for vague questions.
    """
    client = _get_llm_client()
    from config.settings import settings
    model = getattr(settings, "LLM_MODEL", "gpt-4o-mini")

    prompt = (
        "Expand this financial research question into a comprehensive search query. "
        "Include related terms, synonyms, and financial concepts that would help "
        "find relevant information in annual reports and SEC filings. "
        "Keep it under 80 words. Return ONLY the expanded query.\n\n"
        f"Question: {question}"
    )
    if company:
        prompt += f"\nCompany: {company}"

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=150,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning("Query rewriting failed, using original: %s", exc)
        return question


# ---------------------------------------------------------------------------
# LLM client (lazy singleton)
# ---------------------------------------------------------------------------
_client = None


def _get_llm_client():
    """Lazily initialize the OpenAI client for answer generation."""
    global _client
    if _client is not None:
        return _client

    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai package not installed. Run: pip install openai")

    from config.settings import settings
    if not settings.OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY not set. Add it to backend/config/.env"
        )

    _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


# ---------------------------------------------------------------------------
# LLM answer generation
# ---------------------------------------------------------------------------

def _generate_answer(system_prompt: str, user_prompt: str, model: str) -> str:
    """Call the LLM to generate an answer."""
    client = _get_llm_client()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,  # Low temperature for factual answers
        max_tokens=2000,
    )

    return response.choices[0].message.content.strip()


# ===========================================================================
# Public API — The Orchestrator
# ===========================================================================

def ask(
    question: str,
    company: str = None,
    year: int = None,
    doc_type: str = None,
    top_k: int = 10,
    rewrite_query: bool = False,
    collection: str = None,
) -> dict:
    """Answer a question using the full RAG pipeline.

    This is the main entry point. It coordinates:
        1. Question classification
        2. Query expansion / rewriting
        3. Retrieval
        4. Context assembly
        5. Prompt building
        6. LLM answer generation
        7. Confidence scoring

    Parameters
    ----------
    question : str
        Natural language question.
    company : str, optional
        Company ticker to scope retrieval.
    year : int, optional
        Fiscal year filter.
    doc_type : str, optional
        Document type filter.
    top_k : int
        Max chunks to retrieve.
    rewrite_query : bool
        Whether to use LLM for query expansion.
    collection : str, optional
        Qdrant collection override.

    Returns
    -------
    dict
        RAGAnswer-compatible dict::

            {
                "answer": "Revenue increased...",
                "citations": [...],
                "confidence": 0.85,
                "confidence_tier": "high",
                "question_type": "factual",
                "evidence_sufficient": True,
                ...
            }
    """
    from retrieval.retriever import retrieve
    from rag.context_builder import build_context
    from rag.prompt_builder import build_prompt
    from rag.confidence import compute_confidence
    from config.settings import settings

    model = getattr(settings, "LLM_MODEL", "gpt-4o-mini")
    start_time = time.time()

    # --- Step 1: Classify question ---
    question_type = classify_question(question)
    logger.info("Question type: %s", question_type)

    # --- Step 2: Query expansion ---
    if rewrite_query:
        query_used = rewrite_query_with_llm(question, company=company)
    else:
        query_used = expand_query(question)
    logger.info("Query: '%s'", query_used[:100])

    # --- Step 3: Retrieve ---
    retrieval_kwargs = {
        "query": query_used,
        "top_k": top_k,
        "min_score": 0.0,
    }
    if company:
        retrieval_kwargs["company"] = company
    if year is not None:
        retrieval_kwargs["year"] = year
    if doc_type:
        retrieval_kwargs["doc_type"] = doc_type
    if collection:
        retrieval_kwargs["collection"] = collection

    retrieval_result = retrieve(**retrieval_kwargs)
    hits = retrieval_result.get("hits", [])
    logger.info("Retrieved %d chunks", len(hits))

    # --- Step 4: Build context ---
    context = build_context(hits)
    context_text = context["context_text"]
    citations = context["citations"]
    chunks_used = context["chunks_used"]

    # --- Step 5: Handle insufficient evidence ---
    if not context_text.strip():
        conf = compute_confidence([], 0, top_k)
        return {
            "answer": (
                "The available documents do not contain sufficient information "
                "to answer this question. Please ensure relevant documents have "
                "been indexed for this company."
            ),
            "citations": [],
            "confidence": conf["score"],
            "confidence_tier": conf["tier"],
            "question": question,
            "question_type": question_type,
            "query_used": query_used,
            "chunks_retrieved": len(hits),
            "chunks_used": 0,
            "model": model,
            "evidence_sufficient": False,
        }

    # --- Step 6: Build prompt ---
    prompt = build_prompt(question, context_text, question_type)

    # --- Step 7: Generate answer ---
    answer_text = _generate_answer(prompt["system"], prompt["user"], model)

    # --- Step 8: Compute confidence ---
    retrieval_scores = [h.get("score", 0.0) for h in hits[:chunks_used]]
    conf = compute_confidence(retrieval_scores, chunks_used, top_k)

    elapsed = time.time() - start_time
    logger.info("Answer generated in %.1fs, confidence=%s (%.2f)",
                elapsed, conf["tier"], conf["score"])

    return {
        "answer": answer_text,
        "citations": citations,
        "confidence": conf["score"],
        "confidence_tier": conf["tier"],
        "question": question,
        "question_type": question_type,
        "query_used": query_used,
        "chunks_retrieved": len(hits),
        "chunks_used": chunks_used,
        "model": model,
        "evidence_sufficient": conf["evidence_sufficient"],
    }
