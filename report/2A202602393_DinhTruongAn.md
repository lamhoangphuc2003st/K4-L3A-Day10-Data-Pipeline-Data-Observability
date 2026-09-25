# Member Role Report - Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Đinh Trường An |
| MSSV | 2A202602393 |
| Khóa/Lớp | K4 - K4-L3-DAY10 |
| Tên nhóm | one4all |
| Vai trò chính | Source owner (Raw ingestion) |
| Repository | https://github.com/lamhoangphuc2003st/K4A-Day10-one4all |
| Ngày hoàn thành | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Raw ingestion | `parse_crossref_payload`, `fetch_source_records`, `load_raw_records` | Query/filter Crossref hoặc snapshot | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Hỗ trợ tích hợp | Cả nhóm | Cung cấp `load_raw_records` cho luồng repair của Phúc và Sơn. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Parse payload, bỏ thẻ JATS, chuẩn hoá ngày từ `date-parts` | `crossref.py` | 24 `PaperRecord` | Lệnh CP0 in `Đã tải 24 bài báo` |
| Retry/backoff và fallback snapshot | `_request_live`, `fetch_source_records` | Raw không mất khi API lỗi | Đọc code + chạy offline |

Output cụ thể: In 24 record; hai file raw được ghi lại.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Cần lấy metadata bài báo thành schema thống nhất và giữ bản gốc để repair, kể cả khi Crossref trả 429 hoặc mất mạng.

### Cách triển khai

Payload được duyệt theo `message.items`; abstract bỏ tag bằng regex rồi normalize whitespace; ngày lấy theo thứ tự published, published-online, published-print, issued, cuối cùng `created`. Record thiếu DOI/title/abstract/ngày bị bỏ. Mặc định (dev mode) đọc snapshot; `REFRESH_SOURCE=1` mới gọi API với 3 lần retry.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Settings + payload JSON |
| Output | list `PaperRecord`, 2 file raw |
| Module phụ thuộc | `core/config.py` |
| Module sử dụng output | `cleaning.py`, `corruption_flow.py` |
| Điều kiện lỗi cần xử lý | 429/5xx, timeout, thiếu trường ngày |

### Cách xác minh

```bash
python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); print(len(fetch_source_records(s)))"
```

- **Kết quả mong đợi:** lệnh chạy không lỗi và in đúng tín hiệu hoàn thành trong `docs/Guide.md`.
- **Kết quả thực tế:** In 24 record; hai file raw được ghi lại.
- **Artifact/log:** `data/` (không chứa secret).

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Snapshot hay live API là mặc định?
- **Các phương án đã cân nhắc:** (a) luôn gọi API; (b) mặc định snapshot, live khi `REFRESH_SOURCE=1`
- **Phương án đã chọn:** (b)
- **Lý do:** Tái lập được, không phụ thuộc mạng/429
- **Bằng chứng quyết định phù hợp:** Chạy nhiều lần cho cùng 24 record và cùng metrics

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Snapshot không có trường `deposited`/`indexed`
- **Lệnh hoặc bước tái hiện:** Chạy `parse_crossref_payload` trên snapshot
- **Nguyên nhân gốc:** Payload không có nguồn cho trường `updated`
- **Cách xử lý:** Fallback `updated = published`
- **Cách xác minh sau khi sửa:** Đủ 24 record, không exception
- **Điều học được:** Payload thực tế có thể thiếu trường; parser cần fallback

## 7. Hiểu biết về luồng end-to-end

1. Dữ liệu: Crossref (hoặc snapshot) -> raw records -> clean df -> `text_for_embedding` -> MiniLM -> ChromaDB.
2. Test set có ground-truth doc ID; `retrieval_hit_rate` kiểm tra doc đúng có trong top-4, token F1/judge chấm câu trả lời.
3. Quality checks (GX) kiểm tra hợp đồng dữ liệu (số dòng, null, trùng, độ dài); freshness đo độ tươi qua `age_days`.
4. Cùng test set để chênh lệch chỉ do dữ liệu.
5. Repair thành công khi Gate `True` và metrics repaired bằng baseline (1.0/1.0/1.0/5.0).

## 8. Phân tích kết quả

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0 | 0.7 | 1.0 | Không đổi ở khâu ingestion; snapshot cố định giúp so sánh công bằng. |
| `mean_token_f1` | 1.0 | 0.8 | 1.0 | Raw không đổi nên repair dựng lại đúng baseline. |
| `judge_accuracy` | 1.0 | 0.8 | 1.0 | heuristic fallback, không phải LLM judge |
| `mean_judge_score` | 5.0 | 4.2 | 5.0 | như trên |
| Quality checks | Pass | Fail (2 check) | Pass | Repair đọc lại `crossref_records.json` do phần này tạo. |
| Freshness status | Fresh | Fresh (4/22) | Fresh (1/24) | dưới ngưỡng 25% |

1. Drop latest + duplicate + blank summary -> Gate `False` (2 check fail) -> hit rate 1.0 -> 0.7, F1 1.0 -> 0.8.
2. Repair từ raw -> Gate `True`, 24 dòng -> metrics về baseline.

Corruption ảnh hưởng rõ nhất: drop latest records, vì 3/10 tài liệu ground-truth bị xoá (eval_001-003).

Khác kỳ vọng: freshness không báo động (4/22 = 18.2% < 25%), thấy trong `corrupted_freshness_report.json`.

Lưu ý trung thực: judge trong lần chạy là heuristic fallback vì LLM evaluator không khả dụng; Ragas không chạy.

## 9. Điều học được và hướng cải thiện

1. Luôn lưu raw trước khi biến đổi.
2. Retry cần backoff và có đường lui offline.
3. Nguồn dữ liệu quyết định độ tin cậy của mọi metric phía sau.

### Nếu có thêm thời gian

Ghi thêm timestamp và hash của raw response để kiểm chứng lineage.

## 10. Cam kết của thành viên

Thành viên tự kiểm tra và đánh dấu sau khi rà soát lại nội dung:

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [ ] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc thành viên khác.

**Họ và tên:** Đinh Trường An
**Ngày xác nhận:** _(thành viên tự điền)_
