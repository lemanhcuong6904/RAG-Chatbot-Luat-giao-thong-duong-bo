from __future__ import annotations

import json
from datetime import datetime, timezone

from rag_luat_gt.config import (
    MANIFEST_PATH,
    QDRANT_COLLECTION,
    QDRANT_READY_FILE,
    RAG_EMBEDDING_BATCH_SIZE,
    RAG_EMBEDDING_MODEL,
)
from rag_luat_gt.embedding.bge_m3 import BGEM3Embedder
from rag_luat_gt.retrieval.qdrant_store import (
    load_chunks,
    qdrant_client,
    recreate_collection,
    upsert_chunks,
)


BATCHES_PER_UPSERT = 4


def build_dense_index() -> dict:
    chunks = load_chunks()
    client = qdrant_client()
    try:
        recreate_collection(client)

        embedder = BGEM3Embedder()
        batch_size = RAG_EMBEDDING_BATCH_SIZE * BATCHES_PER_UPSERT
        indexed = 0

        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            vectors = embedder.encode(chunk.retrieval_text for chunk in batch)
            upsert_chunks(client, batch, vectors)
            indexed += len(batch)
            print(f"Indexed dense vectors: {indexed}/{len(chunks)}")

        manifest = {}
        if MANIFEST_PATH.exists():
            manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        manifest["dense"] = {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "embedding_model": RAG_EMBEDDING_MODEL,
            "collection": QDRANT_COLLECTION,
            "chunks": indexed,
            "corpus_hash": manifest.get("corpus_hash"),
            "chunking_version": manifest.get("chunking_version"),
        }
        MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        QDRANT_READY_FILE.write_text(json.dumps(manifest["dense"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return manifest["dense"]
    finally:
        client.close()


def main() -> None:
    # Configure model, batch size, and Qdrant settings in .env.
    print(json.dumps(build_dense_index(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
