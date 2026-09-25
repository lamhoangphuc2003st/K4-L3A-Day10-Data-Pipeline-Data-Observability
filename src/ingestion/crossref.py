from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from html import unescape
from pathlib import Path
import re
import time

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def _plain(value: object) -> str:
    return normalize_whitespace(unescape(re.sub(r"<[^>]*>", " ", str(value or ""))))


def _date(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    parts = value.get("date-parts", [[]])
    if not parts or not parts[0]:
        return ""
    try:
        year, *rest = parts[0]
        return date(int(year), int(rest[0]) if rest else 1, int(rest[1]) if len(rest) > 1 else 1).isoformat()
    except (TypeError, ValueError, IndexError):
        return ""


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    records = []
    for item in payload.get("message", {}).get("items", []):
        doi = normalize_whitespace(str(item.get("DOI") or "")).lower()
        titles = item.get("title") or []
        title = _plain(titles[0] if isinstance(titles, list) and titles else titles)
        published = (_date(item.get("published")) or _date(item.get("published-print"))
                 or _date(item.get("published-online")) or _date(item.get("created")))
        if not doi or not title or not published:
            continue
        authors = [name for author in item.get("author", []) if (name := normalize_whitespace(
            f"{author.get('given', '')} {author.get('family', '')}"
        ))]
        categories = [_plain(subject) for subject in item.get("subject", []) if _plain(subject)]
        url = str(item.get("URL") or f"https://doi.org/{doi}")
        links = item.get("link") or []
        pdf_url = next((str(link.get("URL")) for link in links if "pdf" in str(link.get("content-type", "")).lower()), url)
        records.append(PaperRecord(
            paper_id=doi, title=title, summary=_plain(item.get("abstract")),
            authors=authors, categories=categories, primary_category=categories[0] if categories else "",
            published=published, updated=_date(item.get("updated")) or published,
            abs_url=url, pdf_url=pdf_url, comment=f"Crossref record {doi}",
        ))
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    path = settings.paths.raw_api_response
    if settings.refresh_source:
        for attempt in range(3):
            try:
                response = requests.get(
                    "https://api.crossref.org/works",
                    params={"query": settings.source_query, "filter": settings.source_filter, "rows": settings.max_results},
                    headers={"User-Agent": "day10-data-observability-lab/0.1"}, timeout=30,
                )
                response.raise_for_status()
                payload = response.json()
                records = parse_crossref_payload(payload)
                if not records:
                    raise ValueError("Crossref returned no usable records")
                write_json(path, payload)
                write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
                return records
            except (requests.RequestException, ValueError):
                if attempt < 2:
                    time.sleep(2 ** attempt)
    if not path.exists():
        raise FileNotFoundError(f"No Crossref snapshot available: {path}")
    records = parse_crossref_payload(read_json(path))
    if not records:
        raise ValueError(f"Crossref snapshot has no usable records: {path}")
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError("Raw records must be a JSON list")
    return [PaperRecord(**item) for item in payload]
