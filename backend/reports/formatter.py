import markdown
from typing import Dict, Any

def report_to_markdown(report_data: Dict[str, Any]) -> str:
    """Converts a 12-section report dictionary to a Markdown string."""
    metadata = report_data.get("metadata", {})
    sections = report_data.get("sections", [])
    
    company = metadata.get("company", "Company")
    ticker = metadata.get("ticker", "TICKER")
    generated_at = metadata.get("generated_at", "")
    
    md = f"# Equity Research Report: {company} ({ticker})\n\n"
    md += f"**Generated At:** {generated_at}\n\n"
    md += "---\n\n"
    
    for section in sections:
        title = section.get("title", "")
        content = section.get("content", "")
        
        md += f"## {title}\n\n"
        if content:
            md += f"{content}\n\n"
            
        # Optional data (citations, lists)
        data = section.get("data", {})
        if title == "Sources" and isinstance(data, list):
            for i, citation in enumerate(data):
                md += f"{i+1}. **{citation.get('source', 'Unknown')}**: {citation.get('text_preview', '')}\n"
            md += "\n"
            
    return md

def report_to_html(report_data: Dict[str, Any]) -> str:
    """Converts a 12-section report dictionary to an HTML string."""
    md_text = report_to_markdown(report_data)
    # Convert markdown to HTML
    html_content = markdown.markdown(md_text, extensions=['tables'])
    
    # Wrap in basic HTML structure
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{report_data.get("metadata", {}).get("company", "Report")}</title>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 40px; max-width: 900px; margin: 0 auto; }}
            h1 {{ color: #2c3e50; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
            h2 {{ color: #34495e; margin-top: 30px; }}
            p {{ color: #333; }}
        </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """
    return html
