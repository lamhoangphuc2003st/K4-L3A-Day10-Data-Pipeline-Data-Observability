# Phase 1 Report - Baseline Pipeline

## Source

- source_api: Crossref REST API
- query: agentic retrieval augmented generation large language model
- records_ingested: 24
- clean_rows: 24
- embedding_model: sentence-transformers/all-MiniLM-L6-v2
- collection: papers-baseline

## Retrieval & Answer Metrics

| Metric | Value |
| :--- | ---: |
| Retrieval Hit Rate | 1.0000 |
| Mean Token F1 | 1.0000 |
| Judge Accuracy | 1.0000 |
| Mean Judge Score | 5.0000 |
| Samples | 10 |

## Data Quality (Great Expectations 1.x)

- Gate success: **True**
- Failed checks: none

| Check | Passed |
| :--- | :---: |
| row_count_between_5_and_5000 | True |
| paper_id_not_null | True |
| title_not_null | True |
| text_for_embedding_not_null | True |
| paper_id_unique | True |
| summary_length_min_30 | True |

## Freshness

- Latest published: 2026-07-22
- Oldest published: 2026-03-28
- Stale rows (> 180 days): 1/24
- is_fresh: **True**
