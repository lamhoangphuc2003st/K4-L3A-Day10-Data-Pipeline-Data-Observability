# Member Role Report - Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Trần Hồng Sơn |
| MSSV | 2A202602475 |
| Khóa/Lớp | K4 - K4-L3-DAY10 |
| Tên nhóm | one4all |
| Vai trò chính | Corruption & repair owner |
| Repository | https://github.com/lamhoangphuc2003st/K4A-Day10-one4all |
| Ngày hoàn thành | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Corruption suite | `corrupt_clean_dataframe` | clean df, log path | `corruption_log.json`, df corrupted | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Hỗ trợ tích hợp | Cả nhóm | Kiểm tra dữ liệu repaired khớp baseline. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| 6 lỗi có seed 42, rebuild `text_for_embedding`, ghi log | `corruption.py` | 24 -> 22 dòng | Xem `corruption_log.json` |
| Đối chiếu tác động lên metric | `data/results/` | Hit rate 0.7 | So sánh answers baseline/corrupted |

Output cụ thể: `corruption_log.json` ghi 5/2/2/2/3/3 và 24 -> 22 dòng.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Mô phỏng sự cố dữ liệu thực tế để chứng minh silent failure và giá trị của quality gate.

### Cách triển khai

Xoá 20% bản ghi mới nhất (5), rồi dùng shuffle theo `random_state=42` chọn riêng các tập cho blank summary (2), noise (2), cắt title còn 6 ký tự (2), lùi ngày 365 ngày (3, cập nhật `age_days`) và nhân bản dòng (3). Cuối cùng dựng lại `text_for_embedding`.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | DataFrame sạch |
| Output | DataFrame hỏng + log JSON |
| Module phụ thuộc | `cleaning.build_text_for_embedding` |
| Module sử dụng output | `corruption_flow.py` |
| Điều kiện lỗi cần xử lý | Df quá nhỏ, chỉ số chọn trùng |

### Cách xác minh

```bash
python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** lệnh chạy không lỗi và in đúng tín hiệu hoàn thành trong `docs/Guide.md`.
- **Kết quả thực tế:** `corruption_log.json` ghi 5/2/2/2/3/3 và 24 -> 22 dòng.
- **Artifact/log:** `data/` (không chứa secret).

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Ngẫu nhiên hay xác định
- **Các phương án đã cân nhắc:** (a) random không seed; (b) seed cố định
- **Phương án đã chọn:** (b)
- **Lý do:** Tái lập kết quả để so sánh và bảo vệ
- **Bằng chứng quyết định phù hợp:** Chạy lại cho cùng log

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Hit rate giảm nhưng cần biết vì sao
- **Lệnh hoặc bước tái hiện:** Đối chiếu `corrupted_answers.json` với `corruption_log.json`
- **Nguyên nhân gốc:** 3 doc ground-truth (...812, ...804, ...802) nằm trong 5 bản ghi bị xoá
- **Cách xử lý:** Ghi nhận quan hệ nhân quả trong báo cáo
- **Cách xác minh sau khi sửa:** eval_001-003 có `retrieval_hit=False`
- **Điều học được:** Lỗi mất dữ liệu mới gây hại nhất khi test set phủ bài mới

## 7. Hiểu biết về luồng end-to-end

1. Dữ liệu: Crossref (hoặc snapshot) -> raw records -> clean df -> `text_for_embedding` -> MiniLM -> ChromaDB.
2. Test set có ground-truth doc ID; `retrieval_hit_rate` kiểm tra doc đúng có trong top-4, token F1/judge chấm câu trả lời.
3. Quality checks (GX) kiểm tra hợp đồng dữ liệu (số dòng, null, trùng, độ dài); freshness đo độ tươi qua `age_days`.
4. Cùng test set để chênh lệch chỉ do dữ liệu.
5. Repair thành công khi Gate `True` và metrics repaired bằng baseline (1.0/1.0/1.0/5.0).

## 8. Phân tích kết quả

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0 | 0.7 | 1.0 | Giảm 0.3, do drop latest. |
| `mean_token_f1` | 1.0 | 0.8 | 1.0 | Giảm 0.2; eval_002 vẫn F1=1.0 dù miss retrieval. |
| `judge_accuracy` | 1.0 | 0.8 | 1.0 | heuristic fallback, không phải LLM judge |
| `mean_judge_score` | 5.0 | 4.2 | 5.0 | như trên |
| Quality checks | Pass | Fail (2 check) | Pass | Duplicate và blank summary bị Gate bắt. |
| Freshness status | Fresh | Fresh (4/22) | Fresh (1/24) | dưới ngưỡng 25% |

1. Drop latest + duplicate + blank summary -> Gate `False` (2 check fail) -> hit rate 1.0 -> 0.7, F1 1.0 -> 0.8.
2. Repair từ raw -> Gate `True`, 24 dòng -> metrics về baseline.

Corruption ảnh hưởng rõ nhất: drop latest records, vì 3/10 tài liệu ground-truth bị xoá (eval_001-003).

Khác kỳ vọng: freshness không báo động (4/22 = 18.2% < 25%), thấy trong `corrupted_freshness_report.json`.

Lưu ý trung thực: judge trong lần chạy là heuristic fallback vì LLM evaluator không khả dụng; Ragas không chạy.

## 9. Điều học được và hướng cải thiện

1. Corruption phải tái lập được.
2. Không phải lỗi nào cũng có check tương ứng (noise, truncate title).
3. Repair từ raw xoá lỗi tận gốc.

### Nếu có thêm thời gian

Thêm mức độ (severity) cho từng lỗi và vẽ đường cong metric theo mức; đo bằng hit rate ở mỗi mức.

## 10. Cam kết của thành viên

Thành viên tự kiểm tra và đánh dấu sau khi rà soát lại nội dung:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc thành viên khác.

**Họ và tên:** Trần Hồng Sơn  
**Ngày xác nhận:** 2026-09-25

