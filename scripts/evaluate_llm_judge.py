from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def _context_from_citations(citations: list[dict[str, Any]], limit: int = 8) -> str:
    parts = []
    for index, citation in enumerate(citations[:limit], start=1):
        ref = ", ".join(
            part
            for part in [
                citation.get("document_number"),
                f"Điều {citation.get('article')}" if citation.get("article") else None,
                f"Khoản {citation.get('clause')}" if citation.get("clause") else None,
                f"Điểm {citation.get('point')}" if citation.get("point") else None,
            ]
            if part
        )
        parts.append(f"[{index}] {ref}\n{citation.get('text') or ''}")
    return "\n\n".join(parts)


def _gold_summary(row: dict[str, Any]) -> str:
    provisions = row.get("expected_provisions") or []
    provision_text = "; ".join(
        ", ".join(
            part
            for part in [
                item.get("document_number"),
                f"Điều {item.get('article')}" if item.get("article") else None,
                f"Khoản {item.get('clause')}" if item.get("clause") else None,
                f"Điểm {item.get('point')}" if item.get("point") else None,
            ]
            if part
        )
        for item in provisions
    )
    return json.dumps(
        {
            "expected_answerable": row.get("expected_answerable"),
            "expected_answer": row.get("expected_answer"),
            "expected_provisions": provision_text,
            "expected_fine_min": row.get("expected_fine_min"),
            "expected_fine_max": row.get("expected_fine_max"),
            "expected_points": row.get("expected_points"),
            "expected_items": row.get("expected_item_texts") or row.get("expected_items"),
            "expected_temporal_status": row.get("expected_temporal_status"),
            "gold_evidence_texts": row.get("gold_evidence_texts"),
            "must_include": row.get("must_include"),
        },
        ensure_ascii=False,
        indent=2,
    )


def _judge_prompt(case: dict[str, Any]) -> list[dict[str, str]]:
    row = case["row"]
    response = case["response"]
    context = _context_from_citations(response.get("citations") or [])
    user_content = f"""Evaluate this Vietnamese legal RAG answer.

Question:
{row.get("query")}

Gold / expected data:
{_gold_summary(row)}

Retrieved context:
{context}

Model answer:
{response.get("answer") or ""}

Answerable flag returned by system: {response.get("answerable")}

Score each metric from 0 to 1:
- faithfulness: answer claims are supported by retrieved context.
- answer_relevancy: answer addresses the question directly without unrelated content.
- context_precision: retrieved context/citations are relevant and not noisy.
- context_recall: retrieved context covers the necessary gold evidence.
- answer_correctness: final answer is legally/numerically correct against gold data.
- abstention_quality: if expected_answerable=false, did the system abstain/fail closed; if expected_answerable=true, did it avoid unnecessary abstention.

Return strict JSON only:
{{
  "faithfulness": number,
  "answer_relevancy": number,
  "context_precision": number,
  "context_recall": number,
  "answer_correctness": number,
  "abstention_quality": number,
  "notes": "brief Vietnamese explanation"
}}
"""
    return [
        {
            "role": "system",
            "content": (
                "You are a strict evaluator for Vietnamese traffic-law RAG. "
                "Do not answer the legal question. Only judge the provided answer. "
                "Be conservative: unsupported legal/numeric claims should lower faithfulness and correctness."
            ),
        },
        {"role": "user", "content": user_content},
    ]


def _parse_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end >= start:
        text = text[start : end + 1]
    return json.loads(text)


