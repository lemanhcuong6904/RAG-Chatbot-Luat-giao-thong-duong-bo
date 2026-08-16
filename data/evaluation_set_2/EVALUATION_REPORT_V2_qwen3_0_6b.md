# Báo cáo đánh giá RAG Luật giao thông

- Thời điểm chạy: `2026-08-16T14:33:59`
- Dataset: `D:\RAG_luat_giao_thong\data\evaluation_set_2\golden_v2_200.jsonl`
- Embedding preset: `qwen3_0_6b`
- Chế độ: `full`
- Pre-RAG stage: `True`
- Pre-RAG LLM transformer: `True`
- Query router LLM: `True`
- Số câu: `200`
- Số lỗi runtime: `0`
- Latency trung bình: `6.63s`; p50: `6.52s`

## Retrieval

| Metric | Score |
|---|---:|
| recall@1 | 0.516 |
| recall@3 | 0.789 |
| recall@5 | 0.842 |
| recall@10 | 0.889 |
| completeness@10 | 0.816 |
| mrr | 0.660 |
| ndcg@10 | 0.808 |

## Generation / Answer

| Metric | Score |
|---|---:|
| answerable_correct | 0.975 |
| citation_correct | 0.895 |
| citation_complete | 0.825 |
| numeric_exact | 1.000 |
| points_exact | 1.000 |
| enumeration_completeness | N/A |
| must_include | 0.965 |
| context_recall_proxy | 0.789 |
| answer_relevance_proxy | 0.652 |

## Abstention

| Metric | Score |
|---|---:|
| accuracy | 0.975 |
| f1_answerable | 0.986 |
| TP/TN/FP/FN | 180/15/3/2 |

## Structured Sanction

| Metric | Score |
|---|---:|
| vehicle_mapping_accuracy | N/A |
| behavior_mapping_accuracy | N/A |

## Theo nhóm câu hỏi

| Category | N | Recall@5 | Citation Complete | Answerable Acc | Numeric Exact | Points Exact |
|---|---:|---:|---:|---:|---:|---:|
| diagnostic | 30 | 1.000 | 0.933 | 0.967 | 1.000 | 1.000 |
| production | 140 | 0.850 | 0.864 | 0.986 | 1.000 | 1.000 |
| robustness | 30 | 0.700 | 0.533 | 0.933 | 1.000 | 1.000 |

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
