# Phase 6 — Professional Research Workspace

Transform the AI backend into a full-stack, interactive research platform that analysts can read, explore, compare, and export.

---

## Architecture

```
Verified Report (Phase 5 output)
         │
         ▼
  Report Builder       ← structures into 12-section format + charts data
         │
    ┌────┼────────────┐
    ▼    ▼            ▼
  HTML  JSON        Export
  View  API    (PDF / DOCX / MD)
    │    │            │
    └────┼────────────┘
         ▼
  React Frontend Dashboard
```

---

## Part A — Backend

### New Backend Folders
```
backend/
├── reports/
│   ├── report_builder.py      ← 12-section assembler
│   ├── formatter.py           ← Markdown / HTML rendering
│   └── exporter.py            ← PDF, DOCX, Markdown, JSON
├── dashboard/
│   ├── charts.py              ← chart data from financial engine
│   └── comparison.py          ← multi-company comparison table
└── models/
    └── workspace.py           ← ReportVersion, AnalystNote, Watchlist (peewee ORM)
```

---

### Report Builder (`reports/report_builder.py`)

Assembles the Phase 5 output + financial engine metrics into the full **12-section format**:

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
12. Appendix (formula registry + data lineage)

---

### Chart Data (`dashboard/charts.py`)

Reads `financial_engine.engine` output and generates chart-ready structures:

```python
{
  "revenue_trend": {"labels": ["2021","2022","2023","2024"], "values": [...]},
  "margin_trend":  {"labels": [...], "net_margin": [...], "op_margin": [...]},
  "cash_flow_trend": {...},
  "roe_trend": {...}
}
```

Consumed directly by Recharts in the frontend.

---

### Exporter (`reports/exporter.py`)

| Format | Library |
|---|---|
| PDF | `weasyprint` |
| DOCX | `python-docx` |
| Markdown | built-in string formatting |
| JSON | `json.dumps` (already a dict) |

---

### Workspace DB Models (`models/workspace.py`)

Three new peewee tables (same SQLite as document DB):

- **`ReportVersion`** — `report_id`, `ticker`, `company`, `model`, `version`, `created_at`, `report_json`
- **`AnalystNote`** — `note_id`, `ticker`, `content`, `created_at`
- **`WatchlistEntry`** — `ticker`, `company_name`, `added_at`

---

### New API Routes (`api/workspace_routes.py`)

| Method | Endpoint | Returns |
|---|---|---|
| `GET` | `/report/{ticker}/latest` | Latest versioned report |
| `GET` | `/report/{ticker}/versions` | All version metadata |
| `GET` | `/report/{ticker}/version/{n}` | Specific version |
| `GET` | `/report/{ticker}/charts` | Chart data JSON |
| `GET` | `/report/{ticker}/export/pdf` | PDF file download |
| `GET` | `/report/{ticker}/export/docx` | DOCX file download |
| `GET` | `/report/{ticker}/export/markdown` | Markdown text |
| `GET` | `/report/{ticker}/export/json` | Raw JSON |
| `GET` | `/compare` | `?tickers=TCS,INFY,HCL` comparison table |
| `GET` | `/watchlist` | All saved tickers |
| `POST` | `/watchlist/{ticker}` | Add to watchlist |
| `DELETE` | `/watchlist/{ticker}` | Remove from watchlist |
| `GET` | `/notes/{ticker}` | Get analyst notes |
| `POST` | `/notes/{ticker}` | Save analyst note |
| `DELETE` | `/notes/{note_id}` | Delete note |

---

## Part B — Frontend

**Framework**: Vite + React  
**Charts**: Recharts  
**Styling**: Vanilla CSS (dark-mode, glassmorphism, modern design)  
**HTTP client**: Fetch API (no extra library needed)

### Frontend Pages

```
frontend/src/
├── pages/
│   ├── Dashboard.jsx          ← Home — watchlist + recent reports
│   ├── Company.jsx            ← Full company workspace (charts + report)
│   └── Compare.jsx            ← Side-by-side comparison table
├── components/
│   ├── CompanyCard.jsx        ← Price / Market Cap / P/E / Recommendation badge
│   ├── Charts/
│   │   ├── RevenueTrend.jsx
│   │   ├── MarginTrend.jsx
│   │   ├── CashFlowTrend.jsx
│   │   └── ROETrend.jsx
│   ├── ReportViewer.jsx       ← 12-section collapsible report
│   ├── ExplainPanel.jsx       ← AI Explainability: "Why?" expandable per insight
│   ├── SourceViewer.jsx       ← Clickable citations → highlights on PDF
│   ├── CompareView.jsx        ← Metric comparison table with AI explanation
│   ├── NotesPanel.jsx         ← Analyst notes (save / delete)
│   ├── Watchlist.jsx          ← Bookmarked tickers sidebar
│   └── ExportBar.jsx          ← PDF / DOCX / MD / JSON download buttons
└── App.jsx                    ← Router (hash-based, no server needed)
```

---

### Key UI Features

**1. Live Dashboard**  
Watchlist sidebar + recent reports. Search any ticker to trigger report generation.

**2. Company Workspace**  
- KPI cards: Current Price, Market Cap, P/E, Recommendation, Confidence  
- Revenue / Margin / ROE / Cash Flow charts (Recharts LineChart)  
- 12-section AI report (collapsible accordion)  
- AI Explainability Panel: every insight has a ▼ "Why?" that shows bullet points + citations  
- Clickable citations: open/highlight the source PDF page in a side panel  

**3. Company Comparison**  
Table with TCS vs INFY vs HCL across ~15 metrics. AI explains key differences.

**4. Analyst Notes**  
Text area per ticker — saved to backend. Shown alongside AI report.

**5. Export Bar**  
One-click download as PDF, DOCX, Markdown, or JSON.

---

## Open Questions

> [!IMPORTANT]
> **Streaming during generation**: The research graph supports `stream_research()` SSE. Should the Company page show a live progress bar ("Gathering evidence… Generating sections… Verifying claims…") while the report is being built? This requires connecting the SSE stream to the frontend.

> [!NOTE]
> **PDF highlighting**: Source citations can open a specific page of the PDF. Do you want an in-browser PDF viewer (using `pdf.js`) that highlights the cited paragraph, or just a download link to the raw PDF file?

> [!NOTE]
> **Authentication**: Should the watchlist and analyst notes be per-user (requires login) or shared/local (no auth)? For now I'll make them local (no login required) unless you specify otherwise.

---

## Implementation Order

1. `models/workspace.py` + DB migration  
2. `reports/report_builder.py` — 12-section assembler  
3. `dashboard/charts.py` — chart data  
4. `reports/exporter.py` — PDF, DOCX, MD, JSON  
5. `api/workspace_routes.py` — all 15 new routes  
6. Frontend scaffold (Vite + React)  
7. Dashboard page + Watchlist  
8. Company workspace page + Charts  
9. ReportViewer + ExplainPanel + SourceViewer  
10. Compare page  
11. NotesPanel + ExportBar  
12. Polish + responsive design  

## Verification Plan
- All new backend endpoints return correct JSON  
- Export files open correctly in PDF/Word  
- Charts render from real financial data  
- All existing Phase 1–5 tests continue to pass  
