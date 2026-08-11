from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL

from qdrant_client import QdrantClient
from qdrant_client.http import models

from rag_luat_gt.config import (
    CHUNKS_PATH,
    QDRANT_API_KEY,
    QDRANT_COLLECTION,
    QDRANT_PATH,
    QDRANT_URL,
    RAG_EMBEDDING_VECTOR_SIZE,
)
from rag_luat_gt.schemas import Chunk


def load_chunks(path: Path = CHUNKS_PATH) -> list[Chunk]:
    with path.open("r", encoding="utf-8") as file:
        return [Chunk(**json.loads(line)) for line in file if line.strip()]


def qdrant_client() -> QdrantClient:
    if QDRANT_URL:
        return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)
    QDRANT_PATH.mkdir(parents=True, exist_ok=True)
    return QdrantClient(path=str(QDRANT_PATH))


def point_id(chunk_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, chunk_id))


def recreate_collection(client: QdrantClient, collection_name: str = QDRANT_COLLECTION) -> None:
    existing = {item.name for item in client.get_collections().collections}
    if collection_name in existing:
        client.delete_collection(collection_name=collection_name)
    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(
            size=RAG_EMBEDDING_VECTOR_SIZE,
            distance=models.Distance.COSINE,
        ),
    )
    for field in ["document_number", "article", "clause", "point", "coverage_status", "chunk_type"]:
        client.create_payload_index(
            collection_name=collection_name,
            field_name=field,
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
    for field in ["valid_from", "valid_to"]:
        client.create_payload_index(
            collection_name=collection_name,
            field_name=field,
            field_schema=models.PayloadSchemaType.DATETIME,
        )


def chunk_payload(chunk: Chunk) -> dict:
    payload = chunk.model_dump()
    payload["text_preview"] = chunk.text[:500]
    return payload


def upsert_chunks(
    client: QdrantClient,
    chunks: list[Chunk],
    vectors: list[list[float]],
    collection_name: str = QDRANT_COLLECTION,
) -> None:
    points = [
        models.PointStruct(
            id=point_id(chunk.chunk_id),
            vector=vector,
            payload=chunk_payload(chunk),
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    client.upsert(collection_name=collection_name, points=points)
