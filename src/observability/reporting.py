from __future__ import annotations

from pathlib import Path
from typing import Any

from core.utils import read_json, write_text


def _metric(value: Any) -> str:
    return "unavailable" if value is None else f"{value:.3f}" if isinstance(value, float) else str(value)


def generate_phase1_report(
    report_path: Path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    lines = [
        "# Phase 1 — Clean baseline",
        "",
        f"- Source: {source_summary['source']}; records: {source_summary['records']}",
        f"- Great Expectations quality gate: {'PASS' if quality['success'] else 'FAIL'}",
        f"- Freshness SLA: {'PASS' if freshness['is_fresh'] else 'FAIL'} "
        f"({freshness['stale_rows']}/{freshness['total_rows']} older than {freshness['threshold_days']} days)",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Retrieval hit rate | {_metric(metrics['retrieval_hit_rate'])} |",
        f"| Mean token F1 | {_metric(metrics['mean_token_f1'])} |",
        f"| LLM judge score | {_metric(metrics['mean_judge_score'])} |",
        f"| LLM judge status | {metrics['judge_status']} |",
        "",
        "The benchmark uses the fixed 10-question test set in data/eval/test_set.json.",
    ]
    write_text(report_path, "\n".join(lines) + "\n")


def generate_corruption_report(
    report_path: Path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    baseline_quality = baseline_metrics["quality"]
    baseline_freshness = baseline_metrics["freshness"]
    states = [
        (baseline_metrics, baseline_quality, baseline_freshness),
        (corrupted_metrics, corrupted_quality, corrupted_freshness),
        (repaired_metrics, repaired_quality, repaired_freshness),
    ]
    def row(name: str, values: list[Any]) -> str:
        return "| " + name + " | " + " | ".join(_metric(value) for value in values) + " |"

    log = read_json(report_path.parent.parent / "results" / "corruption_log.json")
    failed = [check["expectation"] for check in corrupted_quality["checks"] if not check["success"]]
    lines = [
        "# Corruption and repair experiment", "",
        "| Metric / Quality | Clean | Corrupted | Repaired |",
        "|---|---:|---:|---:|",
        row("Quality gate", ["PASS" if q["success"] else "FAIL" for _, q, _ in states]),
        row("Freshness", ["PASS" if f["is_fresh"] else "FAIL" for _, _, f in states]),
        row("Stale rows", [f["stale_rows"] for _, _, f in states]),
        row("Missing IDs", [m["missing_ids"] for m, _, _ in states]),
        row("Duplicate IDs", [m["duplicates"] for m, _, _ in states]),
        row("Hit rate", [m["retrieval_hit_rate"] for m, _, _ in states]),
        row("Token F1", [m["mean_token_f1"] for m, _, _ in states]),
        row("LLM judge", [m["mean_judge_score"] for m, _, _ in states]),
        "",
        "## Injected errors", "",
    ]
    lines += [f"- {item['corruption_type']}: {item['count']} records" for item in log]
    lines += [
        "", "## Detection and repair", "",
        f"GX / integrity failures: {', '.join(failed) if failed else 'none'}.",
        f"Freshness detected {corrupted_freshness['stale_rows']} stale rows "
        f"({corrupted_freshness['stale_fraction']:.1%}; maximum 25%).",
        "Corrupted data was indexed only in an isolated experiment collection after its failed gate. "
        "Repair rebuilt the clean dataframe from preserved raw records and replaced the repaired collection.",
        f"Hit rate changed {_metric(baseline_metrics['retrieval_hit_rate'])} → "
        f"{_metric(corrupted_metrics['retrieval_hit_rate'])} → "
        f"{_metric(repaired_metrics['retrieval_hit_rate'])}.",
        f"Token F1 changed {_metric(baseline_metrics['mean_token_f1'])} → "
        f"{_metric(corrupted_metrics['mean_token_f1'])} → "
        f"{_metric(repaired_metrics['mean_token_f1'])}.",
        "Judge scores are unavailable when no configured LLM judge successfully responds.",
    ]
    if (baseline_metrics["retrieval_hit_rate"] != repaired_metrics["retrieval_hit_rate"]
            or baseline_metrics["mean_token_f1"] != repaired_metrics["mean_token_f1"]):
        lines.append("Repaired metrics differ from baseline; inspect retrieval rankings and runtime conditions.")
    else:
        lines.append("Measured hit rate and token F1 returned to baseline.")
    write_text(report_path, "\n".join(lines) + "\n")
