from __future__ import annotations

from datetime import datetime

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord

MIN_SUMMARY_CHARS = 30


def build_text_for_embedding(row: pd.Series | dict) -> str:
    return (
        f"Title: {row['title']}\n"
        f"Authors: {row['authors_joined']}\n"
        f"Published: {row['published']}\n"
        f"Categories: {row['categories_joined']}\n"
        f"Summary: {row['summary']}"
    )


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    rows = []
    for record in records:
        authors = [normalize_whitespace(a) for a in record.authors if a]
        categories = [normalize_whitespace(c) for c in record.categories if c]
        published = pd.to_datetime(record.published, errors="coerce")
        updated = pd.to_datetime(record.updated, errors="coerce")
        if pd.isna(published):
            continue
        rows.append(
            {
                "paper_id": normalize_whitespace(record.paper_id),
                "title": normalize_whitespace(record.title),
                "summary": normalize_whitespace(record.summary),
                "authors": authors,
                "categories": categories,
                "primary_category": normalize_whitespace(record.primary_category),
                "published": published.date().isoformat(),
                "updated": (updated if not pd.isna(updated) else published).date().isoformat(),
                "abs_url": record.abs_url,
                "pdf_url": record.pdf_url,
                "comment": record.comment,
            }
        )

    columns = [
        "paper_id", "title", "summary", "authors", "categories", "primary_category",
        "published", "updated", "abs_url", "pdf_url", "comment",
    ]
    df = pd.DataFrame(rows, columns=columns)
    if df.empty:
        return df.assign(
            age_days=[], authors_joined=[], categories_joined=[], summary_chars=[], text_for_embedding=[]
        )

    run_day = pd.Timestamp(run_date.date())
    df["age_days"] = (run_day - pd.to_datetime(df["published"])).dt.days.astype(int)
    df["authors_joined"] = df["authors"].apply(compact_join)
    df["categories_joined"] = df["categories"].apply(compact_join)
    df["summary_chars"] = df["summary"].str.len()
    df["text_for_embedding"] = df.apply(build_text_for_embedding, axis=1)

    df = df[(df["title"] != "") & (df["summary_chars"] >= MIN_SUMMARY_CHARS)]
    df = df.drop_duplicates(subset="paper_id", keep="first")
    return df.sort_values(["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
