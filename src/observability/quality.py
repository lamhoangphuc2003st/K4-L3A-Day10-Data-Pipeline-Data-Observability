from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import great_expectations as gx
import pandas as pd

from core.config import Settings
from core.utils import write_json


logger = logging.getLogger(__name__)


def _freshness_summary(df: pd.DataFrame, settings: Settings) -> dict[str, Any]:
    threshold = settings.freshness_threshold_days
    ages = pd.to_numeric(df.get("age_days", pd.Series(index=df.index, dtype=float)), errors="coerce")
    valid_ages = ages.notna() & ~ages.isin([float("inf"), float("-inf")])
    unknown_rows = int((~valid_ages).sum())
    stale_rows = int((ages.gt(threshold) & valid_ages).sum())
    total_rows = len(df)
    stale_ratio = stale_rows / total_rows if total_rows else 0.0
    dates = pd.to_datetime(
        df.get("published", pd.Series(index=df.index, dtype=object)),
        errors="coerce", utc=True, format="mixed",
    ).dropna()
    warnings = []
    if stale_ratio > 0.25:
        warnings.append(
            f"Stale data: {stale_ratio:.1%} of papers are older than {threshold} days "
            "(limit: 25%). Update the corpus with newer papers."
        )
    if unknown_rows:
        warnings.append(f"Freshness is unknown for {unknown_rows} rows with missing or invalid age_days.")
    if not total_rows:
        warnings.append("Freshness cannot be established for an empty dataset.")
    return {
        "latest_published": dates.max().date().isoformat() if not dates.empty else None,
        "oldest_published": dates.min().date().isoformat() if not dates.empty else None,
        "threshold_days": threshold,
        "max_stale_ratio": 0.25,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": stale_ratio,
        "unknown_age_rows": unknown_rows,
        "is_fresh": bool(total_rows and not unknown_rows and stale_ratio <= 0.25),
        "warnings": warnings,
    }


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Validate through GX 1.x and persist a JSON quality report.

    ``success`` reflects the mandatory expectations; freshness is a separate
    warning. Blank required strings count as nulls, without changing the input.
    Missing columns are checked as all-null columns so they fail the gate.
    """
    if not report_name or Path(report_name).name != report_name:
        raise ValueError("report_name must be a filename within the quality directory")
    filename = report_name if report_name.endswith(".json") else f"{report_name}.json"
    required_columns = ["paper_id", "title", "text_for_embedding", "summary"]
    checked_df = df.copy(deep=True)
    missing_columns = [column for column in required_columns if column not in checked_df]
    for column in required_columns:
        if column not in checked_df:
            checked_df[column] = None
        else:
            checked_df[column] = checked_df[column].replace(r"^\s*$", None, regex=True)

    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": checked_df})
    expectations = [
        gx.expectations.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000),
        *[gx.expectations.ExpectColumnValuesToNotBeNull(column=column) for column in required_columns],
        gx.expectations.ExpectColumnValuesToBeUnique(column="paper_id"),
        gx.expectations.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30),
    ]
    results = [batch.validate(expectation).to_json_dict() for expectation in expectations]
    successful = sum(bool(result["success"]) for result in results)
    freshness = _freshness_summary(df, settings)
    report = {
        "report_name": report_name,
        "success": successful == len(results) and not missing_columns,
        "row_count": len(df),
        "missing_columns": missing_columns,
        "statistics": {
            "evaluated_expectations": len(results),
            "successful_expectations": successful,
            "unsuccessful_expectations": len(results) - successful,
        },
        "results": results,
        "freshness": freshness,
        "warnings": freshness["warnings"],
    }
    write_json(settings.paths.quality_dir / filename, report)
    for warning in report["warnings"]:
        logger.warning(warning)
    return report


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Write freshness metrics using the configured age limit (default 180 days)."""
    report = _freshness_summary(df, settings)
    write_json(Path(report_path), report)
    for warning in report["warnings"]:
        logger.warning(warning)
    return report
