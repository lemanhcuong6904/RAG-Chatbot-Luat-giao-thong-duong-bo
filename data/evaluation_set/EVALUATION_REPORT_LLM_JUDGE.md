# Báo cáo đánh giá LLM-as-Judge / RAGAS-style

- Thời điểm chạy: `2026-08-13T19:07:17`
- Judge model: `gpt-4o-mini`
- Số case đã chấm: `200`
- Nguồn input: `data/evaluation_set/eval_outputs.jsonl`
- Đây là LLM-as-judge theo rubric RAGAS-style, không phải package `ragas` chính thức.

## Tổng quan

| Metric | Score |
|---|---:|
| faithfulness | 0.749 |
| answer_relevancy | 0.929 |
| context_precision | 0.865 |
| context_recall | 0.694 |
| answer_correctness | 0.657 |
| abstention_quality | 0.940 |

## Theo nhóm câu hỏi

| Category | N | Faithfulness | Relevancy | Context Precision | Context Recall | Correctness | Abstention |
|---|---:|---:|---:|---:|---:|---:|---:|
| enumeration | 35 | 0.600 | 0.600 | 0.600 | 0.600 | 0.543 | 0.743 |
| exact_lookup | 35 | 1.000 | 1.000 | 1.000 | 1.000 | 0.929 | 1.000 |
| hard_negative | 20 | 0.835 | 0.990 | 0.890 | 0.135 | 0.580 | 0.850 |
| penalty | 40 | 0.588 | 1.000 | 0.950 | 0.655 | 0.405 | 1.000 |
| semantic_fact | 40 | 0.918 | 1.000 | 0.978 | 0.929 | 0.905 | 1.000 |
| temporal | 30 | 0.560 | 1.000 | 0.733 | 0.560 | 0.527 | 1.000 |

## 15 case correctness thấp nhất

| ID | Category | Correctness | Faithfulness | Notes |
|---|---|---:|---:|---|
| GT_013 | exact_lookup | 0.000 | 1.000 | Mặc dù câu trả lời đã trích dẫn chính xác nội dung từ văn bản pháp luật, tuy nhiên, thông tin về hiệu lực từ ngày 01 tháng 01 năm 2025 không được đề cập trong ngữ cảnh đã cho, dẫn đến việc không chính xác về thời gian hiệu lực của quy định. |
| GT_023 | exact_lookup | 0.000 | 1.000 | Mặc dù câu trả lời cung cấp thông tin chính xác về các hình thức khai thác và sử dụng cơ sở dữ liệu đường bộ, tuy nhiên, thông tin về hiệu lực từ ngày 01 tháng 01 năm 2025 không được hỗ trợ bởi ngữ cảnh đã truy xuất, dẫn đến việc đánh giá đ |
| GT_038 | enumeration | 0.000 | 0.000 | Mô hình không cung cấp thông tin liên quan đến câu hỏi và không có căn cứ để trả lời, do đó không đạt yêu cầu về độ chính xác và liên quan. |
| GT_039 | enumeration | 0.000 | 0.000 | Mô hình không cung cấp thông tin liên quan đến câu hỏi và không có căn cứ pháp lý nào được trích dẫn. |
| GT_041 | enumeration | 0.000 | 0.000 | Mô hình không cung cấp thông tin liên quan đến câu hỏi và không đưa ra câu trả lời chính xác nào. Do đó, tất cả các chỉ số đều bị đánh giá thấp. |
| GT_047 | enumeration | 0.000 | 1.000 | Mặc dù câu trả lời đã liệt kê đầy đủ các điểm theo quy định, tuy nhiên, thông tin về hiệu lực từ ngày 01 tháng 01 năm 2025 không được hỗ trợ bởi ngữ cảnh đã cho, dẫn đến việc không chính xác về mặt pháp lý. |
| GT_051 | enumeration | 0.000 | 1.000 | Mặc dù câu trả lời đã liệt kê đầy đủ các điểm quy định, nhưng thông tin về hiệu lực từ ngày 01 tháng 01 năm 2025 là không chính xác và không có trong ngữ cảnh đã cho. |
| GT_052 | enumeration | 0.000 | 0.000 | Mô hình không cung cấp thông tin liên quan đến câu hỏi và không có căn cứ để đưa ra câu trả lời chính xác. |
| GT_055 | enumeration | 0.000 | 0.000 | Mô hình không cung cấp thông tin liên quan đến câu hỏi và từ chối trả lời, điều này phù hợp với tình huống không có đủ dữ liệu. Tuy nhiên, không có thông tin nào được cung cấp để hỗ trợ câu hỏi, dẫn đến điểm số thấp cho các tiêu chí khác. |
| GT_060 | enumeration | 0.000 | 0.000 | Mô hình không cung cấp thông tin liên quan đến câu hỏi và từ chối trả lời, điều này là hợp lý vì nó không có đủ căn cứ. Tuy nhiên, câu trả lời không liên quan đến nội dung yêu cầu. |
| GT_061 | enumeration | 0.000 | 0.000 | Mô hình không cung cấp thông tin liên quan đến câu hỏi và không có căn cứ để trả lời, do đó không thể đánh giá độ chính xác hay độ liên quan của câu trả lời. |
| GT_063 | enumeration | 0.000 | 0.000 | Mô hình không cung cấp thông tin nào liên quan đến câu hỏi và không có căn cứ pháp lý nào được trích dẫn. |
| GT_064 | enumeration | 0.000 | 0.000 | Mô hình không cung cấp thông tin nào liên quan đến câu hỏi và không có căn cứ để trả lời, do đó không đạt yêu cầu về độ tin cậy và tính chính xác. |
| GT_065 | enumeration | 0.000 | 0.000 | Mô hình không cung cấp thông tin liên quan đến câu hỏi và không có căn cứ để trả lời, do đó không đạt yêu cầu về độ chính xác và tính liên quan. |
| GT_067 | enumeration | 0.000 | 0.000 | Mô hình không cung cấp thông tin nào liên quan đến câu hỏi và không có căn cứ pháp lý nào được trích dẫn. |

## Lưu ý

- LLM judge có sai số và có thể dao động nhẹ giữa các lần chạy.
- Các điểm này nên đọc cùng báo cáo deterministic `EVALUATION_REPORT.md`.
- Package `ragas` chưa được cài trong môi trường, nên report này tự triển khai rubric tương đương các metric RAGAS phổ biến.
