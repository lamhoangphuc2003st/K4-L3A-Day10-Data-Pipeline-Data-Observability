# Group Report - Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin | Nội dung |
| --- | --- |
| Khóa/Lớp | K4 - K4-L3-DAY10 |
| Tên nhóm | DAYTEN |
| Repository | https://github.com/lamhoangphuc2003st/K4-L3A-Day10-Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-09-25 |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Đinh Trường An | 2A202602393 | Source owner (Raw ingestion) | `src/ingestion/crossref.py` |
| 2 | Đinh Đức Thái | 2A202602648 | Cleaning, data model & test-set owner | `src/ingestion/cleaning.py`, `src/evaluation/testset.py` |
| 3 | Lâm Hoàng Phúc | 2A202602582 | Trưởng nhóm / Pipeline integration & evidence owner | `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py`, `src/core/` |
| 4 | Phan Đức Duy | 2A202602397 | Observability owner (GX 1.x, freshness, reporting) | `src/observability/quality.py`, `src/observability/reporting.py` |
| 5 | Trần Hồng Sơn | 2A202602475 | Corruption & repair owner | `src/ingestion/corruption.py`; kiểm tra dữ liệu corrupted/repaired |

## 2. Tóm tắt kết quả

Nhóm đã hoàn thiện toàn bộ các khối `TODO(student)` trong `src/`: ingestion Crossref (retry + fallback snapshot), cleaning, test set 10 câu, Quality Gate Great Expectations 1.x kèm Freshness SLA, corruption suite 6 lỗi, idempotent repair và hai báo cáo Markdown. Baseline pipeline tạo ra `data/clean/papers_clean.csv|json`, `data/embeddings/`, `data/chroma/` (collection `papers-baseline`), `data/eval/test_set.json`, `data/results/baseline_metrics.json`, `data/quality/*` và `data/reports/phase1_report.md`. Baseline đạt hit rate 1.0 và token F1 1.0. Sau khi tiêm 6 lỗi (24 -> 22 dòng), hit rate giảm còn 0.7, token F1 và judge accuracy còn 0.8; lỗi ảnh hưởng rõ nhất là *drop latest records* vì 3 tài liệu ground-truth (eval_001-003) nằm trong 5 bản ghi bị xóa. Quality Gate báo `False` (fail `paper_id_unique`, `summary_length_min_30`). Sau repair từ `data/raw/crossref_records.json`, mọi metric trở lại đúng giá trị baseline và Gate về `True`. Giới hạn quan trọng: judge LLM không khả dụng trong lần chạy nên hệ thống dùng heuristic judge dự phòng (dựa trên token F1) và Ragas không được bật; freshness không bị kích hoạt trên dữ liệu lỗi vì chỉ 4/22 dòng quá hạn (< 25%).

## 3. Kiến trúc và luồng dữ liệu

```text
Crossref API / snapshot data/raw
    -> raw response + raw records
    -> cleaning (age_days, text_for_embedding, dedup)
    -> MiniLM embedding + ChromaDB (papers-baseline)
    -> evaluation baseline (test_set.json, 10 câu)
    -> GX 1.x quality + freshness reports
    -> corruption (6 lỗi, seed 42) -> papers-corrupted -> evaluate
    -> repair từ raw records -> papers-repaired -> evaluate
    -> data/reports/corruption_report.md
```

