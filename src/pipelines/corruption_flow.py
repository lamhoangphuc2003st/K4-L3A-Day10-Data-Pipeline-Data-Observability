from __future__ import annotations

import pandas as pd

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    """Compare isolated baseline/corrupted/repaired collections on one benchmark."""
    settings = load_settings()
    paths = settings.paths
    run_date = now_utc()
    if not paths.raw_records_json.exists():
        raise FileNotFoundError("Raw records snapshot is missing. Run script/run_phase1.py first.")

    # Read-only recovery source: no fetch, refresh, or edits to raw data here.
    baseline = build_clean_dataframe(load_raw_records(paths.raw_records_json), run_date)
    if settings.refresh_test_set or not paths.eval_testset.exists():
        build_test_set(baseline, paths.eval_testset)
    test_set = read_json(paths.eval_testset)
    if not test_set or any(
        not item.get("ground_truth_doc_ids")
        or not set(item["ground_truth_doc_ids"]).issubset(set(baseline.paper_id))
        for item in test_set
    ):
        raise ValueError("Benchmark does not match the raw snapshot. Set REFRESH_TEST_SET=true to rebuild it.")

    def measure(label, frame, csv_path, json_path, embeddings_path, metrics_path, answers_path):
        print(f"[{label}] Saving data and checking quality...", flush=True)
        write_csv(frame, csv_path)
        write_json(json_path, frame.to_dict(orient="records"))
        quality = run_data_quality_checks(frame, settings, f"{label}_quality_report")
        freshness = build_freshness_report(frame, settings, paths.quality_dir / f"{label}_freshness_report.json")
        if label != "corrupted" and not quality["success"]:
            raise RuntimeError(f"{label} quality gate failed; see {paths.quality_dir}")
        # Corrupted quality failures are deliberately allowed for this experiment.
        print(f"[{label}] Building isolated index and evaluating...", flush=True)
        index = LocalEmbeddingIndex.build(frame, settings, embeddings_path)
        evaluation = evaluate_pipeline(settings, index, paths.eval_testset, metrics_path, answers_path)
        return evaluation, quality, freshness

    baseline_eval, baseline_quality, baseline_freshness = measure(
        "baseline", baseline, paths.clean_csv, paths.clean_json, paths.embeddings_json,
        paths.baseline_metrics, paths.baseline_answers,
    )
    corrupted = corrupt_clean_dataframe(baseline, paths.corruption_log)
    corrupted_eval, corrupted_quality, corrupted_freshness = measure(
        "corrupted", corrupted, paths.corrupted_clean_csv, paths.corrupted_clean_json,
        paths.corrupted_embeddings_json, paths.corrupted_metrics, paths.corrupted_answers,
    )
    # Re-read raw for both repair passes: never deduplicate/clean the corrupted data.
    repaired = build_clean_dataframe(load_raw_records(paths.raw_records_json), run_date)
    repaired_again = build_clean_dataframe(load_raw_records(paths.raw_records_json), run_date)
    pd.testing.assert_frame_equal(repaired, baseline)
    pd.testing.assert_frame_equal(repaired_again, repaired)
    repaired_eval, repaired_quality, repaired_freshness = measure(
        "repaired", repaired, paths.repaired_clean_csv, paths.repaired_clean_json,
        paths.repaired_embeddings_json, paths.repaired_metrics, paths.repaired_answers,
    )
    question_ids = [answer["id"] for answer in baseline_eval.answers]
    for evaluation in (corrupted_eval, repaired_eval):
        if [answer["id"] for answer in evaluation.answers] != question_ids:
            raise RuntimeError("Comparison requires identical evaluation questions in all three states.")
    generate_corruption_report(
        paths.comparison_report, baseline_eval.summary, corrupted_eval.summary, repaired_eval.summary,
        corrupted_quality, repaired_quality, corrupted_freshness, repaired_freshness,
        baseline_quality=baseline_quality, baseline_freshness=baseline_freshness,
        repair_verified=True,
    )
    print(f"Corruption and repair complete. Report: {paths.comparison_report}")
