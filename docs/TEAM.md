# Danh Sách Thành Viên & Báo Cáo Phân Công Nhóm

- **Tên Nhóm:** `DAYTEN`
- **Mã Nhóm / Lớp:** `K4-L3-DAY10`
- **Repository Nộp Bài:** https://github.com/lamhoangphuc2003st/K4-L3A-Day10-Data-Pipeline-Data-Observability

---

## # Thành viên

| STT | Họ và tên | MSSV | Email | Vai trò & Phân công công việc | Báo cáo cá nhân |
|---:|---|---|---|---|---|
| 1 | Đinh Trường An | 2A202602393 | _(chưa cung cấp)_ | Source owner (Raw ingestion) (`src/ingestion/crossref.py`) | `report/2A202602393_DinhTruongAn.md` |
| 2 | Đinh Đức Thái | 2A202602648 | _(chưa cung cấp)_ | Cleaning, data model & test-set owner (`src/ingestion/cleaning.py`, `src/evaluation/testset.py`) | `report/2A202602648_DinhDucThai.md` |
| 3 | Lâm Hoàng Phúc | 2A202602582 | _(chưa cung cấp)_ | Trưởng nhóm / Pipeline integration & evidence owner (`src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py`, `src/core/`) | `report/2A202602582_LamHoangPhuc.md` |
| 4 | Phan Đức Duy | 2A202602397 | _(chưa cung cấp)_ | Observability owner (GX 1.x, freshness, reporting) (`src/observability/quality.py`, `src/observability/reporting.py`) | `report/2A202602397_PhanDucDuy.md` |
| 5 | Trần Hồng Sơn | 2A202602475 | _(chưa cung cấp)_ | Corruption & repair owner (`src/ingestion/corruption.py`; kiểm tra dữ liệu corrupted/repaired) | `report/2A202602475_TranHongSon.md` |

*Nhóm 5 thành viên, phân công theo bảng "Nhóm 5 thành viên" trong `report/README.md`.*

---

## # Cá nhân

### ## Đinh Trường An - 2A202602393
- **Vai trò:** Source owner (Raw ingestion).
- **Công việc chi tiết:**
  - Hoàn thiện `parse_crossref_payload` (bóc DOI, title, abstract, author, subject, ngày; loại thẻ `<jats:p>`; bỏ record thiếu trường bắt buộc).
  - `fetch_source_records`: gọi API có retry/backoff (429/5xx), lưu `crossref_response.json` + `crossref_records.json`, tự fallback về snapshot khi lỗi mạng.
  - `load_raw_records`: nạp lại raw records thành `PaperRecord` cho luồng repair.
- **Điều học được / Đóng góp chính:**
  - Data lineage: luôn giữ raw nguyên bản để có nguồn tin cậy phục hồi.

### ## Đinh Đức Thái - 2A202602648
- **Vai trò:** Cleaning, data model & test-set owner.
- **Công việc chi tiết:**
  - `build_clean_dataframe`: chuẩn hoá whitespace, tính `age_days`, tạo `authors_joined`, `categories_joined`, `summary_chars`, `text_for_embedding`, khử trùng `paper_id`.
  - `build_test_set`: 10 câu hỏi 4 loại (summary/authors/date/categories) rải đều từ bài mới đến cũ, ghi `data/eval/test_set.json`.
- **Điều học được / Đóng góp chính:**
  - Schema/contract sạch quyết định chất lượng embedding và cách chấm điểm.

### ## Lâm Hoàng Phúc - 2A202602582
- **Vai trò:** Trưởng nhóm / Pipeline integration & evidence owner.
- **Công việc chi tiết:**
  - Viết `pipelines/phase1.py` (raw → clean → index → evaluate → quality → report) và `pipelines/corruption_flow.py` (corrupt → evaluate → repair từ raw → so sánh 3 trạng thái).
  - Chạy end-to-end, đối chiếu report với artifact, quản lý contributor trên nhánh `main`.
- **Điều học được / Đóng góp chính:**
  - Idempotent pipeline: repair luôn dựng lại từ raw, không từ dữ liệu đã hỏng.

### ## Phan Đức Duy - 2A202602397
- **Vai trò:** Observability owner (GX 1.x, freshness, reporting).
- **Công việc chi tiết:**
  - `run_data_quality_checks` theo chuẩn GX 1.x (ephemeral context, 4 nhóm expectation) và `build_freshness_report` (stale > 180 ngày, ngưỡng 25%).
  - `generate_phase1_report`, `generate_corruption_report` (bảng Baseline vs Corrupted vs Repaired).
- **Điều học được / Đóng góp chính:**
  - Quality gate và freshness là hai tín hiệu khác nhau; cần cả hai để chặn silent failure.

### ## Trần Hồng Sơn - 2A202602475
- **Vai trò:** Corruption & repair owner.
- **Công việc chi tiết:**
  - `corrupt_clean_dataframe`: 6 loại lỗi (drop latest, blank summary, noise, truncate title, stale date, duplicate) với seed cố định, ghi `corruption_log.json`.
  - Kiểm tra dữ liệu corrupted/repaired và mức phục hồi metrics.
- **Điều học được / Đóng góp chính:**
  - Corruption phải tái lập được (seed) để so sánh công bằng.
