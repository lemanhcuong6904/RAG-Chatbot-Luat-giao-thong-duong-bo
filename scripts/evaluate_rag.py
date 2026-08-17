from __future__ import annotations

import json
import math
import os
import re
import statistics
import time
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

# =========================
# CONFIG - edit here only
# =========================
DATASET_PATH = ROOT_DIR / "data" / "evaluation_set_2" / "golden_v2_200.jsonl"
REPORT_PATH = ROOT_DIR / "data" / "evaluation_set_2" / "EVALUATION_REPORT_bge_m3.md"
CACHE_PATH = ROOT_DIR / "data" / "evaluation_set_2" / "eval_outputs_bge_m3.jsonl"

# Smoke-test alternative:
# DATASET_PATH = ROOT_DIR / "data" / "evaluation_set_2" / "smoke_v2_50.jsonl"
# REPORT_PATH = ROOT_DIR / "data" / "evaluation_set_2" / "EVALUATION_REPORT_SMOKE_V2.md"
# CACHE_PATH = ROOT_DIR / "data" / "evaluation_set_2" / "eval_outputs_smoke_v2.jsonl"

# Options: "full", "fast", "deterministic"
EVALUATION_MODE = "full"

# Set to None to evaluate all rows.
LIMIT: int | None = None

TOP_K = 8
RESUME_FROM_CACHE = False

# Dense embedding preset for this evaluation run.
# Options: "bge_m3", "qwen3_0_6b"
EVALUATION_EMBEDDING_PRESET = "bge_m3"

# Pre-RAG controls.
# Set ENABLE_PRE_RAG_STAGE=False to bypass Pre-RAG completely.
# Set ENABLE_PRE_RAG_LLM=True to run the LLM query transformer before retrieval.
# Keep ENABLE_QUERY_ROUTER_LLM=False when you want the Pre-RAG transformer to run
# consistently; an OpenAI router can make the transformer skip when its plan is sufficient.
ENABLE_PRE_RAG_STAGE = True
ENABLE_PRE_RAG_LLM = False
ENABLE_QUERY_ROUTER_LLM = True


def _parse_expected_answerable(row: dict[str, Any]) -> bool:
    if "expected_answerable" in row:
        return bool(row.get("expected_answerable"))
    mode = str(row.get("expected_response_mode") or "ANSWER").strip().upper()
    return mode == "ANSWER"


