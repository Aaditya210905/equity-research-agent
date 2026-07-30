"""
AI Equity Research Analyst — Phase 4

A single AI analyst that produces professional equity research reports
using pre-computed evidence. The analyst:

    - DOES NOT download reports
    - DOES NOT query Yahoo Finance
    - DOES NOT compute financial ratios
    - DOES NOT search PDFs

It ONLY:

    - Analyzes structured evidence
    - Identifies trends
    - Connects qualitative and quantitative findings
    - Explains risks
    - Produces a professional report

Architecture:
    Evidence Payload
        |
        v
    Evidence Matrix (categorize)
        |
        v
    For each section:
        Load prompt template
        Format section-specific evidence
        Call LLM
        Compute section confidence
        |
        v
    Assembled Research Report
"""

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# ---------------------------------------------------------------------------
# LLM client (lazy singleton — shared with orchestrator)
# ---------------------------------------------------------------------------
_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai package not installed. Run: pip install openai")
    from config.settings import settings
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set.")
    _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------

def _load_prompt(filename: str) -> str:
    path = _PROMPTS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    logger.warning("Prompt '%s' not found", filename)
    return ""


# ---------------------------------------------------------------------------
# Evidence formatting helpers
# ---------------------------------------------------------------------------

def format_metrics(metrics: dict, category: str = None) -> str:
    """Format MetricResult dicts into readable text for the LLM."""
    if not metrics:
        return "No financial metrics available."

    lines = []
    targets = {category: metrics[category]} if category and category in metrics else {
        k: v for k, v in metrics.items() if isinstance(v, dict) and k != "summary"
    }

    for cat_name, cat_metrics in targets.items():
        if not isinstance(cat_metrics, dict):
            continue
        lines.append(f"\n  {cat_name.upper().replace('_', ' ')}:")
        for name, m in cat_metrics.items():
            if not isinstance(m, dict) or "value" not in m:
                continue
            val = m.get("value")
            unit = m.get("unit", "")
            status = m.get("status", "")
            if status == "computed" and val is not None:
                lines.append(f"    {name}: {val}{unit}")
            else:
                lines.append(f"    {name}: N/A ({status})")

    return "\n".join(lines) if lines else "No metrics computed."


def format_evidence(chunks: list[dict]) -> str:
    """Format retrieved evidence chunks into numbered references."""
    if not chunks:
        return "No documentary evidence available."

    lines = []
    for i, chunk in enumerate(chunks, start=1):
        source_parts = []
        if chunk.get("section"):
            source_parts.append(chunk["section"])
        if chunk.get("page_start"):
            if chunk.get("page_end") and chunk["page_end"] != chunk["page_start"]:
                source_parts.append(f"Pages {chunk['page_start']}–{chunk['page_end']}")
            else:
                source_parts.append(f"Page {chunk['page_start']}")
        source = ", ".join(source_parts) if source_parts else "Unknown source"
        score = chunk.get("score", 0)

        text = chunk.get("text", "").strip()[:500]
        lines.append(f"  [{i}] ({source}, relevance: {score:.2f})")
        lines.append(f"      {text}")
        lines.append("")

    return "\n".join(lines)


