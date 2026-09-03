import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

def build_12_section_report(
    ai_report: dict,
    financial_data: dict,
    market_data: dict,
    charts_data: dict,
    news_data: list,
) -> Dict[str, Any]:
    """Assembles the Phase 5 output into the full 12-section format.

    Sections:
    1. Executive Summary
    2. Investment Thesis
    3. Company Overview
    4. Financial Performance
    5. Financial Ratio Dashboard
    6. Growth Analysis
    7. Competitive Analysis
    8. Risk Analysis
    9. Recent News Impact
    10. Valuation Commentary
    11. Sources
    12. Appendix
    """
    try:
        executive_summary = ai_report.get("executive_summary", {})
        investment_thesis = ai_report.get("investment_thesis", {})
        business_overview = ai_report.get("business_overview", {})
        financial_analysis = ai_report.get("financial_analysis", {})
        growth_opportunities = ai_report.get("growth_opportunities", {})
        risk_analysis = ai_report.get("risk_analysis", {})
        valuation = ai_report.get("valuation", {})
        citations = ai_report.get("citations", [])

        report_data = {
            "metadata": {
                "company": ai_report.get("company", ""),
                "ticker": ai_report.get("ticker", ""),
                "sector": ai_report.get("sector", ""),
                "model": ai_report.get("model", ""),
                "generated_at": ai_report.get("generated_at", ""),
                "overall_confidence": ai_report.get("overall_confidence", 0),
            },
            "sections": [
                {
                    "id": 1,
                    "title": "Executive Summary",
                    "content": executive_summary.get("content", ""),
                    "confidence": executive_summary.get("confidence", 0),
                },
                {
                    "id": 2,
                    "title": "Investment Thesis",
                    "content": investment_thesis.get("content", ""),
                    "confidence": investment_thesis.get("confidence", 0),
                },
                {
                    "id": 3,
                    "title": "Company Overview",
                    "content": business_overview.get("content", ""),
                    "confidence": business_overview.get("confidence", 0),
                },
                {
                    "id": 4,
                    "title": "Financial Performance",
                    "content": financial_analysis.get("content", ""),
                    "confidence": financial_analysis.get("confidence", 0),
                    "data": charts_data.get("revenue_trend", {}), # Attached chart data
                },
                {
                    "id": 5,
                    "title": "Financial Ratio Dashboard",
                    "content": "Key performance indicators and financial health metrics.",
                    "data": {
                        "health_score": ai_report.get("financial_health_score", 0),
                        "metrics": financial_data.get("metrics", {}),
                        "market": market_data,
                    },
                },
                {
                    "id": 6,
                    "title": "Growth Analysis",
                    "content": growth_opportunities.get("content", ""),
                    "confidence": growth_opportunities.get("confidence", 0),
                },
                {
                    "id": 7,
                    "title": "Competitive Analysis",
                    "content": "Peer comparison and competitive positioning in the sector.",
                    "data": {}, # To be filled by comparison module if needed
                },
                {
                    "id": 8,
                    "title": "Risk Analysis",
                    "content": risk_analysis.get("content", ""),
                    "confidence": risk_analysis.get("confidence", 0),
                },
                {
                    "id": 9,
                    "title": "Recent News Impact",
                    "content": "Analysis of recent events and news items.",
                    "data": news_data,
                },
                {
                    "id": 10,
                    "title": "Valuation Commentary",
                    "content": valuation.get("content", ""),
                    "confidence": valuation.get("confidence", 0),
                },
                {
                    "id": 11,
                    "title": "Sources",
                    "content": "References and citations used to compile this report.",
                    "data": citations,
                },
                {
                    "id": 12,
                    "title": "Appendix",
                    "content": "Raw financial data and methodology.",
                    "data": {
                        "raw_financials": financial_data.get("raw", {}),
                    },
                },
            ]
        }
        return report_data
    except Exception as exc:
        logger.error(f"Failed to build 12-section report: {exc}")
        return {}
