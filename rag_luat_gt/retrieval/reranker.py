from __future__ import annotations

from rag_luat_gt.config import RAG_RERANKER_LOCAL_FILES_ONLY, RAG_RERANKER_MODEL
from rag_luat_gt.schemas import Chunk, ParsedQuery


class BGEReranker:
    def __init__(self) -> None:
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(
            RAG_RERANKER_MODEL,
            automodel_args={"local_files_only": RAG_RERANKER_LOCAL_FILES_ONLY},
            tokenizer_args={"local_files_only": RAG_RERANKER_LOCAL_FILES_ONLY},
        )

    def rerank(
        self,
        parsed: ParsedQuery,
        results: list[tuple[Chunk, float]],
        top_n: int,
    ) -> list[tuple[Chunk, float]]:
        if not results:
            return []
        candidates = results[:top_n]
        pairs = [(parsed.query, chunk.retrieval_text) for chunk, _score in candidates]
        scores = self.model.predict(pairs)
        rescored = [
            (chunk, float(score))
            for (chunk, _old_score), score in zip(candidates, scores, strict=True)
        ]
        return sorted(rescored, key=lambda item: item[1], reverse=True)
