from __future__ import annotations

import os
import re
from dataclasses import dataclass
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
RAG_LOCAL_LLM_BASE_URL = os.getenv("RAG_LOCAL_LLM_BASE_URL", "http://127.0.0.1:8080/v1").rstrip("/")
RAG_LOCAL_LLM_API_KEY = os.getenv("RAG_LOCAL_LLM_API_KEY", "local")
RAG_LOCAL_LLM_MODEL = os.getenv("RAG_LOCAL_LLM_MODEL", "qwen3.5-4b-q4_k_m")


def _is_local_llm_provider(provider: str) -> bool:
    return provider.strip().lower().replace("-", "_") in {"local", "local_openai", "qwen", "qwen_local"}


RAG_LLM_MODEL = os.getenv(
    "RAG_LLM_MODEL",
    RAG_LOCAL_LLM_MODEL if _is_local_llm_provider(RAG_LLM_PROVIDER) else OPENAI_MODEL,
)
RAG_OPENAI_TEMPERATURE = float(os.getenv("RAG_OPENAI_TEMPERATURE", "0"))
RAG_OPENAI_MAX_TOKENS = int(os.getenv("RAG_OPENAI_MAX_TOKENS", "1200"))
RAG_PRERAG_PROVIDER = os.getenv("RAG_PRERAG_PROVIDER", "rule").lower()
RAG_PRERAG_MODEL = os.getenv(
    "RAG_PRERAG_MODEL",
    RAG_LOCAL_LLM_MODEL if _is_local_llm_provider(RAG_PRERAG_PROVIDER) else OPENAI_MODEL,
)
RAG_PRERAG_TEMPERATURE = float(os.getenv("RAG_PRERAG_TEMPERATURE", "0"))
RAG_PRERAG_MAX_TOKENS = int(os.getenv("RAG_PRERAG_MAX_TOKENS", "900"))
RAG_QUERY_ROUTER_PROVIDER = os.getenv("RAG_QUERY_ROUTER_PROVIDER", RAG_PRERAG_PROVIDER).lower()
RAG_QUERY_ROUTER_MODEL = os.getenv(
    "RAG_QUERY_ROUTER_MODEL",
    RAG_LOCAL_LLM_MODEL if _is_local_llm_provider(RAG_QUERY_ROUTER_PROVIDER) else OPENAI_MODEL,
)
RAG_QUERY_ROUTER_TEMPERATURE = float(os.getenv("RAG_QUERY_ROUTER_TEMPERATURE", "0"))
RAG_QUERY_ROUTER_MAX_TOKENS = int(os.getenv("RAG_QUERY_ROUTER_MAX_TOKENS", "700"))
RAG_SANCTION_LLM_PROVIDER = os.getenv("RAG_SANCTION_LLM_PROVIDER", RAG_LLM_PROVIDER).lower()
RAG_SANCTION_LLM_MODEL = os.getenv(
    "RAG_SANCTION_LLM_MODEL",
    RAG_LOCAL_LLM_MODEL if _is_local_llm_provider(RAG_SANCTION_LLM_PROVIDER) else OPENAI_MODEL,
)
RAG_SANCTION_LLM_TEMPERATURE = float(os.getenv("RAG_SANCTION_LLM_TEMPERATURE", "0.2"))
RAG_SANCTION_LLM_MAX_TOKENS = int(os.getenv("RAG_SANCTION_LLM_MAX_TOKENS", "900"))

RAG_DENSE_ENABLED = os.getenv("RAG_DENSE_ENABLED", "false").lower() == "true"
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "traffic_law_chunks")
QDRANT_PATH = Path(os.getenv("QDRANT_PATH", ROOT_DIR / "data" / "qdrant"))
QDRANT_URL = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")

EMBEDDING_PRESETS = {
    "bge_m3": {
        "model": "BAAI/bge-m3",
        "vector_size": 1024,
        "query_instruction": "",
        "document_instruction": "",
    },
    "qwen3_0_6b": {
        "model": "Qwen/Qwen3-Embedding-0.6B",
        "vector_size": 1024,
        "query_instruction": "Instruct: Retrieve passages from Vietnamese traffic law documents that answer the legal question.\nQuery: ",
        "document_instruction": "",
    },
}


@dataclass(frozen=True)
class EmbeddingSettings:
    preset: str
    model: str
    vector_size: int
    query_instruction: str
    document_instruction: str
    collection: str
    ready_file: Path


def _split_csv(value: str) -> list[str]:
    return [item.strip().lower() for item in value.split(",") if item.strip()]


