from __future__ import annotations

from typing import Any

from core.utils import write_text


def _pct(value: Any) -> str:
    return f"{float(value or 0):.1%}"


def generate_phase1_report(
    report_path, source_summary: dict[str, Any], metrics: dict[str, Any],
    quality: dict[str, Any], freshness: dict[str, Any],
) -> None:
    lines = [
        "# Phase 1 — Baseline data pipeline", "",
        f"Source: {source_summary.get('source', 'Crossref snapshot')}",
        f"Raw records: {source_summary.get('raw_records', 'n/a')}",
        f"Clean records: {source_summary.get('clean_records', 'n/a')}", "",
        "## Quality and freshness", "",
        f"GX quality gate: **{'PASS' if quality['success'] else 'FAIL'}**",
        f"Freshness SLA: **{'PASS' if freshness['is_fresh'] else 'ALERT'}**",
        f"Stale rows: {freshness['stale_rows']}/{freshness['total_rows']} ({_pct(freshness['stale_rate'])})", "",
        "## Evaluation", "",
        "| Metric | Value |", "| --- | ---: |",
        f"| Questions | {metrics['samples']} |",
        f"| Hybrid retrieval Hit Rate | {_pct(metrics['retrieval_hit_rate'])} |",
        f"| Pure vector retrieval Hit Rate | {_pct(metrics['vector_retrieval_hit_rate'])} |",
        f"| Mean Token F1 | {_pct(metrics['mean_token_f1'])} |",
        f"| Judge accuracy | {_pct(metrics['judge_accuracy'])} |",
        f"| Mean judge score (1–5) | {metrics['mean_judge_score']:.2f} |", "",
        "Hybrid retrieval uses exact title lookup plus vectors; pure vector retrieval uses Chroma alone.",
        f"Judge methods: {metrics['judge_methods']}. Heuristic fallback scores are not LLM judgments.", "",
    ]
    write_text(report_path, "\n".join(lines))


def generate_corruption_report(
    report_path, baseline_metrics: dict[str, Any], corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any], corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any], corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any], baseline_freshness: dict[str, Any] | None = None,
) -> None:
    def metric(name: str, percent: bool = True) -> str:
        values = [baseline_metrics[name], corrupted_metrics[name], repaired_metrics[name]]
        return " | ".join(_pct(value) if percent else str(value) for value in values)

    lines = [
        "# Data corruption and repair comparison", "",
        "The corrupted collection is isolated. Its failing quality gate prevents promotion to the baseline collection.",
        "Repair rebuilds from raw records and replaces only the repaired collection.", "",
        "| Measure | Baseline | Corrupted | Repaired |", "| --- | ---: | ---: | ---: |",
        f"| Questions | {metric('samples', False)} |",
        f"| Hybrid retrieval Hit Rate | {metric('retrieval_hit_rate')} |",
        f"| Pure vector Hit Rate | {metric('vector_retrieval_hit_rate')} |",
        f"| Mean Token F1 | {metric('mean_token_f1')} |",
        f"| Judge accuracy | {metric('judge_accuracy')} |",
        f"| Mean judge score | {metric('mean_judge_score', False)} |",
        f"| GX quality gate | PASS | {'PASS' if corrupted_quality['success'] else 'FAIL'} | {'PASS' if repaired_quality['success'] else 'FAIL'} |",
        f"| Freshness SLA | {'PASS' if baseline_freshness and baseline_freshness['is_fresh'] else 'ALERT'} | {'PASS' if corrupted_freshness['is_fresh'] else 'ALERT'} | {'PASS' if repaired_freshness['is_fresh'] else 'ALERT'} |",
        f"| Stale rows | {baseline_freshness['stale_rows'] if baseline_freshness else 'n/a'} | {corrupted_freshness['stale_rows']} | {repaired_freshness['stale_rows']} |", "",
        "## Interpretation", "",
        "Hit Rate is reported separately for hybrid title-assisted retrieval and pure vector retrieval.",
        "The two-paper multi-hop question requires both source documents to count as a retrieval hit.",
        f"Judge methods — baseline: {baseline_metrics['judge_methods']}; corrupted: {corrupted_metrics['judge_methods']}; repaired: {repaired_metrics['judge_methods']}.",
        "A heuristic fallback is recorded as such and must not be described as an LLM judgment.", "",
    ]
    write_text(report_path, "\n".join(lines))
