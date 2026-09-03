import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

def generate_charts_data(financial_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generates chart-ready structures from raw financial_engine output.
    
    Expected output structure for Recharts:
    {
      "revenue_trend": {"labels": ["2021", ...], "revenue": [...]},
      "margin_trend":  {"labels": ["2021", ...], "net_margin": [...], "op_margin": [...]},
      "cash_flow_trend": {"labels": ["2021", ...], "operating_cf": [...], "free_cf": [...]},
      "roe_trend": {"labels": ["2021", ...], "roe": [...]}
    }
    """
    try:
        if not financial_data or "raw" not in financial_data:
            return {}

        raw = financial_data["raw"]
        
        # Sort years if they are available
        years = sorted(list(raw.keys()))
        labels = [str(y) for y in years]
        
        revenue = []
        net_margin = []
        op_margin = []
        operating_cf = []
        free_cf = []
        roe = []
        
        for y in years:
            y_data = raw[y]
            
            # Revenue
            revenue.append(y_data.get("income_statement", {}).get("total_revenue", 0))
            
            # Margins
            inc = y_data.get("income_statement", {})
            rev = inc.get("total_revenue", 1) or 1 # avoid div by zero
            net_inc = inc.get("net_income", 0)
            op_inc = inc.get("operating_income", 0)
            
            net_margin.append(round((net_inc / rev) * 100, 2))
            op_margin.append(round((op_inc / rev) * 100, 2))
            
            # Cash Flow
            cf = y_data.get("cash_flow", {})
            ocf = cf.get("operating_cash_flow", 0)
            capex = cf.get("capital_expenditure", 0)
            fcf = ocf - abs(capex) # capex might be negative or positive depending on statement
            
            operating_cf.append(ocf)
            free_cf.append(fcf)
            
            # ROE
            bs = y_data.get("balance_sheet", {})
            equity = bs.get("total_equity", 1) or 1
            roe.append(round((net_inc / equity) * 100, 2))
            
        return {
            "revenue_trend": {
                "labels": labels,
                "revenue": revenue
            },
            "margin_trend": {
                "labels": labels,
                "net_margin": net_margin,
                "op_margin": op_margin
            },
            "cash_flow_trend": {
                "labels": labels,
                "operating_cash_flow": operating_cf,
                "free_cash_flow": free_cf
            },
            "roe_trend": {
                "labels": labels,
                "roe": roe
            }
        }
    except Exception as exc:
        logger.error(f"Failed to generate charts data: {exc}")
        return {}
