# Báo cáo đánh giá RAG Luật giao thông

- Thời điểm chạy: `2026-08-17T21:01:36`
- Dataset: `D:\RAG_luat_giao_thong\data\evaluation_set_2\golden_v2_200.jsonl`
- Embedding preset: `bge_m3`
- Chế độ: `full`
- Pre-RAG stage: `True`
- Pre-RAG LLM transformer: `False`
- Query router LLM: `True`
- Số câu: `200`
- Số lỗi runtime: `0`
- Latency trung bình: `4.03s`; p50: `3.89s`

## Retrieval

| Metric | Score |
|---|---:|
| recall@1 | 0.695 |
| recall@3 | 0.884 |
| recall@5 | 0.932 |
| recall@10 | 0.947 |
| completeness@10 | 0.900 |
| mrr | 0.795 |
| ndcg@10 | 0.924 |

## Generation / Answer

| Metric | Score |
|---|---:|
| answerable_correct | 0.995 |
| citation_correct | 0.950 |
| citation_complete | 0.905 |
| numeric_exact | 1.000 |
| points_exact | 1.000 |
| enumeration_completeness | N/A |
| must_include | 0.965 |
| context_recall_proxy | 0.814 |
| answer_relevance_proxy | 0.643 |

## Abstention

| Metric | Score |
|---|---:|
| accuracy | 0.995 |
| f1_answerable | 0.997 |
| TP/TN/FP/FN | 182/17/1/0 |

## Structured Sanction

| Metric | Score |
|---|---:|
| vehicle_mapping_accuracy | N/A |
| behavior_mapping_accuracy | N/A |

## Theo nhóm câu hỏi

| Category | N | Recall@5 | Citation Complete | Answerable Acc | Numeric Exact | Points Exact |
|---|---:|---:|---:|---:|---:|---:|
| diagnostic | 30 | 0.950 | 0.900 | 0.967 | 1.000 | 1.000 |
| production | 140 | 0.964 | 0.971 | 1.000 | 1.000 | 1.000 |
| robustness | 30 | 0.767 | 0.600 | 1.000 | 1.000 | 1.000 |

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