| Khối | Input | Xử lý chính | Output/artifact | Owner |
| --- | --- | --- | --- | --- |
| Ingestion | Crossref API hoặc `data/raw/crossref_response.json` | Retry/backoff 429/5xx, parse, bỏ thẻ JATS, fallback snapshot | `data/raw/crossref_records.json` | Đinh Trường An |
| Cleaning | raw records | Chuẩn hoá text, `age_days`, dedup `paper_id`, lọc summary < 30 ký tự | `data/clean/papers_clean.*` | Đinh Đức Thái |
| Embedding/index | clean df | all-MiniLM-L6-v2, Chroma cosine (code starter `retrieval/`) | `data/chroma/`, `data/embeddings/*.json` | Lâm Hoàng Phúc (tích hợp) |
| Evaluation | clean df, index | Test set 10 câu; hit rate, token F1, judge | `data/eval/test_set.json`, `data/results/*_metrics.json` | Đinh Đức Thái / Phan Đức Duy |
| Observability | df | 6 GX expectation + freshness | `data/quality/*.json` | Phan Đức Duy |
| Corruption/repair | clean df / raw records | 6 lỗi có seed; rebuild từ raw | `corruption_log.json`, `*_repaired.*` | Trần Hồng Sơn |
| Orchestration | tất cả | Thứ tự chạy phase1 -> corruption flow | `phase1_report.md`, `corruption_report.md` | Lâm Hoàng Phúc |

## 4. Cách tái hiện kết quả

| Biến/cấu hình | Giá trị sử dụng |
| --- | --- |
| `LLM_PROVIDER` | openai (judge không gọi được -> dùng heuristic fallback) |
| `LLM_MODEL` | gpt-4o-mini |
| Embedding model | sentence-transformers/all-MiniLM-L6-v2 |
| Số lượng Crossref records | 24 (snapshot `data/raw/`) |
| Retrieval `top_k` | 4 |
| Freshness threshold | 180 ngày; cảnh báo khi stale > 25% |
| Random seed | 42 (corruption) |

Không chứa API key hay `.env` trong báo cáo.

```bash
python -m pip install -e .
# Windows: đặt PYTHONUTF8=1 để tránh UnicodeEncodeError khi in tiếng Việt
python script/run_phase1.py
python script/run_corruption_flow.py
```

| Lệnh | Trạng thái | Thời điểm chạy gần nhất | Bằng chứng |
| --- | --- | --- | --- |
| Baseline pipeline | Thành công | 2026-09-25 | `data/results/baseline_metrics.json`, `data/reports/phase1_report.md` |
| Corruption flow | Thành công | 2026-09-25 | `data/reports/corruption_report.md`, `data/results/corruption_log.json` |

## 5. Ingestion, cleaning và data contract

| Thuộc tính | Giá trị |
| --- | --- |
| Source | Crossref REST API `https://api.crossref.org/works` (mặc định đọc snapshot offline) |
| Query/filter | `agentic retrieval augmented generation large language model`; `from-pub-date:<today-180d>,has-abstract:true` |
| Số record nhận được | 24 |
| Cơ chế retry/backoff | 3 lần, ngủ 1s/2s/4s với 429/5xx; thất bại -> fallback snapshot |

| Trường | Kiểu | Bắt buộc? | Ý nghĩa | Xử lý khi thiếu/sai |
| --- | --- | --- | --- | --- |
| `paper_id` | str | Có | DOI, khoá duy nhất | Bỏ record; dedup giữ bản đầu |
| `title` | str | Có | Tiêu đề | Bỏ record |
| `summary` | str | Có | Abstract đã bỏ thẻ JATS | Bỏ record nếu rỗng; cleaning lọc < 30 ký tự |
| `authors`, `categories` | list[str] | Không | Tác giả, chuyên ngành | Danh sách rỗng |
| `published` | str YYYY-MM-DD | Có | Ngày xuất bản | Fallback `created`; bỏ nếu không parse được |
| `age_days` | int | Có | `run_date - published` | Tính lại mỗi lần chạy |
| `text_for_embedding` | str | Có | Title/Authors/Published/Categories/Summary | Sinh lại sau corruption |

| Quy tắc | Dimension | Số record bị tác động | Cách xác minh |
| --- | --- | ---: | --- |
| Bỏ thẻ JATS, normalize whitespace | Validity | 24 (đầu vào) | `data/clean/papers_clean.json` |
| Dedup theo `paper_id` | Uniqueness | 0 (snapshot sạch) | GX `paper_id_unique` = True |
| Loại summary < 30 ký tự / title rỗng | Completeness | 0 | GX `summary_length_min_30` = True |

