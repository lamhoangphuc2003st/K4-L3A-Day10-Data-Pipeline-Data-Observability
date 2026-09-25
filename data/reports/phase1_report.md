# Phase 1 — Clean baseline

- Source: offline Crossref snapshot; records: 24
- Answer generator: llm; LLM: opencode_go/glm-5.3-flash
- Great Expectations quality gate: PASS
- Freshness SLA: PASS (1/24 older than 180 days)

| Metric | Value |
|---|---:|
| Retrieval hit rate | 1.000 |
| Mean token F1 | 0.613 |
| LLM judge score | 5 |
| LLM judge status | available (10/10) |

The benchmark uses the fixed 10-question test set in data/eval/test_set.json.
