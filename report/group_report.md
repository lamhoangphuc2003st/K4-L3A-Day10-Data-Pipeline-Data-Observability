# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

- Lớp: K4-L3-DAY10
- Ngày chạy: 2026-09-25
- Tên nhóm, thành viên, MSSV, vai trò, link repo: **nhóm sẽ điền trước khi nộp**.

## 2. Tóm tắt kết quả

Pipeline dùng snapshot Crossref 24 bài khi Crossref API không có sẵn; chế độ live API đã được thử riêng với hai bài và hai file raw tạm. Dữ liệu được parse, chuẩn hóa, khử DOI trùng, tính tuổi bài báo và ghép văn bản cho MiniLM. Great Expectations 1.x kiểm tra số dòng, các cột bắt buộc, DOI duy nhất và độ dài summary; thêm tín hiệu noise, title ngắn, thiếu DOI so với raw và freshness SLA. Dữ liệu baseline vượt quality gate trước khi vào ChromaDB. Bộ 10 câu hỏi gồm summary, authors, date, categories được giữ cố định qua ba lần đánh giá.

Trong thí nghiệm, sáu lỗi được tiêm trên bản sao clean. Hit Rate giảm từ 1.000 xuống 0.500, Token F1 từ 0.613 xuống 0.232 và LLM Judge từ 5 xuống 3. Quality gate và freshness đều báo FAIL. Dữ liệu lỗi chỉ được index trong collection riêng phục vụ thí nghiệm. Repair đọc lại raw records, làm sạch và index lại, đưa Hit Rate về 1.000, Token F1 lên 0.729 và LLM Judge về 5. Benchmark dùng OpenCode Go với model GLM-5.3-Flash để tạo câu trả lời và chấm Judge. Tên nhóm và thông tin nộp bài là phần duy nhất nhóm cần bổ sung.

## 3. Kiến trúc và data contract

```text
Crossref API / offline snapshot → raw response + raw records → clean CSV/JSON
→ GX + freshness gate → MiniLM → ChromaDB → 10-question evaluation
→ corruption copy → isolated index/evaluation → repair from raw → comparison
```

Raw record gồm `paper_id`, `title`, `summary`, `authors`, `categories`, `published` và metadata URL. Cleaning bỏ bản ghi thiếu DOI/title hoặc ngày không hợp lệ, chuẩn hóa whitespace và khử trùng DOI. `age_days = (run_date - published).days`. `text_for_embedding` ghép Title, Authors, Published, Categories, Summary. Index lưu metadata gốc cần trả lời và dùng collection `papers-baseline`, `papers-corrupted`, `papers-repaired`.

## 4. Tái hiện

- Python 3.12.10; `python -c "import chromadb, great_expectations, sentence_transformers; print('Môi trường sẵn sàng')"`: PASS.
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2`; top K: 4.
- `python script/run_phase1.py`: PASS.
- `python script/run_corruption_flow.py`: PASS.
- `python -m unittest discover -s tests -v`: 3 PASS.
- Offline mặc định; `REFRESH_SOURCE=1` kích hoạt Crossref live API. Live đã được kiểm tra với file tạm, không thay snapshot.
- LLM provider: OpenCode Go; model: glm-5.3-flash. API key chỉ nằm trong file .env bị Git bỏ qua.

## 5. Quality, freshness và benchmark

| Signal | Baseline | Corrupted | Repaired |
|---|---:|---:|---:|
| GX + integrity gate | PASS | FAIL | PASS |
| Freshness SLA | PASS | FAIL | PASS |
| Stale rows (>180 ngày) | 1 | 10 | 1 |
| Missing DOI so với raw | 0 | 5 | 0 |
| Duplicate DOI | 0 | 2 | 0 |
| Hit Rate | 1.000 | 0.500 | 1.000 |
| Token F1 | 0.613 | 0.232 | 0.729 |
| LLM Judge score | 5 | 3 | 5 |
| LLM Judge accuracy | 1.0 | 0.5 | 1.0 |

Freshness FAIL khi tỷ lệ bài quá 180 ngày vượt 25%. Trong corruption, tỷ lệ stale là 10/21 = 47.6%. GX phát hiện duplicate DOI và summary thiếu; kiểm tra bổ sung phát hiện noise, title ngắn và thiếu DOI so với raw.

## 6. Sáu lỗi và repair

| Corruption | Bản ghi | Tín hiệu |
|---|---:|---|
| Drop latest records (20%) | 5 | Raw source coverage FAIL; Hit Rate giảm |
| Blank summary | 2 | GX summary length FAIL |
| Inject noise | 2 | NoNoiseRuns FAIL |
| Truncate title (<8 ký tự) | 2 | TitleLengthAtLeast8 FAIL |
| Stale date (365 ngày) | 8 | Freshness FAIL |
| Duplicate rows | 2 | GX uniqueness FAIL |

Log lưu DOI, before/after và count ở data/results/corruption_log.json. Repair không chỉnh từng dòng lỗi; nó đọc data/raw/crossref_records.json, chạy lại cleaning, quality/freshness, rồi thay dữ liệu trong collection repaired. Chroma giữ 24/21/24 documents theo từng collection. Hit Rate và Judge phục hồi; Token F1 sau repair khác baseline vì LLM diễn đạt câu trả lời khác nhau dù cùng dữ liệu và test set.

## 7. Vấn đề tích hợp và giới hạn

- Model MiniLM chưa có trong cache; sau khi cho phép truy cập Hugging Face, model được tải và pipeline chạy được offline từ cache.
- QA starter ưu tiên khớp title trước vector search; đã bỏ đường tắt này trong benchmark để Hit Rate phản ánh Chroma retrieval thực.
- Judge starter dùng heuristic khi LLM lỗi; đã thay bằng phép chấm có cấu trúc từ OpenCode Go. Câu trả lời RAG cũng được sinh từ ngữ cảnh truy xuất bằng LLM.
- Nhóm cần tự điền danh tính, phân công trong `docs/TEAM.md`, báo cáo cá nhân và link repo/LMS. Chưa thể xác nhận các bước nộp bài đó.
