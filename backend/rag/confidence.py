"""
Confidence Engine — Phase 2.6

Computes a confidence score for a RAG answer using multiple signals:

    1. Retrieval confidence  — average similarity score of used chunks
    2. Coverage confidence   — did we find enough relevant chunks?
    3. Evidence sufficiency   — are the top scores high enough?

Confidence Tiers:
    >= 0.80   high          — strong evidence, trustworthy answer
    >= 0.60   medium        — reasonable evidence, some uncertainty
    >= 0.40   low           — weak evidence, treat with caution
    <  0.40   insufficient  — not enough evidence to answer
"""

import logging

logger = logging.getLogger(__name__)

# Thresholds
TIER_HIGH = 0.80
TIER_MEDIUM = 0.60
TIER_LOW = 0.40

# Weights for combining signals
W_RETRIEVAL = 0.50
W_COVERAGE = 0.30
W_SUFFICIENCY = 0.20


def _retrieval_confidence(scores: list[float]) -> float:
    """Average retrieval similarity score."""
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _coverage_confidence(chunks_used: int, chunks_requested: int) -> float:
    """What fraction of requested chunks were actually usable?"""
    if chunks_requested <= 0:
        return 0.0
    ratio = chunks_used / chunks_requested
    return min(1.0, ratio)


def _evidence_sufficiency(scores: list[float], threshold: float = 0.5) -> float:
    """Are the top retrieval scores high enough to trust?

    Returns 1.0 if the best score exceeds threshold,
    scaled down if scores are weak.
    """
    if not scores:
        return 0.0
    best = max(scores)
    if best >= threshold:
        return min(1.0, best)
    return best / threshold * 0.5  # Penalize weak evidence


def compute_confidence(
    retrieval_scores: list[float],
    chunks_used: int,
    chunks_requested: int = 10,
) -> dict:
    """Compute overall confidence for a RAG answer.

    Parameters
    ----------
    retrieval_scores : list[float]
        Similarity scores of the chunks used in the context.
    chunks_used : int
        Number of chunks actually included in the context.
    chunks_requested : int
        Number of chunks originally requested from retriever.

    Returns
    -------
    dict
        {
            "score": 0.85,
            "tier": "high",
            "retrieval_confidence": 0.90,
            "coverage_confidence": 0.80,
            "evidence_sufficient": True,
            "details": {
                "avg_score": 0.90,
                "best_score": 0.95,
                "chunks_used": 5,
                "chunks_requested": 10,
            }
        }
    """
    rc = _retrieval_confidence(retrieval_scores)
    cc = _coverage_confidence(chunks_used, chunks_requested)
    es = _evidence_sufficiency(retrieval_scores)

    # Weighted combination
    score = (W_RETRIEVAL * rc) + (W_COVERAGE * cc) + (W_SUFFICIENCY * es)
    score = round(min(1.0, max(0.0, score)), 2)

    # Tier classification
    if score >= TIER_HIGH:
        tier = "high"
    elif score >= TIER_MEDIUM:
        tier = "medium"
    elif score >= TIER_LOW:
        tier = "low"
    else:
        tier = "insufficient"

    evidence_sufficient = score >= TIER_LOW

    return {
        "score": score,
        "tier": tier,
        "retrieval_confidence": round(rc, 3),
        "coverage_confidence": round(cc, 3),
        "evidence_sufficient": evidence_sufficient,
        "details": {
            "avg_score": round(rc, 3),
            "best_score": round(max(retrieval_scores) if retrieval_scores else 0.0, 3),
            "chunks_used": chunks_used,
            "chunks_requested": chunks_requested,
        },
    }
