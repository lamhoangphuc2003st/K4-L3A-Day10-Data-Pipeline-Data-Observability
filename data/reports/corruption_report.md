# Corruption, repair and comparison

All states use the same benchmark and sample selection. Corrupted and repaired data use separate Chroma collections. Raw snapshots are read-only.

| Metric | Baseline | Corrupted | Repaired |
| --- | --- | --- | --- |
| Data Quality Gate | PASSED | FAILED | PASSED |
| Freshness | PASSED | FAILED | PASSED |
| Questions evaluated | 10 | 10 | 10 |
| Retrieval Hit Rate | 0.9000 | 0.8000 | 0.9000 |
| Mean Token F1 | 0.6022 | 0.5400 | 0.6022 |
| Judge accuracy | 0.6000 | 0.5000 | 0.6000 |
| Mean judge score | 3.0000 | 2.8000 | 3.0000 |

## Interpretation

Retrieval Hit Rate requires all reference documents, including both documents for multi-hop questions.
Numbers are observations, not target scores. The lab's example thresholds are not guaranteed. A quality failure does not by itself prove hallucination; inspect the answer files for specific errors.
Repair idempotency (two rebuilds from raw, identical to baseline): VERIFIED.

- retrieval_hit_rate: corrupted minus baseline = -0.1000; repaired minus baseline = +0.0000.
- mean_token_f1: corrupted minus baseline = -0.0622; repaired minus baseline = +0.0000.

## Judge provenance

- Baseline: 10 heuristic fallback judgments.
- Corrupted: 10 heuristic fallback judgments.
- Repaired: 10 heuristic fallback judgments.
Heuristic scores are not independent LLM judgments; live LLM judge scores can vary across runs.

## Baseline freshness

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

## Corrupted freshness

```json
{
  "latest_published": "2026-06-12",
  "oldest_published": "2021-09-25",
  "threshold_days": 180,
  "max_stale_ratio": 0.25,
  "stale_rows": 13,
  "total_rows": 24,
  "stale_ratio": 0.5416666666666666,
  "unknown_age_rows": 0,
  "is_fresh": false,
  "warnings": [
    "Stale data: 54.2% of papers are older than 180 days (limit: 25%). Update the corpus with newer papers."
  ]
}
```

## Repaired freshness

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
