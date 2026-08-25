import os
import re
import time
from datetime import datetime, timedelta
from urllib.parse import quote

import requests

API = "https://api.bseindia.com/BseIndiaAPI/api"
SITE = "https://www.bseindia.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": SITE,
    "Referer": f"{SITE}/",
    "Connection": "keep-alive",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def _request(url, params=None, extra_headers=None, retries=2):
    last_error = None
    for attempt in range(retries + 1):
        try:
            resp = SESSION.get(url, params=params, headers=extra_headers, timeout=25)
            resp.raise_for_status()
            return resp
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status not in (429, 500, 502, 503, 504) or attempt == retries:
                raise
            last_error = e
            time.sleep(0.4 * (attempt + 1))
        except requests.RequestException as e:
            last_error = e
            if attempt == retries:
                raise
            time.sleep(0.4 * (attempt + 1))
    raise last_error


def _yyyymmdd(d):
    return d.strftime("%Y%m%d")


def _clean_attachment_name(name):
    name = re.sub(r"^\\+", "", name or "")
    name = re.sub(r"\.pdf\.pdf$", ".pdf", name, flags=re.IGNORECASE)
    return name.strip()


def _has_pdf(row):
    return str(row.get("PDFFLAG")) == "1" and bool(row.get("ATTACHMENTNAME"))


def _slugify(value, max_len=60):
    value = re.sub(r"&", "and", value or "")
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:max_len] or "file"


def search_company(query):
    q = query.strip()
    if len(q) < 2:
        return []
    resp = _request(f"{API}/PeerSmartSearch/w", params={"Type": "SS", "text": q})
    html = resp.json()
    html = html if isinstance(html, str) else str(html or "")
    pattern = r"liclick\('(\d+)','([^']+)'\)[\s\S]*?<strong>([^<]*)</strong>&nbsp;&nbsp;&nbsp;([^<&]+)&nbsp;&nbsp;&nbsp;(\d+)"
    hits, seen = [], set()
    for m in re.finditer(pattern, html):
        scrip_code = m.group(1)
        if not scrip_code or scrip_code in seen:
            continue
        seen.add(scrip_code)
        hits.append({
            "scrip_code": scrip_code,
            "name": m.group(2).strip(),
            "symbol": re.sub(r"</?strong>", "", m.group(3)).strip() or scrip_code,
            "isin": m.group(4).strip(),
        })
    if not hits:
        for m in re.finditer(r"liclick\('(\d+)','([^']+)'\)", html):
            scrip_code = m.group(1)
            if not scrip_code or scrip_code in seen:
                continue
            seen.add(scrip_code)
            hits.append({"scrip_code": scrip_code, "name": m.group(2).strip(), "symbol": scrip_code, "isin": ""})
    return hits[:12]


def resolve_scrip_code(company):
    company = str(company).strip()
    if re.fullmatch(r"\d{5,7}", company):
        return company, None
    hits = search_company(company)
    if not hits:
        return None, []
    return hits[0]["scrip_code"], hits


def _fetch_announcement_pages(scrip_code, from_date, to_date, category=None, max_pages=6):
    rows = []
    total = float("inf")
    page = 1
    while page <= max_pages and len(rows) < total:
        params = {
            "pageno": page,
            "strCat": category or "-1",
            "subcategory": "-1",
            "strPrevDate": _yyyymmdd(from_date),
            "strToDate": _yyyymmdd(to_date),
            "strSearch": "P",
            "strscrip": scrip_code,
            "strType": "C",
        }
        resp = _request(f"{API}/AnnSubCategoryGetData/w", params=params)
        data = resp.json()
        batch = data.get("Table") or []
        table1 = data.get("Table1") or [{}]
        total = table1[0].get("ROWCNT", len(batch))
        rows.extend(batch)
        if not batch:
            break
        page += 1
        time.sleep(0.15)
    return rows


def _normalize_filing(row, kind):
    when = row.get("DissemDT") or row.get("DT_TM") or row.get("NEWS_DT") or ""
    headline = (row.get("HEADLINE") or row.get("NEWSSUB") or "Filing").strip()
    return {
        "kind": kind,
        "news_id": str(row.get("NEWSID") or ""),
        "headline": headline,
        "category": row.get("CATEGORYNAME") or "",
        "subcategory": row.get("SUBCATNAME") or "",
        "date": when,
        "attachment_name": row.get("ATTACHMENTNAME") or "",
        "old_flag": row.get("OLD"),
        "has_pdf": _has_pdf(row),
    }


def get_corporate_announcements(scrip_code, days=90, exclude_results=True, limit=30):
    to_date = datetime.now()
    from_date = to_date - timedelta(days=days)
    rows = _fetch_announcement_pages(scrip_code, from_date, to_date)
    out = []
    for row in rows:
        if exclude_results and (row.get("CATEGORYNAME") or "").strip().lower() == "result":
            continue
        if not _has_pdf(row):
            continue
        out.append(_normalize_filing(row, "announcement"))
        if len(out) >= limit:
            break
    return out


def get_quarterly_reports(scrip_code, lookback_days=900, limit=8):
    to_date = datetime.now()
    from_date = to_date - timedelta(days=lookback_days)
    rows = _fetch_announcement_pages(scrip_code, from_date, to_date, category="Result")
    out = []
    for row in rows:
        if not _has_pdf(row):
            continue
        out.append(_normalize_filing(row, "quarterly-report"))
        if len(out) >= limit:
            break
    return out


