from __future__ import annotations

import json

import pandas as pd

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex
from retrieval.qa import answer_question

DEMO_QUESTIONS = 2


def save_clean(df: pd.DataFrame, csv_path, json_path) -> None:
    write_csv(df, csv_path)
    write_json(json_path, json.loads(df.to_json(orient="records")))


def main() -> None:
    settings = load_settings()
    paths = settings.paths

    if settings.refresh_source or not paths.raw_records_json.exists():
        records = fetch_source_records(settings)
    else:
        records = load_raw_records(paths.raw_records_json)

    df = build_clean_dataframe(records, now_utc())
    save_clean(df, paths.clean_csv, paths.clean_json)
    print(f"[phase1] clean rows: {len(df)}")

    index = LocalEmbeddingIndex.build(df, settings, paths.embeddings_json)

    if settings.refresh_test_set or not paths.eval_testset.exists():
        build_test_set(df, paths.eval_testset)

    bundle = evaluate_pipeline(
        settings, index, paths.eval_testset, paths.baseline_metrics, paths.baseline_answers
    )
    quality = run_data_quality_checks(df, settings, "baseline")
    freshness = build_freshness_report(df, settings, paths.freshness_report)

    source_summary = {
        "source_api": settings.source_api,
        "query": settings.source_query,
        "records_ingested": len(records),
        "clean_rows": len(df),
        "embedding_model": settings.embedding_model,
        "collection": settings.baseline_collection_name,
    }
    generate_phase1_report(paths.baseline_report, source_summary, bundle.summary, quality, freshness)

    demo = read_json(paths.eval_testset)[:DEMO_QUESTIONS]
    write_json(
        paths.demo_answers,
        [
            {"question": item["question"], "answer": answer_question(item["question"], settings, index).answer}
            for item in demo
        ],
    )

    print(json.dumps({k: v for k, v in bundle.summary.items() if k != "ragas"}, indent=2))
    print(f"[phase1] quality success={quality['success']} is_fresh={freshness['is_fresh']}")
    print(f"[phase1] report: {paths.baseline_report}")


if __name__ == "__main__":
    main()
