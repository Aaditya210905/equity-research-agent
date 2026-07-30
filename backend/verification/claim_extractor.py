"""
Claim Extractor — Phase 5

Breaks a generated report into individual verifiable claims.

A "claim" is a sentence that makes a factual assertion:
    - Contains a number or percentage
    - References a specific metric
    - States something about the company

Pipeline:
    Report Text
        |
        v
    Split into sections
        |
        v
    Split into sentences
        |
        v
    Filter for factual claims
        |
        v
    List of Claims
"""

import re
import logging

logger = logging.getLogger(__name__)

# Patterns that indicate a factual claim
_NUMBER_PATTERN = re.compile(r"\d+[\.\,]?\d*\s*[%$xX]?")
_METRIC_KEYWORDS = {
    "revenue", "margin", "profit", "income", "growth", "ratio", "yield",
    "earnings", "ebitda", "debt", "equity", "assets", "cash", "dividend",
    "roe", "roa", "roic", "p/e", "pe", "ev", "market cap", "turnover",
    "billion", "million", "trillion", "crore", "lakh",
}

# Sentence splitting (handles abbreviations like "Inc." and "e.g.")
_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')


def extract_claims(report: dict) -> list[dict]:
    """Extract verifiable claims from a research report.

    Parameters
    ----------
    report : dict
        Research report from the equity analyst.

    Returns
    -------
    list[dict]
        [
            {
                "text": "Revenue increased by 14%.",
                "section": "financial_analysis",
                "has_number": True,
                "has_citation": True,
                "verification": "pending",
            },
            ...
        ]
    """
    claims = []

    section_keys = [
        "executive_summary", "business_overview", "financial_analysis",
        "risk_analysis", "growth_opportunities", "valuation", "investment_thesis",
    ]

    for section_key in section_keys:
        section_data = report.get(section_key, {})
        content = section_data.get("content", "") if isinstance(section_data, dict) else ""
        if not content:
            continue

        sentences = _split_sentences(content)

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 15:
                continue

            has_number = bool(_NUMBER_PATTERN.search(sentence))
            has_metric = any(kw in sentence.lower() for kw in _METRIC_KEYWORDS)
            has_citation = bool(re.search(r'\[\d+\]', sentence))

            # A claim is a sentence with a number OR a financial metric reference
            if has_number or has_metric:
                claims.append({
                    "text": sentence,
                    "section": section_key,
                    "has_number": has_number,
                    "has_citation": has_citation,
                    "verification": "pending",
                    "supporting_evidence": "",
                })

    logger.info("Extracted %d claims from report", len(claims))
    return claims


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences, handling common abbreviations."""
    # Remove markdown formatting
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)

    # Split on sentence boundaries
    sentences = _SENTENCE_SPLIT.split(text)

    # Further split on newlines that start new sentences
    result = []
    for s in sentences:
        parts = re.split(r'\n+', s)
        result.extend(parts)

    return [s.strip() for s in result if s.strip()]
