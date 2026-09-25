"""Great Expectations quality gate and freshness SLA reporting for paper data."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

import great_expectations as gx
from great_expectations import expectations as gxe
import pandas as pd

from core.config import Settings


MIN_ROWS = 5
MAX_ROWS = 5_000
MIN_SUMMARY_LENGTH = 30
STALE_RATE_LIMIT = 0.25
REQUIRED_FIELDS = ("paper_id", "title", "summary", "text_for_embedding")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _json_default(value: Any) -> str:
    """Serialize pandas/numpy values that can occur in GE validation output."""
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return str(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=_json_default), encoding="utf-8")


def _freshness_payload(df: pd.DataFrame, settings: Settings, run_date: datetime) -> dict[str, Any]:
    """Build the SLA measurements without writing an artifact."""
    total_rows = len(df)
    threshold_days = settings.freshness_threshold_days
    published_dates = (
        pd.to_datetime(df["published"], errors="coerce", utc=True)
        if "published" in df.columns
        else pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")
    )
    # Recalculate from the publication date so a corrupted date cannot be hidden
    # by an unchanged age_days helper column.
    ages = (pd.Timestamp(run_date.date(), tz="UTC") - published_dates).dt.days
    invalid_date_rows = int(published_dates.isna().sum())
    stale_rows = int((ages > threshold_days).sum())
    stale_rate = stale_rows / total_rows if total_rows else 0.0
    valid_dates = published_dates.dropna()
    oldest = valid_dates.min().isoformat() if not valid_dates.empty else None
    latest = valid_dates.max().isoformat() if not valid_dates.empty else None

    return {
        "run_date": run_date.isoformat(),
        "thresholds": {"stale_after_days": threshold_days, "maximum_stale_rate": STALE_RATE_LIMIT},
        "total_rows": total_rows,
        "stale_rows": stale_rows,
        "invalid_date_rows": invalid_date_rows,
        "fresh_rows": total_rows - stale_rows,
        "stale_rate": stale_rate,
        "is_fresh": total_rows > 0 and invalid_date_rows == 0 and stale_rate <= STALE_RATE_LIMIT,
        "oldest_published": oldest,
        "latest_published": latest,
    }


def _report_path(settings: Settings, report_name: str) -> Path:
    name = Path(report_name).name
    if name.endswith(".json"):
        return settings.paths.quality_dir / name
    if name.endswith("_quality_report"):
        return settings.paths.quality_dir / f"{name}.json"
    return settings.paths.quality_dir / f"{name}_quality_report.json"


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Validate papers with GX 1.x and write a report with individual results."""
    run_date = _utc_now()
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_definition = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_definition.get_batch(batch_parameters={"dataframe": df})

    suite = gx.ExpectationSuite(name="papers_quality_suite")
    suite.add_expectation(gxe.ExpectTableRowCountToBeBetween(min_value=MIN_ROWS, max_value=MAX_ROWS))
    for column in REQUIRED_FIELDS:
        if column in df.columns:
            suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column=column))
            suite.add_expectation(gxe.ExpectColumnValuesToMatchRegex(column=column, regex=r".*\S.*"))
    if "paper_id" in df.columns:
        suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(column="paper_id"))
    if "summary" in df.columns:
        suite.add_expectation(
            gxe.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=MIN_SUMMARY_LENGTH)
        )

    validation_dict = batch.validate(suite).to_json_dict()
    missing_columns = [column for column in REQUIRED_FIELDS if column not in df.columns]
    report = {
        "success": bool(validation_dict.get("success", False)) and not missing_columns,
        "run_date": run_date.isoformat(),
        "thresholds": {
            "min_rows": MIN_ROWS,
            "max_rows": MAX_ROWS,
            "min_summary_length": MIN_SUMMARY_LENGTH,
            "required_fields": list(REQUIRED_FIELDS),
        },
        "row_count": len(df),
        "missing_required_columns": missing_columns,
        "expectation_results": validation_dict.get("results", []),
        "freshness": _freshness_payload(df, settings, run_date),
    }
    _write_json(_report_path(settings, report_name), report)
    return report


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Calculate the 180-day SLA and save its JSON report."""
    report = _freshness_payload(df, settings, _utc_now())
    _write_json(Path(report_path), report)
    return report
