import json
import uuid
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse, Response
from pydantic import BaseModel

from models.workspace import User, WatchlistEntry, AnalystNote, ReportVersion
from api.auth import get_current_user
from dashboard.charts import generate_charts_data
from reports.report_builder import build_12_section_report
from reports.exporter import generate_pdf, generate_docx
from reports.formatter import report_to_markdown

router = APIRouter(prefix="/workspace", tags=["Workspace"])

class NoteCreate(BaseModel):
    content: str

# ---------------------------------------------------------------------------
# Watchlist Endpoints
# ---------------------------------------------------------------------------
@router.get("/watchlist")
def get_watchlist(current_user: User = Depends(get_current_user)):
    entries = WatchlistEntry.select().where(WatchlistEntry.user == current_user)
    return [{"ticker": e.ticker, "company_name": e.company_name, "added_at": e.added_at} for e in entries]

@router.post("/watchlist/{ticker}")
def add_to_watchlist(ticker: str, company_name: str = "", current_user: User = Depends(get_current_user)):
    entry, created = WatchlistEntry.get_or_create(
        user=current_user, ticker=ticker.upper(), defaults={"company_name": company_name}
    )
    return {"message": "Added to watchlist", "ticker": ticker}

@router.delete("/watchlist/{ticker}")
def remove_from_watchlist(ticker: str, current_user: User = Depends(get_current_user)):
    deleted = WatchlistEntry.delete().where(
        (WatchlistEntry.user == current_user) & (WatchlistEntry.ticker == ticker.upper())
    ).execute()
    return {"message": "Removed from watchlist", "deleted": bool(deleted)}

# ---------------------------------------------------------------------------
# Analyst Notes Endpoints
# ---------------------------------------------------------------------------
@router.get("/notes/{ticker}")
def get_notes(ticker: str, current_user: User = Depends(get_current_user)):
    notes = AnalystNote.select().where((AnalystNote.user == current_user) & (AnalystNote.ticker == ticker.upper()))
    return [{"id": n.id, "content": n.content, "created_at": n.created_at, "updated_at": n.updated_at} for n in notes]

@router.post("/notes/{ticker}")
def save_note(ticker: str, note: NoteCreate, current_user: User = Depends(get_current_user)):
    new_note = AnalystNote.create(user=current_user, ticker=ticker.upper(), content=note.content)
    return {"message": "Note saved", "id": new_note.id}

@router.delete("/notes/{note_id}")
def delete_note(note_id: int, current_user: User = Depends(get_current_user)):
    note = AnalystNote.get_or_none(AnalystNote.id == note_id, AnalystNote.user == current_user)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    note.delete_instance()
    return {"message": "Note deleted"}

# ---------------------------------------------------------------------------
# Report Endpoints
# ---------------------------------------------------------------------------
@router.post("/report/{ticker}/format_and_save")
def format_and_save_report(ticker: str, raw_state: dict, current_user: User = Depends(get_current_user)):
    """Takes the raw LangGraph state output, formats it into 12 sections, and saves it."""
    ai_report = raw_state.get("report", {})
    if not isinstance(ai_report, dict) and hasattr(ai_report, 'model_dump'):
        ai_report = ai_report.model_dump()
        
    financial_data = raw_state.get("financial_statements", {})
    market_data = raw_state.get("market_snapshot", {})
    news_data = raw_state.get("news", [])
    
    charts_data = generate_charts_data(financial_data)
    
    formatted_report = build_12_section_report(
        ai_report=ai_report,
        financial_data=financial_data,
        market_data=market_data,
        charts_data=charts_data,
        news_data=news_data
    )
    
    report_id = str(uuid.uuid4())
    version_count = ReportVersion.select().where(
        (ReportVersion.user == current_user) & (ReportVersion.ticker == ticker.upper())
    ).count()
    
    new_version = version_count + 1
    
    ReportVersion.create(
        report_id=report_id,
        user=current_user,
        ticker=ticker.upper(),
        company=formatted_report.get("metadata", {}).get("company", ticker.upper()),
        model=formatted_report.get("metadata", {}).get("model", "unknown"),
        version=new_version,
        report_json=json.dumps(formatted_report)
    )
    return {"message": "Report formatted and saved", "report_id": report_id, "version": new_version, "report": formatted_report}

