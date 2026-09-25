from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from core.utils import write_json
from ingestion.cleaning import embedding_text


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path: Path) -> pd.DataFrame:
    if len(df) < 10:
        raise ValueError("Corruption experiment requires at least 10 clean papers")
    result = df.copy(deep=True).sort_values(["published", "paper_id"], ascending=[False, True])
    log = []

    def record(kind: str, changes: list[dict]) -> None:
        log.append({"corruption_type": kind, "count": len(changes), "affected_records": changes})

    drop_count = max(1, round(len(result) * 0.2))
    dropped = result.head(drop_count)
    record("drop_latest_records", [
        {"paper_id": row.paper_id, "before": row.published, "after": None}
        for row in dropped.itertuples()
    ])
    result = result.iloc[drop_count:].copy()
    targets = list(result.index)

    changes = []
    for idx in targets[:2]:
        changes.append({"paper_id": result.at[idx, "paper_id"],
                        "before": result.at[idx, "summary"], "after": ""})
        result.at[idx, "summary"] = ""
    record("blank_summary", changes)

    changes = []
    for idx in targets[2:4]:
        before = result.at[idx, "summary"]
        after = "@@@ NOISE ### " + before
        changes.append({"paper_id": result.at[idx, "paper_id"], "before": before, "after": after})
        result.at[idx, "summary"] = after
    record("inject_noise", changes)

    changes = []
    for idx in targets[4:6]:
        before = result.at[idx, "title"]
        after = before[:6]
        changes.append({"paper_id": result.at[idx, "paper_id"], "before": before, "after": after})
        result.at[idx, "title"] = after
    record("truncate_title", changes)

    changes = []
    stale_date = date.today() - timedelta(days=365)
    for idx in targets[:8]:
        before = result.at[idx, "published"]
        result.at[idx, "published"] = stale_date.isoformat()
        result.at[idx, "age_days"] = 365
        changes.append({"paper_id": result.at[idx, "paper_id"], "before": before,
                        "after": stale_date.isoformat()})
    record("stale_date", changes)

    duplicate_rows = result.loc[targets[-2:]].copy()
    record("duplicate_rows", [
        {"paper_id": row.paper_id, "before": 1, "after": 2}
        for row in duplicate_rows.itertuples()
    ])
    result = pd.concat([result, duplicate_rows], ignore_index=True)
    result["summary_chars"] = result["summary"].str.len()
    result["text_for_embedding"] = [embedding_text(row) for row in result.to_dict("records")]
    write_json(output_log_path, log)
    return result
