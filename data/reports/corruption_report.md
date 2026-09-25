# Corruption Report - Baseline vs Corrupted vs Repaired

## Metrics

| Metric | Baseline | Corrupted | Repaired |
| :--- | ---: | ---: | ---: |
| Retrieval Hit Rate | 1.0000 | 0.7000 | 1.0000 |
| Mean Token F1 | 1.0000 | 0.8000 | 1.0000 |
| Judge Accuracy | 1.0000 | 0.8000 | 1.0000 |
| Mean Judge Score | 5.0000 | 4.2000 | 5.0000 |

## Observability

| Signal | Corrupted | Repaired |
| :--- | :--- | :--- |
| GX quality gate success | False | True |
| Failed checks | paper_id_unique, summary_length_min_30 | none |
| Freshness is_fresh | True | True |
| Stale rows | 4/22 | 1/24 |
| Latest published | 2026-06-12 | 2026-07-22 |

## Conclusion

Corrupted data trips the quality gate / freshness SLA while the agent keeps answering (silent failure). Re-running the repair from the raw snapshot is idempotent and restores the baseline metrics.
