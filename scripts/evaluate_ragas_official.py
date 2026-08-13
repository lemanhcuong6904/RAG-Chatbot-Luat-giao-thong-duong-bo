from __future__ import annotations

import json
import math
import os
import sys
import types
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langchain_core.embeddings import Embeddings

from rag_luat_gt.config import RAG_EMBEDDING_MODEL
from rag_luat_gt.embedding.bge_m3 import BGEM3Embedder

DATA_DIR = ROOT / "data" / "evaluation_set"
DEFAULT_INPUT = DATA_DIR / "eval_outputs.jsonl"
DEFAULT_REPORT = DATA_DIR / "EVALUATION_REPORT_RAGAS.md"
DEFAULT_JSON = DATA_DIR / "ragas_official_scores.json"
DEFAULT_CSV = DATA_DIR / "ragas_official_scores.csv"

# =========================
# CONFIG - edit here only
# =========================
INPUT_PATH = DEFAULT_INPUT
LIMIT: int | None = None
MAX_CONTEXTS = 8

RAGAS_LLM_MODEL = "gpt-4o-mini"
RAGAS_EMBEDDING_MODEL = RAG_EMBEDDING_MODEL
BATCH_SIZE = 4

REPORT_PATH = DEFAULT_REPORT
JSON_OUTPUT_PATH = DEFAULT_JSON
CSV_OUTPUT_PATH = DEFAULT_CSV