def _score_case(client: Any, model: str, case: dict[str, Any]) -> dict[str, Any]:
    response = client.chat.completions.create(
        model=model,
        messages=_judge_prompt(case),
        temperature=0,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or "{}"
    scores = _parse_json_object(content)
    normalized = {}
    for key in [
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
        "answer_correctness",
        "abstention_quality",
    ]:
        value = float(scores.get(key, 0))
        normalized[key] = max(0.0, min(1.0, value))
    normalized["notes"] = str(scores.get("notes", ""))
    return normalized


def _mean(values: list[float]) -> float:
    return sum(values) / max(len(values), 1)


def _write_report(scores: list[dict[str, Any]], out: Path, model: str) -> None:
    metric_keys = [
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
        "answer_correctness",
        "abstention_quality",
    ]
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in scores:
        by_category[item["category"]].append(item)

    lines = [
        "# Báo cáo đánh giá LLM-as-Judge / RAGAS-style",
        "",
        f"- Thời điểm chạy: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Judge model: `{model}`",
        f"- Số case đã chấm: `{len(scores)}`",
        "- Nguồn input: `data/evaluation_set/eval_outputs.jsonl`",
        "- Đây là LLM-as-judge theo rubric RAGAS-style, không phải package `ragas` chính thức.",
        "",
        "## Tổng quan",
        "",
        "| Metric | Score |",
        "|---|---:|",
    ]
    for key in metric_keys:
        lines.append(f"| {key} | {_mean([item[key] for item in scores]):.3f} |")

    lines.extend(["", "## Theo nhóm câu hỏi", "", "| Category | N | Faithfulness | Relevancy | Context Precision | Context Recall | Correctness | Abstention |", "|---|---:|---:|---:|---:|---:|---:|---:|"])
    for category, items in sorted(by_category.items()):
        lines.append(
            "| {category} | {n} | {faith:.3f} | {rel:.3f} | {cp:.3f} | {cr:.3f} | {corr:.3f} | {absq:.3f} |".format(
                category=category,
                n=len(items),
                faith=_mean([item["faithfulness"] for item in items]),
                rel=_mean([item["answer_relevancy"] for item in items]),
                cp=_mean([item["context_precision"] for item in items]),
                cr=_mean([item["context_recall"] for item in items]),
                corr=_mean([item["answer_correctness"] for item in items]),
                absq=_mean([item["abstention_quality"] for item in items]),
            )
        )

    weakest = sorted(scores, key=lambda item: item["answer_correctness"])[:15]
    lines.extend(["", "## 15 case correctness thấp nhất", "", "| ID | Category | Correctness | Faithfulness | Notes |", "|---|---|---:|---:|---|"])
    for item in weakest:
        notes = str(item.get("notes", "")).replace("|", "\\|").replace("\n", " ")[:240]
        lines.append(f"| {item['id']} | {item['category']} | {item['answer_correctness']:.3f} | {item['faithfulness']:.3f} | {notes} |")

    lines.extend(
        [
            "",
            "## Lưu ý",
            "",
            "- LLM judge có sai số và có thể dao động nhẹ giữa các lần chạy.",
            "- Các điểm này nên đọc cùng báo cáo deterministic `EVALUATION_REPORT.md`.",
            "- Package `ragas` chưa được cài trong môi trường, nên report này tự triển khai rubric tương đương các metric RAGAS phổ biến.",
        ]
    )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/evaluation_set/eval_outputs.jsonl")
    parser.add_argument("--cache", default="data/evaluation_set/llm_judge_scores.jsonl")
    parser.add_argument("--out", default="data/evaluation_set/EVALUATION_REPORT_LLM_JUDGE.md")
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--sleep", type=float, default=0.0)
    args = parser.parse_args()

    _load_env(ROOT_DIR / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not configured.")

    from openai import OpenAI

    cases = _load_jsonl(Path(args.input))
    if args.limit:
        cases = cases[: args.limit]
    cached: dict[str, dict[str, Any]] = {}
    cache_path = Path(args.cache)
    if args.resume and cache_path.exists():
        cached = {row["id"]: row for row in _load_jsonl(cache_path)}

    client = OpenAI()
    scores = list(cached.values())
    done = set(cached)
    for index, case in enumerate(cases, start=1):
        case_id = case["id"]
        if case_id in done:
            continue
        try:
            judged = _score_case(client, args.model, case)
            row = {
                "id": case_id,
                "category": case["row"].get("category", "unknown"),
                **judged,
            }
        except Exception as exc:
            row = {
                "id": case_id,
                "category": case["row"].get("category", "unknown"),
                "faithfulness": 0.0,
                "answer_relevancy": 0.0,
                "context_precision": 0.0,
                "context_recall": 0.0,
                "answer_correctness": 0.0,
                "abstention_quality": 0.0,
                "notes": f"JUDGE_ERROR: {exc!r}",
            }
        scores.append(row)
        done.add(case_id)
        if index % 5 == 0:
            _write_jsonl(cache_path, scores)
            print(f"[judge] {len(done)}/{len(cases)} last={case_id}", flush=True)
        if args.sleep:
            time.sleep(args.sleep)

    _write_jsonl(cache_path, scores)
    _write_report(scores, Path(args.out), args.model)
    print(f"[judge] wrote {args.out}")


if __name__ == "__main__":
    main()