def normalize_embedding_preset(value: str | None) -> str:
    preset = (value or RAG_EMBEDDING_PRESET).strip().lower()
    return preset if preset in EMBEDDING_PRESETS else RAG_EMBEDDING_PRESET


def embedding_collection_for_preset(preset: str | None) -> str:
    normalized = normalize_embedding_preset(preset)
    suffix = re.sub(r"[^a-z0-9]+", "_", normalized.lower()).strip("_")
    return f"{QDRANT_COLLECTION}_{suffix}"


def embedding_settings_for_preset(preset: str | None = None, *, allow_model_override: bool = False) -> EmbeddingSettings:
    normalized = normalize_embedding_preset(preset)
    preset_config = EMBEDDING_PRESETS[normalized]
    model_override = os.getenv("RAG_EMBEDDING_MODEL") if allow_model_override else None
    model = model_override or preset_config["model"]
    vector_size = int(os.getenv("RAG_EMBEDDING_VECTOR_SIZE") or str(preset_config["vector_size"]))
    query_instruction = (
        os.getenv("RAG_EMBEDDING_QUERY_INSTRUCTION", preset_config["query_instruction"])
        or preset_config["query_instruction"]
    )
    document_instruction = (
        os.getenv("RAG_EMBEDDING_DOCUMENT_INSTRUCTION", preset_config["document_instruction"])
        or preset_config["document_instruction"]
    )
    collection = embedding_collection_for_preset(normalized)
    return EmbeddingSettings(
        preset=normalized,
        model=model,
        vector_size=vector_size,
        query_instruction=query_instruction,
        document_instruction=document_instruction,
        collection=collection,
        ready_file=INDEX_DIR / f"{collection}.ready",
    )


_REQUESTED_EMBEDDING_PRESET = os.getenv("RAG_EMBEDDING_PRESET", "bge_m3").lower()
RAG_EMBEDDING_PRESET = _REQUESTED_EMBEDDING_PRESET if _REQUESTED_EMBEDDING_PRESET in EMBEDDING_PRESETS else "bge_m3"
RAG_EMBEDDING_AVAILABLE_PRESETS = [
    preset for preset in _split_csv(os.getenv("RAG_EMBEDDING_AVAILABLE_PRESETS", "bge_m3,qwen3_0_6b")) if preset in EMBEDDING_PRESETS
] or [RAG_EMBEDDING_PRESET]
RAG_BUILD_EMBEDDING_PRESETS = [
    preset for preset in _split_csv(os.getenv("RAG_BUILD_EMBEDDING_PRESETS", ",".join(RAG_EMBEDDING_AVAILABLE_PRESETS))) if preset in EMBEDDING_PRESETS
] or [RAG_EMBEDDING_PRESET]
_EMBEDDING_SETTINGS = embedding_settings_for_preset(RAG_EMBEDDING_PRESET, allow_model_override=True)
RAG_EMBEDDING_MODEL = _EMBEDDING_SETTINGS.model
RAG_EMBEDDING_DEVICE = os.getenv("RAG_EMBEDDING_DEVICE", "cpu")
RAG_EMBEDDING_BATCH_SIZE = int(os.getenv("RAG_EMBEDDING_BATCH_SIZE", "8"))
RAG_EMBEDDING_VECTOR_SIZE = _EMBEDDING_SETTINGS.vector_size
RAG_EMBEDDING_LOCAL_FILES_ONLY = os.getenv("RAG_EMBEDDING_LOCAL_FILES_ONLY", "false").lower() == "true"
RAG_EMBEDDING_PROGRESS = os.getenv("RAG_EMBEDDING_PROGRESS", "true").lower() == "true"
RAG_EMBEDDING_QUERY_INSTRUCTION = _EMBEDDING_SETTINGS.query_instruction
RAG_EMBEDDING_DOCUMENT_INSTRUCTION = _EMBEDDING_SETTINGS.document_instruction
RAG_EMBEDDING_TRUST_REMOTE_CODE = os.getenv("RAG_EMBEDDING_TRUST_REMOTE_CODE", "false").lower() == "true"
RAG_RERANKER_ENABLED = os.getenv("RAG_RERANKER_ENABLED", "false").lower() == "true"
RAG_RERANKER_MODEL = os.getenv("RAG_RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
RAG_RERANKER_DEVICE = os.getenv("RAG_RERANKER_DEVICE", "cpu")
RAG_RERANKER_TOP_N = int(os.getenv("RAG_RERANKER_TOP_N", "40"))
RAG_RERANKER_LOCAL_FILES_ONLY = os.getenv("RAG_RERANKER_LOCAL_FILES_ONLY", "false").lower() == "true"
QDRANT_READY_FILE = _EMBEDDING_SETTINGS.ready_file

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
