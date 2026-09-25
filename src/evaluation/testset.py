from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json

MIN_DOCUMENTS = 10
# 10 questions across 4 types.
QUESTION_PLAN = ["summary", "authors", "date", "categories", "summary",
                 "authors", "date", "categories", "summary", "authors"]


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    # Apostrophes in titles would break the '<title>' pattern the QA agent parses.
    pool = df[~df["title"].str.contains("'")].drop_duplicates("paper_id")
    pool = pool.sort_values(["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
    if len(pool) < MIN_DOCUMENTS:
        raise ValueError(f"Need at least {MIN_DOCUMENTS} usable documents, got {len(pool)}.")

    # Evenly spread picks so both newest and oldest papers are covered.
    step = len(pool) / len(QUESTION_PLAN)
    picks = [pool.iloc[int(i * step)] for i in range(len(QUESTION_PLAN))]

    test_set: list[dict[str, Any]] = []
    for number, (qtype, row) in enumerate(zip(QUESTION_PLAN, picks), start=1):
        title = row["title"]
        if qtype == "summary":
            question = f"What is the summary of the paper '{title}'?"
            truth = first_sentence(row["summary"])
        elif qtype == "authors":
            question = f"Who authored the paper '{title}'?"
            truth = row["authors_joined"]
        elif qtype == "date":
            question = f"When was the paper '{title}' published?"
            truth = row["published"]
        else:
            question = f"What categories does the paper '{title}' belong to?"
            truth = row["categories_joined"]
        test_set.append(
            {
                "id": f"eval_{number:03d}",
                "question_type": qtype,
                "question": question,
                "ground_truth": truth,
                "ground_truth_doc_ids": [row["paper_id"]],
            }
        )

    write_json(output_path, test_set)
    return test_set