def _parse_expected_provision(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    document_number = None
    document_match = re.search(r"(\d+/\d{4}/[^,\s]+)", text, flags=re.IGNORECASE)
    if document_match:
        document_number = document_match.group(1)

    folded = _fold(text)
    article = None
    article_match = re.search(r"dieu\s+(\d+[a-z]?)", folded, flags=re.IGNORECASE)
    if article_match:
        article = article_match.group(1)

    clause = None
    clause_match = re.search(r"khoan\s+(\d+[a-z]?)", folded, flags=re.IGNORECASE)
    if clause_match:
        clause = clause_match.group(1)

    point = None
    point_match = re.search(r"diem\s+([a-z])", folded, flags=re.IGNORECASE)
    if point_match:
        point = point_match.group(1).casefold()

    return {
        "document_number": document_number,
        "article": article,
        "clause": clause,
        "point": point,
    }


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    normalized.setdefault("query", row.get("question") or row.get("query") or "")
    normalized.setdefault("expected_answer", row.get("reference_answer") or row.get("expected_answer") or "")
    normalized.setdefault("category", row.get("category") or row.get("benchmark_suite") or row.get("intent") or "unknown")
    normalized["expected_answerable"] = _parse_expected_answerable(row)

    provisions = []
    for item in row.get("expected_provisions") or []:
        parsed = _parse_expected_provision(item)
        if parsed:
            provisions.append(parsed)
    normalized["expected_provisions"] = provisions

    if "must_include" not in normalized:
        normalized["must_include"] = row.get("required_claims") or []
    if "gold_evidence_texts" not in normalized and row.get("reference_answer"):
        normalized["gold_evidence_texts"] = [row["reference_answer"]]
    return normalized


def _set_mode(mode: str) -> None:
    os.environ["RAG_EMBEDDING_PRESET"] = EVALUATION_EMBEDDING_PRESET
    os.environ.setdefault("RAG_EMBEDDING_MODEL", "")
    os.environ["RAG_EMBEDDING_PROGRESS"] = "false"
    if mode == "deterministic":
        os.environ["RAG_PRERAG_PROVIDER"] = "rule"
        os.environ["RAG_LLM_PROVIDER"] = "extractive"
        os.environ["RAG_SANCTION_LLM_PROVIDER"] = "extractive"
        os.environ["RAG_RERANKER_ENABLED"] = "false"
    elif mode == "fast":
        os.environ["RAG_PRERAG_PROVIDER"] = "rule"
        os.environ["RAG_SANCTION_LLM_PROVIDER"] = "extractive"


def _set_eval_prerag_config() -> None:
    os.environ["RAG_PRERAG_PROVIDER"] = "openai" if ENABLE_PRE_RAG_LLM else "rule"
    os.environ["RAG_QUERY_ROUTER_PROVIDER"] = "openai" if ENABLE_QUERY_ROUTER_LLM else "rule"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def _norm(value: Any) -> str:
    return _fold(value)


def _fold(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().casefold().replace("đ", "d")
    return "".join(
        char
        for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    )


def _provision_key(item: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        _norm(item.get("document_number")),
        _norm(item.get("article")),
        _norm(item.get("clause")),
        _norm(item.get("point")),
    )


def _citation_key(item: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        _norm(item.get("document_number")),
        _norm(item.get("article")),
        _norm(item.get("clause")),
        _norm(item.get("point")),
    )


def _matches(expected: tuple[str, str, str, str], actual: tuple[str, str, str, str]) -> bool:
    return all(not exp or exp == got for exp, got in zip(expected, actual, strict=True))


def _money_values(text: str) -> list[int]:
    values: list[int] = []
    for match in re.finditer(r"\b\d{1,3}(?:\.\d{3})+\b", text):
        try:
            values.append(int(match.group(0).replace(".", "")))
        except ValueError:
            pass
    return values


def _point_values(text: str) -> list[int]:
    values = []
    for match in re.finditer(r"(?:trừ|tru)\s*(\d{1,2})\s*(?:điểm|diem)", text, flags=re.IGNORECASE):
        values.append(int(match.group(1)))
    return values


def _tokens(text: str) -> set[str]:
    return {token.casefold() for token in re.findall(r"\w+", text, flags=re.UNICODE) if len(token) >= 3}


def _f1(tp: int, fp: int, fn: int) -> float:
    if tp == 0:
        return 0.0
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    return 2 * precision * recall / max(precision + recall, 1e-12)


@dataclass
class CaseMetrics:
    row: dict[str, Any]
    response: dict[str, Any]
    latency_s: float
    error: str | None = None

    @property
    def citations(self) -> list[dict[str, Any]]:
        return self.response.get("citations") or []

    @property
    def answer(self) -> str:
        return self.response.get("answer") or ""

    @property
    def answerable(self) -> bool:
        return bool(self.response.get("answerable"))


def _retrieval_metrics(case: CaseMetrics) -> dict[str, Any]:
    expected = [_provision_key(item) for item in case.row.get("expected_provisions") or []]
    citations = [_citation_key(item) for item in case.citations]
    if not expected:
        return {"applicable": False}

    ranks = []
    for exp in expected:
        rank = next((idx for idx, got in enumerate(citations, start=1) if _matches(exp, got)), None)
        if rank is not None:
            ranks.append(rank)

    rels = [1 if any(_matches(exp, got) for exp in expected) else 0 for got in citations[:10]]
    dcg = sum(rel / math.log2(idx + 2) for idx, rel in enumerate(rels))
    ideal_rels = [1] * min(len(expected), 10)
    idcg = sum(rel / math.log2(idx + 2) for idx, rel in enumerate(ideal_rels))

    return {
        "applicable": True,
        "recall@1": any(rank <= 1 for rank in ranks),
        "recall@3": any(rank <= 3 for rank in ranks),
        "recall@5": any(rank <= 5 for rank in ranks),
        "recall@10": any(rank <= 10 for rank in ranks),
        "completeness@10": len(set(ranks)) >= len(expected),
        "mrr": 0.0 if not ranks else 1.0 / min(ranks),
        "ndcg@10": 0.0 if idcg == 0 else dcg / idcg,
    }


def _generation_metrics(case: CaseMetrics) -> dict[str, Any]:
    expected_answerable = bool(case.row.get("expected_answerable"))
    expected_provisions = [_provision_key(item) for item in case.row.get("expected_provisions") or []]
    citation_keys = [_citation_key(item) for item in case.citations]
    cited_matches = [
        exp
        for exp in expected_provisions
        if any(_matches(exp, got) for got in citation_keys)
    ]

    fine_min = case.row.get("expected_fine_min")
    fine_max = case.row.get("expected_fine_max")
    expected_points = case.row.get("expected_points")
    money = _money_values(case.answer)
    points = _point_values(case.answer)
    expected_items = case.row.get("expected_item_texts") or case.row.get("expected_items") or []
    answer_tokens = _tokens(case.answer)

    item_hits = 0
    for item in expected_items:
        item_tokens = _tokens(str(item))
        if item_tokens and len(item_tokens & answer_tokens) / len(item_tokens) >= 0.5:
            item_hits += 1

    gold_texts = case.row.get("gold_evidence_texts") or []
    gold_tokens = set().union(*[_tokens(str(text)) for text in gold_texts]) if gold_texts else set()
    context_tokens = set().union(*[_tokens(str(citation.get("text") or "")) for citation in case.citations]) if case.citations else set()

    return {
        "answerable_correct": case.answerable == expected_answerable,
        "citation_correct": (not expected_provisions) or bool(cited_matches),
        "citation_complete": (not expected_provisions) or len(cited_matches) == len(expected_provisions),
        "numeric_exact": fine_min is None and fine_max is None or (fine_min in money and fine_max in money),
        "points_exact": expected_points is None or expected_points in points,
        "enumeration_completeness": None if not expected_items else item_hits / len(expected_items),
        "must_include": all(str(item).casefold() in case.answer.casefold() for item in case.row.get("must_include") or []),
        "context_recall_proxy": None if not gold_tokens else len(gold_tokens & context_tokens) / len(gold_tokens),
        "answer_relevance_proxy": len(_tokens(case.row.get("query") or case.row.get("question") or "") & answer_tokens) / max(len(_tokens(case.row.get("query") or case.row.get("question") or "")), 1),
    }


def _structured_metrics(case: CaseMetrics) -> dict[str, Any]:
    debug = case.response.get("debug") or {}
    parsed = debug.get("parsed_query") or {}
    expected_vehicle = case.row.get("expected_vehicle")
    expected_behavior = case.row.get("expected_behavior")
    return {
        "vehicle_applicable": expected_vehicle is not None,
        "vehicle_correct": expected_vehicle is None or _norm(expected_vehicle) in {_norm(parsed.get("vehicle_type")), _norm(parsed.get("vehicle_code"))},
        "behavior_applicable": expected_behavior is not None,
        "behavior_correct": expected_behavior is None or _norm(expected_behavior) in _norm(parsed.get("behavior_text_query") or parsed.get("behavior_code") or parsed.get("query")),
    }


def _run_cases(dataset: list[dict[str, Any]], cache_path: Path, resume: bool, top_k: int) -> list[dict[str, Any]]:
    cached: dict[str, dict[str, Any]] = {}
    if resume and cache_path.exists():
        cached = {row["id"]: row for row in _load_jsonl(cache_path)}

    from rag_luat_gt.schemas import ChatRequest
    from rag_luat_gt.service import RAGService

    service = RAGService()
    service.warm_up()
    dataset_ids = {row["id"] for row in dataset}
    outputs = [cached[row["id"]] for row in dataset if row["id"] in cached]
    done = {row["id"] for row in outputs}
    if resume:
        print(f"[eval] resume cache: {len(done)}/{len(dataset)} cases already available", flush=True)

    from tqdm.auto import tqdm

    progress = tqdm(dataset, total=len(dataset), desc="Evaluating RAG", unit="case")
    for index, row in enumerate(progress, start=1):
        if row["id"] in done:
            progress.set_postfix(status="cached", done=len(done))
            continue
        started = time.perf_counter()
        error = None
        try:
            request = ChatRequest(
                query=row["query"],
                event_date=row.get("event_date"),
                as_of_date=row.get("as_of_date"),
                top_k=top_k,
                debug=True,
                pre_rag_enabled=ENABLE_PRE_RAG_STAGE,
                embedding_preset=EVALUATION_EMBEDDING_PRESET,
            )
            response = service.answer(request).model_dump()
        except Exception as exc:
            response = {"answer": "", "citations": [], "warnings": [str(exc)], "answerable": False, "debug": {}}
            error = repr(exc)
        latency = time.perf_counter() - started
        output = {"id": row["id"], "row": row, "response": response, "latency_s": latency, "error": error}
        outputs.append(output)
        done.add(row["id"])
        progress.set_postfix(status="ran", last=row["id"], latency=f"{latency:.2f}s")
        if index % 5 == 0:
            _write_jsonl(cache_path, outputs)

    outputs = [row for row in outputs if row["id"] in dataset_ids]
    _write_jsonl(cache_path, outputs)
    return outputs


def _mean(values: list[float | bool | None]) -> float | None:
    filtered = [float(value) for value in values if value is not None]
    return None if not filtered else sum(filtered) / len(filtered)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    rank = (len(ordered) - 1) * percentile
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[int(rank)]
    fraction = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _summarize(outputs: list[dict[str, Any]], mode: str, dataset_path: Path) -> tuple[str, dict[str, Any]]:
    cases = [CaseMetrics(row=o["row"], response=o["response"], latency_s=o["latency_s"], error=o.get("error")) for o in outputs]
    latencies = [case.latency_s for case in cases]
    retrieval = [_retrieval_metrics(case) for case in cases]
    generation = [_generation_metrics(case) for case in cases]
    structured = [_structured_metrics(case) for case in cases]
    by_category: dict[str, list[int]] = defaultdict(list)
    for idx, case in enumerate(cases):
        by_category[case.row.get("category", "unknown")].append(idx)

    abst_tp = sum(case.answerable and bool(case.row.get("expected_answerable")) for case in cases)
    abst_tn = sum((not case.answerable) and (not bool(case.row.get("expected_answerable"))) for case in cases)
    abst_fp = sum(case.answerable and (not bool(case.row.get("expected_answerable"))) for case in cases)
    abst_fn = sum((not case.answerable) and bool(case.row.get("expected_answerable")) for case in cases)

    summary = {
        "n": len(cases),
        "errors": sum(1 for case in cases if case.error),
        "latency_mean_s": statistics.mean(latencies) if latencies else 0,
        "latency_p50_s": statistics.median(latencies) if latencies else 0,
        "latency_p95_s": _percentile(latencies, 0.95),
        "retrieval": {
            key: _mean([item.get(key) for item in retrieval if item.get("applicable")])
            for key in ["recall@1", "recall@3", "recall@5", "recall@10", "completeness@10", "mrr", "ndcg@10"]
        },
        "generation": {
            key: _mean([item.get(key) for item in generation])
            for key in [
                "answerable_correct",
                "citation_correct",
                "citation_complete",
                "numeric_exact",
                "points_exact",
                "enumeration_completeness",
                "must_include",
                "context_recall_proxy",
                "answer_relevance_proxy",
            ]
        },
        "abstention": {
            "accuracy": (abst_tp + abst_tn) / max(len(cases), 1),
            "f1_answerable": _f1(abst_tp, abst_fp, abst_fn),
            "tp": abst_tp,
            "tn": abst_tn,
            "fp": abst_fp,
            "fn": abst_fn,
        },
        "structured": {
            "vehicle_mapping_accuracy": _mean([item["vehicle_correct"] for item in structured if item["vehicle_applicable"]]),
            "behavior_mapping_accuracy": _mean([item["behavior_correct"] for item in structured if item["behavior_applicable"]]),
        },
    }

    lines = [
        "# Báo cáo đánh giá RAG Luật giao thông",
        "",
        f"- Thời điểm chạy: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Dataset: `{dataset_path}`",
        f"- Embedding preset: `{EVALUATION_EMBEDDING_PRESET}`",
        f"- Chế độ: `{mode}`",
        f"- Pre-RAG stage: `{ENABLE_PRE_RAG_STAGE}`",
        f"- Pre-RAG LLM transformer: `{ENABLE_PRE_RAG_LLM}`",
        f"- Query router LLM: `{ENABLE_QUERY_ROUTER_LLM}`",
        f"- Số câu: `{summary['n']}`",
        f"- Số lỗi runtime: `{summary['errors']}`",
        f"- Latency trung bình: `{summary['latency_mean_s']:.2f}s`; p50: `{summary['latency_p50_s']:.2f}s`; p95: `{summary['latency_p95_s']:.2f}s`",
        "",
        "## Retrieval",
        "",
        "| Metric | Score |",
        "|---|---:|",
    ]
    for key, value in summary["retrieval"].items():
        lines.append(f"| {key} | {_fmt(value)} |")

    lines.extend(["", "## Generation / Answer", "", "| Metric | Score |", "|---|---:|"])
    for key, value in summary["generation"].items():
        lines.append(f"| {key} | {_fmt(value)} |")

    lines.extend(
        [
            "",
            "## Abstention",
            "",
            "| Metric | Score |",
            "|---|---:|",
            f"| accuracy | {_fmt(summary['abstention']['accuracy'])} |",
            f"| f1_answerable | {_fmt(summary['abstention']['f1_answerable'])} |",
            f"| TP/TN/FP/FN | {abst_tp}/{abst_tn}/{abst_fp}/{abst_fn} |",
            "",
            "## Structured Sanction",
            "",
            "| Metric | Score |",
            "|---|---:|",
            f"| vehicle_mapping_accuracy | {_fmt(summary['structured']['vehicle_mapping_accuracy'])} |",
            f"| behavior_mapping_accuracy | {_fmt(summary['structured']['behavior_mapping_accuracy'])} |",
            "",
            "## Theo nhóm câu hỏi",
            "",
            "| Category | N | Recall@5 | Citation Complete | Answerable Acc | Numeric Exact | Points Exact |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for category, indexes in sorted(by_category.items()):
        lines.append(
            "| {category} | {n} | {r5} | {cc} | {aa} | {ne} | {pe} |".format(
                category=category,
                n=len(indexes),
                r5=_fmt(_mean([retrieval[i].get("recall@5") for i in indexes if retrieval[i].get("applicable")])),
                cc=_fmt(_mean([generation[i].get("citation_complete") for i in indexes])),
                aa=_fmt(_mean([generation[i].get("answerable_correct") for i in indexes])),
                ne=_fmt(_mean([generation[i].get("numeric_exact") for i in indexes])),
                pe=_fmt(_mean([generation[i].get("points_exact") for i in indexes])),
            )
        )

    lines.extend(
        [
            "",
            "## RAGAS",
            "",
            "`ragas` và `datasets` không có trong môi trường hiện tại, nên báo cáo này không chạy RAGAS chính thức.",
            "Thay vào đó báo cáo có hai proxy deterministic:",
            "",
            "- `context_recall_proxy`: overlap token giữa `gold_evidence_texts` và citations/context trả về.",
            "- `answer_relevance_proxy`: overlap token giữa query và answer.",
            "",
            "Để chạy RAGAS chính thức, cần cài thêm `ragas`, `datasets` và cấu hình LLM/embedding judge ổn định.",
            "",
            "## Lưu ý diễn giải",
            "",
            "- `score` là tỷ lệ 0-1 trừ MRR/nDCG vốn cũng chuẩn hóa 0-1.",
            "- `numeric_exact` chỉ áp dụng khi case có `expected_fine_min/max`; case không có numeric gold được tính là pass.",
            "- `points_exact` tương tự cho `expected_points`.",
            "- `Citation Complete` yêu cầu tất cả provisions gold xuất hiện trong citations, không chấm exact wording.",
        ]
    )
    return "\n".join(lines) + "\n", summary


def _fmt(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.3f}"


def main() -> None:
    _set_mode(EVALUATION_MODE)
    _set_eval_prerag_config()
    dataset = [_normalize_row(row) for row in _load_jsonl(DATASET_PATH)]
    if LIMIT is not None:
        dataset = dataset[:LIMIT]
    outputs = _run_cases(dataset, CACHE_PATH, resume=RESUME_FROM_CACHE, top_k=TOP_K)
    report, summary = _summarize(outputs, EVALUATION_MODE, DATASET_PATH)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    REPORT_PATH.with_suffix(".summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[eval] wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
