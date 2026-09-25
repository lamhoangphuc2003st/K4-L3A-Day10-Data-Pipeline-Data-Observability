# Member Role Report - Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Lâm Hoàng Phúc |
| MSSV | 2A202602582 |
| Khóa/Lớp | K4 - K4-L3-DAY10 |
| Tên nhóm | one4all |
| Vai trò chính | Trưởng nhóm / Pipeline integration & evidence owner |
| Repository | https://github.com/lamhoangphuc2003st/K4A-Day10-one4all |
| Ngày hoàn thành | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Baseline orchestration | `phase1.main`, `save_clean` | Settings, raw records | Đủ artifact pha 1 | Hoàn thành |
| Corruption & repair flow | `corruption_flow.main` | baseline metrics, clean json | `corrupted_*`, `repaired_*`, `corruption_report.md` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Hỗ trợ tích hợp | Cả nhóm | Chạy tích hợp, đối chiếu report với artifact, xử lý lỗi môi trường Windows. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Nối raw -> clean -> index -> evaluate -> quality -> report | `pipelines/phase1.py` | Baseline metrics + `phase1_report.md` | `python script/run_phase1.py` |
| Corrupt -> evaluate -> repair từ raw -> so sánh 3 trạng thái | `pipelines/corruption_flow.py` | Bảng 3 cột | `python script/run_corruption_flow.py` |

Output cụ thể: Cả hai lệnh thành công; bảng 3 cột in ra console.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Ghép các module độc lập thành hai luồng chạy được và tái lập.

### Cách triển khai

Phase1 đọc raw records, clean, ghi CSV/JSON, build index, sinh test set nếu chưa có, evaluate, chạy quality/freshness và sinh báo cáo. Corruption flow luôn tạo dữ liệu hỏng từ clean JSON, dùng collection riêng cho từng trạng thái, và repair bằng cách chạy lại `build_clean_dataframe` trên raw records nên idempotent.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `data/raw`, `test_set.json`, `baseline_metrics.json` |
| Output | Metrics + report của 3 trạng thái |
| Module phụ thuộc | mọi module `src/` |
| Module sử dụng output | `docs/`, báo cáo |
| Điều kiện lỗi cần xử lý | Thiếu baseline metrics, LLM không khả dụng |

### Cách xác minh

```bash
python script/run_phase1.py && python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** lệnh chạy không lỗi và in đúng tín hiệu hoàn thành trong `docs/Guide.md`.
- **Kết quả thực tế:** Cả hai lệnh thành công; bảng 3 cột in ra console.
- **Artifact/log:** `data/` (không chứa secret).

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Repair từ đâu
- **Các phương án đã cân nhắc:** (a) undo trên df corrupted; (b) rebuild từ raw records
- **Phương án đã chọn:** (b)
- **Lý do:** Đảm bảo nguồn tin cậy và idempotent
- **Bằng chứng quyết định phù hợp:** Repaired metrics = baseline (1.0/1.0/1.0/5.0)

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `UnicodeEncodeError: 'charmap' codec can't encode character`
- **Lệnh hoặc bước tái hiện:** Chạy lệnh kiểm tra CP0 trên Windows
- **Nguyên nhân gốc:** Console dùng cp1252 mặc định
- **Cách xử lý:** Đặt `PYTHONUTF8=1`
- **Cách xác minh sau khi sửa:** Lệnh in `Đã tải 24 bài báo`
- **Điều học được:** Môi trường cũng là một phần của pipeline

## 7. Hiểu biết về luồng end-to-end

1. Dữ liệu: Crossref (hoặc snapshot) -> raw records -> clean df -> `text_for_embedding` -> MiniLM -> ChromaDB.
2. Test set có ground-truth doc ID; `retrieval_hit_rate` kiểm tra doc đúng có trong top-4, token F1/judge chấm câu trả lời.
3. Quality checks (GX) kiểm tra hợp đồng dữ liệu (số dòng, null, trùng, độ dài); freshness đo độ tươi qua `age_days`.
4. Cùng test set để chênh lệch chỉ do dữ liệu.
5. Repair thành công khi Gate `True` và metrics repaired bằng baseline (1.0/1.0/1.0/5.0).

## 8. Phân tích kết quả

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0 | 0.7 | 1.0 | Tổng hợp từ pipeline; nguyên nhân là mất 3 doc ground-truth. |
| `mean_token_f1` | 1.0 | 0.8 | 1.0 | Ghi trong `corrupted_metrics.json`. |
| `judge_accuracy` | 1.0 | 0.8 | 1.0 | heuristic fallback, không phải LLM judge |
| `mean_judge_score` | 5.0 | 4.2 | 5.0 | như trên |
| Quality checks | Pass | Fail (2 check) | Pass | Gate fail ở corrupted, pass ở repaired. |
| Freshness status | Fresh | Fresh (4/22) | Fresh (1/24) | dưới ngưỡng 25% |

1. Drop latest + duplicate + blank summary -> Gate `False` (2 check fail) -> hit rate 1.0 -> 0.7, F1 1.0 -> 0.8.
2. Repair từ raw -> Gate `True`, 24 dòng -> metrics về baseline.

Corruption ảnh hưởng rõ nhất: drop latest records, vì 3/10 tài liệu ground-truth bị xoá (eval_001-003).

Khác kỳ vọng: freshness không báo động (4/22 = 18.2% < 25%), thấy trong `corrupted_freshness_report.json`.

Lưu ý trung thực: judge trong lần chạy là heuristic fallback vì LLM evaluator không khả dụng; Ragas không chạy.

## 9. Điều học được và hướng cải thiện

1. Repair phải bắt nguồn từ raw.
2. Tách collection Chroma cho từng trạng thái.
3. Đối chiếu report với artifact trước khi kết luận.

### Nếu có thêm thời gian

Chạy Gate trước khi index và chặn nạp nếu fail; đo bằng việc dữ liệu corrupted không vào collection production.

## 10. Cam kết của thành viên

Thành viên tự kiểm tra và đánh dấu sau khi rà soát lại nội dung:

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [ ] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc thành viên khác.

**Họ và tên:** Lâm Hoàng Phúc
**Ngày xác nhận:** _(thành viên tự điền)_
