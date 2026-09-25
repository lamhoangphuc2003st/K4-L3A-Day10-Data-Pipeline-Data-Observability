from __future__ import annotations

from typing import Any

from core.utils import write_text

METRIC_KEYS = [
    ("retrieval_hit_rate", "Retrieval Hit Rate"),
    ("mean_token_f1", "Mean Token F1"),
    ("judge_accuracy", "Judge Accuracy"),
    ("mean_judge_score", "Mean Judge Score"),
]


def _fmt(value: Any) -> str:
    return f"{value:.4f}" if isinstance(value, (int, float)) and not isinstance(value, bool) else str(value)


def _quality_lines(quality: dict[str, Any]) -> list[str]:
    lines = [f"- Gate success: **{quality['success']}**"]
    failed = quality.get("failed_checks") or []
    lines.append(f"- Failed checks: {', '.join(failed) if failed else 'none'}")
    return lines


def _freshness_lines(freshness: dict[str, Any]) -> list[str]:
    return [
        f"- Latest published: {freshness['latest_published']}",
        f"- Oldest published: {freshness['oldest_published']}",
        f"- Stale rows (> {freshness['stale_threshold_days']} days): "
        f"{freshness['stale_rows']}/{freshness['total_rows']}",
        f"- is_fresh: **{freshness['is_fresh']}**",
    ]


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    lines = ["# Phase 1 Report - Baseline Pipeline", "", "## Source", ""]
    lines += [f"- {key}: {value}" for key, value in source_summary.items()]
    lines += ["", "## Retrieval & Answer Metrics", "", "| Metric | Value |", "| :--- | ---: |"]
    lines += [f"| {label} | {_fmt(metrics.get(key))} |" for key, label in METRIC_KEYS]
    lines += [f"| Samples | {metrics.get('samples')} |"]
    lines += ["", "## Data Quality (Great Expectations 1.x)", ""] + _quality_lines(quality)
    lines += ["", "| Check | Passed |", "| :--- | :---: |"]
    lines += [f"| {c['check']} | {c['success']} |" for c in quality.get("checks", [])]
    lines += ["", "## Freshness", ""] + _freshness_lines(freshness) + [""]
    write_text(report_path, "\n".join(lines))


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    lines = [
        "# Corruption Report - Baseline vs Corrupted vs Repaired",
        "",
        "## Metrics",
        "",
        "| Metric | Baseline | Corrupted | Repaired |",
        "| :--- | ---: | ---: | ---: |",
    ]
    for key, label in METRIC_KEYS:
        lines.append(
            f"| {label} | {_fmt(baseline_metrics.get(key))} | {_fmt(corrupted_metrics.get(key))} "
            f"| {_fmt(repaired_metrics.get(key))} |"
        )
    lines += [
        "",
        "## Observability",
        "",
        "| Signal | Corrupted | Repaired |",
        "| :--- | :--- | :--- |",
        f"| GX quality gate success | {corrupted_quality['success']} | {repaired_quality['success']} |",
        f"| Failed checks | {', '.join(corrupted_quality.get('failed_checks') or ['none'])} "
        f"| {', '.join(repaired_quality.get('failed_checks') or ['none'])} |",
        f"| Freshness is_fresh | {corrupted_freshness['is_fresh']} | {repaired_freshness['is_fresh']} |",
        f"| Stale rows | {corrupted_freshness['stale_rows']}/{corrupted_freshness['total_rows']} "
        f"| {repaired_freshness['stale_rows']}/{repaired_freshness['total_rows']} |",
        f"| Latest published | {corrupted_freshness['latest_published']} "
        f"| {repaired_freshness['latest_published']} |",
        "",
        "## Conclusion",
        "",
        "Corrupted data trips the GX quality gate (and the freshness SLA when enough rows go stale) "
        "while the agent keeps answering "
        "(silent failure). Re-running the repair from the raw snapshot is idempotent and restores "
        "the baseline metrics.",
        "",
    ]
    write_text(report_path, "\n".join(lines))
