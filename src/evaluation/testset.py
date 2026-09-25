from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json


QUESTION_TYPES = ("summary", "authors", "date", "categories")


def build_test_set(df: pd.DataFrame, output_path: Path) -> list[dict[str, Any]]:
    required = {"paper_id", "title", "summary", "authors_joined", "categories_joined", "published"}
    if len(df) < 10 or required - set(df.columns):
        raise ValueError(f"Test set needs 10 papers and columns: {sorted(required)}")
    rows = df.sort_values(["published", "paper_id"], ascending=[False, True]).head(10)
    questions = []
    for number, row in enumerate(rows.to_dict("records"), 1):
        kind = QUESTION_TYPES[(number - 1) % len(QUESTION_TYPES)]
        title = row["title"]
        if kind == "summary":
            question, answer = f"What is the summary of the paper '{title}'?", first_sentence(row["summary"])
        elif kind == "authors":
            question, answer = f"Who authored the paper '{title}'?", row["authors_joined"]
        elif kind == "date":
            question, answer = f"When was the paper '{title}' published?", row["published"]
        else:
            question, answer = f"What categories describe the paper '{title}'?", row["categories_joined"]
        if not answer:
            raise ValueError(f"Paper {row['paper_id']} has no {kind} ground truth")
        questions.append({
            "id": f"eval_{number:03d}", "question_type": kind, "question": question,
            "ground_truth": answer, "ground_truth_doc_ids": [row["paper_id"]],
        })
    write_json(output_path, questions)
    return questions
