from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import PaperRecord, load_raw_records


RUN_DATE = datetime(2026, 5, 25, 12, tzinfo=UTC)


def paper(**changes):
    return replace(PaperRecord(
        paper_id="10.1234/test", title=" A\n title ", summary=" Some\t summary. ",
        authors=[" An  Nguyen ", "Bo Le", "An Nguyen", ""],
        categories=[" AI ", "Data\n Science"], primary_category=" AI ",
        published="2026-05-20", updated="2026-05-21T10:00:00Z",
        abs_url="https://doi.org/10.1234/test", pdf_url="", comment="source",
    ), **changes)


def test_embedding_text_and_age():
    record = paper()
    row = build_clean_dataframe([record], RUN_DATE).iloc[0]
    assert row.age_days == 5
    assert row.updated == "2026-05-21"
    assert row.authors == ["An Nguyen", "Bo Le"]
    assert row.categories == ["AI", "Data Science"]
    assert row.summary_chars == len("Some summary.")
    assert row.text_for_embedding == (
        "Title: A title\nAuthors: An Nguyen, Bo Le\nPublished: 2026-05-20\n"
        "Categories: AI, Data Science\nSummary: Some summary."
    )
    assert record.title == " A\n title "  # Do not mutate raw records.


def test_duplicates_keep_first_valid_row_and_sort():
    records = [paper(published="invalid"), paper(paper_id=" 10.1234/TEST "),
               paper(title="Later duplicate"), paper(paper_id="10.1234/new", published="2026-05-24")]
    frame = build_clean_dataframe(records, RUN_DATE)
    assert frame.paper_id.tolist() == ["10.1234/new", "10.1234/test"]
    assert frame.title.tolist() == ["A title", "A title"]
    assert frame.index.tolist() == [0, 1]


@pytest.mark.parametrize("changes", [{"paper_id": " "}, {"title": ""}, {"summary": " "}, {"published": "2026-02-30"}])
def test_invalid_rows_are_filtered(changes):
    assert build_clean_dataframe([paper(**changes)], RUN_DATE).empty


def test_empty_input_retains_schema():
    frame = build_clean_dataframe([], RUN_DATE)
    assert frame.empty
    assert {"paper_id", "published", "age_days", "text_for_embedding", "authors_joined"} <= set(frame.columns)
    assert pd.api.types.is_integer_dtype(frame.age_days)


def test_naive_dates_future_dates_and_missing_optional_metadata():
    row = build_clean_dataframe(
        [paper(published="2026-05-26", updated="invalid", authors=[], categories=[], primary_category="")],
        RUN_DATE.replace(tzinfo=None),
    ).iloc[0]
    assert row.age_days == -1
    assert row.updated == row.published == "2026-05-26"
    assert row.authors_joined == row.categories_joined == ""


def test_real_snapshot():
    path = Path(__file__).resolve().parents[1] / "data/raw/crossref_records.json"
    frame = build_clean_dataframe(load_raw_records(path), RUN_DATE)
    assert len(frame) == 24
    assert frame.paper_id.is_unique
    assert frame.text_for_embedding.str.count("\n").eq(4).all()