def format_news(news: list[dict]) -> str:
    """Format news items for the prompt."""
    if not news:
        return "No recent news available."

    lines = []
    for item in news[:10]:
        title = item.get("title", "Untitled")
        date = item.get("date", "")
        summary = item.get("summary", "")[:200]
        lines.append(f"  - {title} ({date})")
        if summary:
            lines.append(f"    {summary}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Evidence matrix — categorize chunks by topic
# ---------------------------------------------------------------------------

_SECTION_KEYWORDS = {
    "business_overview": ["business", "revenue", "segment", "product", "service",
                          "customer", "market", "industry", "overview", "operations"],
    "risk_analysis": ["risk", "threat", "uncertainty", "litigation", "regulatory",
                      "cybersecurity", "compliance", "adverse", "challenge"],
    "growth_opportunities": ["growth", "opportunity", "expansion", "innovation",
                             "strategy", "invest", "acquisition", "digital",
                             "transform", "AI", "artificial intelligence", "new market"],
    "financial_analysis": ["revenue", "income", "margin", "profit", "cash flow",
                           "earnings", "financial", "balance sheet", "debt"],
}


def categorize_evidence(chunks: list[dict]) -> dict:
    """Sort retrieved chunks into section-relevant buckets.

    Each chunk can appear in multiple categories.
    """
    buckets = {k: [] for k in _SECTION_KEYWORDS}
    buckets["other"] = []

    for chunk in chunks:
        text_lower = (chunk.get("text", "") + " " + (chunk.get("section") or "")).lower()
        placed = False
        for category, keywords in _SECTION_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                buckets[category].append(chunk)
                placed = True
        if not placed:
            buckets["other"].append(chunk)

    return buckets


# ---------------------------------------------------------------------------
# Section confidence
# ---------------------------------------------------------------------------

def _section_confidence(
    has_metrics: bool,
    evidence_count: int,
    has_news: bool = False,
) -> float:
    """Compute confidence for a report section based on evidence availability."""
    score = 0.0
    if has_metrics:
        score += 0.5
    if evidence_count >= 3:
        score += 0.35
    elif evidence_count >= 1:
        score += 0.20
    if has_news:
        score += 0.15
    return min(1.0, round(score, 2))


# ---------------------------------------------------------------------------
# Section generation
# ---------------------------------------------------------------------------

def _generate_section(
    section_name: str,
    prompt_file: str,
    template_vars: dict,
    model: str,
) -> dict:
    """Generate one report section via the LLM.

    Returns:
        {"title": "...", "content": "...", "confidence": 0.85, "evidence_count": N}
    """
    system_prompt = _load_prompt("report_system.txt")
    section_template = _load_prompt(prompt_file)

    if not section_template:
        return {
            "title": section_name,
            "content": f"Section template '{prompt_file}' not found.",
            "confidence": 0.0,
            "evidence_count": 0,
        }

    # Fill template placeholders — skip missing keys gracefully
    try:
        user_prompt = section_template.format(**template_vars)
    except KeyError as e:
        logger.warning("Missing template var %s for %s", e, section_name)
        user_prompt = section_template
        for k, v in template_vars.items():
            user_prompt = user_prompt.replace(f"{{{k}}}", str(v))

    client = _get_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=2500,
    )

    content = response.choices[0].message.content.strip()

    return {
        "title": section_name,
        "content": content,
    }


# ===========================================================================
# Public API — generate_report
# ===========================================================================

