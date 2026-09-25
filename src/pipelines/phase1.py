from __future__ import annotations

from core.config import load_settings
from core.utils import now_utc, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    settings = load_settings()
    records = fetch_source_records(settings)
    clean = build_clean_dataframe(records, now_utc())
    write_csv(clean, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, clean.to_dict("records"))
    quality = run_data_quality_checks(clean, settings, "baseline")
    freshness = build_freshness_report(clean, settings, settings.paths.freshness_report)
    if not quality["success"] or not freshness["is_fresh"]:
        raise RuntimeError("Baseline quality/freshness gate failed; index was not built")
    build_test_set(clean, settings.paths.eval_testset)
    index = LocalEmbeddingIndex.build(clean, settings, settings.paths.embeddings_json)
    bundle = evaluate_pipeline(settings, index, settings.paths.eval_testset,
                               settings.paths.baseline_metrics, settings.paths.baseline_answers)
    metrics = {**bundle.summary, "quality": quality, "freshness": freshness,
               "duplicates": int(clean["paper_id"].duplicated().sum()), "missing_ids": 0}
    write_json(settings.paths.baseline_metrics, metrics)
    generate_phase1_report(settings.paths.baseline_report,
                           {"source": "Crossref API or snapshot fallback" if settings.refresh_source
                            else "offline Crossref snapshot", "records": len(records)},
                           metrics, quality, freshness)
    print(f"Baseline: {len(clean)} papers, hit rate {metrics['retrieval_hit_rate']:.3f}, "
          f"token F1 {metrics['mean_token_f1']:.3f}")
