from __future__ import annotations

import json
import base64
import re
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from rag_luat_gt.config import (
    CHUNKS_PATH,
    DOCUMENTS_PATH,
    MANIFEST_PATH,
    RAG_LLM_MODEL,
    RAG_LLM_PROVIDER,
    RAG_LOCAL_LLM_BASE_URL,
    RAG_PRERAG_MODEL,
    RAG_PRERAG_PROVIDER,
    RAG_QUERY_ROUTER_MODEL,
    RAG_QUERY_ROUTER_PROVIDER,
    RAG_EMBEDDING_AVAILABLE_PRESETS,
    RAG_EMBEDDING_MODEL,
    RAG_EMBEDDING_PRESET,
    RAG_EMBEDDING_VECTOR_SIZE,
    RAG_STRUCTURED_FACT_ENABLED,
    RAG_STRUCTURED_LOOKUP_ENABLED,
    RAG_STRUCTURED_SANCTION_ENABLED,
    ROOT_DIR,
    SANCTION_DB_PATH,
    SANCTION_ENABLED,
)
from rag_luat_gt.schemas import ChatRequest
from rag_luat_gt.service import RAGService


app = FastAPI(title="RAG Chatbot Luat Giao Thong", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
service = RAGService()
service.warm_up()


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


RAW_DIR = ROOT_DIR / "data" / "raw"
ADMIN_DOCUMENTS_PATH = ROOT_DIR / "data" / "index" / "admin_documents.jsonl"
ADMIN_UPLOAD_DIR = RAW_DIR / "_admin_uploads"


class AdminDocumentCreate(BaseModel):
    document_number: str
    title: str
    document_type: str | None = None
    issuing_authority: str | None = None
    issue_date: str | None = None
    effective_from: str | None = None
    abstract: str | None = None
    pdf_filename: str | None = None
    pdf_base64: str | None = None


def _all_document_rows() -> list[dict]:
    return _load_jsonl(DOCUMENTS_PATH) + _load_jsonl(ADMIN_DOCUMENTS_PATH)


def _compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _safe_filename(value: str) -> str:
    name = Path(value).name or "document.pdf"
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).stem).strip("._") or "document"
    return f"{stem}.pdf"


def _document_pdf_path(row: dict) -> Path | None:
    candidates: list[str] = []
    raw_pdf_path = row.get("raw_pdf_path")
    if isinstance(raw_pdf_path, str):
        candidates.append(raw_pdf_path)
    source_original = row.get("source_original")
    if isinstance(source_original, str):
        candidates.append(source_original)
    elif isinstance(source_original, list):
        candidates.extend(str(item) for item in source_original)
    metadata = row.get("metadata") or {}
    for key in ["file_nguon", "source_original"]:
        value = metadata.get(key)
        if isinstance(value, str):
            candidates.append(value)

    for value in candidates:
        path = Path(value)
        if not path.is_absolute():
            path = ROOT_DIR / value
        if not path.exists():
            path = RAW_DIR / value
        if path.exists() and path.suffix.lower() == ".pdf":
            return path
        matches = list(RAW_DIR.rglob(Path(value).name))
        for match in matches:
            if match.suffix.lower() == ".pdf":
                return match

    document_number = str(row.get("document_number") or "")
    number_dash = document_number.replace("/", "-").lower()
    compact_number = _compact(document_number)
    if not document_number:
        return None
    for match in RAW_DIR.rglob("*.pdf"):
        haystack = f"{match.name} {match.parent.name}".lower()
        compact_haystack = _compact(haystack)
        if number_dash in haystack or compact_number in compact_haystack:
            return match
    return None


def _document_payload(row: dict) -> dict:
    metadata = row.get("metadata") or {}
    pdf_path = _document_pdf_path(row)
    payload = dict(row)
    payload["abstract"] = row.get("abstract") or metadata.get("trich_yeu") or ""
    payload["issue_date"] = row.get("issue_date") or metadata.get("ngay_ban_hanh")
    payload["document_type"] = row.get("document_type") or metadata.get("loai_van_ban")
    payload["raw_pdf_url"] = f"/api/v1/documents/{row['document_id']}/pdf" if pdf_path else None
    return payload


