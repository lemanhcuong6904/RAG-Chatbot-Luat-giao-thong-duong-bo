from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from rag_luat_gt.config import (
    RAG_EMBEDDING_BATCH_SIZE,
    RAG_EMBEDDING_DOCUMENT_INSTRUCTION,
    RAG_EMBEDDING_DEVICE,
    RAG_EMBEDDING_LOCAL_FILES_ONLY,
    RAG_EMBEDDING_MODEL,
    RAG_EMBEDDING_PROGRESS,
    RAG_EMBEDDING_QUERY_INSTRUCTION,
    RAG_EMBEDDING_TRUST_REMOTE_CODE,
)


class SentenceTransformerEmbedder:
    def __init__(
        self,
        model_name: str = RAG_EMBEDDING_MODEL,
        device: str = RAG_EMBEDDING_DEVICE,
        batch_size: int = RAG_EMBEDDING_BATCH_SIZE,
        local_files_only: bool = RAG_EMBEDDING_LOCAL_FILES_ONLY,
        query_instruction: str = RAG_EMBEDDING_QUERY_INSTRUCTION,
        document_instruction: str = RAG_EMBEDDING_DOCUMENT_INSTRUCTION,
    ) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.batch_size = batch_size
        self.query_instruction = query_instruction
        self.document_instruction = document_instruction
        self.model = SentenceTransformer(
            model_name,
            device=device,
            local_files_only=local_files_only,
            model_kwargs={"use_safetensors": True, "trust_remote_code": RAG_EMBEDDING_TRUST_REMOTE_CODE},
        )

    @staticmethod
    def _apply_instruction(texts: Iterable[str], instruction: str) -> list[str]:
        items = list(texts)
        if not instruction:
            return items
        return [f"{instruction}{item}" for item in items]

    def _encode_texts(self, texts: Iterable[str]) -> list[list[float]]:
        embeddings = self.model.encode(
            list(texts),
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=RAG_EMBEDDING_PROGRESS,
        )
        array = np.asarray(embeddings, dtype=np.float32)
        return array.tolist()

    def encode(self, texts: Iterable[str]) -> list[list[float]]:
        return self.encode_documents(texts)

    def encode_documents(self, texts: Iterable[str]) -> list[list[float]]:
        return self._encode_texts(self._apply_instruction(texts, self.document_instruction))

    def encode_query(self, query: str) -> list[float]:
        return self._encode_texts(self._apply_instruction([query], self.query_instruction))[0]


class BGEM3Embedder(SentenceTransformerEmbedder):
    """Backward-compatible name for the configured local SentenceTransformer embedder."""
