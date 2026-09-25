from __future__ import annotations

import pandas as pd

from core.config import load_settings
from core.utils import now_utc, read_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from pipelines.phase1 import save_clean
from retrieval.index import LocalEmbeddingIndex

METRIC_ROWS = ["retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"]


def _print_comparison(baseline: dict, corrupted: dict, repaired: dict) -> None:
    print(f"{'Metric':<22}{'Baseline':>10}{'Corrupted':>11}{'Repaired':>10}")
    for key in METRIC_ROWS:
        print(f"{key:<22}{baseline[key]:>10.4f}{corrupted[key]:>11.4f}{repaired[key]:>10.4f}")


def main() -> None:
    settings = load_settings()
    paths = settings.paths

    baseline_metrics = read_json(paths.baseline_metrics)
    clean_df = pd.DataFrame(read_json(paths.clean_json))

    # Corrupt -> index -> evaluate -> observe
    corrupted_df = corrupt_clean_dataframe(clean_df, paths.corruption_log)
    save_clean(corrupted_df, paths.corrupted_clean_csv, paths.corrupted_clean_json)
    corrupted_index = LocalEmbeddingIndex.build(corrupted_df, settings, paths.corrupted_embeddings_json)
    corrupted_bundle = evaluate_pipeline(
        settings, corrupted_index, paths.eval_testset, paths.corrupted_metrics, paths.corrupted_answers
    )
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted")
    corrupted_freshness = build_freshness_report(corrupted_df, settings, paths.quality_dir / "corrupted_freshness_report.json")
    print(f"[corruption] quality gate success={corrupted_quality['success']} "
          f"failed={corrupted_quality['failed_checks']} is_fresh={corrupted_freshness['is_fresh']}")

    # Idempotent repair: always rebuilt from the preserved raw records, never from the corrupted data.
    repaired_df = build_clean_dataframe(load_raw_records(paths.raw_records_json), now_utc())
    save_clean(repaired_df, paths.repaired_clean_csv, paths.repaired_clean_json)
    repaired_index = LocalEmbeddingIndex.build(repaired_df, settings, paths.repaired_embeddings_json)
    repaired_bundle = evaluate_pipeline(
        settings, repaired_index, paths.eval_testset, paths.repaired_metrics, paths.repaired_answers
    )
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")
    repaired_freshness = build_freshness_report(repaired_df, settings, paths.quality_dir / "repaired_freshness_report.json")

    generate_corruption_report(
        paths.comparison_report,
        baseline_metrics,
        corrupted_bundle.summary,
        repaired_bundle.summary,
        corrupted_quality,
        repaired_quality,
        corrupted_freshness,
        repaired_freshness,
    )
    _print_comparison(baseline_metrics, corrupted_bundle.summary, repaired_bundle.summary)
    print(f"[corruption] report: {paths.comparison_report}")


if __name__ == "__main__":
    main()