def _save_admin_pdf(document_id: str, payload: AdminDocumentCreate) -> str | None:
    if not payload.pdf_base64:
        return None
    try:
        encoded = payload.pdf_base64.split(",", 1)[-1]
        data = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid PDF base64") from exc
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Uploaded file is not a PDF")
    ADMIN_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{document_id}_{_safe_filename(payload.pdf_filename or 'document.pdf')}"
    path = ADMIN_UPLOAD_DIR / filename
    path.write_bytes(data)
    return str(path.relative_to(ROOT_DIR)).replace("\\", "/")


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
            "embedding_preset": RAG_EMBEDDING_PRESET,
            "embedding_available_presets": RAG_EMBEDDING_AVAILABLE_PRESETS,
            "embedding_model": RAG_EMBEDDING_MODEL,
            "embedding_vector_size": RAG_EMBEDDING_VECTOR_SIZE,
            "dense_indexes": service.retriever.dense_status_by_preset(),
            "reranker_active": service.retriever.reranker is not None,
            "reranker_error": service.retriever.reranker_error,
            "llm_provider": RAG_LLM_PROVIDER,
            "llm_model": RAG_LLM_MODEL,
            "local_llm_base_url": RAG_LOCAL_LLM_BASE_URL,
            "pre_rag_provider": RAG_PRERAG_PROVIDER,
            "pre_rag_model": RAG_PRERAG_MODEL,
            "query_router_provider": RAG_QUERY_ROUTER_PROVIDER,
            "query_router_model": RAG_QUERY_ROUTER_MODEL,
            "pre_rag_modes": ["rule", "llm", "optimized"],
            "warmup_status": service.warmup_status,
            "warmup_error": service.warmup_error,
        },
        "sanctions": {
            "enabled": SANCTION_ENABLED,
            "structured_sanction_enabled": RAG_STRUCTURED_SANCTION_ENABLED,
            "env_key": "RAG_STRUCTURED_SANCTION_ENABLED",
            "db_path": str(SANCTION_DB_PATH),
            "available": SANCTION_DB_PATH.exists(),
        },
        "structured_lookup": {
            "enabled": RAG_STRUCTURED_LOOKUP_ENABLED,
            "fact_enabled": RAG_STRUCTURED_FACT_ENABLED,
            "sanction_enabled": RAG_STRUCTURED_SANCTION_ENABLED,
            "env_key": "RAG_STRUCTURED_LOOKUP_ENABLED",
        },
    }


@app.post("/api/v1/chat")
def chat(request: ChatRequest) -> dict:
    return service.answer(request).model_dump()


@app.get("/api/v1/documents")
def documents() -> list[dict]:
    return [_document_payload(row) for row in _all_document_rows()]


@app.get("/api/v1/documents/{document_id}")
def document(document_id: str) -> dict:
    for row in _all_document_rows():
        if row["document_id"] == document_id:
            return _document_payload(row)
    raise HTTPException(status_code=404, detail="Document not found")


@app.get("/api/v1/documents/{document_id}/pdf")
def document_pdf(document_id: str):
    for row in _all_document_rows():
        if row["document_id"] != document_id:
            continue
        pdf_path = _document_pdf_path(row)
        if not pdf_path:
            raise HTTPException(status_code=404, detail="PDF not found")
        try:
            pdf_path.resolve().relative_to(RAW_DIR.resolve())
        except ValueError as exc:
            raise HTTPException(status_code=403, detail="Invalid PDF path") from exc
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=pdf_path.name,
            content_disposition_type="inline",
        )
    raise HTTPException(status_code=404, detail="Document not found")


@app.post("/api/v1/admin/documents")
def create_admin_document(payload: AdminDocumentCreate) -> dict:
    document_id = f"ADMIN_{uuid.uuid4().hex}"
    raw_pdf_path = _save_admin_pdf(document_id, payload)
    row = {
        "document_id": document_id,
        "document_number": payload.document_number.strip(),
        "title": payload.title.strip(),
        "document_type": (payload.document_type or "").strip() or None,
        "issuing_authority": (payload.issuing_authority or "").strip() or None,
        "issue_date": (payload.issue_date or "").strip() or None,
        "effective_from": (payload.effective_from or "").strip() or None,
        "effective_to": None,
        "abstract": (payload.abstract or "").strip(),
        "raw_pdf_path": raw_pdf_path,
        "source_markdown": "",
        "source_original": payload.pdf_filename,
        "metadata": {
            "trich_yeu": (payload.abstract or "").strip(),
            "ngay_ban_hanh": (payload.issue_date or "").strip(),
            "loai_van_ban": (payload.document_type or "").strip(),
        },
    }
    ADMIN_DOCUMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ADMIN_DOCUMENTS_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(row, ensure_ascii=False) + "\n")
    return _document_payload(row)


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