@router.post("/report/{ticker}/save")
def save_report(ticker: str, report_data: dict, current_user: User = Depends(get_current_user)):
    report_id = str(uuid.uuid4())
    version_count = ReportVersion.select().where(
        (ReportVersion.user == current_user) & (ReportVersion.ticker == ticker.upper())
    ).count()
    
    new_version = version_count + 1
    
    ReportVersion.create(
        report_id=report_id,
        user=current_user,
        ticker=ticker.upper(),
        company=report_data.get("metadata", {}).get("company", ticker.upper()),
        model=report_data.get("metadata", {}).get("model", "unknown"),
        version=new_version,
        report_json=json.dumps(report_data)
    )
    return {"message": "Report saved", "report_id": report_id, "version": new_version}

@router.get("/report/{ticker}/latest")
def get_latest_report(ticker: str, current_user: User = Depends(get_current_user)):
    report = ReportVersion.select().where(
        (ReportVersion.user == current_user) & (ReportVersion.ticker == ticker.upper())
    ).order_by(ReportVersion.version.desc()).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="No reports found for this ticker")
    
    return json.loads(report.report_json)

@router.get("/report/{ticker}/versions")
def get_report_versions(ticker: str, current_user: User = Depends(get_current_user)):
    reports = ReportVersion.select().where(
        (ReportVersion.user == current_user) & (ReportVersion.ticker == ticker.upper())
    ).order_by(ReportVersion.version.desc())
    
    return [{"version": r.version, "created_at": r.created_at, "report_id": r.report_id} for r in reports]

# ---------------------------------------------------------------------------
# Export Endpoints
# ---------------------------------------------------------------------------
@router.get("/report/{ticker}/export/json")
def export_report_json(ticker: str, current_user: User = Depends(get_current_user)):
    report = ReportVersion.select().where(
        (ReportVersion.user == current_user) & (ReportVersion.ticker == ticker.upper())
    ).order_by(ReportVersion.version.desc()).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="No reports found")
    return Response(content=report.report_json, media_type="application/json")

@router.get("/report/{ticker}/export/markdown")
def export_report_markdown(ticker: str, current_user: User = Depends(get_current_user)):
    report = ReportVersion.select().where(
        (ReportVersion.user == current_user) & (ReportVersion.ticker == ticker.upper())
    ).order_by(ReportVersion.version.desc()).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="No reports found")
        
    report_data = json.loads(report.report_json)
    md_content = report_to_markdown(report_data)
    return Response(content=md_content, media_type="text/markdown")

@router.get("/report/{ticker}/export/pdf")
def export_report_pdf(ticker: str, current_user: User = Depends(get_current_user)):
    report = ReportVersion.select().where(
        (ReportVersion.user == current_user) & (ReportVersion.ticker == ticker.upper())
    ).order_by(ReportVersion.version.desc()).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="No reports found")
        
    report_data = json.loads(report.report_json)
    pdf_io = generate_pdf(report_data)
    return StreamingResponse(
        pdf_io, 
        media_type="application/pdf", 
        headers={"Content-Disposition": f"attachment; filename=report_{ticker}.pdf"}
    )

@router.get("/report/{ticker}/export/docx")
def export_report_docx(ticker: str, current_user: User = Depends(get_current_user)):
    report = ReportVersion.select().where(
        (ReportVersion.user == current_user) & (ReportVersion.ticker == ticker.upper())
    ).order_by(ReportVersion.version.desc()).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="No reports found")
        
    report_data = json.loads(report.report_json)
    docx_io = generate_docx(report_data)
    return StreamingResponse(
        docx_io, 
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", 
        headers={"Content-Disposition": f"attachment; filename=report_{ticker}.docx"}
    )