`text_for_embedding` ghép 5 dòng `Title/Authors/Published/Categories/Summary`; document ID trong Chroma là `paper_id::index`; `age_days = (ngày chạy - published).days`.

## 6. Evaluation setup

| Thành phần | Cấu hình thực tế |
| --- | --- |
| Số câu hỏi | 10 |
| `question_type` | summary (3), authors (3), date (2), categories (2) |
| Ground-truth document ID | DOI của bài được hỏi, lấy từ clean df |
| Embedding model | all-MiniLM-L6-v2 |
| Vector store/collection | ChromaDB cosine: `papers-baseline`, `papers-corrupted`, `papers-repaired` |
| Retrieval `top_k` | 4 |
| LLM provider/model | openai / gpt-4o-mini; judge fallback heuristic |
| Test set dùng chung | `data/eval/test_set.json` |

Test set được sinh một lần từ dữ liệu sạch và chỉ được đọc lại ở corrupted/repaired, nên chênh lệch metric chỉ do dữ liệu chứ không do đề thi.

## 7. Kết quả baseline

| Artifact | Đường dẫn | Trạng thái | Ghi chú |
| --- | --- | --- | --- |
| Raw | `data/raw/` | Có | 2 file |
| Clean | `data/clean/` | Có | 24 dòng |
| Embedding/index | `data/embeddings/`, `data/chroma/` | Có | 24 docs |
| Eval set | `data/eval/test_set.json` | Có | 10 câu |
| Baseline metrics | `data/results/baseline_metrics.json` | Có | |
| Quality/freshness | `data/quality/` | Có | |
| Baseline report | `data/reports/phase1_report.md` | Có | |

| Metric | Giá trị | Diễn giải |
| --- | ---: | --- |
| `retrieval_hit_rate` | 1.0 | Cả 10 tài liệu ground-truth nằm trong top-4 |
| `mean_token_f1` | 1.0 | Câu trả lời trích xuất trùng ground truth |
| `judge_accuracy` | 1.0 | Heuristic fallback (LLM judge không dùng được) |
| `mean_judge_score` | 5.0 | Như trên |
| Ragas | N/A | Không bật (`RUN_RAGAS` chưa đặt) |

## 8. Data quality và freshness

| Check | Dimension | Ngưỡng | Kết quả baseline | Bằng chứng |
| --- | --- | --- | --- | --- |
| Row count | Volume | 5-5000 | Pass (24) | `data/quality/baseline_quality_report.json` |
| `paper_id`, `title`, `text_for_embedding` not null | Completeness | 0 null | Pass | như trên |
| `paper_id` unique | Uniqueness | 0 trùng | Pass | như trên |
| `summary` length | Validity | >= 30 ký tự | Pass | như trên |

| Thuộc tính | Giá trị |
| --- | --- |
| Đo tại | Clean dataset (`age_days`) |
| Timestamp mới nhất | 2026-07-22 |
| Ngưỡng | age > 180 ngày; cảnh báo nếu > 25% |
| Trạng thái baseline | Fresh |
| Lý do | 1/24 dòng quá hạn (4.17%) |

## 9. Corruption scenarios và repair

| Corruption | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair |
| --- | --- | ---: | --- | --- | --- |
| Drop latest | Xóa 20% bản ghi mới nhất | 5 | Freshness/volume | Mất doc ground-truth eval_001-003 -> hit false | Rebuild từ raw |
| Blank summary | Summary = "" | 2 | `summary_length_min_30` | Gate fail (2 dòng) | Rebuild từ raw |
| Inject noise | Thêm chuỗi rác vào summary | 2 | Không có check trực tiếp | Nhiễu embedding | Rebuild từ raw |
| Truncate title | Cắt title còn 6 ký tự | 2 | Không có check trực tiếp | Mất exact-title lookup | Rebuild từ raw |
| Stale date | Lùi `published` 365 ngày | 3 | Freshness | stale 4/22 (18.2%) < 25% -> chưa báo động | Rebuild từ raw |
| Duplicate rows | Nhân bản dòng | 3 | `paper_id_unique` | Gate fail (6 dòng trùng) | Rebuild từ raw |

