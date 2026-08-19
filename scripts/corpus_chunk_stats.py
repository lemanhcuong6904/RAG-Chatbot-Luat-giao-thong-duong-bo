from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INDEX_DIR = ROOT_DIR / "data" / "index"


WORD_RE = re.compile(r"\S+")
STRUCTURAL_TYPES = ("ARTICLE", "CLAUSE", "POINT")


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
    return rows


def _text_length(text: str) -> dict[str, int]:
    return {
        "chars": len(text),
        "words": len(WORD_RE.findall(text)),
    }


def _percent(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return count * 100 / total


def _fmt_number(value: int | float) -> str:
    if isinstance(value, float):
        return f"{value:,.2f}"
    return f"{value:,}"


def _manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_stats(chunks_path: Path, documents_path: Path | None = None, manifest_path: Path | None = None) -> dict[str, Any]:
    chunks = _load_jsonl(chunks_path)
    documents = _load_jsonl(documents_path) if documents_path and documents_path.exists() else []
    manifest = _manifest(manifest_path) if manifest_path else {}

    document_ids_from_chunks = {chunk.get("document_id") for chunk in chunks if chunk.get("document_id")}
    document_count = len(documents) if documents else len(document_ids_from_chunks)

    article_keys = {
        (chunk.get("document_id"), str(chunk.get("article")))
        for chunk in chunks
        if chunk.get("document_id") and chunk.get("article") not in (None, "")
    }

    type_counts = Counter(str(chunk.get("chunk_type") or "UNKNOWN").upper() for chunk in chunks)
    lengths = [_text_length(str(chunk.get("text") or "")) for chunk in chunks]
    total_chunks = len(chunks)

    avg_chars = sum(item["chars"] for item in lengths) / total_chunks if total_chunks else 0.0
    avg_words = sum(item["words"] for item in lengths) / total_chunks if total_chunks else 0.0

    structural_counts = {chunk_type: type_counts.get(chunk_type, 0) for chunk_type in STRUCTURAL_TYPES}
    structural_total = sum(structural_counts.values())

    return {
        "source": {
            "chunks_path": str(chunks_path),
            "documents_path": str(documents_path) if documents_path else None,
            "manifest_path": str(manifest_path) if manifest_path else None,
            "chunking_version": manifest.get("chunking_version"),
            "corpus_hash": manifest.get("corpus_hash"),
        },
        "totals": {
            "documents": document_count,
            "articles": len(article_keys),
            "chunks": total_chunks,
        },
        "length": {
            "avg_chars": avg_chars,
            "avg_words": avg_words,
        },
        "chunk_types": {
            "counts": dict(sorted(type_counts.items())),
            "article_clause_point": {
                chunk_type: {
                    "count": count,
                    "pct_of_all_chunks": _percent(count, total_chunks),
                    "pct_of_article_clause_point_chunks": _percent(count, structural_total),
                }
                for chunk_type, count in structural_counts.items()
            },
            "article_clause_point_total": structural_total,
            "other_total": total_chunks - structural_total,
        },
    }


def print_report(stats: dict[str, Any]) -> None:
    totals = stats["totals"]
    length = stats["length"]
    source = stats["source"]
    acp = stats["chunk_types"]["article_clause_point"]

    print("THỐNG KÊ CORPUS CHUNK")
    print("=" * 24)
    print(f"Chunks file      : {source['chunks_path']}")
    if source.get("chunking_version"):
        print(f"Chunking version : {source['chunking_version']}")
    if source.get("corpus_hash"):
        print(f"Corpus hash      : {source['corpus_hash']}")
    print()
    print(f"Số văn bản       : {_fmt_number(totals['documents'])}")
    print(f"Số Điều          : {_fmt_number(totals['articles'])}")
    print(f"Số chunk         : {_fmt_number(totals['chunks'])}")
    print(f"Độ dài TB        : {_fmt_number(length['avg_chars'])} ký tự | {_fmt_number(length['avg_words'])} từ")
    print()
    print("TỶ LỆ ARTICLE / CLAUSE / POINT")
    print("-" * 58)
    print(f"{'Loại':<10} {'Số chunk':>12} {'% toàn bộ':>12} {'% A/C/P':>12}")
    for chunk_type in STRUCTURAL_TYPES:
        item = acp[chunk_type]
        print(
            f"{chunk_type:<10} "
            f"{_fmt_number(item['count']):>12} "
            f"{item['pct_of_all_chunks']:>11.2f}% "
            f"{item['pct_of_article_clause_point_chunks']:>11.2f}%"
        )

    print("-" * 58)
    print(f"{'A/C/P total':<10} {_fmt_number(stats['chunk_types']['article_clause_point_total']):>12}")
    print(f"{'Other':<10} {_fmt_number(stats['chunk_types']['other_total']):>12}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Thống kê chunk trong corpus/index JSONL.")
    parser.add_argument(
        "--index-dir",
        type=Path,
        default=DEFAULT_INDEX_DIR,
        help="Thư mục index chứa chunks.jsonl/documents.jsonl/manifest.json.",
    )
    parser.add_argument("--chunks", type=Path, default=None, help="Đường dẫn chunks.jsonl tùy chỉnh.")
    parser.add_argument("--documents", type=Path, default=None, help="Đường dẫn documents.jsonl tùy chỉnh.")
    parser.add_argument("--manifest", type=Path, default=None, help="Đường dẫn manifest.json tùy chỉnh.")
    parser.add_argument("--json", action="store_true", help="In kết quả dạng JSON.")
    return parser.parse_args()


def main() -> None:
    _configure_stdout()
    args = parse_args()
    index_dir = args.index_dir
    chunks_path = args.chunks or index_dir / "chunks.jsonl"
    documents_path = args.documents or index_dir / "documents.jsonl"
    manifest_path = args.manifest or index_dir / "manifest.json"

    stats = build_stats(chunks_path=chunks_path, documents_path=documents_path, manifest_path=manifest_path)
    if args.json:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    else:
        print_report(stats)


if __name__ == "__main__":
    main()
