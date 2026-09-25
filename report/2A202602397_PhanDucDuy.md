# Member Role Report - Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Phan Đức Duy |
| MSSV | 2A202602397 |
| Khóa/Lớp | K4 - K4-L3-DAY10 |
| Tên nhóm | one4all |
| Vai trò chính | Observability owner (GX 1.x, freshness, reporting) |
| Repository | https://github.com/lamhoangphuc2003st/K4A-Day10-one4all |
| Ngày hoàn thành | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Quality & freshness | `run_data_quality_checks`, `build_freshness_report` | DataFrame, Settings | `data/quality/*.json` | Hoàn thành |
| Reporting | `generate_phase1_report`, `generate_corruption_report` | metrics, quality, freshness | `phase1_report.md`, `corruption_report.md` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Hỗ trợ tích hợp | Cả nhóm | Phối hợp Thái về schema clean để GX chạy. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| GX 1.x ephemeral context, 6 expectation | `quality.py` | `success`, `failed_checks` | `Quality check status = True` |
| Freshness SLA và báo cáo Markdown | `quality.py`, `reporting.py` | Bảng 3 trạng thái | Mở `corruption_report.md` |

Output cụ thể: True cho baseline; corrupted fail 2 check.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Phát hiện dữ liệu xấu trước khi vào vector store thay vì để agent trả lời sai âm thầm.

### Cách triển khai

Dùng `gx.get_context(mode="ephemeral")`, `add_pandas`, `add_dataframe_asset`, `add_batch_definition_whole_dataframe`; mỗi expectation validate riêng để có kết quả từng check. Freshness tính tỉ lệ dòng có `age_days` > 180, cờ `is_fresh` sai khi > 25%. Kết quả ghi JSON theo tên trạng thái.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | DataFrame, `report_name` |
| Output | dict `success`, `checks`, `freshness` |
| Module phụ thuộc | `great_expectations` |
| Module sử dụng output | `phase1.py`, `corruption_flow.py` |
| Điều kiện lỗi cần xử lý | df rỗng, cột thiếu |

### Cách xác minh

```bash
python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); print(run_data_quality_checks(df,s,'baseline')['success'])"
```

- **Kết quả mong đợi:** lệnh chạy không lỗi và in đúng tín hiệu hoàn thành trong `docs/Guide.md`.
- **Kết quả thực tế:** True cho baseline; corrupted fail 2 check.
- **Artifact/log:** `data/` (không chứa secret).

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** `success` có gộp freshness không
- **Các phương án đã cân nhắc:** (a) gộp; (b) tách riêng
- **Phương án đã chọn:** (b)
- **Lý do:** Tách rõ hai loại tín hiệu (contract vs độ tươi)
- **Bằng chứng quyết định phù hợp:** Corrupted: gate False nhưng freshness True; hai tín hiệu độc lập

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Kết quả khác kỳ vọng: freshness vẫn `True` sau stale-date
- **Lệnh hoặc bước tái hiện:** Xem `data/quality/corrupted_freshness_report.json`
- **Nguyên nhân gốc:** Chỉ 4/22 (18.2%) dòng quá hạn, thấp hơn ngưỡng 25%
- **Cách xử lý:** Giữ ngưỡng theo Guide và ghi nhận trung thực trong báo cáo
- **Cách xác minh sau khi sửa:** Report hiển thị đúng `is_fresh=True`
- **Điều học được:** Báo cáo phải bám số liệu, không bám kỳ vọng

## 7. Hiểu biết về luồng end-to-end

1. Dữ liệu: Crossref (hoặc snapshot) -> raw records -> clean df -> `text_for_embedding` -> MiniLM -> ChromaDB.
2. Test set có ground-truth doc ID; `retrieval_hit_rate` kiểm tra doc đúng có trong top-4, token F1/judge chấm câu trả lời.
3. Quality checks (GX) kiểm tra hợp đồng dữ liệu (số dòng, null, trùng, độ dài); freshness đo độ tươi qua `age_days`.
4. Cùng test set để chênh lệch chỉ do dữ liệu.
5. Repair thành công khi Gate `True` và metrics repaired bằng baseline (1.0/1.0/1.0/5.0).

## 8. Phân tích kết quả

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0 | 0.7 | 1.0 | Thấp hơn baseline do mất tài liệu. |
| `mean_token_f1` | 1.0 | 0.8 | 1.0 | Giảm theo hit rate. |
| `judge_accuracy` | 1.0 | 0.8 | 1.0 | heuristic fallback, không phải LLM judge |
| `mean_judge_score` | 5.0 | 4.2 | 5.0 | như trên |
| Quality checks | Pass | Fail (2 check) | Pass | `paper_id_unique` (6 dòng) và `summary_length_min_30` (2 dòng) fail. |
| Freshness status | Fresh | Fresh (4/22) | Fresh (1/24) | dưới ngưỡng 25% |

1. Drop latest + duplicate + blank summary -> Gate `False` (2 check fail) -> hit rate 1.0 -> 0.7, F1 1.0 -> 0.8.
2. Repair từ raw -> Gate `True`, 24 dòng -> metrics về baseline.

Corruption ảnh hưởng rõ nhất: drop latest records, vì 3/10 tài liệu ground-truth bị xoá (eval_001-003).

Khác kỳ vọng: freshness không báo động (4/22 = 18.2% < 25%), thấy trong `corrupted_freshness_report.json`.

Lưu ý trung thực: judge trong lần chạy là heuristic fallback vì LLM evaluator không khả dụng; Ragas không chạy.

## 9. Điều học được và hướng cải thiện

1. Quality gate khác freshness.
2. Ngưỡng cần chọn dựa trên dữ liệu.
3. Judge dự phòng cần được ghi rõ trong báo cáo.

### Nếu có thêm thời gian

Thêm check độ dài title và pattern ký tự rác để bắt noise/truncate; đo bằng số lỗi được Gate phát hiện trên 6 corruption.

## 10. Cam kết của thành viên

Thành viên tự kiểm tra và đánh dấu sau khi rà soát lại nội dung:

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [ ] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc thành viên khác.

**Họ và tên:** Phan Đức Duy
**Ngày xác nhận:** _(thành viên tự điền)_
