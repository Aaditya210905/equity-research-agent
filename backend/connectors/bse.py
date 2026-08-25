from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import quote

import httpx

from schemas.bse import CompanyHit


API = "https://api.bseindia.com/BseIndiaAPI/api"
SITE = "https://www.bseindia.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/134.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": SITE,
    "Referer": f"{SITE}/",
    "Connection": "keep-alive",
}


def days_ago(days: int) -> date:
    return date.today() - timedelta(days=days)


def yyyymmdd(value: date) -> str:
    return value.strftime("%Y%m%d")


async def get_json(url: str, headers: dict[str, str] | None = None) -> Any:
    request_headers = {**HEADERS, **(headers or {})}
    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
        response = await client.get(url, headers=request_headers)
        response.raise_for_status()
        return response.json()


async def search_companies(query: str) -> list[CompanyHit]:
    query = query.strip()
    if len(query) < 2:
        return []
    url = f"{API}/PeerSmartSearch/w?Type=SS&text={quote(query)}"
    raw = await get_json(url)
    html = raw if isinstance(raw, str) else str(raw or "")
    hits: list[CompanyHit] = []
    seen: set[str] = set()
    pattern = re.compile(
        r"liclick\('(?P<code>\d+)','(?P<name>[^']+)'\).*?<strong>(?P<symbol>[^<]*)</strong>&nbsp;&nbsp;&nbsp;(?P<isin>[^<&]+)&nbsp;&nbsp;&nbsp;\d+",
        re.I | re.S,
    )
    for match in pattern.finditer(html):
        code = match.group("code")
        if code in seen:
            continue
        seen.add(code)
        hits.append(CompanyHit(
            scripCode=code,
            name=match.group("name").strip(),
            symbol=match.group("symbol").strip() or code,
            isin=match.group("isin").strip(),
        ))
    if not hits:
        for match in re.finditer(r"liclick\('(?P<code>\d+)','(?P<name>[^']+)'\)", html):
            code = match.group("code")
            if code in seen:
                continue
            seen.add(code)
            hits.append(CompanyHit(scripCode=code, name=match.group("name").strip(), symbol=code, isin=""))
    return hits[:12]


async def fetch_annual_reports(scrip_code: str) -> list[dict[str, Any]]:
    data = await get_json(f"{API}/AnnualReport/w?scripcode={quote(scrip_code)}")
    return data.get("Table", []) if isinstance(data, dict) else []


async def fetch_announcements(
    scrip_code: str,
    category: str | None = None,
    from_date: date | None = None,
    max_pages: int = 6,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    total = float("inf")
    from_date = from_date or days_ago(90)
    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
        for page in range(1, max_pages + 1):
            params = {
                "pageno": page,
                "strCat": category or "-1",
                "subcategory": "-1",
                "strPrevDate": yyyymmdd(from_date),
                "strToDate": yyyymmdd(date.today()),
                "strSearch": "P",
                "strscrip": scrip_code,
                "strType": "C",
            }
            response = await client.get(f"{API}/AnnSubCategoryGetData/w", params=params, headers=HEADERS)
            response.raise_for_status()
            data = response.json()
            batch = data.get("Table", []) if isinstance(data, dict) else []
            total = float((data.get("Table1") or [{}])[0].get("ROWCNT", len(batch))) if isinstance(data, dict) else len(batch)
            rows.extend(batch)
            if not batch or len(rows) >= total:
                break
    return rows


def clean_attachment_name(name: str) -> str:
    return re.sub(r"\.pdf\.pdf$", ".pdf", name.lstrip("\\").strip(), flags=re.I)


async def download_pdf(attachment_name: str, old_flag: Any = None) -> bytes | None:
    name = clean_attachment_name(attachment_name)
    if not name:
        return None
    encoded = quote(name)
    paths = ["AttachLive", "AttachHis"] if str(old_flag) == "0" else ["AttachHis", "AttachLive"]
    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
        for path in paths:
            try:
                response = await client.get(
                    f"{SITE}/xml-data/corpfiling/{path}/{encoded}",
                    headers={**HEADERS, "Accept": "application/pdf,*/*"},
                )
                content = response.content
                if (
                    response.is_success
                    and "pdf" in response.headers.get("content-type", "").lower()
                    and len(content) >= 800
                    and content[:4] == b"%PDF"
                ):
                    return content
            except httpx.HTTPError:
                continue
    return None
