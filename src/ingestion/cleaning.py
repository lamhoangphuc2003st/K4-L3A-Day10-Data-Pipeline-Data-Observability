from __future__ import annotations

from dataclasses import asdict, fields
from datetime import datetime

import pandas as pd

from core.utils import normalize_whitespace
from ingestion.crossref import PaperRecord


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Build embedding-ready rows, retaining the first valid row per paper ID.

    Dates use UTC (including naive inputs) and are stored as ISO calendar dates.
    Rows need an ID, title, summary, and valid publication date. Missing/invalid
    update dates fall back to publication dates. Future dates retain negative
    ages so downstream quality checks can detect them.
    """
    run_timestamp = pd.to_datetime(run_date, utc=True, errors="raise")
    if pd.isna(run_timestamp):
        raise ValueError("run_date must be a valid datetime")

    def clean_text(value: object) -> str:
        return normalize_whitespace(value) if isinstance(value, str) else ""

    def clean_list(values: list[str]) -> list[str]:
        return list(dict.fromkeys(text for value in values or [] if (text := clean_text(value))))

    rows = []
    seen = set()
    for record in records:
        paper_id = clean_text(record.paper_id).lower()
        title = clean_text(record.title)
        summary = clean_text(record.summary)
        published = pd.to_datetime(record.published, utc=True, errors="coerce")
        if not paper_id or not title or not summary or pd.isna(published) or paper_id in seen:
            continue
        # Publication is a calendar date; calculate age from its UTC midnight.
        published = published.normalize()
        updated = pd.to_datetime(record.updated, utc=True, errors="coerce")
        if pd.isna(updated):
            updated = published
        authors = clean_list(record.authors)
        categories = clean_list(record.categories)
        authors_joined = ", ".join(authors)
        categories_joined = ", ".join(categories)
        published_iso = published.date().isoformat()
        row = asdict(record)
        row.update(
            paper_id=paper_id, title=title, summary=summary,
            authors=authors, categories=categories,
            primary_category=clean_text(record.primary_category) or (categories[0] if categories else ""),
            published=published_iso, updated=updated.date().isoformat(),
            age_days=(run_timestamp - published).days,
            authors_joined=authors_joined, categories_joined=categories_joined,
            summary_chars=len(summary),
            text_for_embedding=(
                f"Title: {title}\n"
                f"Authors: {authors_joined}\n"
                f"Published: {published_iso}\n"
                f"Categories: {categories_joined}\n"
                f"Summary: {summary}"
            ),
        )
        rows.append(row)
        seen.add(paper_id)

    columns = [field.name for field in fields(PaperRecord)] + [
        "age_days", "authors_joined", "categories_joined", "summary_chars", "text_for_embedding",
    ]
    frame = pd.DataFrame(rows, columns=columns).astype({"age_days": "int64", "summary_chars": "int64"})
    return frame.sort_values(["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
