# Phase 1 baseline report

Quality gate: **PASS**. Freshness: **PASS**.

## Source and run

```json
{
  "source": "Crossref REST API",
  "run_date": "2026-09-25T10:02:26.442630+00:00",
  "raw_records": 24,
  "clean_records": 24,
  "test_samples": 108,
  "llm_provider": "mock",
  "heuristic_judgments": 10
}
```

## Evaluation metrics

```json
{
  "samples": 10,
  "total_test_samples": 108,
  "heuristic_judgments": 10,
  "retrieval_hit_rate": 0.9,
  "mean_token_f1": 0.6022262872628726,
  "judge_accuracy": 0.6,
  "mean_judge_score": 3,
  "ragas": {
    "skipped": "Set RUN_RAGAS=1 to enable the slower Ragas pass."
  }
}
```

## Quality checks

```json
{
  "report_name": "baseline_quality_report.json",
  "success": true,
  "row_count": 24,
  "missing_columns": [],
  "statistics": {
    "evaluated_expectations": 7,
    "successful_expectations": 7,
    "unsuccessful_expectations": 0
  },
  "freshness": {
    "latest_published": "2026-07-22",
    "oldest_published": "2026-03-28",
    "threshold_days": 180,
    "max_stale_ratio": 0.25,
    "stale_rows": 1,
    "total_rows": 24,
    "stale_ratio": 0.041666666666666664,
    "unknown_age_rows": 0,
    "is_fresh": true,
    "warnings": []
  },
  "warnings": []
}
```

## Freshness

```json
{
  "latest_published": "2026-07-22",
  "oldest_published": "2026-03-28",
  "threshold_days": 180,
  "max_stale_ratio": 0.25,
  "stale_rows": 1,
  "total_rows": 24,
  "stale_ratio": 0.041666666666666664,
  "unknown_age_rows": 0,
  "is_fresh": true,
  "warnings": []
}
```

Some or all judge scores use the token-overlap fallback because the LLM judge was unavailable. These scores are not independent LLM judgments.
