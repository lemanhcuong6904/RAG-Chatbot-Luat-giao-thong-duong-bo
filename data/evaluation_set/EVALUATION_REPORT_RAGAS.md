# Official RAGAS Evaluation Report

- Generated at: `2026-08-12T16:28:06.059949+00:00`
- Input: `D:\RAG_luat_giao_thong\data\evaluation_set\eval_outputs.jsonl`
- RAGAS version: `0.4.3`
- Judge LLM: `gpt-4o-mini`
- Embedding model: `text-embedding-3-small`
- Samples: `200`
- Raw JSON: `D:\RAG_luat_giao_thong\data\evaluation_set\ragas_official_scores.json`
- CSV: `D:\RAG_luat_giao_thong\data\evaluation_set\ragas_official_scores.csv`

## Metrics

| Metric | Mean |
|---|---:|
| faithfulness | 0.569 |
| answer_relevancy | 0.131 |
| context_precision | 0.609 |
| context_recall | 0.485 |
| answer_correctness | 0.346 |

## By Category

| Category | N | faithfulness | answer_relevancy | context_precision | context_recall | answer_correctness |
|---|---:|---:|---:|---:|---:|---:|
| enumeration | 35 | 0.542 | 0.073 | 0.200 | 0.424 | 0.221 |
| exact_lookup | 35 | 0.526 | 0.042 | 0.514 | 0.374 | 0.391 |
| hard_negative | 20 | 0.410 | 0.000 | 0.493 | 0.800 | 0.145 |
| penalty | 40 | 0.581 | 0.259 | 0.883 | 0.525 | 0.508 |
| semantic_fact | 40 | 0.755 | 0.232 | 0.766 | 0.538 | 0.395 |
| temporal | 30 | 0.495 | 0.082 | 0.700 | 0.351 | 0.293 |

## Notes

- This report uses the official `ragas.evaluate` implementation.
- It evaluates the answers and contexts already present in `eval_outputs.jsonl`; rerun `scripts/evaluate_rag.py` first if the RAG pipeline/config changed.
- Rows with no returned citations use a placeholder context so RAGAS can still score the sample.
