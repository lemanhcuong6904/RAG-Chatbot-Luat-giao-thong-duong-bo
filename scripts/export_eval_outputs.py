from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]

# =========================
# CONFIG - edit here only
# =========================
INPUT_PATH = ROOT_DIR / "data" / "evaluation_set_2" / "eval_outputs_v2.jsonl"
MARKDOWN_OUTPUT_PATH = ROOT_DIR / "data" / "evaluation_set_2" / "eval_outputs_v2_table.md"
CSV_OUTPUT_PATH = ROOT_DIR / "data" / "evaluation_set_2" / "eval_outputs_v2_table.csv"

WRITE_MARKDOWN = True
WRITE_CSV = True

# Set to None to export all rows.
LIMIT: int | None = None

# Keep the table readable. Set to None for full text in Markdown.
MARKDOWN_CELL_MAX_CHARS: int | None = 900


def _load_jsonl(path: Path, limit: int | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            rows.append(json.loads(line))
            if limit is not None and len(rows) >= limit:
                break
    return rows


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _clip(value: str, max_chars: int | None) -> str:
    if max_chars is None or len(value) <= max_chars:
        return value
    return value[: max_chars - 1].rstrip() + "..."


def _markdown_cell(value: Any) -> str:
    text = _clip(_text(value), MARKDOWN_CELL_MAX_CHARS)
    return text.replace("|", "\\|").replace("\r\n", "\n").replace("\n", "<br>")


def _citation_summary(citations: list[dict[str, Any]]) -> str:
    parts = []
    for citation in citations:
        ref = " ".join(
            part
            for part in [
                _text(citation.get("document_number")),
                f"Điều {citation.get('article')}" if citation.get("article") else "",
                f"Khoản {citation.get('clause')}" if citation.get("clause") else "",
                f"Điểm {citation.get('point')}" if citation.get("point") else "",
            ]
            if part
        )
        text = _text(citation.get("text")).replace("\r\n", "\n").replace("\n", " ")
        parts.append(f"{ref}: {text}".strip(": "))
    return "\n".join(parts)


def _pre_rag_summary(debug: dict[str, Any]) -> str:
    routing = debug.get("routing") or {}
    pre_rag = routing.get("pre_rag") or {}
    if not pre_rag:
        return ""
    if pre_rag.get("skipped"):
        return f"skipped: {pre_rag.get('skip_reason') or ''}".strip()
    provider = pre_rag.get("provider")
    enabled = pre_rag.get("enabled")
    error = pre_rag.get("error")
    if error:
        return f"enabled={enabled}; provider={provider}; error={error}"
    return f"enabled={enabled}; provider={provider}"


def _flatten(record: dict[str, Any]) -> dict[str, Any]:
    row = record.get("row") or {}
    response = record.get("response") or {}
    debug = response.get("debug") or {}
    citations = response.get("citations") or []
    expected_answerable = row.get("expected_answerable")
    if expected_answerable is None and row.get("expected_response_mode"):
        expected_answerable = str(row.get("expected_response_mode")).upper() == "ANSWER"

    return {
        "id": record.get("id") or row.get("id"),
        "category": row.get("category") or row.get("benchmark_suite") or row.get("intent"),
        "difficulty": row.get("difficulty"),
        "question": row.get("query") or row.get("question"),
        "reference_answer": row.get("expected_answer") or row.get("reference_answer"),
        "system_answer": response.get("answer"),
        "expected_answerable": expected_answerable,
        "system_answerable": response.get("answerable"),
        "expected_provisions": row.get("expected_provisions"),
        "citations": _citation_summary(citations),
        "warnings": response.get("warnings"),
        "pre_rag": _pre_rag_summary(debug),
        "latency_s": record.get("latency_s"),
        "error": record.get("error"),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _text(value) for key, value in row.items()})


def _write_markdown(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "id",
        "category",
        "difficulty",
        "question",
        "reference_answer",
        "system_answer",
        "expected_answerable",
        "system_answerable",
        "expected_provisions",
        "citations",
        "pre_rag",
        "latency_s",
        "error",
    ]
    lines = [
        "# Evaluation Outputs V2",
        "",
        f"- Input: `{INPUT_PATH}`",
        f"- Rows: `{len(rows)}`",
        "",
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_markdown_cell(row.get(column)) for column in columns) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    records = _load_jsonl(INPUT_PATH, LIMIT)
    rows = [_flatten(record) for record in records]
    if WRITE_CSV:
        _write_csv(CSV_OUTPUT_PATH, rows)
        print(f"[export] wrote {CSV_OUTPUT_PATH}")
    if WRITE_MARKDOWN:
        _write_markdown(MARKDOWN_OUTPUT_PATH, rows)
        print(f"[export] wrote {MARKDOWN_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