def generate_report(evidence: dict, model: str = None) -> dict:
    """Generate a complete equity research report.

    The analyst receives a structured evidence payload and produces
    a professional research report with citations and confidence scores.

    Parameters
    ----------
    evidence : dict
        {
            "company": {"name": str, "ticker": str, "sector": str, ...},
            "market_data": dict,              # from Phase 1.2
            "financial_metrics": dict,         # from engine.compute_all()
            "financial_health": dict,          # from engine.financial_health_score()
            "growth_metrics": dict,            # from engine.compute_growth()
            "retrieved_evidence": list[dict],  # from retriever
            "news": list[dict],
        }
    model : str, optional
        Override the LLM model.

    Returns
    -------
    dict (ResearchReport-compatible)
    """
    from config.settings import settings

    if model is None:
        model = getattr(settings, "LLM_MODEL", "gpt-4o-mini")

    start_time = time.time()

    # --- Unpack evidence ---
    company = evidence.get("company", {})
    company_name = company.get("name", "Unknown")
    ticker = company.get("ticker", "???")
    sector = company.get("sector", "Unknown")

    metrics = evidence.get("financial_metrics", {})
    health = evidence.get("financial_health", {})
    growth = evidence.get("growth_metrics", {})
    market = evidence.get("market_data", {})
    retrieved = evidence.get("retrieved_evidence", [])
    news = evidence.get("news", [])

    health_score = health.get("overall", "N/A")

    # --- Categorize evidence ---
    evidence_matrix = categorize_evidence(retrieved)

    # --- Pre-format shared data ---
    all_metrics_text = format_metrics(metrics)
    growth_text = format_metrics({"growth": growth}) if growth else "No growth data available."
    news_text = format_news(news)

    market_text = "\n".join(
        f"  {k}: {v}" for k, v in market.items() if v is not None
    ) if market else "No market data available."

    company_profile = "\n".join(
        f"  {k}: {v}" for k, v in company.items() if v is not None
    ) if company else "No company profile available."

    # --- Generate each section ---
    sections_config = [
        ("executive_summary", "executive_summary.txt", {
            "company_name": company_name, "ticker": ticker, "sector": sector,
            "health_score": health_score,
            "financial_summary": format_metrics(metrics, "profitability") + "\n" + format_metrics(metrics, "cash_flow"),
            "evidence_summary": format_evidence(retrieved[:5]),
            "news_summary": news_text,
        }),
        ("business_overview", "business_overview.txt", {
            "company_name": company_name, "ticker": ticker, "sector": sector,
            "company_profile": company_profile,
            "evidence": format_evidence(evidence_matrix.get("business_overview", []) or retrieved[:5]),
        }),
        ("financial_analysis", "financial_analysis.txt", {
            "company_name": company_name, "ticker": ticker,
            "metrics": all_metrics_text,
            "growth_metrics": growth_text,
            "evidence": format_evidence(evidence_matrix.get("financial_analysis", [])),
        }),
        ("risk_analysis", "risk_analysis.txt", {
            "company_name": company_name, "ticker": ticker, "sector": sector,
            "solvency_metrics": format_metrics(metrics, "solvency"),
            "evidence": format_evidence(evidence_matrix.get("risk_analysis", []) or retrieved[:5]),
            "news": news_text,
        }),
        ("growth_opportunities", "growth_analysis.txt", {
            "company_name": company_name, "ticker": ticker, "sector": sector,
            "growth_metrics": growth_text,
            "evidence": format_evidence(evidence_matrix.get("growth_opportunities", []) or retrieved[:3]),
            "news": news_text,
        }),
        ("valuation", "valuation_commentary.txt", {
            "company_name": company_name, "ticker": ticker,
            "valuation_metrics": format_metrics(metrics, "valuation"),
            "market_data": market_text,
            "profitability_metrics": format_metrics(metrics, "profitability"),
        }),
        ("investment_thesis", "investment_thesis.txt", {
            "company_name": company_name, "ticker": ticker, "sector": sector,
            "health_score": health_score,
            "metrics_summary": format_metrics(metrics, "profitability"),
            "risk_summary": format_evidence(evidence_matrix.get("risk_analysis", [])[:3]),
            "growth_summary": format_evidence(evidence_matrix.get("growth_opportunities", [])[:3]),
            "valuation_summary": format_metrics(metrics, "valuation"),
        }),
    ]

    report = {
        "company": company_name,
        "ticker": ticker,
        "sector": sector,
        "citations": [],
        "model": model,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "financial_health_score": health.get("overall"),
        "sections_generated": 0,
        "sections_failed": 0,
    }

    all_confidences = []

    for section_key, prompt_file, template_vars in sections_config:
        try:
            logger.info("Generating section: %s", section_key)
            result = _generate_section(section_key, prompt_file, template_vars, model)

            # Compute confidence
            section_evidence = evidence_matrix.get(section_key, [])
            conf = _section_confidence(
                has_metrics=bool(metrics),
                evidence_count=len(section_evidence) if section_evidence else len(retrieved),
                has_news=bool(news),
            )

            report[section_key] = {
                "title": section_key.replace("_", " ").title(),
                "content": result["content"],
                "confidence": conf,
                "evidence_count": len(section_evidence) if section_evidence else len(retrieved),
            }
            all_confidences.append(conf)
            report["sections_generated"] += 1

        except Exception as exc:
            logger.error("Failed to generate section '%s': %s", section_key, exc)
            report[section_key] = {
                "title": section_key.replace("_", " ").title(),
                "content": f"Section generation failed: {str(exc)}",
                "confidence": 0.0,
                "evidence_count": 0,
            }
            report["sections_failed"] += 1

    # --- Overall confidence ---
    report["overall_confidence"] = (
        round(sum(all_confidences) / len(all_confidences), 2)
        if all_confidences else 0.0
    )

    # --- Collect all citations from evidence ---
    for i, chunk in enumerate(retrieved, start=1):
        source_parts = []
        if chunk.get("company"):
            source_parts.append(chunk["company"])
        if chunk.get("doc_type"):
            source_parts.append(chunk["doc_type"])
        if chunk.get("year"):
            source_parts.append(str(chunk["year"]))
        if chunk.get("section"):
            source_parts.append(chunk["section"])
        report["citations"].append({
            "ref": i,
            "source": ", ".join(source_parts) if source_parts else "Unknown",
            "chunk_id": chunk.get("chunk_id", ""),
        })

    elapsed = time.time() - start_time
    logger.info("Report generated in %.1fs — %d sections, confidence %.2f",
                elapsed, report["sections_generated"], report["overall_confidence"])

    return report
