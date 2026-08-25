from __future__ import annotations

import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from connectors.bse import clean_attachment_name, days_ago, download_pdf, fetch_announcements, fetch_annual_reports
from schemas.bse import CompanyFolder, FetchOptions, FetchResult, StoredFile
from services.bse_storage import company_dir, company_folder_name, relative_path, unique_file_name, write_manifest


KINDS = ("annual-reports", "quarterly-reports", "announcements")


def headline(row: dict[str, Any]) -> str:
    return re.sub(r"\s+", " ", str(row.get("HEADLINE") or row.get("NEWSSUB") or "Filing")).strip()


async def save_pdf(directory: Path, kind: str, file_name: str, row: dict[str, Any], attachment: str, log: list[str]) -> StoredFile:
    destination = directory / kind / file_name
    when = str(row.get("DissemDT") or row.get("DT_TM") or row.get("NEWS_DT") or row.get("dt_tm") or "")
    item = StoredFile(
        kind=kind,
        relativePath=relative_path(destination),
        fileName=file_name,
        headline=headline(row),
        category=str(row.get("CATEGORYNAME") or ""),
        subcategory=str(row.get("SUBCATNAME") or ""),
        newsId=str(row.get("NEWSID") or attachment),
        attachmentName=attachment,
        disseminatedAt=when,
        bytes=0,
        saved=False,
    )
    pdf = await download_pdf(attachment, row.get("OLD"))
    if pdf is None:
        log.append(f"skip {kind}: no PDF for {file_name}")
        item.skipped = "PDF not available on BSE"
        return item
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(pdf)
    log.append(f"saved {kind}/{file_name} ({len(pdf)} bytes)")
    item.bytes = len(pdf)
    item.saved = True
    return item


async def ingest_company(options: FetchOptions) -> FetchResult:
    symbol = (options.symbol or options.scripCode).upper()
    name = options.name or symbol
    directory = company_dir(options.scripCode, symbol)
    folder = company_folder_name(options.scripCode, symbol)
    log = [f"folder {folder}"]
    files: list[StoredFile] = []
    seen: set[str] = set()

    if options.annual:
        log.append("fetching annual reports")
        rows = await fetch_annual_reports(options.scripCode)
        by_year = {str(row.get("year")): row for row in rows if row.get("year")}
        for row in sorted(by_year.values(), key=lambda item: str(item.get("year")), reverse=True)[: options.annualLimit]:
            attachment = clean_attachment_name(str(row.get("file_name") or ""))
            if not attachment:
                continue
            seen.add(attachment)
            year = str(row.get("year", "unknown"))
            files.append(await save_pdf(directory, "annual-reports", f"FY-{year}_Annual-Report.pdf", row, attachment, log))
            await asyncio.sleep(0.18)

    if options.quarterly:
        log.append("fetching quarterly results")
        rows = await fetch_announcements(options.scripCode, "Result", days_ago(900))
        saved = 0
        for row in rows:
            attachment = clean_attachment_name(str(row.get("ATTACHMENTNAME") or ""))
            if saved >= options.quarterlyLimit or str(row.get("PDFFLAG")) != "1" or not attachment or attachment in seen:
                continue
            seen.add(attachment)
            when = str(row.get("DissemDT") or row.get("DT_TM") or row.get("NEWS_DT") or "")
            item = await save_pdf(directory, "quarterly-reports", unique_file_name(when, headline(row), attachment), row, attachment, log)
            files.append(item)
            saved += int(item.saved)
            await asyncio.sleep(0.15)

    if options.announcements:
        log.append("fetching corporate announcements")
        rows = await fetch_announcements(options.scripCode, from_date=days_ago(options.announcementDays))
        saved = 0
        for row in rows:
            category = str(row.get("CATEGORYNAME") or "").lower()
            title = headline(row)
            attachment = clean_attachment_name(str(row.get("ATTACHMENTNAME") or ""))
            if (
                saved >= options.announcementLimit
                or category == "result"
                or ("annual report" in title.lower() and "update" in category)
                or str(row.get("PDFFLAG")) != "1"
                or not attachment
                or attachment in seen
            ):
                continue
            seen.add(attachment)
            when = str(row.get("DissemDT") or row.get("DT_TM") or row.get("NEWS_DT") or "")
            subcategory = str(row.get("SUBCATNAME") or "General")
            item = await save_pdf(directory, "announcements", unique_file_name(when, f"{subcategory}-{title}", attachment), row, attachment, log)
            files.append(item)
            saved += int(item.saved)
            await asyncio.sleep(0.15)

    counts = {kind: sum(item.saved and item.kind == kind for item in files) for kind in KINDS}
    company = CompanyFolder(
        scripCode=options.scripCode,
        symbol=symbol,
        name=name,
        folder=folder,
        fetchedAt=datetime.now().astimezone().isoformat(),
        files=files,
        counts=counts,
        totalBytes=sum(item.bytes for item in files if item.saved),
    )
    write_manifest(directory, company)
    log.append(f"done - {counts['annual-reports']} annual, {counts['quarterly-reports']} quarterly, {counts['announcements']} announcements")
    return FetchResult(company=company, log=log)
