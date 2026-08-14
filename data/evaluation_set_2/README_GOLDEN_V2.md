# Golden Dataset V2 – RAG Luật giao thông

## Phân bố

### `golden_v2_200.jsonl`
- 140 câu `production`: câu hỏi tự nhiên, gần cách người dùng thực tế hỏi.
- 30 câu `robustness`: typo, viết tắt, mixed-language, ambiguity, multi-violation, long-context.
- 30 câu `diagnostic`: exact legal reference, invalid reference, out-of-scope, prompt injection và temporal boundary.

### `smoke_v2_50.jsonl`
Là tập con 50 câu của Golden V2:
- 35 production
- 8 robustness
- 7 diagnostic

## Schema chính

- `id`: mã test case.
- `question`: câu hỏi đưa vào hệ thống.
- `reference_answer`: đáp án chuẩn.
- `intent`: loại nhu cầu.
- `reasoning_types`: dạng reasoning/retrieval cần thiết.
- `difficulty`: easy / medium / hard.
- `user_persona`: loại người dùng.
- `language_style`: natural / casual / typo / legal_reference / adversarial...
- `expected_response_mode`: ANSWER / CLARIFY / ABSTAIN.
- `as_of_date`: mốc pháp luật mặc định để đánh giá.
- `event_date`: ngày xảy ra hành vi nếu case temporal có yêu cầu.
- `expected_provisions`: căn cứ pháp lý mong đợi.
- `required_claims`: claim bắt buộc với một số case.
- `tags`: nhãn phụ.
- `benchmark_suite`: production / robustness / diagnostic.
- `version`: 2.0.

## Nguyên tắc thiết kế

1. Câu hỏi production không nhét Điều/Khoản vào query nếu người dùng bình thường không cần biết trước căn cứ.
2. Exact legal lookup vẫn được giữ trong diagnostic suite để kiểm tra structural retrieval.
3. Câu mơ hồ phải có thể chấm đúng hành vi `CLARIFY`, không ép hệ thống đoán.
4. Câu ngoài phạm vi hoặc căn cứ không tồn tại phải chấm `ABSTAIN`.
5. Penalty case lưu cả mức phạt và trừ điểm khi văn bản có cross-reference.
6. Temporal case gắn `as_of_date`/`event_date` để tránh benchmark thay đổi theo ngày chạy.
7. `smoke_v2_50` là subset của `golden_v2_200`, không phải bộ dữ liệu độc lập.
