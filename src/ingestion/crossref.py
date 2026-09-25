from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
import time

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json


CROSSREF_URL = "https://api.crossref.org/works"
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_RETRIES = 3


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


def _strip_markup(text: str) -> str:
    """Remove JATS/HTML tags (e.g. <jats:p>) and normalize whitespace."""
    return normalize_whitespace(re.sub(r"<[^>]+>", " ", text or ""))


def _date_from_parts(value: dict | None) -> str | None:
    parts = ((value or {}).get("date-parts") or [[]])[0]
    if not parts or parts[0] is None:
        return None
    year = int(parts[0])
    month = int(parts[1]) if len(parts) > 1 and parts[1] else 1
    day = int(parts[2]) if len(parts) > 2 and parts[2] else 1
    return f"{year:04d}-{month:02d}-{day:02d}"


def _published_date(item: dict) -> str | None:
    for key in ("published", "published-online", "published-print", "issued"):
        parsed = _date_from_parts(item.get(key))
        if parsed:
            return parsed
    created = (item.get("created") or {}).get("date-time")
    return created[:10] if created else None


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    records: list[PaperRecord] = []
    for item in payload.get("message", {}).get("items", []):
        doi = normalize_whitespace(item.get("DOI", ""))
        title = normalize_whitespace((item.get("title") or [""])[0])
        summary = _strip_markup(item.get("abstract", ""))
        published = _published_date(item)
        if not doi or not title or not summary or not published:
            continue

        authors = [
            normalize_whitespace(f"{a.get('given', '')} {a.get('family', '')}")
            for a in item.get("author", [])
        ]
        authors = [a for a in authors if a]
        categories = [normalize_whitespace(s) for s in item.get("subject", []) if s]
        url = item.get("URL") or f"https://doi.org/{doi}"
        updated = (
            _date_from_parts(item.get("deposited"))
            or _date_from_parts(item.get("indexed"))
            or published
        )
        records.append(
            PaperRecord(
                paper_id=doi,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=categories[0] if categories else "",
                published=published,
                updated=updated,
                abs_url=url,
                pdf_url=url,
                comment=f"Crossref record {doi}",
            )
        )
    return records


def _request_live(settings: Settings) -> dict:
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
        "sort": "published",
        "order": "desc",
    }
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(CROSSREF_URL, params=params, timeout=30)
            if response.status_code in RETRY_STATUS_CODES:
                last_error = RuntimeError(f"Crossref returned {response.status_code}")
                time.sleep(2**attempt)
                continue
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"Crossref API unavailable: {last_error}")


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Dev/offline mode reads the local snapshot; REFRESH_SOURCE=1 calls the live API.

    A failed live call (429/503/no network) falls back to the snapshot.
    """
    paths = settings.paths
    payload: dict | None = None
    if settings.refresh_source or not paths.raw_api_response.exists():
        try:
            payload = _request_live(settings)
            write_json(paths.raw_api_response, payload)
        except RuntimeError as exc:
            if not paths.raw_api_response.exists():
                raise
            print(f"[crossref] {exc}; falling back to snapshot {paths.raw_api_response}")
    if payload is None:
        payload = read_json(paths.raw_api_response)

    records = parse_crossref_payload(payload)
    write_json(paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    return [PaperRecord(**row) for row in read_json(path)]
