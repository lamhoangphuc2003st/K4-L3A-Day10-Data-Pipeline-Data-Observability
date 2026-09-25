# Corruption and repair experiment

| Metric / Quality | Clean | Corrupted | Repaired |
|---|---:|---:|---:|
| Quality gate | PASS | FAIL | PASS |
| Freshness | PASS | FAIL | PASS |
| Stale rows | 1 | 10 | 1 |
| Missing IDs | 0 | 5 | 0 |
| Duplicate IDs | 0 | 2 | 0 |
| Hit rate | 1.000 | 0.500 | 1.000 |
| Token F1 | 0.953 | 0.688 | 0.953 |
| LLM judge | unavailable | unavailable | unavailable |

## Injected errors

- drop_latest_records: 5 records
- blank_summary: 2 records
- inject_noise: 2 records
- truncate_title: 2 records
- stale_date: 8 records
- duplicate_rows: 2 records

## Detection and repair

GX / integrity failures: ExpectColumnValuesToBeUnique, ExpectColumnValueLengthsToBeBetween, NoNoiseRuns, TitleLengthAtLeast8, RawSourceCoverage.
Freshness detected 10 stale rows (47.6%; maximum 25%).
Corrupted data was indexed only in an isolated experiment collection after its failed gate. Repair rebuilt the clean dataframe from preserved raw records and replaced the repaired collection.
Hit rate changed 1.000 → 0.500 → 1.000.
Token F1 changed 0.953 → 0.688 → 0.953.
Judge scores are unavailable when no configured LLM judge successfully responds.
Measured hit rate and token F1 returned to baseline.
