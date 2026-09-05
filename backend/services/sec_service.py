import asyncio
from datetime import datetime
from pathlib import Path

from connectors.sec_edgar import resolve_cik, get_annual_filings, get_quarterly_filings, download_filing, SECEdgarError
from schemas.sec import FetchOptions, FetchResult
from schemas.bse import CompanyFolder, StoredFile
from services.bse_storage import company_dir, company_folder_name, relative_path, write_manifest

def search_companies(query: str) -> list[dict]:
    try:
        # SEC only supports exact ticker lookup
        company = resolve_cik(query)
        return [{"cik": company["cik"], "name": company["name"], "ticker": company["ticker"]}]
    except SECEdgarError:
        return []

def ingest_company(options: FetchOptions) -> FetchResult:
    ticker = options.ticker
    company_info = resolve_cik(ticker)
    cik = company_info["cik"]
    name = company_info["name"]
    
    # We reuse bse_storage's conventions. 
    # We pass 'cik' as the scripCode so it works with the CompanyFolder schema seamlessly!
    directory = company_dir(cik, ticker)
    folder = company_folder_name(cik, ticker)
    log = [f"folder {folder}"]
    files: list[StoredFile] = []
    
    def _process_filing(filing: dict, kind: str):
        result = download_filing(filing, directory / kind)
        if result["success"]:
            log.append(f"saved {kind}/{filing['primary_doc']} ({result['file_size']} bytes)")
            
            item = StoredFile(
                kind=kind,
                relativePath=relative_path(Path(result["file_path"])),
                fileName=filing["primary_doc"],
                headline=filing["primary_doc_description"] or filing["form"],
                category=filing["form"],
                subcategory="SEC Filing",
                newsId=filing["accession"],
                attachmentName=filing["primary_doc"],
                disseminatedAt=filing["filing_date"],
                bytes=result["file_size"],
                saved=True,
            )
            files.append(item)
        else:
            log.append(f"error downloading {kind}/{filing['primary_doc']}: {result.get('error')}")

    if options.annual:
        log.append("fetching annual reports")
        filings = get_annual_filings(ticker, limit=options.annualLimit)
        for f in filings:
            _process_filing(f, "annual_reports")
            
    if options.quarterly:
        log.append("fetching quarterly reports")
        filings = get_quarterly_filings(ticker, limit=options.quarterlyLimit)
        for f in filings:
            _process_filing(f, "quarterly_reports")
            
    counts = {
        "annual_reports": sum(1 for item in files if item.kind == "annual_reports"),
        "quarterly_reports": sum(1 for item in files if item.kind == "quarterly_reports"),
        "announcements": 0
    }
    
    company = CompanyFolder(
        scripCode=cik,
        symbol=ticker,
        name=name,
        folder=folder,
        fetchedAt=datetime.now().astimezone().isoformat(),
        files=files,
        counts=counts,
        totalBytes=sum(item.bytes for item in files if item.saved),
    )
    write_manifest(directory, company)
    log.append(f"done - {counts['annual_reports']} annual, {counts['quarterly_reports']} quarterly")
    
    return FetchResult(company=company.model_dump(), log=log)
