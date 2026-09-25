# Member Role Report - Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Đinh Đức Thái |
| MSSV | 2A202602648 |
| Khóa/Lớp | K4 - K4-L3-DAY10 |
| Tên nhóm | one4all |
| Vai trò chính | Cleaning, data model & test-set owner |
| Repository làm việc | https://github.com/lamhoangphuc2003st/K4-L3A-Day10-Data-Pipeline-Data-Observability |
| Ngày cập nhật kết quả | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Cleaning & data model | `src/ingestion/cleaning.py`: `build_clean_dataframe()` | `list[PaperRecord]`, `run_date` | DataFrame 16 cột; pipeline lưu `data/clean/papers_clean.csv` và `.json` | Đã triển khai, kiểm thử |
| Evaluation set | `src/evaluation/testset.py`: `build_test_set()` | Clean DataFrame, đường dẫn output | `data/eval/test_set.json`, 108 mẫu thuộc 5 dạng | Đã triển khai, kiểm thử |

`text_for_embedding` được xây dựng bên trong `build_clean_dataframe()`; module hiện tại không có hàm riêng tên `build_text_for_embedding()`.

### Việc hỗ trợ tích hợp

Đối chiếu schema sạch với các cột Chroma, GX và module corruption sử dụng; xác minh lệnh tạo benchmark; rà soát artifacts baseline/corrupted/repaired. Các số liệu end-to-end bên dưới là bằng chứng tích hợp chung, không đồng nghĩa nhận toàn bộ ownership các module của nhóm.

## 3. Kết quả theo vai trò

| Nhiệm vụ | Code/artifact | Kết quả | Cách xác minh |
| --- | --- | --- | --- |
| Chuẩn hóa, tính tuổi, khử trùng lặp, tạo nội dung embedding | [cleaning.py](../src/ingestion/cleaning.py) | 24 dòng sạch, 16 cột | [papers_clean.json](../data/clean/papers_clean.json), [test_cleaning.py](../tests/test_cleaning.py) |
| Tạo câu hỏi và đáp án có nguồn | [testset.py](../src/evaluation/testset.py) | 108 câu: 24 `summary`, 24 `authors`, 24 `date`, 24 `category`, 12 `multi_hop` | [test_set.json](../data/eval/test_set.json), [test_testset.py](../tests/test_testset.py) |
| Kiểm tra tích hợp | Hai pipeline baseline và corruption/repair | Cả hai lệnh chạy thành công với cấu hình ở mục 4 | [phase1_report.md](../data/reports/phase1_report.md), [corruption_report.md](../data/reports/corruption_report.md) |

Benchmark lưu trên đĩa có **108 mẫu**. Lần đánh giá được báo cáo chọn **10 mẫu**, mỗi dạng 2 câu, bằng `EVAL_MAX_SAMPLES=10`; không cắt file benchmark xuống còn 10 mục.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Cần bảng sạch có schema ổn định để lập chỉ mục và benchmark có đáp án truy vết được tới tài liệu nguồn. Quy tắc cleaning và điều kiện kiểm tra chất lượng phải được phân biệt rõ.

### Cách triển khai cleaning

- Chuẩn hóa khoảng trắng trong title, summary, tác giả và danh mục; bỏ phần tử trống và trùng trong danh sách tác giả/danh mục.
- Chuẩn hóa `paper_id` bằng cách bỏ khoảng trắng đầu/cuối và chuyển chữ thường; giữ bản hợp lệ đầu tiên theo khóa này.
- Loại dòng thiếu ID, title, summary hoặc không parse được ngày xuất bản. Cleaning **không lọc summary dưới 30 ký tự**; đó là expectation ở Quality Gate.
- Parse ngày theo UTC, đưa ngày xuất bản về đầu ngày rồi tính `age_days = (run_date - published).days`. Giữ tuổi âm để có thể nhận biết ngày tương lai.
- Lưu `published` và `updated` dạng ISO `YYYY-MM-DD`; `updated` thiếu hoặc không hợp lệ thì dùng ngày xuất bản.
- Tạo `authors_joined`, `categories_joined`, `summary_chars`, `text_for_embedding`; sắp ngày xuất bản giảm dần rồi ID tăng dần. Không sửa các `PaperRecord` đầu vào.

