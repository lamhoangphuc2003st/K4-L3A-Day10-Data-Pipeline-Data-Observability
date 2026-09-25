# Data corruption and repair comparison

The corrupted collection is isolated. Its failing quality gate prevents promotion to the baseline collection.
Repair rebuilds from raw records and replaces only the repaired collection.

| Measure | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| Questions | 5 | 5 | 5 |
| Hybrid retrieval Hit Rate | 100.0% | 80.0% | 100.0% |
| Pure vector Hit Rate | 100.0% | 80.0% | 100.0% |
| Mean Token F1 | 100.0% | 40.0% | 100.0% |
| Judge accuracy | 100.0% | 60.0% | 100.0% |
| Mean judge score | 5 | 3.2 | 5 |
| GX quality gate | PASS | FAIL | PASS |
| Freshness SLA | PASS | ALERT | PASS |
| Stale rows | 0 | 13 | 0 |

## Interpretation

Hit Rate is reported separately for hybrid title-assisted retrieval and pure vector retrieval.
The two-paper multi-hop question requires both source documents to count as a retrieval hit.
Judge methods — baseline: {'llm': 5}; corrupted: {'llm': 5}; repaired: {'llm': 5}.
A heuristic fallback is recorded as such and must not be described as an LLM judgment.
