from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
import re
from typing import Any

import pandas as pd

from core.utils import first_sentence, read_json, write_json


@dataclass(frozen=True)
class TestSet:
    samples: list[dict[str, Any]]


def _sample(number: int, kind: str, question: str, answer: str, ids: list[str]) -> dict[str, Any]:
    return {
        "id": f"eval_{number:03d}", "type": kind, "question_type": kind,
        "question": question, "ground_truth": answer,
        "ground_truth_doc_ids": ids,
    }


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Create the five deterministic PHA 3 questions from clean records."""
    if len(df) < 5 or df["paper_id"].nunique() < 5:
        raise ValueError("The benchmark needs at least five unique papers")
    papers = df.sort_values("paper_id").reset_index(drop=True)
    summary, category, date = papers.iloc[0], papers.iloc[2], papers.iloc[3]
    newest = papers.sort_values(["published", "paper_id"], ascending=[False, True]).iloc[0]
    pair = next((
        (left, right, common)
        for (_, left), (_, right) in combinations(papers.iterrows(), 2)
        if (common := sorted(set(left["categories"]) & set(right["categories"])))
    ), None)
    shared_term = None
    if pair is None:
        stopwords = {"the", "and", "for", "with", "from", "into", "via", "using", "based", "this", "that"}
        pair = next((
            (left, right, [])
            for (_, left), (_, right) in combinations(papers.iterrows(), 2)
            if set(re.findall(r"[a-z0-9]+", left["title"].lower()))
            & set(re.findall(r"[a-z0-9]+", right["title"].lower())) - stopwords
        ), None)
        if pair is None:
            raise ValueError("The multi-hop question needs two papers with overlapping source text")
        left, right, _ = pair
        left_terms = set(re.findall(r"[a-z0-9]+", left["title"].lower())) - stopwords
        right_terms = set(re.findall(r"[a-z0-9]+", right["title"].lower())) - stopwords
        shared_term = sorted(left_terms & right_terms, key=lambda term: (-len(term), term))[0]
        common = []
    else:
        left, right, common = pair
    category_truth = category["categories_joined"] or "No subject categories are listed by Crossref."
    multi_question = (
        f"Which research area is shared by the papers '{left['title']}' and '{right['title']}'?"
        if common else
        f"Which term appears in both paper titles '{left['title']}' and '{right['title']}'?"
    )
    multi_truth = ", ".join(common) if common else shared_term
    samples = [
        _sample(1, "summary", f"What is the summary of the paper '{summary['title']}'?",
                first_sentence(summary["summary"]), [summary["paper_id"]]),
        _sample(2, "authors", f"Who authored the paper '{newest['title']}'?",
                newest["authors_joined"], [newest["paper_id"]]),
        _sample(3, "date", f"When was the paper '{date['title']}' published?",
                date["published"], [date["paper_id"]]),
        _sample(4, "category", f"Which subject categories does Crossref list for the paper '{category['title']}'?",
                category_truth, [category["paper_id"]]),
        _sample(5, "multi_hop", multi_question, multi_truth,
                [left["paper_id"], right["paper_id"]]),
    ]
    write_json(Path(output_path), samples)
    return samples


def load_or_create_test_set(df: pd.DataFrame, output_path, refresh: bool = False) -> TestSet:
    path = Path(output_path)
    if path.exists() and not refresh:
        samples = read_json(path)
        expected = {"summary", "authors", "date", "category", "multi_hop"}
        ids = set(df["paper_id"])
        if (isinstance(samples, list) and len(samples) == 5
                and {item.get("type") for item in samples} == expected
                and all(set(item.get("ground_truth_doc_ids", [])) <= ids for item in samples)):
            return TestSet(samples)
    return TestSet(build_test_set(df, path))