Corruption log: `data/results/corruption_log.json` - Có; ghi seed, số dòng trước/sau (24 -> 22), loại lỗi, số lượng và `paper_id` bị tác động.

Repair luôn đọc `data/raw/crossref_records.json` rồi chạy lại `build_clean_dataframe`, không dùng dữ liệu corrupted, nên chạy lại bao nhiêu lần cũng cho cùng kết quả và loại bỏ lỗi tận gốc.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0 | 0.7 | 1.0 | -0.3 | 100% | 3 doc bị xóa |
| `mean_token_f1` | 1.0 | 0.8 | 1.0 | -0.2 | 100% | |
| `judge_accuracy` | 1.0 | 0.8 | 1.0 | -0.2 | 100% | heuristic judge |
| `mean_judge_score` | 5.0 | 4.2 | 5.0 | -0.8 | 100% | heuristic judge |
| Quality checks | Pass | Fail (2 check) | Pass | | | `paper_id_unique`, `summary_length_min_30` |
| Freshness | Fresh | Fresh (4/22 stale) | Fresh (1/24) | | | dưới ngưỡng 25% |

1. Drop latest records (xóa ...812, ...804, ...802) -> hit rate 1.0 -> 0.7 (eval_001, 002, 003 miss); token F1 giảm 0.2 vì hai câu trả sai.
2. Duplicate rows + blank summary -> Gate `False` (`paper_id_unique`, `summary_length_min_30`); repair từ raw -> Gate `True` và toàn bộ metric quay về baseline.

Kết quả khác kỳ vọng: freshness không báo động sau stale-date vì tỉ lệ stale 18.2% thấp hơn 25%; tín hiệu lỗi chỉ đến từ GX. Ngoài ra eval_002 (authors) vẫn có F1 = 1.0 dù miss retrieval, nên hit rate nghiêm ngặt hơn F1.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** `UnicodeEncodeError: 'charmap' codec can't encode character` khi in tiếng Việt trên Windows.
- **Nguyên nhân:** console mặc định cp1252.
- **Cách xử lý:** đặt `PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8` trước khi chạy.
- **Cách xác minh:** lệnh kiểm tra CP0 in `Đã tải 24 bài báo`.

Vấn đề thứ hai: tiêu đề có dấu `'` làm hỏng regex `'([^']+)'` của QA agent, nên `testset.py` loại các title đó khỏi test set.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng | Hướng cải thiện có thể kiểm chứng |
| --- | --- | --- |
| Judge LLM không khả dụng, dùng heuristic | judge_* chỉ phản ánh token F1 | Cấu hình API key hợp lệ rồi chạy lại và so sánh |
| Freshness không bắt được stale-date ở mức 18% | Lỗi date lọt qua freshness | Thêm check phân phối ngày / độ trễ bản ghi mới nhất |
| Không có check cho noise/truncate title | Hai lỗi chỉ thấy qua metric | Thêm expectation độ dài title, pattern ký tự rác |
| Test set chỉ 10 câu | Metric thô (bước 0.1) | Tăng lên >= 30 câu |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository (theo remote git hiện tại; nhóm kiểm tra lại nếu fork sang repo khác).
- [ ] Phân công khớp thực tế - **nhóm xác nhận**, vì phân công dựa trên gợi ý của `report/README.md`.
- [x] Lệnh tái hiện đã chạy lại ngày 2026-09-25.
- [x] Ba trạng thái dùng cùng `data/eval/test_set.json`.
- [x] Metrics khớp `data/results/`.
- [x] Quality/freshness khớp `data/quality/`.
- [ ] Mỗi thành viên rà soát và xác nhận báo cáo riêng.
- [x] Không có `.env`/secret trong báo cáo.
