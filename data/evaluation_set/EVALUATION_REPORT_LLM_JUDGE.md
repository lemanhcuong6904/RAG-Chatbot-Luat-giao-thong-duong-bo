# Báo cáo đánh giá LLM-as-Judge / RAGAS-style

- Thời điểm chạy: `2026-08-12T22:28:17`
- Judge model: `gpt-4o-mini`
- Số case đã chấm: `200`
- Nguồn input: `data/evaluation_set/eval_outputs.jsonl`
- Đây là LLM-as-judge theo rubric RAGAS-style, không phải package `ragas` chính thức.

## Tổng quan

| Metric | Score |
|---|---:|
| faithfulness | 0.539 |
| answer_relevancy | 0.582 |
| context_precision | 0.571 |
| context_recall | 0.476 |
| answer_correctness | 0.482 |
| abstention_quality | 0.785 |

## Theo nhóm câu hỏi

| Category | N | Faithfulness | Relevancy | Context Precision | Context Recall | Correctness | Abstention |
|---|---:|---:|---:|---:|---:|---:|---:|
| enumeration | 35 | 0.171 | 0.171 | 0.171 | 0.171 | 0.171 | 0.400 |
| exact_lookup | 35 | 0.514 | 0.514 | 0.514 | 0.514 | 0.514 | 0.600 |
| hard_negative | 20 | 0.820 | 0.875 | 0.855 | 0.090 | 0.500 | 0.850 |
| penalty | 40 | 0.785 | 0.882 | 0.875 | 0.812 | 0.705 | 1.000 |
| semantic_fact | 40 | 0.660 | 0.667 | 0.667 | 0.670 | 0.630 | 1.000 |
| temporal | 30 | 0.320 | 0.427 | 0.380 | 0.340 | 0.303 | 0.833 |

## 15 case correctness thấp nhất

| ID | Category | Correctness | Faithfulness | Notes |
|---|---|---:|---:|---|
| GT_001 | exact_lookup | 0.000 | 0.000 | Mô hình không cung cấp thông tin cần thiết và không trả lời câu hỏi, nhưng đã từ chối đúng cách do thiếu căn cứ. |
| GT_002 | exact_lookup | 0.000 | 0.000 | Mô hình không cung cấp thông tin liên quan đến câu hỏi và không trích dẫn đúng nội dung từ văn bản pháp luật. |
| GT_003 | exact_lookup | 0.000 | 0.000 | Mô hình không cung cấp thông tin liên quan đến câu hỏi và không có căn cứ để trả lời, do đó không đạt yêu cầu. |
| GT_004 | exact_lookup | 0.000 | 0.000 | Mô hình không cung cấp thông tin liên quan đến câu hỏi và không có căn cứ để đưa ra câu trả lời chính xác. |
| GT_005 | exact_lookup | 0.000 | 0.000 | Mô hình không cung cấp thông tin liên quan đến câu hỏi và không có căn cứ để trả lời, do đó không đạt yêu cầu về độ chính xác và liên quan. |
| GT_006 | exact_lookup | 0.000 | 0.000 | Mô hình không cung cấp thông tin liên quan đến câu hỏi và không có căn cứ để trả lời, do đó không đạt yêu cầu. |
| GT_007 | exact_lookup | 0.000 | 0.000 | Mô hình không cung cấp thông tin liên quan đến câu hỏi và không đưa ra câu trả lời chính xác theo dữ liệu vàng. |
| GT_008 | exact_lookup | 0.000 | 0.000 | Mô hình không cung cấp thông tin cần thiết và không trả lời câu hỏi một cách chính xác. |
| GT_009 | exact_lookup | 0.000 | 0.000 | Mô hình không cung cấp thông tin liên quan đến câu hỏi và không có căn cứ để trả lời, do đó không đạt yêu cầu. |
| GT_010 | exact_lookup | 0.000 | 0.000 | Mô hình không cung cấp thông tin liên quan đến câu hỏi và không có căn cứ để trả lời, do đó không đạt yêu cầu. |
| GT_011 | exact_lookup | 0.000 | 0.000 | Mô hình không cung cấp thông tin chính xác về quy định trong câu hỏi, nhưng đã từ chối trả lời một cách hợp lý do thiếu căn cứ. |
| GT_012 | exact_lookup | 0.000 | 0.000 | Mô hình không cung cấp thông tin liên quan đến câu hỏi và không có căn cứ để trả lời, nhưng đã từ chối trả lời một cách hợp lý. |
| GT_013 | exact_lookup | 0.000 | 0.000 | Mô hình không cung cấp thông tin liên quan đến câu hỏi và không có căn cứ để trả lời, do đó không đạt yêu cầu. |
| GT_014 | exact_lookup | 0.000 | 0.000 | Mô hình không cung cấp thông tin liên quan đến câu hỏi và không có căn cứ để đưa ra câu trả lời chính xác. |
| GT_015 | exact_lookup | 0.000 | 0.000 | Mô hình không cung cấp thông tin liên quan đến câu hỏi và không có căn cứ để trả lời, do đó không đạt yêu cầu. |

## Lưu ý

- LLM judge có sai số và có thể dao động nhẹ giữa các lần chạy.
- Các điểm này nên đọc cùng báo cáo deterministic `EVALUATION_REPORT.md`.
- Package `ragas` chưa được cài trong môi trường, nên report này tự triển khai rubric tương đương các metric RAGAS phổ biến.
