from __future__ import annotations

import json
import pickle
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
    ROOT_DIR,
)
from rag_luat_gt.ingestion.legal_parser import parse_chunks
from rag_luat_gt.ingestion.markdown import read_markdown
from rag_luat_gt.ingestion.normalizer import normalize_document
from rag_luat_gt.text import tokenize


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_index(markdown_dir: Path, root_dir: Path, index_dir: Path = INDEX_DIR) -> dict:
    documents = []
    chunks = []

    for markdown_file in sorted(markdown_dir.rglob("*.md")):
        source_file = markdown_file.relative_to(root_dir).as_posix()
        metadata, body = read_markdown(markdown_file)
        document = normalize_document(metadata, source_file)
        documents.append(document)
        chunks.extend(parse_chunks(document, body, source_file))

    index_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(DOCUMENTS_PATH, [document.model_dump() for document in documents])
    write_jsonl(CHUNKS_PATH, [chunk.model_dump() for chunk in chunks])

    tokenized_corpus = [tokenize(chunk.retrieval_text) for chunk in chunks]
    bm25 = BM25Okapi(tokenized_corpus)
    with BM25_PATH.open("wb") as file:
        pickle.dump({"bm25": bm25, "chunks": [chunk.model_dump() for chunk in chunks]}, file)

    manifest = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "markdown_dir": markdown_dir.relative_to(root_dir).as_posix(),
        "documents": len(documents),
        "chunks": len(chunks),
        "retriever": "BM25Okapi",
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    # Configure these values in .env or rag_luat_gt/config.py.
    manifest = build_index(MARKDOWN_DIR.resolve(), ROOT_DIR.resolve())
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
