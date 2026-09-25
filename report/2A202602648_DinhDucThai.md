# Member Role Report - Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Đinh Đức Thái |
| MSSV | 2A202602648 |
| Khóa/Lớp | K4 - K4-L3-DAY10 |
| Tên nhóm | DAYTEN |
| Vai trò chính | Cleaning, data model & test-set owner |
| Repository | https://github.com/lamhoangphuc2003st/K4-L3A-Day10-Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Cleaning & data model | `build_clean_dataframe`, `build_text_for_embedding` | `list[PaperRecord]`, run_date | `data/clean/papers_clean.*` | Hoàn thành |
| Evaluation set | `build_test_set` | clean df | `data/eval/test_set.json` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Hỗ trợ tích hợp | Cả nhóm | Kiểm tra schema clean cùng Duy để GX chạy đúng cột. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Chuẩn hoá, tính `age_days`, tạo cột helper, dedup | `cleaning.py` | 24 dòng sạch | `Clean thành công 24 dòng` |
| Sinh 10 câu hỏi 4 loại, ground-truth doc ID | `testset.py` | 10 câu | `Sinh được 10 câu hỏi test` |

Output cụ thể: In 10; file test_set.json có 10 mục.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Cần bảng sạch có schema ổn định để embed và một đề thi cố định để đo suy giảm.

### Cách triển khai

`published` giữ dạng chuỗi ISO để tương thích metadata Chroma và `pd.read_json`; `age_days` tính theo ngày. Dòng có title rỗng hoặc summary < 30 ký tự bị lọc, dedup theo `paper_id`, sắp xếp mới nhất trước. Test set chọn paper cách đều trên danh sách sắp theo ngày để phủ cả bài mới lẫn cũ, câu hỏi bám đúng cụm từ QA agent nhận diện.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | List `PaperRecord`, `run_date` |
| Output | DataFrame 16 cột |
| Module phụ thuộc | `crossref.py` |
| Module sử dụng output | `index.py`, `quality.py`, `corruption.py` |
| Điều kiện lỗi cần xử lý | Ngày không parse được, title chứa dấu `'` |

### Cách xác minh

```bash
python -c "from core.config import load_settings; from evaluation.testset import build_test_set; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); print(len(build_test_set(df, s.paths.eval_testset)))"
```

- **Kết quả mong đợi:** lệnh chạy không lỗi và in đúng tín hiệu hoàn thành trong `docs/Guide.md`.
- **Kết quả thực tế:** In 10; file test_set.json có 10 mục.
- **Artifact/log:** `data/` (không chứa secret).

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Chọn paper nào cho test set
- **Các phương án đã cân nhắc:** (a) ngẫu nhiên; (b) N bài mới nhất; (c) cách đều theo ngày
- **Phương án đã chọn:** (c)
- **Lý do:** Xác định, phủ cả bài mới lẫn cũ nên corruption drop-latest đo được
- **Bằng chứng quyết định phù hợp:** Hit rate 1.0 -> 0.7 sau khi xoá bài mới

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Title chứa `'` làm regex `'([^']+)'` của QA agent sai
- **Lệnh hoặc bước tái hiện:** Đọc `qa.py`
- **Nguyên nhân gốc:** Regex lấy chuỗi giữa hai dấu nháy đơn nên title có nháy bị cắt
- **Cách xử lý:** Loại title có `'` khỏi pool test set
- **Cách xác minh sau khi sửa:** Baseline hit rate 1.0
- **Điều học được:** Contract ngầm giữa test set và QA agent phải được kiểm tra

## 7. Hiểu biết về luồng end-to-end

1. Dữ liệu: Crossref (hoặc snapshot) -> raw records -> clean df -> `text_for_embedding` -> MiniLM -> ChromaDB.
2. Test set có ground-truth doc ID; `retrieval_hit_rate` kiểm tra doc đúng có trong top-4, token F1/judge chấm câu trả lời.
3. Quality checks (GX) kiểm tra hợp đồng dữ liệu (số dòng, null, trùng, độ dài); freshness đo độ tươi qua `age_days`.
4. Cùng test set để chênh lệch chỉ do dữ liệu.
5. Repair thành công khi Gate `True` và metrics repaired bằng baseline (1.0/1.0/1.0/5.0).

## 8. Phân tích kết quả

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0 | 0.7 | 1.0 | 3 miss đều thuộc bài mới nhất mà test set cố ý phủ tới. |
| `mean_token_f1` | 1.0 | 0.8 | 1.0 | F1 giảm khi bài ground-truth bị xoá. |
| `judge_accuracy` | 1.0 | 0.8 | 1.0 | heuristic fallback, không phải LLM judge |
| `mean_judge_score` | 5.0 | 4.2 | 5.0 | như trên |
| Quality checks | Pass | Fail (2 check) | Pass | Clean schema đủ cột để 6 check chạy được. |
| Freshness status | Fresh | Fresh (4/22) | Fresh (1/24) | dưới ngưỡng 25% |

1. Drop latest + duplicate + blank summary -> Gate `False` (2 check fail) -> hit rate 1.0 -> 0.7, F1 1.0 -> 0.8.
2. Repair từ raw -> Gate `True`, 24 dòng -> metrics về baseline.

Corruption ảnh hưởng rõ nhất: drop latest records, vì 3/10 tài liệu ground-truth bị xoá (eval_001-003).

Khác kỳ vọng: freshness không báo động (4/22 = 18.2% < 25%), thấy trong `corrupted_freshness_report.json`.

Lưu ý trung thực: judge trong lần chạy là heuristic fallback vì LLM evaluator không khả dụng; Ragas không chạy.

## 9. Điều học được và hướng cải thiện

1. Schema là hợp đồng giữa các module.
2. Đề thi phải phủ đủ loại dữ liệu bị lỗi.
3. Kiểu dữ liệu (str/Timestamp) có thể phá metadata index.

### Nếu có thêm thời gian

Tăng test set lên >= 30 câu để metric bớt thô; đo bằng độ lệch giữa các lần chạy.

## 10. Cam kết của thành viên

Thành viên tự kiểm tra và đánh dấu sau khi rà soát lại nội dung:

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [ ] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc thành viên khác.

**Họ và tên:** Đinh Đức Thái
**Ngày xác nhận:** _(thành viên tự điền)_