def get_annual_reports(scrip_code, limit=5):
    resp = _request(f"{API}/AnnualReport/w", params={"scripcode": scrip_code})
    data = resp.json()
    rows = data.get("Table") or []
    by_year = {}
    for row in rows:
        year = str(row.get("year") or "")
        if year and year not in by_year:
            by_year[year] = row
    years = sorted(by_year.items(), key=lambda kv: kv[0], reverse=True)[:limit]
    out = []
    for year, row in years:
        out.append({
            "kind": "annual-report",
            "news_id": f"ar-{year}",
            "headline": f"Annual Report FY {year}",
            "category": "Annual Report",
            "subcategory": "Annual Report",
            "date": row.get("dt_tm") or "",
            "attachment_name": row.get("file_name") or "",
            "old_flag": None,
            "has_pdf": bool(row.get("file_name")),
            "year": year,
        })
    return out


def download_filing_pdf(attachment_name, old_flag=None, out_dir=None, file_label=None):
    name = _clean_attachment_name(attachment_name)
    if not name:
        return None
    encoded = quote(name, safe="")
    prefer_live = str(old_flag) == "0"
    paths = ["AttachLive", "AttachHis"] if prefer_live else ["AttachHis", "AttachLive"]
    for path in paths:
        url = f"{SITE}/xml-data/corpfiling/{path}/{encoded}"
        try:
            resp = _request(url, extra_headers={"Accept": "application/pdf,*/*"})
        except requests.RequestException:
            continue
        ctype = resp.headers.get("content-type", "").lower()
        content = resp.content
        if "pdf" not in ctype or len(content) < 800 or content[:4] != b"%PDF":
            continue
        result = {"content": content, "source_url": url, "bytes": len(content)}
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            fname = _slugify(file_label or name.replace(".pdf", "")) + ".pdf"
            fpath = os.path.join(out_dir, fname)
            if not os.path.exists(fpath):
                with open(fpath, "wb") as f:
                    f.write(content)
            result["local_path"] = fpath
        return result
    return None


def get_bse_filings(
    company,
    report_types=("annual", "quarterly", "announcements"),
    announcement_days=90,
    quarterly_lookback_days=900,
    annual_limit=3,
    quarterly_limit=8,
    announcement_limit=20,
    download=True,
    out_dir="bse_filings",
):
    try:
        scrip_code, candidates = resolve_scrip_code(company)
    except requests.RequestException as e:
        return {"company": company, "scrip_code": None, "error": f"BSE lookup failed: {e}", "filings": []}

    if not scrip_code:
        return {"company": company, "scrip_code": None, "error": "no matching BSE-listed company found", "filings": []}

    try:
        filings = []
        if "annual" in report_types:
            filings += get_annual_reports(scrip_code, limit=annual_limit)
        if "quarterly" in report_types:
            filings += get_quarterly_reports(scrip_code, lookback_days=quarterly_lookback_days, limit=quarterly_limit)
        if "announcements" in report_types:
            filings += get_corporate_announcements(scrip_code, days=announcement_days, limit=announcement_limit)
    except requests.RequestException as e:
        return {"company": company, "scrip_code": scrip_code, "error": f"BSE fetch failed: {e}", "filings": []}

    if download:
        company_dir = os.path.join(out_dir, scrip_code)
        for filing in filings:
            if not filing.get("has_pdf"):
                continue
            label = f'{filing.get("date", "")[:10]}_{filing["kind"]}_{filing["news_id"]}'
            pdf = download_filing_pdf(
                filing["attachment_name"],
                filing.get("old_flag"),
                out_dir=os.path.join(company_dir, filing["kind"]),
                file_label=label,
            )
            if pdf:
                filing["local_path"] = pdf.get("local_path")
                filing["source_url"] = pdf["source_url"]
                filing["bytes"] = pdf["bytes"]
            else:
                filing["download_error"] = "PDF not retrievable from BSE"
            time.sleep(0.15)

    return {
        "company": company,
        "scrip_code": scrip_code,
        "candidates_considered": [c["name"] for c in candidates] if candidates else None,
        "filings": filings,
    }


BSE_FILINGS_TOOL = {
    "name": "get_bse_filings",
    "description": (
        "Fetch Annual Reports, Quarterly Reports, and Corporate Announcements for an Indian "
        "company listed on the BSE. Accepts a company name, symbol, or BSE scrip code and "
        "returns filing metadata, optionally with downloaded PDF content."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "company": {
                "type": "string",
                "description": "Company name, symbol, or BSE scrip code, e.g. 'Reliance Industries' or '500325'",
            },
            "report_types": {
                "type": "array",
                "items": {"type": "string", "enum": ["annual", "quarterly", "announcements"]},
                "description": "Which filing types to fetch. Defaults to all three.",
            },
            "download": {
                "type": "boolean",
                "description": "Whether to download and save PDF content, not just return metadata.",
            },
        },
        "required": ["company"],
    },
}


def run_bse_tool(tool_input):
    return get_bse_filings(
        company=tool_input["company"],
        report_types=tuple(tool_input.get("report_types", ("annual", "quarterly", "announcements"))),
        download=tool_input.get("download", False),
    )


if __name__ == "__main__":
    result = get_bse_filings("Reliance Industries", report_types=("annual", "quarterly"), annual_limit=2, quarterly_limit=4)
    print(result["company"], "->", result["scrip_code"])
    for f in result["filings"]:
        print(f["kind"], f["date"], f["headline"])