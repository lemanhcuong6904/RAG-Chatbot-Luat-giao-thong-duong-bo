# Báo cáo đánh giá LLM-as-Judge / RAGAS-style

- Thời điểm chạy: `2026-08-16T14:45:40`
- Judge model: `gpt-4o-mini`
- Số case đã chấm: `200`
- Nguồn input: `D:\RAG_luat_giao_thong\data\evaluation_set_2\eval_outputs_v2_qwen3_0_6b.jsonl`
- Đây là LLM-as-judge theo rubric RAGAS-style, không phải package `ragas` chính thức.

## Tổng quan

| Metric | Score |
|---|---:|
| faithfulness | 0.879 |
| answer_relevancy | 0.957 |
| context_precision | 0.944 |
| context_recall | 0.900 |
| answer_correctness | 0.824 |
| abstention_quality | 0.985 |

## Theo nhóm câu hỏi

| Category | N | Faithfulness | Relevancy | Context Precision | Context Recall | Correctness | Abstention |
|---|---:|---:|---:|---:|---:|---:|---:|
| diagnostic | 30 | 0.793 | 0.833 | 0.867 | 0.833 | 0.710 | 0.967 |
| production | 140 | 0.909 | 0.982 | 0.966 | 0.936 | 0.876 | 0.986 |
| robustness | 30 | 0.823 | 0.960 | 0.920 | 0.797 | 0.693 | 1.000 |

## 15 case correctness thấp nhất

| ID | Category | Correctness | Faithfulness | Notes |
|---|---|---:|---:|---|
| GDV2_056 | production | 0.000 | 0.500 | Câu trả lời không chính xác vì không đề cập đến các loại xe máy cụ thể mà giấy phép hạng A cho phép lái, và thông tin trích dẫn không hỗ trợ cho các tuyên bố trong câu trả lời. |
| GDV2_057 | production | 0.000 | 0.000 | Câu trả lời không chính xác vì không đề cập đến các loại ô tô mà giấy phép hạng B được phép lái. Thông tin trong ngữ cảnh không liên quan đến câu hỏi và không cung cấp đủ thông tin cần thiết. |
| GDV2_080 | production | 0.000 | 0.000 | Câu trả lời không chính xác vì đưa ra tỷ lệ 50% cho đô thị có yếu tố đặc thù, trong khi câu hỏi yêu cầu tỷ lệ từ 11% đến 26% cho đất giao thông trên đất xây dựng đô thị. |
| GDV2_113 | production | 0.000 | 0.000 | Câu trả lời không chính xác về khoảng cách an toàn tối thiểu, vì theo quy định, khoảng cách này là 55 mét cho tốc độ 80 km/h, không phải 70 mét. |
| GDV2_114 | production | 0.000 | 0.000 | Câu trả lời không chính xác về khoảng cách an toàn tối thiểu, vì theo quy định, khoảng cách này là 70 mét cho tốc độ 100 km/h, không phải 100 mét. |
| GDV2_120 | production | 0.000 | 1.000 | Câu trả lời không chính xác về số điểm bị trừ, theo quy định là 4 điểm chứ không phải 3 điểm. |
| GDV2_127 | production | 0.000 | 1.000 | Mặc dù câu trả lời cung cấp thông tin chính xác về mức phạt tiền, nhưng số điểm bị trừ là không chính xác. Theo dữ liệu vàng, số điểm bị trừ là 4 điểm, trong khi câu trả lời chỉ đề cập đến 2 điểm. |
| GDV2_129 | production | 0.000 | 0.000 | Câu trả lời không cung cấp thông tin cần thiết và không trả lời trực tiếp câu hỏi về mức phạt. Mặc dù ngữ cảnh được trích dẫn là chính xác, nhưng không có thông tin nào liên quan đến mức phạt cho việc không có bằng lái xe điều khiển ô tô. |
| GDV2_132 | production | 0.000 | 0.000 | Câu trả lời không cung cấp thông tin hợp lệ và không giải quyết câu hỏi một cách trực tiếp. Thiếu căn cứ pháp lý và không có thông tin cần thiết để xác định chế tài. |
| GDV2_137 | production | 0.000 | 0.500 | Câu trả lời không chính xác về ngày có hiệu lực, thông tin được cung cấp không đúng với dữ liệu vàng. |
| GDV2_140 | production | 0.000 | 0.500 | Câu trả lời không chính xác vì không đề cập đến điều khoản chuyển tiếp và không hỗ trợ bằng chứng từ ngữ pháp của Nghị định 168/2024/NĐ-CP. |
| GDV2_154 | robustness | 0.000 | 0.500 | Mặc dù câu trả lời liên quan đến việc không được lái xe khi có nồng độ cồn, nhưng không cung cấp thông tin về mức phạt cụ thể như trong dữ liệu vàng. Điều này làm giảm độ chính xác và độ tin cậy của câu trả lời. |
| GDV2_160 | robustness | 0.000 | 0.500 | Câu trả lời không cung cấp thông tin cụ thể về mức phạt và không đề cập đến các tình huống khác nhau liên quan đến việc không nhường đường, dẫn đến độ chính xác thấp. |
| GDV2_162 | robustness | 0.000 | 0.500 | Mặc dù câu trả lời liên quan đến việc sử dụng điện thoại khi lái xe, nhưng không đề cập đến việc trừ điểm và mức phạt cụ thể như trong dữ liệu vàng. Do đó, độ chính xác và độ tin cậy của câu trả lời bị giảm. |
| GDV2_164 | robustness | 0.000 | 1.000 | Mặc dù câu trả lời có đầy đủ thông tin và trích dẫn đúng từ văn bản pháp luật, nhưng phần kết luận về số điểm bị trừ không chính xác. Theo dữ liệu vàng, điểm bị trừ là 6, nhưng câu trả lời lại nói rằng sẽ trừ 4 điểm cho hành vi vượt đèn đỏ, |

## Lưu ý

- LLM judge có sai số và có thể dao động nhẹ giữa các lần chạy.
- Các điểm này nên đọc cùng báo cáo deterministic `EVALUATION_REPORT.md`.
- Package `ragas` chưa được cài trong môi trường, nên report này tự triển khai rubric tương đương các metric RAGAS phổ biến.
