# Báo cáo đánh giá RAG Luật giao thông

- Thời điểm chạy: `2026-08-13T18:55:44`
- Dataset: `golden_200.jsonl`
- Chế độ: `full`
- Số câu: `200`
- Số lỗi runtime: `0`
- Latency trung bình: `7.36s`; p50: `7.07s`

## Retrieval

| Metric | Score |
|---|---:|
| recall@1 | 0.350 |
| recall@3 | 0.678 |
| recall@5 | 0.728 |
| recall@10 | 0.767 |
| completeness@10 | 0.594 |
| mrr | 0.525 |
| ndcg@10 | 0.918 |

## Generation / Answer

| Metric | Score |
|---|---:|
| answerable_correct | 0.910 |
| citation_correct | 0.795 |
| citation_complete | 0.635 |
| numeric_exact | 0.925 |
| points_exact | 0.900 |
| enumeration_completeness | 0.000 |
| must_include | 0.875 |
| context_recall_proxy | 0.840 |
| answer_relevance_proxy | 0.733 |

## Abstention

| Metric | Score |
|---|---:|
| accuracy | 0.910 |
| f1_answerable | 0.949 |
| TP/TN/FP/FN | 166/16/4/14 |

## Structured Sanction

| Metric | Score |
|---|---:|
| vehicle_mapping_accuracy | 0.950 |
| behavior_mapping_accuracy | 0.000 |

## Theo nhóm câu hỏi

| Category | N | Recall@5 | Citation Complete | Answerable Acc | Numeric Exact | Points Exact |
|---|---:|---:|---:|---:|---:|---:|
| enumeration | 35 | 0.600 | 0.600 | 0.600 | 1.000 | 1.000 |
| exact_lookup | 35 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| hard_negative | 20 | N/A | 1.000 | 0.800 | 1.000 | 1.000 |
| penalty | 40 | 0.775 | 0.150 | 1.000 | 0.725 | 0.600 |
| semantic_fact | 40 | 0.775 | 0.850 | 1.000 | 1.000 | 1.000 |
| temporal | 30 | 0.433 | 0.367 | 1.000 | 0.867 | 0.867 |

## RAGAS

`ragas` và `datasets` không có trong môi trường hiện tại, nên báo cáo này không chạy RAGAS chính thức.
Thay vào đó báo cáo có hai proxy deterministic:

- `context_recall_proxy`: overlap token giữa `gold_evidence_texts` và citations/context trả về.
- `answer_relevance_proxy`: overlap token giữa query và answer.

Để chạy RAGAS chính thức, cần cài thêm `ragas`, `datasets` và cấu hình LLM/embedding judge ổn định.

## Lưu ý diễn giải

- `score` là tỷ lệ 0-1 trừ MRR/nDCG vốn cũng chuẩn hóa 0-1.
- `numeric_exact` chỉ áp dụng khi case có `expected_fine_min/max`; case không có numeric gold được tính là pass.
- `points_exact` tương tự cho `expected_points`.
- `Citation Complete` yêu cầu tất cả provisions gold xuất hiện trong citations, không chấm exact wording.
