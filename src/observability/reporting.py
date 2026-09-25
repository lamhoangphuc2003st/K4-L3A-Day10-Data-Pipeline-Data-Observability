from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.utils import write_text


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Persist the baseline results, including judge provenance and warnings."""
    sections = [
        "# Phase 1 baseline report",
        f"Quality gate: **{'PASS' if quality['success'] else 'FAIL'}**. "
        f"Freshness: **{'PASS' if freshness['is_fresh'] else 'WARNING'}**.",
    ]
    for title, payload in (
        ("Source and run", source_summary),
        ("Evaluation metrics", metrics),
        ("Quality checks", {key: value for key, value in quality.items() if key != "results"}),
        ("Freshness", freshness),
    ):
        sections.append(f"## {title}\n\n```json\n{json.dumps(payload, indent=2, ensure_ascii=False)}\n```")
    if source_summary.get("heuristic_judgments"):
        sections.append(
            "Some or all judge scores use the token-overlap fallback because the LLM judge "
            "was unavailable. These scores are not independent LLM judgments."
        )
    write_text(Path(report_path), "\n\n".join(sections) + "\n")


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
    *,
    baseline_quality: dict[str, Any] | None = None,
    baseline_freshness: dict[str, Any] | None = None,
    repair_verified: bool = False,
) -> None:
    """Write measured results without assuming degradation or successful repair."""
    def status(payload, key):
        return "NOT MEASURED" if payload is None else "PASSED" if payload[key] else "FAILED"

    states = (baseline_metrics, corrupted_metrics, repaired_metrics)
    lines = [
        "# Corruption, repair and comparison",
        "",
        "All states use the same benchmark and sample selection. Corrupted and repaired "
        "data use separate Chroma collections. Raw snapshots are read-only.",
        "",
        "| Metric | Baseline | Corrupted | Repaired |",
        "| --- | --- | --- | --- |",
        f"| Data Quality Gate | {status(baseline_quality, 'success')} | {status(corrupted_quality, 'success')} | {status(repaired_quality, 'success')} |",
        f"| Freshness | {status(baseline_freshness, 'is_fresh')} | {status(corrupted_freshness, 'is_fresh')} | {status(repaired_freshness, 'is_fresh')} |",
    ]
    for label, key in (("Questions evaluated", "samples"), ("Retrieval Hit Rate", "retrieval_hit_rate"),
                       ("Mean Token F1", "mean_token_f1"), ("Judge accuracy", "judge_accuracy"),
                       ("Mean judge score", "mean_judge_score")):
        values = [str(item[key]) if key == "samples" else f"{item[key]:.4f}" for item in states]
        lines.append(f"| {label} | {' | '.join(values)} |")
    lines.extend([
        "", "## Interpretation", "",
        "Retrieval Hit Rate requires all reference documents, including both documents for multi-hop questions.",
        "Numbers are observations, not target scores. The lab's example thresholds are not guaranteed. "
        "A quality failure does not by itself prove hallucination; inspect the answer files for specific errors.",
        f"Repair idempotency (two rebuilds from raw, identical to baseline): {'VERIFIED' if repair_verified else 'NOT VERIFIED'}.",
        "",
    ])
    for key in ("retrieval_hit_rate", "mean_token_f1"):
        lines.append(
            f"- {key}: corrupted minus baseline = {corrupted_metrics[key] - baseline_metrics[key]:+.4f}; "
            f"repaired minus baseline = {repaired_metrics[key] - baseline_metrics[key]:+.4f}."
        )
    lines.extend(["", "## Judge provenance", ""])
    for label, metrics in zip(("Baseline", "Corrupted", "Repaired"), states):
        lines.append(f"- {label}: {metrics.get('heuristic_judgments', 'unknown')} heuristic fallback judgments.")
    lines.append("Heuristic scores are not independent LLM judgments; live LLM judge scores can vary across runs.")
    for label, freshness in (("Baseline", baseline_freshness), ("Corrupted", corrupted_freshness), ("Repaired", repaired_freshness)):
        if freshness:
            lines.extend(["", f"## {label} freshness", "", "```json", json.dumps(freshness, indent=2), "```"])
    write_text(Path(report_path), "\n".join(lines) + "\n")
