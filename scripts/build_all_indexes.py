from __future__ import annotations

import json
from datetime import datetime, timezone

from rag_luat_gt.config import MANIFEST_PATH, MARKDOWN_DIR, RAG_DENSE_ENABLED, ROOT_DIR, SANCTION_DB_PATH
from rag_luat_gt.ingestion.build_index import build_index


def build_all_indexes() -> dict:
    bm25_manifest = build_index(MARKDOWN_DIR.resolve(), ROOT_DIR.resolve())
    dense_manifest = None
    if RAG_DENSE_ENABLED:
        from rag_luat_gt.ingestion.build_dense_index import build_dense_indexes

        dense_manifest = build_dense_indexes()

    runtime_manifest = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "corpus_hash": bm25_manifest.get("corpus_hash"),
        "chunking_version": bm25_manifest.get("chunking_version"),
        "bm25": {
            "ready": True,
            "chunks": bm25_manifest.get("chunks", 0),
            "documents": bm25_manifest.get("documents", 0),
        },
        "dense": {
            "ready": bool(dense_manifest),
            "indexes": dense_manifest or {},
        },
        "sanction": {
            "ready": SANCTION_DB_PATH.exists(),
            "db_path": str(SANCTION_DB_PATH),
        },
    }

    manifest = {}
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["runtime"] = runtime_manifest
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return runtime_manifest


def main() -> None:
    print(json.dumps(build_all_indexes(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
