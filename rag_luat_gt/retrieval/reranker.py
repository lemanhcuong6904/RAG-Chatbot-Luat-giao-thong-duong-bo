from __future__ import annotations

from rag_luat_gt.config import RAG_RERANKER_LOCAL_FILES_ONLY, RAG_RERANKER_MODEL
from rag_luat_gt.schemas import Chunk, ParsedQuery


def _reranker_query(parsed: ParsedQuery) -> str:
    if parsed.intent == "DRIVER_AGE_REQUIREMENT":
        return (
            "[INTENT=DRIVER_AGE_REQUIREMENT] "
            "Tìm quy định về điều kiện độ tuổi tối thiểu được phép/cấp giấy phép lái xe; "
            "không ưu tiên quy định xử phạt người chưa đủ tuổi. "
            + parsed.query
        )
    if parsed.intent == "LICENSE_POINT_BALANCE":
        return (
            "[INTENT=LICENSE_POINT_BALANCE] "
            "Tìm quy định trực tiếp về điểm của giấy phép lái xe, số điểm ban đầu/tối đa; "
            "ưu tiên Điều 58 Luật 36/2024/QH15, không ưu tiên phí, sát hạch hoặc thủ tục cấp đổi. "
            + parsed.query
        )
    return parsed.query


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
        query = _reranker_query(parsed)
        pairs = [(query, chunk.retrieval_text) for chunk, _score in candidates]
        scores = self.model.predict(pairs)
        rescored = [
            (chunk, float(score))
            for (chunk, _old_score), score in zip(candidates, scores, strict=True)
        ]
        return sorted(rescored, key=lambda item: item[1], reverse=True)
