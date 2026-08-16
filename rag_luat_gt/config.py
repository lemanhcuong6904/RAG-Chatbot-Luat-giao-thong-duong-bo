from __future__ import annotations

import os
from pathlib import Path


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_env_file(Path(".env").resolve())

ROOT_DIR = Path(os.getenv("RAG_ROOT_DIR", ".")).resolve()
MARKDOWN_DIR = Path(os.getenv("RAG_MARKDOWN_DIR", ROOT_DIR / "data" / "markdown"))
INDEX_DIR = Path(os.getenv("RAG_INDEX_DIR", ROOT_DIR / "data" / "index"))
CHUNKS_PATH = INDEX_DIR / "chunks.jsonl"
DOCUMENTS_PATH = INDEX_DIR / "documents.jsonl"
BM25_PATH = INDEX_DIR / "bm25.pkl"
MANIFEST_PATH = INDEX_DIR / "manifest.json"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
RAG_LLM_PROVIDER = os.getenv("RAG_LLM_PROVIDER", "extractive").lower()
RAG_REQUIRE_LLM = os.getenv("RAG_REQUIRE_LLM", "false").lower() == "true"
RAG_OPENAI_TEMPERATURE = float(os.getenv("RAG_OPENAI_TEMPERATURE", "0"))
RAG_OPENAI_MAX_TOKENS = int(os.getenv("RAG_OPENAI_MAX_TOKENS", "1200"))
RAG_PRERAG_PROVIDER = os.getenv("RAG_PRERAG_PROVIDER", "rule").lower()
RAG_PRERAG_MODEL = os.getenv("RAG_PRERAG_MODEL", OPENAI_MODEL)
RAG_PRERAG_TEMPERATURE = float(os.getenv("RAG_PRERAG_TEMPERATURE", "0"))
RAG_PRERAG_MAX_TOKENS = int(os.getenv("RAG_PRERAG_MAX_TOKENS", "900"))
RAG_QUERY_ROUTER_PROVIDER = os.getenv("RAG_QUERY_ROUTER_PROVIDER", RAG_PRERAG_PROVIDER).lower()
RAG_QUERY_ROUTER_MODEL = os.getenv("RAG_QUERY_ROUTER_MODEL", OPENAI_MODEL)
RAG_QUERY_ROUTER_TEMPERATURE = float(os.getenv("RAG_QUERY_ROUTER_TEMPERATURE", "0"))
RAG_QUERY_ROUTER_MAX_TOKENS = int(os.getenv("RAG_QUERY_ROUTER_MAX_TOKENS", "700"))
RAG_SANCTION_LLM_PROVIDER = os.getenv("RAG_SANCTION_LLM_PROVIDER", RAG_LLM_PROVIDER).lower()
RAG_SANCTION_LLM_MODEL = os.getenv("RAG_SANCTION_LLM_MODEL", OPENAI_MODEL)
RAG_SANCTION_LLM_TEMPERATURE = float(os.getenv("RAG_SANCTION_LLM_TEMPERATURE", "0.2"))
RAG_SANCTION_LLM_MAX_TOKENS = int(os.getenv("RAG_SANCTION_LLM_MAX_TOKENS", "900"))

RAG_DENSE_ENABLED = os.getenv("RAG_DENSE_ENABLED", "false").lower() == "true"
RAG_EMBEDDING_MODEL = os.getenv("RAG_EMBEDDING_MODEL", "BAAI/bge-m3")
RAG_EMBEDDING_DEVICE = os.getenv("RAG_EMBEDDING_DEVICE", "cpu")
RAG_EMBEDDING_BATCH_SIZE = int(os.getenv("RAG_EMBEDDING_BATCH_SIZE", "8"))
RAG_EMBEDDING_VECTOR_SIZE = int(os.getenv("RAG_EMBEDDING_VECTOR_SIZE", "1024"))
RAG_EMBEDDING_LOCAL_FILES_ONLY = os.getenv("RAG_EMBEDDING_LOCAL_FILES_ONLY", "false").lower() == "true"
RAG_EMBEDDING_PROGRESS = os.getenv("RAG_EMBEDDING_PROGRESS", "true").lower() == "true"
RAG_RERANKER_ENABLED = os.getenv("RAG_RERANKER_ENABLED", "false").lower() == "true"
RAG_RERANKER_MODEL = os.getenv("RAG_RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
RAG_RERANKER_DEVICE = os.getenv("RAG_RERANKER_DEVICE", "cpu")
RAG_RERANKER_TOP_N = int(os.getenv("RAG_RERANKER_TOP_N", "40"))
RAG_RERANKER_LOCAL_FILES_ONLY = os.getenv("RAG_RERANKER_LOCAL_FILES_ONLY", "false").lower() == "true"
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "traffic_law_chunks")
QDRANT_PATH = Path(os.getenv("QDRANT_PATH", ROOT_DIR / "data" / "qdrant"))
QDRANT_URL = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
QDRANT_READY_FILE = INDEX_DIR / f"{QDRANT_COLLECTION}.ready"

SANCTION_DB_PATH = Path(
    os.getenv(
        "SANCTION_DB_PATH",
        ROOT_DIR / "structured_sanction_layer" / "structured_sanction_layer" / "sanctions.sqlite",
    )
)
RAG_STRUCTURED_LOOKUP_ENABLED = os.getenv("RAG_STRUCTURED_LOOKUP_ENABLED", "true").lower() == "true"
RAG_STRUCTURED_FACT_ENABLED = (
    RAG_STRUCTURED_LOOKUP_ENABLED and os.getenv("RAG_STRUCTURED_FACT_ENABLED", "true").lower() == "true"
)
RAG_STRUCTURED_SANCTION_ENABLED = (
    RAG_STRUCTURED_LOOKUP_ENABLED
    and os.getenv("RAG_STRUCTURED_SANCTION_ENABLED", os.getenv("SANCTION_ENABLED", "true")).lower() == "true"
)
SANCTION_ENABLED = RAG_STRUCTURED_SANCTION_ENABLED
