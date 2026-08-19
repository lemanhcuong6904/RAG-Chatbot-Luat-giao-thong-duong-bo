# Báo cáo đánh giá LLM-as-Judge / RAGAS-style

- Thời điểm chạy: `2026-08-18T09:40:12`
- Judge model: `gpt-4o-mini`
- Số case đã chấm: `200`
- Nguồn input: `D:\RAG_luat_giao_thong\data\evaluation_set_2\eval_outputs_bge_m3.jsonl`
- Đây là LLM-as-judge theo rubric RAGAS-style, không phải package `ragas` chính thức.

## Tổng quan

| Metric | Score |
|---|---:|
| faithfulness | 0.942 |
| answer_relevancy | 0.977 |
| context_precision | 0.981 |
| context_recall | 0.956 |
| answer_correctness | 0.897 |
| abstention_quality | 0.990 |

## Theo nhóm câu hỏi

| Category | N | Faithfulness | Relevancy | Context Precision | Context Recall | Correctness | Abstention |
|---|---:|---:|---:|---:|---:|---:|---:|
| diagnostic | 30 | 0.827 | 0.867 | 0.917 | 0.843 | 0.727 | 0.967 |
| production | 140 | 0.983 | 1.000 | 0.996 | 0.989 | 0.972 | 1.000 |
| robustness | 30 | 0.867 | 0.980 | 0.977 | 0.910 | 0.713 | 0.967 |

## 15 case correctness thấp nhất

| ID | Category | Correctness | Faithfulness | Notes |
|---|---|---:|---:|---|
| GDV2_132 | production | 0.000 | 1.000 | Câu trả lời không chính xác vì đã áp dụng Nghị định 168 thay vì Nghị định 238, mặc dù Nghị định 238 chưa có hiệu lực tại thời điểm vi phạm. |
| GDV2_133 | production | 0.000 | 0.500 | Câu trả lời không chính xác về thời điểm có hiệu lực của quy định, vì Nghị định 168/2024/NĐ-CP có hiệu lực từ 01/01/2026, nhưng hành vi vi phạm xảy ra vào ngày 14/08/2026, khi Nghị định 238 chưa có hiệu lực. Do đó, câu trả lời không đúng về |
| GDV2_147 | robustness | 0.000 | 0.000 | Câu trả lời không chính xác về khoảng cách an toàn, nên độ chính xác và độ tin cậy bị giảm. |
| GDV2_153 | robustness | 0.000 | 1.000 | Mặc dù câu trả lời có liên quan và chính xác về mặt nội dung, nhưng không cung cấp thông tin cụ thể về mức phạt, dẫn đến việc không hoàn toàn chính xác theo dữ liệu vàng. |
| GDV2_154 | robustness | 0.000 | 1.000 | Mặc dù câu trả lời có nội dung liên quan và chính xác về các yếu tố ảnh hưởng đến mức phạt, nhưng không cung cấp thông tin cụ thể về mức phạt, dẫn đến việc không đúng với dữ liệu vàng. |
| GDV2_155 | robustness | 0.000 | 0.500 | Câu trả lời không cung cấp thông tin đầy đủ về quy định pháp luật liên quan, dẫn đến độ chính xác thấp. Tuy nhiên, nó đã từ chối trả lời đúng cách theo yêu cầu của câu hỏi. |
| GDV2_160 | robustness | 0.000 | 0.500 | Câu trả lời không cung cấp thông tin cụ thể về mức phạt cho hành vi không nhường đường, dẫn đến độ chính xác thấp. Mặc dù có lý do hợp lý để không đưa ra câu trả lời cụ thể, nhưng thiếu thông tin cần thiết làm giảm độ tin cậy của câu trả lờ |
| GDV2_165 | robustness | 0.000 | 1.000 | Mặc dù câu trả lời có đầy đủ thông tin và trích dẫn đúng từ văn bản pháp luật, nhưng phần tổng điểm GPLX bị trừ là không chính xác. Theo dữ liệu vàng, tổng điểm bị trừ là 6 điểm, nhưng câu trả lời lại đưa ra tổng điểm là 6 điểm mà không giả |
| GDV2_181 | diagnostic | 0.000 | 0.500 | Mặc dù câu trả lời không cung cấp thông tin chính xác về Điều 999, nó không đưa ra thông tin sai lệch. Tuy nhiên, nó không hoàn toàn phù hợp với yêu cầu của câu hỏi và thiếu sự hỗ trợ từ ngữ liệu đã được cung cấp. |
| GDV2_182 | diagnostic | 0.000 | 0.500 | Câu trả lời không cung cấp thông tin chính xác về khoản 99 Điều 7, dẫn đến độ chính xác thấp. Tuy nhiên, hệ thống đã từ chối câu hỏi đúng cách vì không có căn cứ hợp lệ. |
| GDV2_183 | diagnostic | 0.000 | 0.000 | Mô hình không cung cấp thông tin chính xác về điểm z trong khoản 1 Điều 58, không đáp ứng yêu cầu của câu hỏi. Tuy nhiên, nó đã từ chối trả lời đúng cách vì không có căn cứ trong dữ liệu hiện tại. |
| GDV2_184 | diagnostic | 0.000 | 0.500 | Mặc dù câu trả lời không có căn cứ rõ ràng và không đề cập đến Điều 100, nhưng nó đã từ chối trả lời đúng cách. Tuy nhiên, không có thông tin chính xác về Điều 100 trong văn bản đã cho, dẫn đến điểm số thấp cho độ chính xác và độ tin cậy. |
| GDV2_185 | diagnostic | 0.000 | 0.000 | Câu trả lời không đúng với yêu cầu, vì nó không đề cập đến khoản 9 và không xác nhận rằng điều 21 không có khoản 9 như trong dữ liệu vàng. |
| GDV2_194 | diagnostic | 0.000 | 0.500 | Câu trả lời không chính xác vì đã chọn mức phạt cụ thể mà không phân nhánh theo phương tiện hoặc dung tích/hạng xe như yêu cầu trong dữ liệu vàng. |
| GDV2_195 | diagnostic | 0.000 | 1.000 | Mặc dù câu trả lời cung cấp thông tin chính xác về mức phạt, nhưng đã vi phạm yêu cầu không đề cập đến việc trừ điểm GPLX. Điều này làm giảm độ chính xác của câu trả lời so với dữ liệu vàng. |

## Lưu ý

- LLM judge có sai số và có thể dao động nhẹ giữa các lần chạy.
- Các điểm này nên đọc cùng báo cáo deterministic `EVALUATION_REPORT.md`.
- Package `ragas` chưa được cài trong môi trường, nên report này tự triển khai rubric tương đương các metric RAGAS phổ biến.
