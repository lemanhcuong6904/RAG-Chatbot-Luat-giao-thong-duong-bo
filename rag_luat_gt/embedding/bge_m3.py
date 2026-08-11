from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from rag_luat_gt.config import (
    RAG_EMBEDDING_BATCH_SIZE,
    RAG_EMBEDDING_DEVICE,
    RAG_EMBEDDING_LOCAL_FILES_ONLY,
    RAG_EMBEDDING_MODEL,
)


class BGEM3Embedder:
    def __init__(
        self,
        model_name: str = RAG_EMBEDDING_MODEL,
        device: str = RAG_EMBEDDING_DEVICE,
        batch_size: int = RAG_EMBEDDING_BATCH_SIZE,
        local_files_only: bool = RAG_EMBEDDING_LOCAL_FILES_ONLY,
    ) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.batch_size = batch_size
        self.model = SentenceTransformer(
            model_name,
            device=device,
            local_files_only=local_files_only,
            model_kwargs={"use_safetensors": True},
        )

    def encode(self, texts: Iterable[str]) -> list[list[float]]:
        embeddings = self.model.encode(
            list(texts),
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=True,
        )
        array = np.asarray(embeddings, dtype=np.float32)
        return array.tolist()

    def encode_query(self, query: str) -> list[float]:
        return self.encode([query])[0]
