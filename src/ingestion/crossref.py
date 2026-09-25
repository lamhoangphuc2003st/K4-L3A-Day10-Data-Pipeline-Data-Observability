from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _plain(value: str) -> str:
    parser = _Text()
    parser.feed(unescape(value))
    return normalize_whitespace(" ".join(parser.parts))


def _date(value: dict | None) -> str:
    if not isinstance(value, dict):
        return ""
    parts = value.get("date-parts", [[]])
    if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
        try:
            return date(*[int(x) for x in (parts[0] + [1, 1])[:3]]).isoformat()
        except (TypeError, ValueError):
            return ""
    timestamp = value.get("date-time", "")
    return timestamp[:10] if isinstance(timestamp, str) else ""


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    message = payload.get("message") if isinstance(payload, dict) else None
    items = message.get("items") if isinstance(message, dict) else None
    if not isinstance(items, list):
        raise ValueError("Crossref response must contain message.items as a list")
    records: list[PaperRecord] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        paper_id = normalize_whitespace(str(item.get("DOI") or ""))
        titles = item.get("title") or []
        title = _plain(str(titles[0])) if isinstance(titles, list) and titles else ""
        if not paper_id or not title:
            continue
        raw_authors = item.get("author")
        raw_categories = item.get("subject")
        authors = [normalize_whitespace(f"{a.get('given', '')} {a.get('family', '')}")
                   for a in raw_authors if isinstance(a, dict)] if isinstance(raw_authors, list) else []
        categories = [_plain(str(x)) for x in raw_categories if x] if isinstance(raw_categories, list) else []
        published = _date(item.get("published")) or _date(item.get("created"))
        updated = _date(item.get("updated")) or published
        url = str(item.get("URL") or f"https://doi.org/{paper_id}")
        pdf_links = [link.get("URL") for link in (item.get("link") or [])
                     if isinstance(link, dict) and "pdf" in link.get("content-type", "").lower()]
        records.append(PaperRecord(
            paper_id=paper_id, title=title, summary=_plain(str(item.get("abstract") or "")),
            authors=[a for a in authors if a], categories=categories,
            primary_category=categories[0] if categories else "", published=published,
            updated=updated, abs_url=url, pdf_url=str(pdf_links[0] if pdf_links else url),
            comment=f"Crossref record {paper_id}",
        ))
    if not records:
        raise ValueError("Crossref response contains no usable records")
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    path = settings.paths.raw_api_response
    if settings.refresh_source:
        retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        session = requests.Session()
        session.mount("https://", HTTPAdapter(max_retries=retry))
        try:
            response = session.get(
                "https://api.crossref.org/works",
                params={"query": settings.source_query, "filter": settings.source_filter,
                        "rows": settings.max_results}, timeout=20,
                headers={"User-Agent": "Day10DataObservabilityLab/1.0"},
            )
            response.raise_for_status()
            payload = response.json()
            records = parse_crossref_payload(payload)
            write_json(path, payload)
        except (requests.RequestException, ValueError) as exc:
            if not path.exists():
                raise RuntimeError(f"Crossref request failed and no offline snapshot exists: {exc}") from exc
            records = parse_crossref_payload(read_json(path))
    else:
        if not path.exists():
            raise FileNotFoundError(f"Offline Crossref snapshot missing: {path}")
        records = parse_crossref_payload(read_json(path))
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"Raw records must be a JSON list: {path}")
    try:
        return [PaperRecord(**record) for record in payload]
    except (TypeError, KeyError) as exc:
        raise ValueError(f"Invalid PaperRecord in {path}: {exc}") from exc