```text
Title: <Tiêu đề>
Authors: <Các tác giả, phân cách bằng dấu phẩy>
Published: <YYYY-MM-DD>
Categories: <Các danh mục, phân cách bằng dấu phẩy>
Summary: <Tóm tắt>
```

### Cách triển khai benchmark

`build_test_set()` chọn bài có đủ ID, title, summary, authors, categories và ngày hợp lệ; loại ID trùng rồi sắp theo `paper_id`. Mỗi bài tạo bốn câu đơn tài liệu. Các cặp có lĩnh vực riêng khác nhau tạo câu `multi_hop`; mỗi bài tham gia tối đa một cặp. Đáp án kết hợp tóm tắt của cả hai bài, không tự suy diễn quan hệ hay kết quả nghiên cứu mới.

Mỗi mẫu có `id`, `type`, `question`, `ground_truth`, `ground_truth_doc_ids`; giữ thêm `question_type` để tương thích evaluator. ID được tạo xác định từ loại câu hỏi và hash DOI nguồn. Câu `date` dùng đáp án năm-tháng `YYYY-MM`; câu `multi_hop` có hai DOI. Nếu không đủ hai bài hoàn chỉnh hoặc không có cặp khác lĩnh vực, hàm báo lỗi trước khi ghi đè benchmark.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input cleaning | Danh sách `PaperRecord` và thời điểm chạy |
| Output cleaning | DataFrame 16 cột: 11 trường của `PaperRecord` và 5 trường helper |
| Input benchmark | DataFrame có `paper_id`, `title`, `summary`, `authors`, `categories`, `published` |
| Output benchmark | Danh sách mẫu và file JSON tại `settings.paths.eval_testset` |
| Module cung cấp dữ liệu | `ingestion.crossref` |
| Module dùng dữ liệu | `retrieval.index`, `observability.quality`, `ingestion.corruption`, `evaluation.metrics` |
| Kiểm tra biên | Input rỗng, ngày sai, thiếu metadata, ID trùng, không có cặp liên ngành |

### Cách xác minh

Trong PowerShell tại thư mục repo, đã kích hoạt `.venv` và có file dữ liệu sạch:

```powershell
$env:PYTHONPATH = "src"
python -c "from core.config import load_settings; from evaluation.testset import build_test_set; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); ts=build_test_set(df, s.paths.eval_testset); print('Test set:', len(ts), 'cau hoi')"
```

Kết quả đã quan sát: **108 câu hỏi**. Cấu hình lần chạy end-to-end làm bằng chứng:

```powershell
$env:LLM_PROVIDER = "mock"
$env:EVAL_MAX_SAMPLES = "10"
$env:REFRESH_SOURCE = "false"
$env:REFRESH_TEST_SET = "false"
$env:RUN_RAGAS = "false"
$env:HF_HUB_OFFLINE = "1"
python script/run_phase1.py
python script/run_corruption_flow.py
```

`HF_HUB_OFFLINE=1` dùng MiniLM đã tải sẵn. Môi trường xác minh: Python 3.11.9, GX 1.23.1. **72 kiểm thử đã đạt**, gồm cleaning, benchmark, lấy mẫu, quality, corruption và phục hồi lặp lại. Judge của lần đo dùng heuristic fallback; Ragas không chạy.

## 5. Một quyết định kỹ thuật quan trọng

**Quyết định:** Tách benchmark đầy đủ khỏi tập mẫu chạy nhanh.

Benchmark sinh xác định từ toàn bộ bài hợp lệ, thay vì chọn ngẫu nhiên hoặc chỉ chọn bài mới nhất. Khi chạy nhanh, evaluator lấy luân phiên theo loại câu hỏi để 10 mẫu phủ đủ 5 dạng. `EVAL_MAX_SAMPLES=0` dùng toàn bộ benchmark.

