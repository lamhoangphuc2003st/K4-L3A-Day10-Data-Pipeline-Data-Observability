from __future__ import annotations

import math

import pandas as pd

from core.utils import write_json
from ingestion.cleaning import build_text_for_embedding

SEED = 42
NOISE = " ### @@ xqzv 9f8a7 ~~~ lorem-ipsum-garbage ###"
STALE_SHIFT_DAYS = 365


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Inject 6 deterministic data faults and write them to `output_log_path`."""
    out = df.sort_values(["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
    log: list[dict] = []

    # 1. Drop the 20% latest records (lost fresh data).
    n_drop = max(1, math.ceil(len(out) * 0.2))
    dropped = out.head(n_drop)["paper_id"].tolist()
    out = out.iloc[n_drop:].reset_index(drop=True)
    log.append({"type": "drop_latest_records", "count": n_drop, "paper_ids": dropped})

    # Remaining faults use a seeded shuffle so every run is reproducible.
    order = out.sample(frac=1.0, random_state=SEED).index.tolist()
    k = max(1, len(out) // 8)
    picks = {
        "blank_summary": order[0:k],
        "inject_noise": order[k:2 * k],
        "truncate_title": order[2 * k:3 * k],
        "stale_date": order[3 * k:4 * k + 1],
    }

    out.loc[picks["blank_summary"], "summary"] = ""
    out.loc[picks["inject_noise"], "summary"] = out.loc[picks["inject_noise"], "summary"] + NOISE
    out.loc[picks["truncate_title"], "title"] = out.loc[picks["truncate_title"], "title"].str[:6]
    shifted = pd.to_datetime(out.loc[picks["stale_date"], "published"]) - pd.Timedelta(days=STALE_SHIFT_DAYS)
    out.loc[picks["stale_date"], "published"] = shifted.dt.date.astype(str)
    out.loc[picks["stale_date"], "age_days"] = out.loc[picks["stale_date"], "age_days"] + STALE_SHIFT_DAYS

    for name, idx in picks.items():
        log.append({"type": name, "count": len(idx), "paper_ids": out.loc[idx, "paper_id"].tolist()})

    out["summary_chars"] = out["summary"].str.len()

    # 6. Duplicate rows.
    dup_idx = order[4 * k + 1:5 * k + 2] or order[:1]
    out = pd.concat([out, out.loc[dup_idx]], ignore_index=True)
    log.append({"type": "duplicate_rows", "count": len(dup_idx), "paper_ids": out.loc[dup_idx, "paper_id"].tolist()})

    out["text_for_embedding"] = out.apply(build_text_for_embedding, axis=1)
    write_json(output_log_path, {"seed": SEED, "rows_before": len(df), "rows_after": len(out), "corruptions": log})
    return out
