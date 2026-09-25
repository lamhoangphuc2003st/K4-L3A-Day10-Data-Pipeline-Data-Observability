from __future__ import annotations

from datetime import datetime

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord


def embedding_text(row: dict) -> str:
    return "\n".join((
        f"Title: {row['title']}",
        f"Authors: {row['authors_joined']}",
        f"Published: {row['published']}",
        f"Categories: {row['categories_joined']}",
        f"Summary: {row['summary']}",
    ))


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    rows = []
    for record in records:
        published = pd.to_datetime(record.published, errors="coerce", utc=True)
        if pd.isna(published):
            continue
        row = {
            "paper_id": normalize_whitespace(record.paper_id),
            "title": normalize_whitespace(record.title),
            "summary": normalize_whitespace(record.summary),
            "authors_joined": compact_join(normalize_whitespace(x) for x in record.authors),
            "categories_joined": compact_join(normalize_whitespace(x) for x in record.categories),
            "primary_category": normalize_whitespace(record.primary_category),
            "published": published.date().isoformat(),
            "updated": record.updated,
            "abs_url": record.abs_url,
            "pdf_url": record.pdf_url,
            "comment": record.comment,
        }
        if not row["paper_id"] or not row["title"]:
            continue
        row["age_days"] = (run_date.date() - published.date()).days
        row["summary_chars"] = len(row["summary"])
        row["text_for_embedding"] = embedding_text(row)
        rows.append(row)
    if not rows:
        raise ValueError("No valid Crossref records remain after cleaning")
    return (pd.DataFrame(rows).drop_duplicates(subset="paper_id")
            .sort_values("paper_id").reset_index(drop=True))
