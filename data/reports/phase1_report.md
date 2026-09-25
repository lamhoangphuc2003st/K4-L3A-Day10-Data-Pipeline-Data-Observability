# Phase 1 — Baseline data pipeline

Source: Crossref offline snapshot
Raw records: 24
Clean records: 24

## Quality and freshness

GX quality gate: **PASS**
Freshness SLA: **PASS**
Stale rows: 0/24 (0.0%)

## Evaluation

| Metric | Value |
| --- | ---: |
| Questions | 5 |
| Hybrid retrieval Hit Rate | 100.0% |
| Pure vector retrieval Hit Rate | 100.0% |
| Mean Token F1 | 100.0% |
| Judge accuracy | 100.0% |
| Mean judge score (1–5) | 5.00 |

Hybrid retrieval uses exact title lookup plus vectors; pure vector retrieval uses Chroma alone.
Judge methods: {'llm': 5}. Heuristic fallback scores are not LLM judgments.
