from __future__ import annotations

from datetime import UTC, datetime

from core.config import load_settings
from core.utils import write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import load_or_create_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    settings = load_settings()
    records = fetch_source_records(settings)
    clean = build_clean_dataframe(records, datetime.now(UTC))
    quality = run_data_quality_checks(clean, settings, "baseline")
    freshness = build_freshness_report(clean, settings, settings.paths.freshness_report)
    if not quality["success"]:
        raise RuntimeError("Baseline quality gate failed; the baseline Chroma collection was not replaced")

    write_csv(clean, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, clean.to_dict(orient="records"))
    test_set = load_or_create_test_set(clean, settings.paths.eval_testset, refresh=settings.refresh_test_set)
    index = LocalEmbeddingIndex.build(clean, settings, settings.paths.embeddings_json)
    bundle = evaluate_pipeline(
        settings, index, settings.paths.eval_testset,
        settings.paths.baseline_metrics, settings.paths.baseline_answers,
    )
    generate_phase1_report(
        settings.paths.baseline_report,
        {"source": "Crossref live" if settings.refresh_source else "Crossref offline snapshot",
         "raw_records": len(records), "clean_records": len(clean), "questions": len(test_set.samples)},
        bundle.summary, quality, freshness,
    )
    print(f"Baseline complete: {len(clean)} papers, {len(test_set.samples)} questions, "
          f"hybrid Hit Rate {bundle.summary['retrieval_hit_rate']:.1%}")
