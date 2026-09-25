from __future__ import annotations

from typing import Any

import great_expectations as gx
import great_expectations.expectations as gxe
import pandas as pd

from core.config import Settings
from core.utils import write_json

STALE_RATIO_THRESHOLD = 0.25
MIN_SUMMARY_LENGTH = 30


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    total = int(len(df))
    stale = int((df["age_days"] > settings.freshness_threshold_days).sum()) if total else 0
    stale_ratio = stale / total if total else 1.0
    payload = {
        "latest_published": str(df["published"].max()) if total else None,
        "oldest_published": str(df["published"].min()) if total else None,
        "stale_threshold_days": settings.freshness_threshold_days,
        "stale_rows": stale,
        "total_rows": total,
        "stale_ratio": round(stale_ratio, 4),
        "max_stale_ratio": STALE_RATIO_THRESHOLD,
        "is_fresh": stale_ratio <= STALE_RATIO_THRESHOLD,
    }
    write_json(report_path, payload)
    return payload


def _report_path(settings: Settings, report_name: str):
    paths = settings.paths
    if report_name == "baseline":
        return paths.baseline_quality_report
    if report_name == "corrupted":
        return paths.corrupted_quality_report
    return paths.quality_dir / f"{report_name}_quality_report.json"


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """GX 1.x quality gate (ephemeral context) + freshness SLA."""
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    expectations = [
        ("row_count_between_5_and_5000", gxe.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000)),
        *[
            (f"{col}_not_null", gxe.ExpectColumnValuesToNotBeNull(column=col))
            for col in ("paper_id", "title", "text_for_embedding")
        ],
        ("paper_id_unique", gxe.ExpectColumnValuesToBeUnique(column="paper_id")),
        (
            f"summary_length_min_{MIN_SUMMARY_LENGTH}",
            gxe.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=MIN_SUMMARY_LENGTH),
        ),
    ]

    checks = []
    for name, expectation in expectations:
        result = batch.validate(expectation)
        details = result.result or {}
        checks.append(
            {
                "check": name,
                "success": bool(result.success),
                "unexpected_count": details.get("unexpected_count"),
                "observed_value": details.get("observed_value"),
            }
        )

    freshness = build_freshness_report(
        df, settings, settings.paths.freshness_report
        if report_name == "baseline"
        else settings.paths.quality_dir / f"{report_name}_freshness_report.json",
    )
    report = {
        "report_name": report_name,
        "success": all(check["success"] for check in checks),
        "failed_checks": [check["check"] for check in checks if not check["success"]],
        "checks": checks,
        "freshness": freshness,
        "alert": (not all(c["success"] for c in checks)) or (not freshness["is_fresh"]),
    }
    write_json(_report_path(settings, report_name), report)
    return report
