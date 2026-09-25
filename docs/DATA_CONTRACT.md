# Checkpoint 1 data contract

This contract is shared by ingestion, quality, retrieval, and evaluation modules.

## Raw data

- `data/raw/crossref_response.json` contains the complete Crossref response or the bundled offline snapshot.
- `data/raw/crossref_records.json` is a JSON list of `PaperRecord` objects parsed from that response.
- Offline mode is the default. `REFRESH_SOURCE=1` requests live data; a failed request falls back to the bundled response when it exists.

## Cleaned DataFrame

Each row represents one DOI. Rows are sorted by lowercase `paper_id`; the first valid occurrence of a duplicate DOI is retained. A row without a DOI, title, nonempty summary, or parseable publication date is discarded.

| Columns | Format |
| --- | --- |
| `paper_id` | Lowercase DOI string, unique |
| `title`, `summary`, `primary_category`, `abs_url`, `pdf_url`, `comment` | Strings with normalized whitespace; title and summary have HTML/JATS tags removed |
| `authors`, `categories` | Lists of cleaned strings |
| `published`, `updated` | ISO dates, `YYYY-MM-DD`; missing or invalid `updated` uses `published` |
| `age_days` | Integer `(run_date.date() - published_date).days` |
| `authors_joined`, `categories_joined` | Comma-separated list values |
| `summary_chars` | Character count of the cleaned summary |
| `text_for_embedding` | Five newline-separated lines: `Title`, `Authors`, `Published`, `Categories`, `Summary` |

The quality gate requires 5–5000 rows, unique DOI values, nonblank `paper_id`, `title`, `summary`, and `text_for_embedding`, and summaries of at least 30 characters. Freshness is calculated from `published` against the current UTC date: a row is stale when its age exceeds 180 days; the dataset is fresh when at most 25% of rows are stale and every publication date is valid.

## PHA 3 benchmark

`data/eval/test_set.json` contains five deterministic samples with types `summary`, `authors`, `date`, `category`, and `multi_hop`. Each sample has both `type` and `question_type` for compatibility, plus `id`, `question`, `ground_truth`, and `ground_truth_doc_ids`. Multi-hop retrieval is counted as a hit only when all listed document IDs are retrieved. Evaluation reports hybrid Hit Rate (exact-title assistance plus vector search) separately from pure vector Hit Rate. LLM judge results include the method; heuristic fallback must not be described as an LLM score.
