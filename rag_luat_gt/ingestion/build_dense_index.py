from __future__ import annotations

import json
from datetime import datetime, timezone

from rag_luat_gt.config import (
    MANIFEST_PATH,
    RAG_BUILD_EMBEDDING_PRESETS,
    RAG_EMBEDDING_BATCH_SIZE,
    RAG_EMBEDDING_PRESET,
    embedding_settings_for_preset,
)
from rag_luat_gt.embedding.bge_m3 import BGEM3Embedder
from rag_luat_gt.retrieval.qdrant_store import (
    load_chunks,
    qdrant_client,
    recreate_collection,
    upsert_chunks,
)


BATCHES_PER_UPSERT = 4
BUILD_EMBEDDING_PRESETS = RAG_BUILD_EMBEDDING_PRESETS


def _load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def _write_manifest(manifest: dict) -> None:
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_dense_index(preset: str | None = None, *, allow_model_override: bool = False) -> dict:
    settings = embedding_settings_for_preset(preset or RAG_EMBEDDING_PRESET, allow_model_override=allow_model_override)
    chunks = load_chunks()
    client = qdrant_client()
    try:
        recreate_collection(client, collection_name=settings.collection, vector_size=settings.vector_size)

        embedder = BGEM3Embedder(
            model_name=settings.model,
            query_instruction=settings.query_instruction,
            document_instruction=settings.document_instruction,
        )
        batch_size = RAG_EMBEDDING_BATCH_SIZE * BATCHES_PER_UPSERT
        indexed = 0

        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            vectors = embedder.encode_documents(chunk.retrieval_text for chunk in batch)
            upsert_chunks(client, batch, vectors, collection_name=settings.collection)
            indexed += len(batch)
            print(f"[{settings.preset}] Indexed dense vectors: {indexed}/{len(chunks)}")

        manifest = _load_manifest()
        dense_manifest = {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "embedding_preset": settings.preset,
            "embedding_model": settings.model,
            "embedding_vector_size": settings.vector_size,
            "embedding_query_instruction": settings.query_instruction,
            "embedding_document_instruction": settings.document_instruction,
            "collection": settings.collection,
            "chunks": indexed,
            "corpus_hash": manifest.get("corpus_hash"),
            "chunking_version": manifest.get("chunking_version"),
        }
        dense_indexes = manifest.get("dense_indexes") if isinstance(manifest.get("dense_indexes"), dict) else {}
        dense_indexes[settings.preset] = dense_manifest
        manifest["dense_indexes"] = dense_indexes
        if settings.preset == RAG_EMBEDDING_PRESET or "dense" not in manifest:
            manifest["dense"] = dense_manifest
        _write_manifest(manifest)
        settings.ready_file.write_text(json.dumps(dense_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return dense_manifest
    finally:
        client.close()


def build_dense_indexes(presets: list[str] | None = None) -> dict[str, dict]:
    selected_presets = presets or BUILD_EMBEDDING_PRESETS
    results: dict[str, dict] = {}
    for preset in selected_presets:
        results[preset] = build_dense_index(preset, allow_model_override=len(selected_presets) == 1)
    return results


def main() -> None:
    # Configure BUILD_EMBEDDING_PRESETS/RAG_BUILD_EMBEDDING_PRESETS in this file or .env.
    print(json.dumps(build_dense_indexes(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
