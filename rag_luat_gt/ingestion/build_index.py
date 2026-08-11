from __future__ import annotations

import json
import pickle
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from rank_bm25 import BM25Okapi

from rag_luat_gt.config import (
    BM25_PATH,
    CHUNKS_PATH,
    DOCUMENTS_PATH,
    INDEX_DIR,
    MANIFEST_PATH,
    MARKDOWN_DIR,
    QDRANT_READY_FILE,
    ROOT_DIR,
)
from rag_luat_gt.ingestion.legal_parser import parse_chunks
from rag_luat_gt.ingestion.markdown import read_markdown
from rag_luat_gt.ingestion.normalizer import normalize_document
from rag_luat_gt.text import tokenize


CHUNKING_VERSION = "legal-parser-v4-rule-function"


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def _corpus_hash(markdown_files: list[Path], root_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in markdown_files:
        digest.update(path.relative_to(root_dir).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def build_index(
    markdown_dir: Path,
    root_dir: Path,
    index_dir: Path = INDEX_DIR,
    invalidate_dense: bool = True,
) -> dict:
    documents = []
    chunks = []
    markdown_files = sorted(markdown_dir.rglob("*.md"))

    for markdown_file in markdown_files:
        source_file = markdown_file.relative_to(root_dir).as_posix()
        metadata, body = read_markdown(markdown_file)
        document = normalize_document(metadata, source_file)
        documents.append(document)
        chunks.extend(parse_chunks(document, body, source_file))

    index_dir.mkdir(parents=True, exist_ok=True)
    documents_path = index_dir / "documents.jsonl"
    chunks_path = index_dir / "chunks.jsonl"
    bm25_path = index_dir / "bm25.pkl"
    manifest_path = index_dir / "manifest.json"
    write_jsonl(documents_path, [document.model_dump() for document in documents])
    write_jsonl(chunks_path, [chunk.model_dump() for chunk in chunks])

    tokenized_corpus = [tokenize(chunk.retrieval_text) for chunk in chunks]
    bm25 = BM25Okapi(tokenized_corpus)
    with bm25_path.open("wb") as file:
        pickle.dump({"bm25": bm25, "chunks": [chunk.model_dump() for chunk in chunks]}, file)

    previous_manifest = {}
    if manifest_path.exists():
        try:
            previous_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous_manifest = {}

    manifest = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "markdown_dir": markdown_dir.relative_to(root_dir).as_posix(),
        "corpus_hash": _corpus_hash(markdown_files, root_dir),
        "chunking_version": CHUNKING_VERSION,
        "documents": len(documents),
        "chunks": len(chunks),
        "retriever": "BM25Okapi",
    }
    previous_dense = previous_manifest.get("dense")
    if (
        not invalidate_dense
        and isinstance(previous_dense, dict)
        and previous_dense.get("corpus_hash") == manifest["corpus_hash"]
        and previous_dense.get("chunking_version") == manifest["chunking_version"]
        and previous_dense.get("chunks") == manifest["chunks"]
    ):
        manifest["dense"] = previous_dense
    if not invalidate_dense and "runtime" in previous_manifest:
        manifest["runtime"] = previous_manifest["runtime"]

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if invalidate_dense and index_dir.resolve() == INDEX_DIR.resolve() and QDRANT_READY_FILE.exists():
        QDRANT_READY_FILE.unlink()
    return manifest


def main() -> None:
    # Configure these values in .env or rag_luat_gt/config.py.
    manifest = build_index(MARKDOWN_DIR.resolve(), ROOT_DIR.resolve())
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
