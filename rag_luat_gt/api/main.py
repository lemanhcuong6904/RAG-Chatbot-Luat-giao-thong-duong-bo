from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException

from rag_luat_gt.config import CHUNKS_PATH, DOCUMENTS_PATH, MANIFEST_PATH, SANCTION_DB_PATH, SANCTION_ENABLED
from rag_luat_gt.schemas import ChatRequest
from rag_luat_gt.service import RAGService


app = FastAPI(title="RAG Chatbot Luat Giao Thong", version="0.1.0")
service = RAGService()
service.warm_up()


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


@app.get("/api/v1/health")
def health() -> dict:
    manifest = {}
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {
        "status": "ok",
        "index": manifest,
        "pipeline": {
            "bm25_active": service.retriever.bm25.bm25 is not None,
            "dense_active": service.retriever.dense is not None,
            "dense_error": service.retriever.dense_error,
            "reranker_active": service.retriever.reranker is not None,
            "reranker_error": service.retriever.reranker_error,
            "warmup_status": service.warmup_status,
            "warmup_error": service.warmup_error,
        },
        "sanctions": {
            "enabled": SANCTION_ENABLED,
            "db_path": str(SANCTION_DB_PATH),
            "available": SANCTION_DB_PATH.exists(),
        },
    }


@app.post("/api/v1/chat")
def chat(request: ChatRequest) -> dict:
    return service.answer(request).model_dump()


@app.get("/api/v1/documents")
def documents() -> list[dict]:
    return _load_jsonl(DOCUMENTS_PATH)


@app.get("/api/v1/documents/{document_id}")
def document(document_id: str) -> dict:
    for row in _load_jsonl(DOCUMENTS_PATH):
        if row["document_id"] == document_id:
            return row
    raise HTTPException(status_code=404, detail="Document not found")


@app.get("/api/v1/chunks/{chunk_id}")
def chunk(chunk_id: str) -> dict:
    for row in _load_jsonl(CHUNKS_PATH):
        if row["chunk_id"] == chunk_id:
            return row
    raise HTTPException(status_code=404, detail="Chunk not found")


@app.post("/api/v1/retrieval/search")
def retrieval_search(request: ChatRequest) -> dict:
    request.debug = True
    response = service.answer(request)
    return response.model_dump()
