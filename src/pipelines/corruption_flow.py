from __future__ import annotations

import pandas as pd

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from pipelines.phase1 import main as run_baseline
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    settings = load_settings()
    if not settings.paths.baseline_metrics.exists() or not settings.paths.clean_csv.exists():
        run_baseline()
    baseline_metrics = read_json(settings.paths.baseline_metrics)
    clean = pd.read_csv(settings.paths.clean_csv).fillna("")
    corrupted = corrupt_clean_dataframe(clean, settings.paths.corruption_log)
    write_csv(corrupted, settings.paths.corrupted_clean_csv)
    write_json(settings.paths.corrupted_clean_json, corrupted.to_dict("records"))
    corrupted_quality = run_data_quality_checks(corrupted, settings, "corrupted")
    corrupted_freshness = build_freshness_report(
        corrupted, settings, settings.paths.quality_dir / "corrupted_freshness_report.json"
    )
    # The failed dataset is indexed only in the isolated experiment collection.
    corrupted_index = LocalEmbeddingIndex.build(
        corrupted, settings, settings.paths.corrupted_embeddings_json
    )
    corrupted_bundle = evaluate_pipeline(
        settings, corrupted_index, settings.paths.eval_testset,
        settings.paths.corrupted_metrics, settings.paths.corrupted_answers
    )
    corrupted_metrics = {**corrupted_bundle.summary, "quality": corrupted_quality,
                         "freshness": corrupted_freshness,
                         "duplicates": int(corrupted["paper_id"].duplicated().sum()),
                         "missing_ids": len(set(clean["paper_id"]) - set(corrupted["paper_id"]))}
    write_json(settings.paths.corrupted_metrics, corrupted_metrics)

    repaired = build_clean_dataframe(
        load_raw_records(settings.paths.raw_records_json), now_utc()
    )
    write_csv(repaired, settings.paths.repaired_clean_csv)
    write_json(settings.paths.repaired_clean_json, repaired.to_dict("records"))
    repaired_quality = run_data_quality_checks(repaired, settings, "repaired")
    repaired_freshness = build_freshness_report(
        repaired, settings, settings.paths.quality_dir / "repaired_freshness_report.json"
    )
    if not repaired_quality["success"] or not repaired_freshness["is_fresh"]:
        raise RuntimeError("Repaired quality/freshness gate failed; index was not built")
    repaired_index = LocalEmbeddingIndex.build(
        repaired, settings, settings.paths.repaired_embeddings_json
    )
    repaired_bundle = evaluate_pipeline(
        settings, repaired_index, settings.paths.eval_testset,
        settings.paths.repaired_metrics, settings.paths.repaired_answers
    )
    repaired_metrics = {**repaired_bundle.summary, "quality": repaired_quality,
                        "freshness": repaired_freshness,
                        "duplicates": int(repaired["paper_id"].duplicated().sum()), "missing_ids": 0}
    write_json(settings.paths.repaired_metrics, repaired_metrics)
    generate_corruption_report(
        settings.paths.comparison_report, baseline_metrics, corrupted_metrics,
        repaired_metrics, corrupted_quality, repaired_quality,
        corrupted_freshness, repaired_freshness
    )
    print("Metric                Clean  Corrupted  Repaired")
    for label, key in [("Hit rate", "retrieval_hit_rate"), ("Token F1", "mean_token_f1")]:
        print(f"{label:<20} {baseline_metrics[key]:.3f}  "
              f"{corrupted_metrics[key]:.3f}      {repaired_metrics[key]:.3f}")
