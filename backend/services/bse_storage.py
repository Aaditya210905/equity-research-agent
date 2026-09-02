from __future__ import annotations

import json
import re
from pathlib import Path

from schemas.bse import CompanyFolder, FilingKind


# Store BSE filings alongside other documents in the project's documents/ folder
FILINGS_ROOT = Path(__file__).resolve().parent.parent / "documents"


def slug(value: str, maximum: int = 72) -> str:
    cleaned = value.replace("&", "and")
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", cleaned)
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return (cleaned[:maximum] or "file")


def company_folder_name(scrip_code: str, symbol: str) -> str:
    return slug(symbol or scrip_code).upper()


def company_dir(scrip_code: str, symbol: str) -> Path:
    return FILINGS_ROOT / company_folder_name(scrip_code, symbol)


def unique_file_name(date_value: str, headline: str, attachment: str) -> str:
    day = (date_value or "")[:10] or "undated"
    base = slug(headline or "filing", 52)
    attachment_id = slug(re.sub(r"\.pdf$", "", attachment, flags=re.I), 16)[-12:]
    return f"{day}_{base}_{attachment_id}.pdf"


def relative_path(path: Path) -> str:
    return path.relative_to(FILINGS_ROOT).as_posix()


def write_manifest(directory: Path, company: CompanyFolder) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "manifest.json").write_text(
        company.model_dump_json(indent=2), encoding="utf-8"
    )


def read_manifest(directory: Path) -> CompanyFolder | None:
    try:
        return CompanyFolder.model_validate_json(
            (directory / "manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None


def list_company_folders() -> list[CompanyFolder]:
    if not FILINGS_ROOT.exists():
        return []
    folders: list[CompanyFolder] = []
    for directory in FILINGS_ROOT.iterdir():
        if not directory.is_dir() or directory.name.startswith("."):
            continue
        manifest = read_manifest(directory)
        if manifest:
            folders.append(manifest)
            continue
        parts = directory.name.split("-", 1)
        symbol = parts[1] if len(parts) == 2 else directory.name
        folders.append(
            CompanyFolder(
                scripCode=parts[0],
                symbol=symbol,
                name=symbol,
                folder=directory.name,
                fetchedAt="",
                files=[],
                counts={kind: 0 for kind in ("annual_reports", "quarterly_reports", "announcements")},
                totalBytes=0,
            )
        )
    return sorted(folders, key=lambda item: item.fetchedAt, reverse=True)


def resolve_under_root(relative: str) -> Path:
    root = FILINGS_ROOT.resolve()
    full = (root / relative).resolve()
    if full != root and root not in full.parents:
        raise ValueError("Invalid file path")
    return full
