from __future__ import annotations

from pathlib import Path
from typing import Any

import great_expectations as gx
from great_expectations import expectations as ge
import pandas as pd

from core.config import Settings
from core.utils import read_json, write_json


REQUIRED_COLUMNS = ("paper_id", "title", "summary", "text_for_embedding", "age_days", "published")


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    missing = sorted(set(REQUIRED_COLUMNS) - set(df.columns))
    if missing:
        result = {"success": False, "error": f"Missing columns: {', '.join(missing)}", "checks": []}
    else:
        context = gx.get_context(mode="ephemeral")
        source = context.data_sources.add_pandas(name="papers_source")
        asset = source.add_dataframe_asset(name="papers_asset")
        batch = asset.add_batch_definition_whole_dataframe("papers_batch").get_batch(
            batch_parameters={"dataframe": df}
        )
        expectations = [ge.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000)]
        expectations += [ge.ExpectColumnValuesToNotBeNull(column=name)
                         for name in ("paper_id", "title", "text_for_embedding")]
        expectations += [
            ge.ExpectColumnValuesToBeUnique(column="paper_id"),
            ge.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30),
        ]
        checks = []
        for expectation in expectations:
            validation = batch.validate(expectation)
            checks.append({
                "expectation": type(expectation).__name__,
                "column": getattr(expectation, "column", None),
                "success": bool(validation.success),
                "result": validation.result,
            })
        checks.extend([
            {"expectation": "NoNoiseRuns", "success": not df["summary"].str.contains(r"[^\w\s]{3,}", regex=True).any()},
            {"expectation": "TitleLengthAtLeast8", "success": bool(df["title"].str.len().ge(8).all())},
        ])
        if settings.paths.raw_records_json.exists():
            expected_ids = {record["paper_id"] for record in read_json(settings.paths.raw_records_json)}
            missing_ids = sorted(expected_ids - set(df["paper_id"]))
            checks.append({"expectation": "RawSourceCoverage", "success": not missing_ids,
                           "missing_paper_ids": missing_ids})
        result = {"success": all(check["success"] for check in checks), "checks": checks}
    write_json(settings.paths.quality_dir / f"{report_name}_quality_report.json", result)
    return result


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path: Path) -> dict[str, Any]:
    if "age_days" not in df or "published" not in df:
        raise ValueError("Freshness requires age_days and published columns")
    ages = pd.to_numeric(df["age_days"], errors="coerce")
    stale = int((ages > settings.freshness_threshold_days).sum())
    total = len(df)
    dates = pd.to_datetime(df["published"], errors="coerce")
    result = {
        "latest_published": dates.max().date().isoformat() if dates.notna().any() else None,
        "oldest_published": dates.min().date().isoformat() if dates.notna().any() else None,
        "stale_rows": stale,
        "total_rows": total,
        "stale_fraction": stale / total if total else 1.0,
        "threshold_days": settings.freshness_threshold_days,
        "max_stale_fraction": 0.25,
        "is_fresh": bool(total > 0 and ages.notna().all() and stale / total <= 0.25),
    }
    write_json(report_path, result)
    return result
