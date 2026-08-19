# Báo cáo đánh giá RAG Luật giao thông

- Thời điểm chạy: `2026-08-17T10:30:40`
- Dataset: `D:\RAG_luat_giao_thong\data\evaluation_set\golden_200.jsonl`
- Embedding preset: `bge_m3`
- Chế độ: `full`
- Pre-RAG stage: `True`
- Pre-RAG LLM transformer: `False`
- Query router LLM: `True`
- Số câu: `200`
- Số lỗi runtime: `0`
- Latency trung bình: `6.01s`; p50: `4.75s`

## Retrieval

| Metric | Score |
|---|---:|
| recall@1 | 0.483 |
| recall@3 | 0.694 |
| recall@5 | 0.728 |
| recall@10 | 0.739 |
| completeness@10 | 0.683 |
| mrr | 0.592 |
| ndcg@10 | 0.996 |

## Generation / Answer

| Metric | Score |
|---|---:|
| answerable_correct | 0.860 |
| citation_correct | 0.770 |
| citation_complete | 0.715 |
| numeric_exact | 0.935 |
| points_exact | 0.965 |
| enumeration_completeness | 0.000 |
| must_include | 0.935 |
| context_recall_proxy | 0.812 |
| answer_relevance_proxy | 0.644 |

## Abstention

| Metric | Score |
|---|---:|
| accuracy | 0.860 |
| f1_answerable | 0.916 |
| TP/TN/FP/FN | 153/19/1/27 |

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
| hard_negative | 20 | N/A | 1.000 | 0.950 | 1.000 | 1.000 |
| penalty | 40 | 0.800 | 0.625 | 0.950 | 0.725 | 0.875 |
| semantic_fact | 40 | 0.675 | 0.700 | 0.925 | 1.000 | 1.000 |
| temporal | 30 | 0.533 | 0.467 | 0.733 | 0.933 | 0.933 |

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
