# Báo cáo đánh giá LLM-as-Judge / RAGAS-style

- Thời điểm chạy: `2026-08-16T14:52:37`
- Judge model: `gpt-4o-mini`
- Số case đã chấm: `200`
- Nguồn input: `D:\RAG_luat_giao_thong\data\evaluation_set_2\eval_outputs_v2.jsonl`
- Đây là LLM-as-judge theo rubric RAGAS-style, không phải package `ragas` chính thức.

## Tổng quan

| Metric | Score |
|---|---:|
| faithfulness | 0.873 |
| answer_relevancy | 0.957 |
| context_precision | 0.939 |
| context_recall | 0.893 |
| answer_correctness | 0.839 |
| abstention_quality | 0.970 |

## Theo nhóm câu hỏi

| Category | N | Faithfulness | Relevancy | Context Precision | Context Recall | Correctness | Abstention |
|---|---:|---:|---:|---:|---:|---:|---:|
| diagnostic | 30 | 0.790 | 0.867 | 0.817 | 0.787 | 0.690 | 0.900 |
| production | 140 | 0.914 | 0.986 | 0.966 | 0.942 | 0.904 | 0.986 |
| robustness | 30 | 0.760 | 0.910 | 0.933 | 0.770 | 0.680 | 0.967 |

## 15 case correctness thấp nhất

| ID | Category | Correctness | Faithfulness | Notes |
|---|---|---:|---:|---|
| GDV2_056 | production | 0.000 | 0.500 | Câu trả lời không chính xác vì không đề cập đến hạng A và các loại xe mà hạng A được phép lái, dẫn đến độ chính xác thấp. |
| GDV2_070 | production | 0.000 | 0.000 | Mặc dù câu trả lời không liên quan đến câu hỏi và không cung cấp thông tin chính xác, nó đã tránh được việc đưa ra thông tin sai lệch. Tuy nhiên, không có thông tin nào trong ngữ cảnh được truy xuất để hỗ trợ cho câu trả lời, dẫn đến điểm s |
| GDV2_113 | production | 0.000 | 0.000 | Câu trả lời không chính xác về khoảng cách an toàn tối thiểu, vì theo quy định, khoảng cách này là 55 mét cho tốc độ 80 km/h, không phải 70 mét. |
| GDV2_114 | production | 0.000 | 0.000 | Câu trả lời không chính xác về khoảng cách an toàn tối thiểu, vì theo quy định, khoảng cách này là 70 mét cho tốc độ 100 km/h, không phải 100 mét. |
| GDV2_129 | production | 0.000 | 0.000 | Câu trả lời không cung cấp thông tin chính xác về mức phạt và không xác định được chế tài cụ thể cho hành vi vi phạm, do đó không đáp ứng yêu cầu của câu hỏi. |
| GDV2_132 | production | 0.000 | 0.000 | Câu trả lời không cung cấp thông tin hợp lệ và không giải quyết câu hỏi một cách trực tiếp. Thiếu căn cứ pháp lý và không đề cập đến các nghị định liên quan. |
| GDV2_137 | production | 0.000 | 0.500 | Câu trả lời không chính xác về ngày có hiệu lực, nên độ chính xác thấp. Tuy nhiên, câu trả lời có liên quan và không có nội dung không liên quan. |
| GDV2_140 | production | 0.000 | 0.500 | Câu trả lời không chính xác về việc áp dụng Nghị định 168, vì không có trích dẫn hỗ trợ cho tuyên bố này. Cần có thông tin rõ ràng hơn từ văn bản pháp luật để xác nhận tính chính xác. |
| GDV2_145 | robustness | 0.000 | 0.000 | Câu trả lời không cung cấp thông tin chính xác về mức phạt và không trả lời trực tiếp câu hỏi. Mặc dù có trích dẫn đúng từ văn bản pháp luật, nhưng không có thông tin cần thiết để xác định mức phạt cụ thể. |
| GDV2_154 | robustness | 0.000 | 0.500 | Mặc dù câu trả lời liên quan đến việc không được lái xe khi có nồng độ cồn, nhưng không cung cấp thông tin về mức phạt cụ thể như trong dữ liệu vàng. Điều này làm giảm độ chính xác và độ tin cậy của câu trả lời. |
| GDV2_155 | robustness | 0.000 | 0.000 | Câu trả lời không cung cấp thông tin hỗ trợ nào từ ngữ cảnh và không trả lời đúng câu hỏi. Tuy nhiên, hệ thống đã đúng khi không trả lời vì câu hỏi không thể trả lời được. |
| GDV2_159 | robustness | 0.000 | 0.500 | Mặc dù câu trả lời có liên quan và trích dẫn đúng các điều khoản, nhưng nó đưa ra các mức phạt cụ thể mà không có sự hỗ trợ từ ngữ liệu vàng, dẫn đến độ chính xác thấp. |
| GDV2_160 | robustness | 0.000 | 0.500 | Câu trả lời không cung cấp thông tin cụ thể về mức phạt và không nhắc đến các tình huống cụ thể, làm giảm độ chính xác và tính liên quan của câu trả lời. |
| GDV2_162 | robustness | 0.000 | 0.500 | Mặc dù câu trả lời liên quan đến việc sử dụng điện thoại khi lái xe, nhưng không đề cập đến việc trừ điểm và mức phạt cụ thể như trong dữ liệu vàng. Do đó, câu trả lời không chính xác về mặt pháp lý và không đầy đủ thông tin cần thiết. |
| GDV2_181 | diagnostic | 0.000 | 0.500 | Mặc dù câu trả lời không cung cấp thông tin chính xác về Điều 999, nó không đưa ra thông tin sai lệch. Tuy nhiên, nó không hoàn toàn phù hợp với yêu cầu của câu hỏi và thiếu sự hỗ trợ từ ngữ liệu đã được cung cấp. |

## Lưu ý

- LLM judge có sai số và có thể dao động nhẹ giữa các lần chạy.
- Các điểm này nên đọc cùng báo cáo deterministic `EVALUATION_REPORT.md`.
- Package `ragas` chưa được cài trong môi trường, nên report này tự triển khai rubric tương đương các metric RAGAS phổ biến.
