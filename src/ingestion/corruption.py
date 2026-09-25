from __future__ import annotations

import json
from math import ceil
from pathlib import Path

import pandas as pd

from core.utils import now_utc, write_json


NOISE = "zxqv_9f3a @@## 000111 xxNULLxx qqqvvv !!!"


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Inject six reproducible faults into a copy and write an action audit.

    Drop 20% of the newest rows (always retain one). Blank, truncate, add
    noise, and duplicate 20% of retained rows each; age 40% to five calendar
    years before this run. Small inputs reuse rows across fault types.
    The original clean data and raw snapshots are never modified.
    """
    required = {
        "paper_id", "title", "summary", "published", "age_days", "summary_chars",
        "authors_joined", "categories_joined", "text_for_embedding",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing corruption columns: {', '.join(sorted(missing))}")
    if len(df) < 2:
        raise ValueError("At least two rows are required to inject all six corruption types.")
    work = df.copy(deep=True).reset_index(drop=True)
    dates = pd.to_datetime(work["published"], utc=True, errors="coerce", format="mixed")
    if dates.isna().any():
        raise ValueError("Corruption requires valid publication dates in the clean input.")
    run_date = pd.Timestamp(now_utc()).normalize()
    actions = []

    def snapshot(position: int) -> dict:
        # pandas handles NumPy scalar types for JSON audit records.
        return json.loads(work.loc[position].to_json(date_format="iso"))

    def embedding(position: int) -> str:
        row = work.loc[position]
        return (
            f"Title: {row['title']}\nAuthors: {row['authors_joined']}\n"
            f"Published: {row['published']}\nCategories: {row['categories_joined']}\n"
            f"Summary: {row['summary']}"
        )

    def change(action: str, positions: list[int], updates) -> None:
        details = []
        for position in positions:
            before = snapshot(position)
            for column, value in updates(position).items():
                work.at[position, column] = value
            work.at[position, "text_for_embedding"] = embedding(position)
            after = snapshot(position)
            changed = [column for column in after if before[column] != after[column]]
            details.append({
                "source_row": int(position), "paper_id": str(work.at[position, "paper_id"]),
                "before": {column: before[column] for column in changed},
                "after": {column: after[column] for column in changed},
            })
        actions.append({"action": action, "affected_rows": len(details), "changes": details})

    drop_count = min(len(work) - 1, max(1, len(work) // 5))
    dropped = dates.sort_values(ascending=False, kind="stable").index[:drop_count].tolist()
    actions.append({
        "action": "drop_latest_records", "affected_rows": drop_count,
        "changes": [{"source_row": int(position), "paper_id": str(work.at[position, "paper_id"]),
                     "before": snapshot(position), "after": None} for position in dropped],
    })
    work = work.drop(index=dropped)
    retained = work.index.tolist()
    count = max(1, ceil(len(work) * 0.2))

    def positions(offset: int, size: int = count) -> list[int]:
        return [retained[(offset + i) % len(retained)] for i in range(size)]

    change("blank_summary", positions(0), lambda _: {"summary": "", "summary_chars": 0})
    change("truncate_title", positions(count), lambda position: {"title": str(work.at[position, "title"])[:9]})
    stale_positions = positions(2 * count, ceil(len(work) * 0.4))
    stale_date = run_date - pd.DateOffset(years=5)
    change("stale_date", stale_positions, lambda _: {
        "published": stale_date.date().isoformat(), "age_days": (run_date - stale_date).days,
    })

    # Inject noise after rebuilding text so subsequent updates cannot erase it.
    details = []
    for position in positions(3 * count):
        before = work.at[position, "text_for_embedding"]
        after = f"{before}\n{NOISE} {NOISE} {NOISE}"
        work.at[position, "text_for_embedding"] = after
        details.append({
            "source_row": int(position), "paper_id": str(work.at[position, "paper_id"]),
            "before": {"text_for_embedding": before}, "after": {"text_for_embedding": after},
        })
    actions.append({"action": "inject_text_noise", "affected_rows": len(details), "changes": details})

    duplicate_positions = stale_positions[:count]
    duplicates = work.loc[duplicate_positions].copy(deep=True)
    actions.append({
        "action": "duplicate_rows", "affected_rows": len(duplicates),
        "changes": [{"source_row": int(position), "paper_id": str(work.at[position, "paper_id"]),
                     "output_row": len(work) + offset, "before": None, "after": snapshot(position)}
                    for offset, position in enumerate(duplicate_positions)],
    })
    corrupted = pd.concat([work, duplicates], ignore_index=True)
    write_json(Path(output_log_path), {
        "run_date": run_date.isoformat(), "input_rows": len(df), "output_rows": len(corrupted),
        "actions": actions,
    })
    return corrupted