Cách này giữ nguyên 108 câu và DOI để tái lập, đồng thời giảm số lần chấm LLM khi thử nghiệm. Cả ba trạng thái dùng cùng ID câu hỏi; pipeline kiểm tra điều kiện này trước khi ghi báo cáo. Đánh đổi là kết quả trên 10 mẫu chỉ mô tả tập con, chưa đại diện cho toàn bộ 108 câu.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** `ImportError: cannot import name 'load_or_create_test_set' from 'evaluation.testset'`.
- **Nguyên nhân:** Lệnh kiểm tra dùng API không tồn tại: `load_or_create_test_set()`, `s.paths.test_set_json` và `ts.samples`.
- **Cách xử lý:** Dùng `build_test_set(df, s.paths.eval_testset)`; kết quả là danh sách nên đếm bằng `len(ts)`.
- **Xác minh:** Terminal in `Tín hiệu hoàn thành: Test set gồm 108 câu hỏi`; file JSON có đủ 5 dạng và các trường bắt buộc.
- **Điều học được:** Kiểm tra chữ ký hàm, tên cấu hình và kiểu trả về trực tiếp trong code trước khi viết lệnh tích hợp.

Lỗi thiếu `papers_clean.json` cũng được xử lý bằng cách chạy cleaning từ raw và lưu JSON/CSV trước khi gọi benchmark hoặc Quality Gate.

## 7. Hiểu biết về luồng end-to-end

1. Crossref hoặc snapshot cung cấp raw records; cleaning tạo dữ liệu sạch và nội dung embedding.
2. GX kiểm tra số dòng, trường bắt buộc, ID duy nhất và độ dài summary. Freshness cảnh báo khi tỷ lệ bài có `age_days > 180` **vượt 25%**.
3. MiniLM tạo vector; Chroma lưu collection baseline, corrupted và repaired riêng biệt.
4. Benchmark cung cấp đáp án và DOI nguồn. Retrieval Hit Rate yêu cầu tìm đủ tài liệu tham chiếu trong kết quả truy hồi, gồm cả hai DOI cho `multi_hop`. Token F1 trong code dùng tập token chuẩn hóa để đo mức trùng đáp án.
5. Sáu kiểu corruption tác động lên bản sao dữ liệu sạch. Luồng thí nghiệm vẫn đánh giá corrupted dù Gate thất bại để đo ảnh hưởng.
6. Repair đọc lại raw, chạy cleaning với cùng `run_date`, rồi tạo chỉ mục repaired. Pipeline kiểm tra repaired giống baseline và hai lần phục hồi giống nhau; không sửa ngược trên dữ liệu corrupted.
7. Repair được xác minh bằng tính nhất quán dữ liệu, Quality Gate, freshness và metrics thực đo; không giả định baseline phải có điểm tuyệt đối.

## 8. Phân tích kết quả

Số liệu ngày 2026-09-25, dùng cùng **10 câu hỏi** cho cả ba trạng thái:

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét |
| --- | ---: | ---: | ---: | --- |
| Số dòng | 24 | 24 | 24 | Bỏ 4 bài mới nhất rồi thêm 4 dòng trùng; cùng số dòng không có nghĩa dữ liệu đầy đủ. |
| `retrieval_hit_rate` | 0,9000 | 0,8000 | 0,9000 | Giảm 10 điểm phần trăm, phục hồi về baseline. |
| `mean_token_f1` | 0,6022 | 0,5400 | 0,6022 | Giảm khoảng 0,0622. |
| `judge_accuracy` | 0,6000 | 0,5000 | 0,6000 | Judge dùng heuristic fallback. |
| `mean_judge_score` | 3,0000 | 2,8000 | 3,0000 | Không phải chấm độc lập bằng LLM. |
| Quality Gate | Pass: 7/7 | Fail: 5/7 | Pass: 7/7 | Corrupted thất bại ở summary không null và `paper_id` duy nhất. |
| Freshness | Đạt: 1/24 bài cũ | Cảnh báo: 13/24 bài cũ | Đạt: 1/24 bài cũ | Tỷ lệ 4,17% → 54,17% → 4,17%. |

