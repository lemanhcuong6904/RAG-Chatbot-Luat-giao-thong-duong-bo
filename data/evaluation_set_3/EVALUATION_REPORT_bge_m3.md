# Báo cáo đánh giá RAG Luật giao thông

- Thời điểm chạy: `2026-08-17T23:57:26`
- Dataset: `D:\RAG_luat_giao_thong\data\evaluation_set_3\golden_v3_200.jsonl`
- Embedding preset: `bge_m3`
- Chế độ: `full`
- Pre-RAG stage: `True`
- Pre-RAG LLM transformer: `False`
- Query router LLM: `True`
- Số câu: `200`
- Số lỗi runtime: `0`
- Latency trung bình: `4.69s`; p50: `4.59s`; p95: `8.88s`

## Retrieval

| Metric | Score |
|---|---:|
| recall@1 | 0.363 |
| recall@3 | 0.595 |
| recall@5 | 0.663 |
| recall@10 | 0.716 |
| completeness@10 | 0.695 |
| mrr | 0.491 |
| ndcg@10 | 0.660 |

## Generation / Answer

| Metric | Score |
|---|---:|
| answerable_correct | 0.910 |
| citation_correct | 0.740 |
| citation_complete | 0.710 |
| numeric_exact | N/A |
| points_exact | N/A |
| enumeration_completeness | N/A |
| must_include | N/A |
| context_recall_proxy | 0.773 |
| answer_relevance_proxy | 0.681 |

## Abstention

| Metric | Score |
|---|---:|
| accuracy | 0.910 |
| f1_answerable | 0.949 |
| TP/TN/FP/FN | 167/15/4/14 |

## Structured Sanction

| Metric | Score |
|---|---:|
| vehicle_mapping_accuracy | N/A |
| behavior_mapping_accuracy | N/A |

## Theo nhóm câu hỏi

| Category | N | Recall@5 | Citation Complete | Answerable Acc | Numeric Exact | Points Exact |
|---|---:|---:|---:|---:|---:|---:|
| diagnostic | 30 | 0.650 | 0.767 | 0.833 | N/A | N/A |
| production | 140 | 0.700 | 0.757 | 0.929 | N/A | N/A |
| robustness | 30 | 0.500 | 0.433 | 0.900 | N/A | N/A |

## RAGAS

`ragas` và `datasets` không có trong môi trường hiện tại, nên báo cáo này không chạy RAGAS chính thức.
Thay vào đó báo cáo có hai proxy deterministic:

- `context_recall_proxy`: overlap token giữa `gold_evidence_texts` và citations/context trả về.
- `answer_relevance_proxy`: overlap token giữa query và answer.

Để chạy RAGAS chính thức, cần cài thêm `ragas`, `datasets` và cấu hình LLM/embedding judge ổn định.

## Lưu ý diễn giải

- `score` là tỷ lệ 0-1 trừ MRR/nDCG vốn cũng chuẩn hóa 0-1.
- `numeric_exact` chỉ áp dụng khi case có `expected_fine_min/max`; case không có numeric gold được tính N/A, không tính pass.
- `points_exact` tương tự cho `expected_points`; case không có gold được tính N/A.
- `Citation Complete` yêu cầu tất cả provisions gold xuất hiện trong citations, không chấm exact wording.
- Coverage metric có gold: `{'numeric_exact': 0, 'points_exact': 0, 'enumeration_completeness': 0, 'must_include': 0, 'context_recall_proxy': 200}`.
