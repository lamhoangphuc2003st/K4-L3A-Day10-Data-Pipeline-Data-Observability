# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

- Lớp: K4-L3-DAY10
- Ngày chạy: 2026-09-25
- Tên nhóm, thành viên, MSSV, vai trò, link repo: **nhóm sẽ điền trước khi nộp**.

## 2. Tóm tắt kết quả

Pipeline dùng snapshot Crossref 24 bài để chạy ổn định khi không có mạng; chế độ live API đã được thử riêng với hai bài và hai file raw tạm. Dữ liệu được parse, chuẩn hóa, khử DOI trùng, tính tuổi bài báo và ghép văn bản cho MiniLM. Great Expectations 1.x kiểm tra số dòng, các cột bắt buộc, DOI duy nhất và độ dài summary; thêm tín hiệu noise, title ngắn, thiếu DOI so với raw và freshness SLA. Dữ liệu baseline vượt quality gate trước khi vào ChromaDB. Bộ 10 câu hỏi gồm summary, authors, date, categories được giữ cố định qua ba lần đánh giá.

Trong thí nghiệm, sáu lỗi được tiêm trên bản sao clean. Hit Rate giảm từ 1.000 xuống 0.500, Token F1 từ 0.953 xuống 0.688. Quality gate và freshness đều báo FAIL. Dữ liệu lỗi chỉ được index trong collection riêng phục vụ thí nghiệm. Repair đọc lại raw records, làm sạch và index lại, đưa Hit Rate về 1.000 và Token F1 về 0.953. LLM Judge không có provider hoạt động nên score được ghi là unavailable, không tính điểm giả. Tên nhóm và thông tin nộp bài là phần duy nhất nhóm cần bổ sung.

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
- `python -m unittest discover -s tests -v`: 2 PASS.
- Offline mặc định; `REFRESH_SOURCE=1` kích hoạt Crossref live API. Live đã được kiểm tra với file tạm, không thay snapshot.
- LLM provider mặc định là Gemini nhưng chưa có API key; LLM Judge unavailable. Không đưa key vào repo.

## 5. Quality, freshness và benchmark

| Signal | Baseline | Corrupted | Repaired |
|---|---:|---:|---:|
| GX + integrity gate | PASS | FAIL | PASS |
| Freshness SLA | PASS | FAIL | PASS |
| Stale rows (>180 ngày) | 1 | 10 | 1 |
| Missing DOI so với raw | 0 | 5 | 0 |
| Duplicate DOI | 0 | 2 | 0 |
| Hit Rate | 1.000 | 0.500 | 1.000 |
| Token F1 | 0.953 | 0.688 | 0.953 |
| LLM Judge | unavailable | unavailable | unavailable |

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

Log lưu DOI, before/after và count ở `data/results/corruption_log.json`. Repair không chỉnh từng dòng lỗi; nó đọc `data/raw/crossref_records.json`, chạy lại cleaning, quality/freshness, rồi thay dữ liệu trong collection repaired. Lần chạy lặp cho cùng hash của clean CSV, repaired CSV, test set và ba file metrics; Chroma giữ 24/21/24 documents theo từng collection.

## 7. Vấn đề tích hợp và giới hạn

- Model MiniLM chưa có trong cache; sau khi cho phép truy cập Hugging Face, model được tải và pipeline chạy được offline từ cache.
- QA starter ưu tiên khớp title trước vector search; đã bỏ đường tắt này trong benchmark để Hit Rate phản ánh Chroma retrieval thực.
- Judge starter dùng heuristic khi LLM lỗi; đã thay bằng `null`/unavailable để không trình bày điểm heuristic như LLM Judge.
- Nhóm cần tự điền danh tính, phân công trong `docs/TEAM.md`, báo cáo cá nhân và link repo/LMS. Chưa thể xác nhận các bước nộp bài đó.
