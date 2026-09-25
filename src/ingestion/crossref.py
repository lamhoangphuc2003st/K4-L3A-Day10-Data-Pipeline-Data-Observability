from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from html.parser import HTMLParser
import logging
from pathlib import Path
import re

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json


logger = logging.getLogger(__name__)
CROSSREF_WORKS_URL = "https://api.crossref.org/works"


class _AbstractParser(HTMLParser):
    """Keep text and inline formatting boundaries, separating JATS paragraphs."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag.split(":")[-1] in {"p", "div", "br", "sec", "title", "li"}:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        self.handle_starttag(tag, [])


def _text(value: object) -> str:
    return normalize_whitespace(value) if isinstance(value, str) else ""


def _iso_date(value: object) -> str:
    """Return an ISO calendar date; incomplete dates use January/day one."""
    if not isinstance(value, dict):
        return ""
    parts = value.get("date-parts")
    if isinstance(parts, list) and parts and isinstance(parts[0], list):
        components = parts[0]
        if 1 <= len(components) <= 3:
            try:
                return date(*(components + [1] * (3 - len(components)))).isoformat()
            except (TypeError, ValueError, OverflowError):
                pass
    timestamp = value.get("date-time")
    if isinstance(timestamp, str):
        try:
            return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            pass
    return ""


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


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse a work-list response, skipping items without a valid DOI/title.

    Missing optional metadata is represented by empty strings/lists. Dates are
    ISO 8601 calendar dates, consistent with the bundled records snapshot.
    """
    message = payload.get("message") if isinstance(payload, dict) else None
    items = message.get("items") if isinstance(message, dict) else None
    if not isinstance(items, list):
        raise ValueError("Crossref payload must contain message.items as a list.")

    records = []
    for item in items:
        if not isinstance(item, dict):
            continue
        doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", _text(item.get("DOI")), flags=re.I).lower()
        titles = item.get("title")
        title = _text(titles[0] if isinstance(titles, list) and titles else titles)
        if not re.fullmatch(r"10\.\d{4,9}/\S+", doi) or not title:
            continue

        abstract = _AbstractParser()
        abstract.feed(_text(item.get("abstract")))
        abstract.close()
        authors = []
        for author in item.get("author") or []:
            if isinstance(author, dict):
                name = _text(" ".join(filter(None, [_text(author.get("given")), _text(author.get("family"))]))) or _text(author.get("name"))
                if name:
                    authors.append(name)
        subjects = item.get("subject") or []
        if isinstance(subjects, str):
            subjects = [subjects]
        categories = [text for subject in subjects if (text := _text(subject))]
        published = next((parsed for key in ("published", "published-print", "published-online", "issued", "created") if (parsed := _iso_date(item.get(key)))), "")
        updated = next((parsed for key in ("indexed", "deposited", "created") if (parsed := _iso_date(item.get(key)))), published)
        abs_url = _text(item.get("URL")) or f"https://doi.org/{doi}"
        pdf_url = next((_text(link.get("URL")) for link in item.get("link") or [] if isinstance(link, dict) and link.get("content-type") == "application/pdf" and _text(link.get("URL"))), abs_url)
        records.append(PaperRecord(
            paper_id=doi, title=title,
            summary=normalize_whitespace("".join(abstract.parts)),
            authors=authors, categories=categories,
            primary_category=categories[0] if categories else "",
            published=published, updated=updated,
            abs_url=abs_url, pdf_url=pdf_url, comment=f"Crossref record {doi}",
        ))
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Use the local snapshot unless refreshing; rescue transient API failures.

    Fall back immediately on rate limits, server errors, and network failures
    so a lab does not wait through repeated retries. Other HTTP errors propagate.
    A failed request never overwrites the available raw snapshot.
    """
    snapshot = settings.paths.raw_api_response
    if not settings.refresh_source and snapshot.exists():
        records = parse_crossref_payload(read_json(snapshot))
    else:
        try:
            response = requests.get(
                CROSSREF_WORKS_URL,
                params={"query": settings.source_query, "filter": settings.source_filter, "rows": settings.max_results},
                headers={"User-Agent": "data-observability-lab/0.1", "Accept": "application/json"},
                timeout=(5, 20),
            )
            response.raise_for_status()
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
            if isinstance(exc, requests.HTTPError):
                status = exc.response.status_code if exc.response is not None else None
                if status != 429 and (status is None or status < 500):
                    raise
            if not snapshot.exists():
                raise RuntimeError(f"Crossref is unavailable and no offline snapshot exists at {snapshot}") from exc
            logger.warning("Crossref unavailable (%s); using offline snapshot %s", exc, snapshot)
            records = parse_crossref_payload(read_json(snapshot))
        else:
            payload = response.json()
            records = parse_crossref_payload(payload)
            write_json(snapshot, payload)
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load serialized PaperRecord objects for downstream cleaning/repair."""
    return [PaperRecord(**record) for record in read_json(path)]
