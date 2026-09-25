from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from core.config import load_settings
from core.utils import read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    settings = load_settings()
    paths = settings.paths
    if not paths.baseline_metrics.exists() or not paths.eval_testset.exists() or not paths.clean_json.exists():
        raise RuntimeError("Run python script/run_phase1.py before the corruption flow")
    baseline_metrics = read_json(paths.baseline_metrics)
    baseline_freshness = read_json(paths.freshness_report)
    clean = pd.read_json(paths.clean_json)

    corrupted = corrupt_clean_dataframe(clean, paths.corruption_log)
    write_csv(corrupted, paths.corrupted_clean_csv)
    write_json(paths.corrupted_clean_json, corrupted.to_dict(orient="records"))
    corrupted_quality = run_data_quality_checks(corrupted, settings, "corrupted")
    corrupted_freshness = build_freshness_report(
        corrupted, settings, paths.quality_dir / "corrupted_freshness_report.json")
    # The failed data is evaluated only in its separate corruption collection.
    corrupted_index = LocalEmbeddingIndex.build(corrupted, settings, paths.corrupted_embeddings_json)
    corrupted_bundle = evaluate_pipeline(
        settings, corrupted_index, paths.eval_testset,
        paths.corrupted_metrics, paths.corrupted_answers,
    )

    repaired = build_clean_dataframe(load_raw_records(paths.raw_records_json), datetime.now(UTC))
    repaired_quality = run_data_quality_checks(repaired, settings, "repaired")
    repaired_freshness = build_freshness_report(
        repaired, settings, paths.quality_dir / "repaired_freshness_report.json")
    if not repaired_quality["success"]:
        raise RuntimeError("Repaired data failed the quality gate; repaired index was not replaced")
    write_csv(repaired, paths.repaired_clean_csv)
    write_json(paths.repaired_clean_json, repaired.to_dict(orient="records"))
    repaired_index = LocalEmbeddingIndex.build(repaired, settings, paths.repaired_embeddings_json)
    repaired_bundle = evaluate_pipeline(
        settings, repaired_index, paths.eval_testset,
        paths.repaired_metrics, paths.repaired_answers,
    )
    generate_corruption_report(
        paths.comparison_report, baseline_metrics,
        corrupted_bundle.summary, repaired_bundle.summary,
        corrupted_quality, repaired_quality, corrupted_freshness, repaired_freshness,
        baseline_freshness,
    )
    print("Corruption/repair complete:")
    for name, metrics in (("baseline", baseline_metrics), ("corrupted", corrupted_bundle.summary),
                          ("repaired", repaired_bundle.summary)):
        print(f"  {name:9} hybrid={metrics['retrieval_hit_rate']:.1%} "
              f"vector={metrics['vector_retrieval_hit_rate']:.1%} F1={metrics['mean_token_f1']:.1%}")
