# Golden Evaluation Dataset — RAG Luật giao thông

Dataset được tạo ngày 2026-08-12 cho repo:
`https://github.com/lemanhcuong6904/RAG-Chatbot-Luat-giao-thong-duong-bo`

## Files

- `golden_200.jsonl`: 200 câu đánh giá đầy đủ.
- `smoke_50.jsonl`: 50 câu regression/smoke test, là tập con của `golden_200.jsonl`.

## Phân bố golden_200

- exact_lookup: 35
- enumeration: 35
- semantic_fact: 40
- penalty: 40
- temporal: 30
- hard_negative: 20

## Phân bố smoke_50

- exact_lookup: 10
- enumeration: 10
- penalty: 10
- temporal: 10
- hard_negative: 10

Smoke set cố ý bám đúng 5 nhóm mà audit của repo đề xuất.

## Schema chính

Mỗi dòng JSON có các trường:

- `id`, `group_id`, `query`, `category`, `difficulty`
- `expected_answerable`
- `expected_document_numbers`
- `expected_provisions`: `document_number`, `article`, `clause`, `point`
- `expected_items`, `expected_item_texts` cho enumeration
- `expected_fine_min`, `expected_fine_max`, `expected_points`
- `expected_answer`, `must_include`
- `event_date`, `expected_temporal_status`
- `expected_vehicle`, `expected_behavior`
- `expected_additional_sanction`
- `gold_evidence_texts`
- `source_files`
- `notes`

## Nguyên tắc ground truth

1. Câu exact/enumeration/semantic được gắn trực tiếp vào provision trong Markdown.
2. Penalty cases lưu riêng fine range, GPLX points và provision cho điểm/hình phạt bổ sung.
3. Multi-violation cases kiểm tra cả cộng tiền phạt từng hành vi và nguyên tắc trừ điểm/tước GPLX.
4. Temporal cases kiểm tra:
   - hiệu lực chung;
   - hiệu lực riêng;
   - NĐ 238/2026/NĐ-CP từ 15/08/2026;
   - quy định chuyển tiếp;
   - các mốc 2028/2029 của thiết bị ghi nhận hình ảnh.
5. Hard-negative yêu cầu fail-closed, không tự sửa Điều/Khoản/Điểm không tồn tại.
6. Các câu hỏi về Phụ lục I-X của NĐ 165 được đánh dấu `expected_answerable=false` vì file Markdown nguồn ghi rõ các phụ lục này không có trong file.

## SHA-256 của 6 nguồn Markdown

- `35-2024-QH15_Luat-Duong-bo(1).md`: `a25040c6b85446ec12ff97fc3a4d35051e40fa84e27479c50f47cf7a75060a5f`
- `36-2024-QH15_Phan-1_Dieu-1-23(1).md`: `2732488af28ca436c18c86dff5db484abb0acd4beaef76da50ab6aa63aa1c475`
- `36-2024-QH15_Phan-2_Dieu-24-89(1).md`: `c898156d8793806a8f7b53824012b4d43fd95d7b4fa249d062d424c763efb87b`
- `165-2024-ND-CP_Huong-dan-Luat-Duong-bo(1).md`: `870da4c003051c3cf36096561a755e87ca93cf8e8941c89212b4d7d4c3a0d7cc`
- `168-2024-ND-CP_Xu-phat-TTATGT-Tru-diem-GPLX(1).md`: `4caccf22b4b9d67238375f39fb339c49315294ca6e3c712541cfd3eb7b87ea4a`
- `238-2026-ND-CP_Sua-doi-ND-168-2024(1).md`: `87e4d3c19a3ae0e29bf4a706910984e120759e95364049f91c5bf5ba8f161e34`

## Gợi ý metric

Retrieval:
- Provision Recall@1/3/5/10
- MRR
- nDCG@10

Generation:
- Citation Correctness / Completeness
- Enumeration Completeness
- Numeric Exact Match
- Temporal Accuracy
- Abstention Accuracy/F1
- RAGAS

Structured sanction:
- Vehicle Mapping Accuracy
- Behavior Mapping Accuracy
- Fine Exact Match
- Points Exact Match
- Rule/Version Selection Accuracy

## Lưu ý

`expected_answer` là gold answer/evidence định hướng; với câu hỏi pháp luật không nên chấm chỉ bằng exact string.
Ưu tiên deterministic metrics trên provision, số tiền, điểm GPLX, item completeness và temporal status.
