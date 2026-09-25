from __future__ import annotations

from hashlib import sha256
from itertools import combinations
from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import normalize_whitespace, write_json


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Build a deterministic, extractive benchmark from real paper metadata.

    Each complete paper contributes four single-document questions. Disjoint
    cross-disciplinary pairs contribute multi-hop comparisons grounded in both
    abstracts, without inventing relationships or research findings. At least
    two complete papers with distinct subject areas are needed for all types.
    ``question_type`` is retained as an alias for the existing evaluator.
    """
    required = {"paper_id", "title", "summary", "authors", "categories", "published"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing benchmark columns: {', '.join(sorted(missing))}")

    def text(value: object) -> str:
        return normalize_whitespace(value) if isinstance(value, str) else ""

    def names(values: object) -> list[str]:
        if not isinstance(values, (list, tuple)):
            return []
        return list(dict.fromkeys(name for value in values if (name := text(value))))

    papers = []
    seen = set()
    for row in df.to_dict(orient="records"):
        paper_id = text(row["paper_id"])
        title, summary = text(row["title"]), text(row["summary"])
        authors, categories = names(row["authors"]), names(row["categories"])
        published = pd.to_datetime(row["published"], errors="coerce", utc=True)
        if not all((paper_id, title, summary, authors, categories)) or pd.isna(published):
            continue
        if paper_id.lower() in seen:
            continue
        seen.add(paper_id.lower())
        papers.append({
            "paper_id": paper_id, "title": title, "summary": summary,
            "authors": authors, "categories": categories,
            "published": published.strftime("%Y-%m"),
        })
    papers.sort(key=lambda paper: paper["paper_id"])
    if len(papers) < 2:
        raise ValueError("At least two distinct papers with complete metadata are required.")

    samples = []

    def add(kind: str, question: str, answer: str, doc_ids: list[str]) -> None:
        fingerprint = sha256("\n".join(doc_ids).encode("utf-8")).hexdigest()[:16]
        samples.append({
            "id": f"{kind}-{fingerprint}",
            "type": kind,
            "question_type": kind,
            "question": question,
            "ground_truth": answer,
            "ground_truth_doc_ids": doc_ids,
        })

    for paper in papers:
        title = paper["title"]
        doc_ids = [paper["paper_id"]]
        add("summary", f"Summarize the main research described in '{title}'.", paper["summary"], doc_ids)
        add("authors", f"Who authored the study '{title}'?", ", ".join(paper["authors"]), doc_ids)
        add("date", f"In which year and month was '{title}' published?", paper["published"], doc_ids)
        add("category", f"What categories of expertise does '{title}' belong to?", ", ".join(paper["categories"]), doc_ids)

    paired = set()
    for left, right in combinations(papers, 2):
        if left["paper_id"] in paired or right["paper_id"] in paired:
            continue
        left_categories = {category.casefold() for category in left["categories"]}
        right_categories = {category.casefold() for category in right["categories"]}
        left_topic = next((category for category in left["categories"] if category.casefold() not in right_categories), None)
        right_topic = next((category for category in right["categories"] if category.casefold() not in left_categories), None)
        if not left_topic or not right_topic:
            continue
        add(
            "multi_hop",
            f"Across {left_topic} and {right_topic}, what research does '{left['title']}' "
            f"describe, and what research does '{right['title']}' describe? "
            "Present both contributions with their respective fields.",
            f"{left_topic} — {left['title']}: {left['summary']}\n"
            f"{right_topic} — {right['title']}: {right['summary']}",
            [left["paper_id"], right["paper_id"]],
        )
        paired.update((left["paper_id"], right["paper_id"]))
    if not paired:
        raise ValueError("Multi-hop questions require two papers with distinct subject areas.")

    write_json(Path(output_path), samples)
    return samples
