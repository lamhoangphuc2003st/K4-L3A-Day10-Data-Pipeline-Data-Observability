from __future__ import annotations

from datetime import datetime
from html import unescape
import re

import pandas as pd

from core.utils import normalize_whitespace
from ingestion.crossref import PaperRecord


def _clean(value: object) -> str:
    return normalize_whitespace(unescape(re.sub(r"<[^>]*>", " ", str(value or ""))))


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    columns = ["paper_id", "title", "summary", "authors", "categories", "primary_category",
               "published", "updated", "abs_url", "pdf_url", "comment", "age_days",
               "authors_joined", "categories_joined", "summary_chars", "text_for_embedding"]
    rows = []
    today = run_date.date()
    seen = set()
    for record in records:
        paper_id = _clean(record.paper_id).lower()
        title, summary = _clean(record.title), _clean(record.summary)
        published = pd.to_datetime(record.published, errors="coerce", utc=True)
        if not paper_id or paper_id in seen or not title or not summary or pd.isna(published):
            continue
        seen.add(paper_id)
        authors = [_clean(author) for author in record.authors if _clean(author)]
        categories = [_clean(category) for category in record.categories if _clean(category)]
        published_iso = published.date().isoformat()
        authors_joined = ", ".join(authors)
        categories_joined = ", ".join(categories)
        updated = pd.to_datetime(record.updated, errors="coerce", utc=True)
        updated_iso = updated.date().isoformat() if not pd.isna(updated) else published_iso
        rows.append({
            "paper_id": paper_id, "title": title, "summary": summary,
            "authors": authors, "categories": categories,
            "primary_category": _clean(record.primary_category),
            "published": published_iso, "updated": updated_iso,
            "abs_url": _clean(record.abs_url), "pdf_url": _clean(record.pdf_url),
            "comment": _clean(record.comment),
            "age_days": (today - published.date()).days,
            "authors_joined": authors_joined, "categories_joined": categories_joined,
            "summary_chars": len(summary),
            "text_for_embedding": "\n".join([
                f"Title: {title}", f"Authors: {authors_joined}", f"Published: {published_iso}",
                f"Categories: {categories_joined}", f"Summary: {summary}",
            ]),
        })
    return pd.DataFrame(rows, columns=columns).sort_values("paper_id").reset_index(drop=True)
