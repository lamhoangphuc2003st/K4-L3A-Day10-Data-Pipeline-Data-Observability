from __future__ import annotations

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    """Run the baseline pipeline, stopping before indexing if quality fails."""
    settings = load_settings()
    paths = settings.paths
    run_date = now_utc()
    print("[1/6] Loading source records...", flush=True)
    if not settings.refresh_source and paths.raw_records_json.exists():
        records = load_raw_records(paths.raw_records_json)
    else:
        records = fetch_source_records(settings)

    print("[2/6] Cleaning and checking data quality...", flush=True)
    df = build_clean_dataframe(records, run_date)
    write_json(paths.clean_json, df.to_dict(orient="records"))
    write_csv(df, paths.clean_csv)
    quality = run_data_quality_checks(df, settings, paths.baseline_quality_report.name)
    freshness = build_freshness_report(df, settings, paths.freshness_report)
    if not quality["success"]:
        raise RuntimeError(f"Data quality gate failed. See {paths.baseline_quality_report}")

    print("[3/6] Preparing benchmark questions...", flush=True)
    if settings.refresh_test_set or settings.refresh_source or not paths.eval_testset.exists():
        test_set = build_test_set(df, paths.eval_testset)
    else:
        test_set = read_json(paths.eval_testset)
        corpus_ids = set(df["paper_id"])
        if not test_set or any(
            not item.get("ground_truth_doc_ids")
            or not set(item["ground_truth_doc_ids"]).issubset(corpus_ids)
            for item in test_set
        ):
            test_set = build_test_set(df, paths.eval_testset)

    print("[4/6] Preparing the embedding index...", flush=True)
    # Reuse an existing index only when its model and full document content match.
    manifest = read_json(paths.embeddings_json) if paths.embeddings_json.exists() else None
    if (
        manifest
        and manifest.get("embedding_model") == settings.embedding_model
        and manifest.get("collection_name") == settings.baseline_collection_name
        and manifest.get("persist_path") == str(paths.chroma_dir)
        and manifest.get("documents") == LocalEmbeddingIndex._build_documents(df)
        and paths.chroma_dir.exists()
    ):
        index = LocalEmbeddingIndex.load(settings)
    else:
        index = LocalEmbeddingIndex.build(df, settings)

    print(f"[5/6] Starting evaluation (benchmark: {len(test_set)} questions)...", flush=True)
    evaluation = evaluate_pipeline(
        settings=settings, index=index, test_set_path=paths.eval_testset,
        metrics_output_path=paths.baseline_metrics, answers_output_path=paths.baseline_answers,
    )
    print("[6/6] Writing the baseline report...", flush=True)
    generate_phase1_report(
        paths.baseline_report,
        source_summary={
            "source": settings.source_api,
            "run_date": run_date.isoformat(),
            "raw_records": len(records),
            "clean_records": len(df),
            "test_samples": len(test_set),
            "llm_provider": settings.llm_provider,
            "heuristic_judgments": sum(
                answer["judge"]["reasoning"].startswith("Fallback heuristic judge")
                for answer in evaluation.answers
            ),
        },
        metrics=evaluation.summary, quality=quality, freshness=freshness,
    )
    print(f"Phase 1 complete. Quality check status = {quality['success']}")
    print(f"Report: {paths.baseline_report}")
