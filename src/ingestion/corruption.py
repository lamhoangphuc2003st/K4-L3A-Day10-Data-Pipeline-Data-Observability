from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from core.utils import write_json


def _embedding_text(row: pd.Series) -> str:
    return "\n".join((
        f"Title: {row['title']}",
        f"Authors: {row['authors_joined']}",
        f"Published: {row['published']}",
        f"Categories: {row['categories_joined']}",
        f"Summary: {row['summary']}",
    ))


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Apply six deterministic faults while keeping the output row count stable."""
    if len(df) < 10:
        raise ValueError("At least 10 clean records are needed for six corruption scenarios")
    corrupted = df.copy(deep=True).reset_index(drop=True)
    original_rows = len(corrupted)
    log: list[dict] = []

    # Remove the newest 20%; later duplicate injection restores the row count,
    # making this loss visible in record identity while preserving the lab's 24-row signal.
    drop_count = max(1, (original_rows + 4) // 5)
    newest = corrupted.sort_values(["published", "paper_id"], ascending=[False, True]).head(drop_count)
    dropped_ids = newest["paper_id"].tolist()
    corrupted = corrupted.loc[~corrupted["paper_id"].isin(dropped_ids)].reset_index(drop=True)
    log.append({"type": "drop_latest_records", "record_ids": dropped_ids, "count": drop_count})

    targets = corrupted.sort_values("paper_id").head(4)["paper_id"].tolist()
    blank_ids, noise_ids, title_id = targets[:2], targets[2:3], targets[3]

    def row_index(paper_id: str) -> int:
        return int(corrupted.index[corrupted["paper_id"] == paper_id][0])

    blank_changes = []
    for paper_id in blank_ids:
        i = row_index(paper_id)
        before = str(corrupted.at[i, "summary"])
        corrupted.at[i, "summary"] = ""
        corrupted.at[i, "summary_chars"] = 0
        blank_changes.append({"paper_id": paper_id, "before": before, "after": ""})
    log.append({"type": "blank_summary", "record_ids": blank_ids,
                "count": len(blank_ids), "changes": blank_changes})

    i = row_index(title_id)
    title_before = str(corrupted.at[i, "title"])
    title_after = title_before[:9]
    corrupted.at[i, "title"] = title_after
    log.append({"type": "truncate_title", "record_ids": [title_id],
                "before": title_before, "after": title_after, "max_length": 9})

    # Backdate enough records to cross the freshness SLA after restoring the row count.
    stale_ids = corrupted.sort_values("paper_id").head(max(7, (original_rows + 2) // 3))["paper_id"].tolist()
    today = datetime.now(timezone.utc).date()
    stale_changes = []
    for paper_id in stale_ids:
        i = row_index(paper_id)
        before = str(corrupted.at[i, "published"])
        after = (pd.Timestamp(before) - pd.DateOffset(years=5)).date().isoformat()
        corrupted.at[i, "published"] = after
        corrupted.at[i, "age_days"] = (today - pd.Timestamp(after).date()).days
        stale_changes.append({"paper_id": paper_id, "before": before, "after": after})
    log.append({"type": "stale_date", "record_ids": stale_ids,
                "years_backdated": 5, "changes": stale_changes})

    corrupted["text_for_embedding"] = corrupted.apply(_embedding_text, axis=1)
    noise_changes = []
    for paper_id in noise_ids:
        i = row_index(paper_id)
        before = str(corrupted.at[i, "text_for_embedding"])
        after = before + "\nXQZXQZ !!! 0000 ### [CORRUPTED]"
        corrupted.at[i, "text_for_embedding"] = after
        noise_changes.append({"paper_id": paper_id, "before": before, "after": after})
    log.append({"type": "inject_text_noise", "field": "text_for_embedding",
                "record_ids": noise_ids, "changes": noise_changes})

    duplicate_ids = corrupted.sort_values("paper_id").head(drop_count)["paper_id"].tolist()
    duplicates = corrupted.loc[corrupted["paper_id"].isin(duplicate_ids)].copy(deep=True)
    corrupted = pd.concat([corrupted, duplicates], ignore_index=True)
    log.append({"type": "duplicate_rows", "record_ids": duplicate_ids,
                "count": len(duplicates), "restores_dropped_row_count": True})

    if len(corrupted) != original_rows:
        raise RuntimeError(f"Corruption changed row count from {original_rows} to {len(corrupted)}")
    write_json(Path(output_log_path), {
        "source_rows": original_rows,
        "corrupted_rows": len(corrupted),
        "scenarios": log,
    })
    print(f"Corruption log written: {Path(output_log_path)} ({len(log)} scenarios)")
    print("Scenarios: " + ", ".join(item["type"] for item in log))
    return corrupted