### Bằng chứng ở mức câu hỏi

- `summary-6308c23437857697`: vẫn truy hồi đúng tài liệu nhưng Token F1 giảm từ khoảng **0,6222 xuống 0**. Truy hồi đúng DOI chưa bảo đảm nội dung trả lời còn đủ thông tin.
- `multi_hop-e93b342e18411ea9`: retrieval hit chuyển từ `true` sang `false`, còn Token F1 vẫn khoảng **0,2933**. Tìm thiếu tài liệu và chất lượng câu trả lời là hai tín hiệu khác nhau cần theo dõi.

Vì nhiều loại lỗi được tiêm đồng thời, chưa thể quy toàn bộ mức giảm cho một kịch bản riêng. Mức giảm cũng chưa đạt ví dụ “Hit Rate ≤40%” trong đề. Dữ liệu chứng minh chất lượng suy giảm và phục hồi; riêng Gate thất bại hoặc F1 thấp chưa đủ kết luận AI đã bịa thông tin.

### Artifacts đối chiếu

- Metrics: [baseline](../data/results/baseline_metrics.json), [corrupted](../data/results/corrupted_metrics.json), [repaired](../data/results/repaired_metrics.json).
- Câu trả lời: [baseline_answers.json](../data/results/baseline_answers.json), [corrupted_answers.json](../data/results/corrupted_answers.json), [repaired_answers.json](../data/results/repaired_answers.json).
- Log tiêm lỗi: [corruption_log.json](../data/results/corruption_log.json).
- Quality/freshness corrupted: [corrupted_quality_report.json](../data/quality/corrupted_quality_report.json), [corrupted_freshness_report.json](../data/quality/corrupted_freshness_report.json).
- Xác minh phục hồi: [corruption_report.md](../data/reports/corruption_report.md), [test_corruption_flow.py](../tests/test_corruption_flow.py).

## 9. Điều học được và hướng cải thiện

1. Schema và tên API là hợp đồng giữa các module; sai tên hàm hoặc đường dẫn có thể chặn toàn bộ luồng.
2. Phân biệt kích thước benchmark với số câu thực sự được đánh giá; không diễn giải kết quả 10 mẫu thành kết quả của 108 mẫu.
3. Đúng số dòng hoặc đúng DOI chưa đủ bảo đảm chất lượng; cần kết hợp nội dung, freshness và đánh giá câu trả lời.
4. Repair từ raw cần giữ cố định thời điểm tính tuổi trong phép so sánh, kiểm tra tính lặp lại và bảo toàn snapshot.

### Nếu có thêm thời gian

Chạy đủ 108 câu với ngân sách phù hợp; tách thí nghiệm từng loại corruption; đánh giá bằng LLM thật và Ragas khi có cấu hình khả dụng. Hoàn thiện QA cho câu hỏi năm-tháng, title chứa dấu nháy và câu đa tài liệu: code hiện trích đáp án từ kết quả đứng đầu, nên baseline chưa đạt điểm tuyệt đối. Đây là hướng cải thiện, không phải phần đã xác nhận hoàn thành.

### Phần nghiệm thu còn lại

Hai pipeline đã chạy thành công, có đủ hai báo cáo và `src/` không còn `TODO(student)` hoặc `NotImplementedError`. `.env` được Git bỏ qua và không nằm trong danh sách file được theo dõi. Phiên xác minh này chưa commit/push các thay đổi và chưa xác nhận biểu đồ Contributors trên GitHub; nhóm cần hoàn tất phần đó riêng.

## 10. Cam kết của thành viên

Thành viên tự kiểm tra và đánh dấu sau khi rà soát nội dung, phạm vi đóng góp và kết quả:

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [ ] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc thành viên khác.

**Họ và tên:** Đinh Đức Thái

**Ngày xác nhận:** 25/09/2026