class BGEEmbeddings(Embeddings):
    """LangChain-compatible wrapper for the project's local BGE-M3 embedder."""

    def __init__(self, model_name: str = RAGAS_EMBEDDING_MODEL) -> None:
        self.model_name = model_name
        self.embedder = BGEM3Embedder(model_name=model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embedder.encode(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.embedder.encode_query(text)


def install_ragas_vertexai_compat_shim() -> None:
    """RAGAS 0.4.3 imports an old LangChain VertexAI path that may be absent.

    The evaluation here uses OpenAI, not VertexAI. The shim only lets ragas import
    without editing site-packages.
    """
    module_name = "langchain_community.chat_models.vertexai"
    if module_name in sys.modules:
        return
    try:
        __import__(module_name)
        return
    except ModuleNotFoundError:
        pass

    from langchain_core.language_models.chat_models import BaseChatModel

    shim = types.ModuleType(module_name)
    shim.ChatVertexAI = BaseChatModel
    sys.modules[module_name] = shim


def read_jsonl(path: Path, limit: int | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rows.append(json.loads(line))
            if limit is not None and len(rows) >= limit:
                break
    return rows


def citation_contexts(response: dict[str, Any], max_contexts: int) -> list[str]:
    contexts: list[str] = []
    for citation in response.get("citations") or []:
        text = citation.get("text") or citation.get("content") or ""
        title_parts = [
            citation.get("document_number"),
            f"Điều {citation.get('article')}" if citation.get("article") else None,
            f"Khoản {citation.get('clause')}" if citation.get("clause") else None,
            f"Điểm {citation.get('point')}" if citation.get("point") else None,
        ]
        title = " - ".join(str(part) for part in title_parts if part)
        merged = f"{title}\n{text}".strip()
        if merged:
            contexts.append(merged)
        if len(contexts) >= max_contexts:
            break
    return contexts


def reference_text(row: dict[str, Any]) -> str:
    pieces: list[str] = []
    if row.get("expected_answer"):
        pieces.append(str(row["expected_answer"]))
    if row.get("gold_evidence_texts"):
        pieces.extend(str(x) for x in row["gold_evidence_texts"] if x)
    provisions = row.get("expected_provisions") or []
    if provisions:
        refs = []
        for prov in provisions:
            ref = [prov.get("document_number")]
            if prov.get("article"):
                ref.append(f"Điều {prov['article']}")
            if prov.get("clause"):
                ref.append(f"Khoản {prov['clause']}")
            if prov.get("point"):
                ref.append(f"Điểm {prov['point']}")
            refs.append(" - ".join(str(x) for x in ref if x))
        pieces.append("Căn cứ kỳ vọng: " + "; ".join(refs))
    if not pieces and row.get("expected_answerable") is False:
        pieces.append("Câu hỏi không đủ căn cứ trong corpus; hệ thống nên từ chối hoặc nói không có nguồn phù hợp.")
    return "\n".join(pieces).strip()


def build_dataset_rows(records: list[dict[str, Any]], max_contexts: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ragas_rows: list[dict[str, Any]] = []
    metadata_rows: list[dict[str, Any]] = []
    for record in records:
        row = record.get("row") or {}
        response = record.get("response") or {}
        contexts = citation_contexts(response, max_contexts=max_contexts)
        if not contexts:
            contexts = ["Không có context/citation được hệ thống trả về."]
        reference = reference_text(row)
        answer = response.get("answer") or ""
        ragas_rows.append(
            {
                "question": row.get("query") or record.get("query") or "",
                "answer": answer,
                "contexts": contexts,
                "ground_truth": reference,
                "reference": reference,
            }
        )
        metadata_rows.append(
            {
                "id": record.get("id") or row.get("id"),
                "category": row.get("category"),
                "difficulty": row.get("difficulty"),
                "expected_answerable": row.get("expected_answerable"),
                "answerable": response.get("answerable"),
                "num_contexts": len(contexts),
                "latency_s": record.get("latency_s"),
                "error": record.get("error"),
            }
        )
    return ragas_rows, metadata_rows


def finite_mean(values: list[Any]) -> float | None:
    nums: list[float] = []
    for value in values:
        try:
            num = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(num):
            nums.append(num)
    if not nums:
        return None
    return sum(nums) / len(nums)


def write_report(
    path: Path,
    *,
    ragas_version: str,
    model: str,
    embedding_model: str,
    input_path: Path,
    output_json: Path,
    output_csv: Path,
    metric_names: list[str],
    rows: list[dict[str, Any]],
) -> None:
    overall = {metric: finite_mean([row.get(metric) for row in rows]) for metric in metric_names}
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_category[str(row.get("category") or "unknown")].append(row)

    lines = [
        "# Official RAGAS Evaluation Report",
        "",
        f"- Generated at: `{datetime.now(timezone.utc).isoformat()}`",
        f"- Input: `{input_path}`",
        f"- RAGAS version: `{ragas_version}`",
        f"- Judge LLM: `{model}`",
        f"- Embedding model: `{embedding_model}`",
        f"- Samples: `{len(rows)}`",
        f"- Raw JSON: `{output_json}`",
        f"- CSV: `{output_csv}`",
        "",
        "## Metrics",
        "",
        "| Metric | Mean |",
        "|---|---:|",
    ]
    for metric, value in overall.items():
        lines.append(f"| {metric} | {value:.3f} |" if value is not None else f"| {metric} | n/a |")

    lines.extend(["", "## By Category", "", "| Category | N | " + " | ".join(metric_names) + " |"])
    lines.append("|---|---:|" + "|".join("---:" for _ in metric_names) + "|")
    for category in sorted(by_category):
        category_rows = by_category[category]
        cells = []
        for metric in metric_names:
            value = finite_mean([row.get(metric) for row in category_rows])
            cells.append(f"{value:.3f}" if value is not None else "n/a")
        lines.append(f"| {category} | {len(category_rows)} | " + " | ".join(cells) + " |")

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This report uses the official `ragas.evaluate` implementation.",
            "- It evaluates the answers and contexts already present in `eval_outputs.jsonl`; rerun `scripts/evaluate_rag.py` first if the RAG pipeline/config changed.",
            "- Rows with no returned citations use a placeholder context so RAGAS can still score the sample.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    load_dotenv(ROOT / ".env")
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for official RAGAS LLM/embedding metrics.")

    install_ragas_vertexai_compat_shim()

    import pandas as pd
    import ragas
    from datasets import Dataset
    from langchain_openai import ChatOpenAI
    from ragas import evaluate
    from ragas.metrics._answer_correctness import answer_correctness
    from ragas.metrics._answer_relevance import answer_relevancy
    from ragas.metrics._context_precision import context_precision
    from ragas.metrics._context_recall import context_recall
    from ragas.metrics._faithfulness import faithfulness

    records = read_jsonl(INPUT_PATH, LIMIT)
    ragas_rows, metadata_rows = build_dataset_rows(records, max_contexts=MAX_CONTEXTS)
    dataset = Dataset.from_list(ragas_rows)

    llm = ChatOpenAI(model=RAGAS_LLM_MODEL, temperature=0)
    embeddings = BGEEmbeddings(model_name=RAGAS_EMBEDDING_MODEL)
    metrics = [faithfulness, answer_relevancy, context_precision, context_recall, answer_correctness]

    result = evaluate(
        dataset,
        metrics=metrics,
        llm=llm,
        embeddings=embeddings,
        raise_exceptions=False,
        show_progress=True,
        batch_size=BATCH_SIZE,
    )
    frame = result.to_pandas()
    meta_frame = pd.DataFrame(metadata_rows)
    for column in meta_frame.columns:
        frame.insert(0, column, meta_frame[column])

    metric_names = [getattr(metric, "name", type(metric).__name__) for metric in metrics]
    JSON_OUTPUT_PATH.write_text(frame.to_json(orient="records", force_ascii=False, indent=2), encoding="utf-8")
    frame.to_csv(CSV_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    write_report(
        REPORT_PATH,
        ragas_version=getattr(ragas, "__version__", "unknown"),
        model=RAGAS_LLM_MODEL,
        embedding_model=RAGAS_EMBEDDING_MODEL,
        input_path=INPUT_PATH,
        output_json=JSON_OUTPUT_PATH,
        output_csv=CSV_OUTPUT_PATH,
        metric_names=metric_names,
        rows=frame.to_dict(orient="records"),
    )
    print(f"Wrote {REPORT_PATH}")
    print(f"Wrote {JSON_OUTPUT_PATH}")
    print(f"Wrote {CSV_OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
