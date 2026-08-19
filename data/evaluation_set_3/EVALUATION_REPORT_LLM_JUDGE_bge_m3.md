# Báo cáo đánh giá LLM-as-Judge / RAGAS-style

- Thời điểm chạy: `2026-08-18T09:33:01`
- Judge model: `gpt-4o-mini`
- Số case đã chấm: `200`
- Nguồn input: `D:\RAG_luat_giao_thong\data\evaluation_set_3\eval_outputs_bge_m3.jsonl`
- Đây là LLM-as-judge theo rubric RAGAS-style, không phải package `ragas` chính thức.

## Tổng quan

| Metric | Score |
|---|---:|
| faithfulness | 0.764 |
| answer_relevancy | 0.868 |
| context_precision | 0.865 |
| context_recall | 0.761 |
| answer_correctness | 0.717 |
| abstention_quality | 0.930 |

## Theo nhóm câu hỏi

| Category | N | Faithfulness | Relevancy | Context Precision | Context Recall | Correctness | Abstention |
|---|---:|---:|---:|---:|---:|---:|---:|
| diagnostic | 30 | 0.700 | 0.817 | 0.767 | 0.683 | 0.633 | 0.900 |
| production | 140 | 0.793 | 0.880 | 0.880 | 0.787 | 0.747 | 0.929 |
| robustness | 30 | 0.693 | 0.860 | 0.890 | 0.720 | 0.660 | 0.967 |

## 15 case correctness thấp nhất

| ID | Category | Correctness | Faithfulness | Notes |
|---|---|---:|---:|---|
| GDV3_012 | production | 0.000 | 0.500 | Câu trả lời không chính xác vì nó không trích dẫn đúng điều luật liên quan đến tốc độ di chuyển chậm hơn. Thông tin được cung cấp không hỗ trợ cho yêu cầu của câu hỏi. |
| GDV3_029 | production | 0.000 | 1.000 | Câu trả lời không chính xác về mức phạt và không trích dẫn đúng điều khoản liên quan đến việc cầm ô khi ngồi sau xe máy. |
| GDV3_031 | production | 0.000 | 0.000 | Câu trả lời không cung cấp thông tin liên quan đến số người tối đa mà xe chở người bốn bánh có gắn động cơ được thiết kế chở, và không có căn cứ pháp lý nào được trích dẫn để hỗ trợ cho câu trả lời. |
| GDV3_035 | production | 0.000 | 0.000 | Câu trả lời không cung cấp thông tin chính xác về niên hạn sử dụng tối đa cho xe ô tô đưa đón trẻ em, mặc dù có quy định rõ ràng trong tài liệu pháp luật. Cần phải trích dẫn đúng quy định để đảm bảo tính chính xác và đầy đủ. |
| GDV3_036 | production | 0.000 | 0.500 | Câu trả lời không chính xác về số lượng người quản lý cần bố trí, theo quy định là tối thiểu 02 người, nhưng câu trả lời lại ghi là 01 người. Điều này làm giảm độ chính xác và độ tin cậy của câu trả lời. |
| GDV3_056 | production | 0.000 | 0.500 | Câu trả lời không cung cấp thông tin chính xác về giá trị của giấy phép lái xe và không đề cập đến việc tiếp tục sử dụng theo thời hạn ghi trên giấy phép như trong dữ liệu vàng. |
| GDV3_069 | production | 0.000 | 0.000 | Câu trả lời không liên quan đến chức năng của đường cứu nạn mà nói về xe cứu hộ, không phù hợp với yêu cầu của câu hỏi. |
| GDV3_075 | production | 0.000 | 0.000 | Câu trả lời không liên quan đến câu hỏi và không cung cấp thông tin hợp lệ nào từ ngữ liệu đã truy xuất. |
| GDV3_080 | production | 0.000 | 0.500 | Câu trả lời không cung cấp thông tin chính xác về thời gian báo cáo và chứa nhiều thông tin không liên quan đến câu hỏi chính, làm giảm độ chính xác và tính liên quan của câu trả lời. |
| GDV3_085 | production | 0.000 | 0.000 | Câu trả lời không liên quan đến câu hỏi và không cung cấp thông tin pháp lý chính xác. |
| GDV3_096 | production | 0.000 | 0.500 | Câu trả lời không chính xác vì không đề cập đến các thiết bị giám sát hành trình và thiết bị ghi nhận hình ảnh người lái xe như yêu cầu trong câu hỏi. Thông tin về phù hiệu và niêm yết không liên quan đến thiết bị quản lý cần thiết cho xe c |
| GDV3_108 | production | 0.000 | 0.000 | Câu trả lời không đề cập đến thông tin cơ bản về phương tiện như biển số xe, loại xe, sức chứa và chủ sở hữu, mà chỉ liệt kê các trách nhiệm của đơn vị kinh doanh vận tải. Điều này làm giảm độ chính xác và tính trung thực của câu trả lời. |
| GDV3_110 | production | 0.000 | 0.500 | Mặc dù câu trả lời có liên quan đến câu hỏi, nhưng nó không cung cấp thông tin chính xác về việc có cần xin lại hay không. Câu trả lời không đúng với nội dung của văn bản pháp luật đã trích dẫn. |
| GDV3_112 | production | 0.000 | 0.000 | Câu trả lời không cung cấp thông tin liên quan đến câu hỏi và không có căn cứ pháp lý nào để hỗ trợ cho các tuyên bố. Không có thông tin bắt buộc nào được đề cập. |
| GDV3_113 | production | 0.000 | 0.000 | Câu trả lời không liên quan đến câu hỏi và không cung cấp thông tin cần thiết về việc trừ điểm GPLX. Không có thông tin về việc bị trừ điểm khi chỉ còn 2 điểm, do đó không đáp ứng yêu cầu của câu hỏi. |

## Lưu ý

- LLM judge có sai số và có thể dao động nhẹ giữa các lần chạy.
- Các điểm này nên đọc cùng báo cáo deterministic `EVALUATION_REPORT.md`.
- Package `ragas` chưa được cài trong môi trường, nên report này tự triển khai rubric tương đương các metric RAGAS phổ biến.
