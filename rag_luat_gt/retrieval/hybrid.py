from __future__ import annotations

from rag_luat_gt.config import QDRANT_READY_FILE, RAG_DENSE_ENABLED
from rag_luat_gt.retrieval.bm25 import BM25Retriever
from rag_luat_gt.schemas import Chunk, ParsedQuery
from rag_luat_gt.text import normalize_text, strip_accents


RRF_K = 60


class HybridRetriever:
    def __init__(self) -> None:
        self.bm25 = BM25Retriever()
        self.dense = None
        self.dense_error: str | None = None
        if RAG_DENSE_ENABLED and QDRANT_READY_FILE.exists():
            try:
                from rag_luat_gt.retrieval.dense import DenseRetriever

                self.dense = DenseRetriever()
            except Exception as exc:
                self.dense_error = str(exc)

    def search(self, parsed: ParsedQuery, top_k: int = 8) -> list[tuple[Chunk, float]]:
        exact = self.bm25._exact_lookup(parsed)
        if exact:
            return self._expand_parent_context(self._apply_preferences(parsed, exact), top_k)

        bm25_results = self.bm25.search(parsed, top_k=top_k * 4)
        dense_results = []
        if self.dense:
            try:
                valid_chunk_ids = {chunk.chunk_id for chunk in self.bm25.chunks}
                dense_results = [
                    (chunk, score)
                    for chunk, score in self.dense.search(parsed, top_k=top_k * 4)
                    if chunk.chunk_id in valid_chunk_ids
                ]
            except Exception as exc:
                self.dense_error = str(exc)

        if not dense_results:
            return self._expand_parent_context(self._apply_preferences(parsed, bm25_results), top_k)

        fused = self._rrf([dense_results, bm25_results])
        return self._expand_parent_context(self._apply_preferences(parsed, fused), top_k)

    @staticmethod
    def _rrf(result_sets: list[list[tuple[Chunk, float]]]) -> list[tuple[Chunk, float]]:
        chunks: dict[str, Chunk] = {}
        scores: dict[str, float] = {}
        for result_set in result_sets:
            for rank, (chunk, _score) in enumerate(result_set, start=1):
                chunks[chunk.chunk_id] = chunk
                scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (RRF_K + rank)
        return [
            (chunks[chunk_id], score)
            for chunk_id, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)
        ]

    def _apply_preferences(
        self,
        parsed: ParsedQuery,
        results: list[tuple[Chunk, float]],
    ) -> list[tuple[Chunk, float]]:
        if not results:
            return []

        reranked = self._apply_vehicle_preferences(parsed, results)
        reranked = self._apply_penalty_focus(parsed, reranked)
        reranked = self._filter_primary_penalty_scope(parsed, reranked)
        reranked = self._apply_amount_focus(parsed, reranked)
        return sorted(reranked, key=lambda item: item[1], reverse=True)

    @staticmethod
    def _apply_vehicle_preferences(
        parsed: ParsedQuery,
        results: list[tuple[Chunk, float]],
    ) -> list[tuple[Chunk, float]]:
        if not parsed.vehicle_type:
            return results

        reranked: list[tuple[Chunk, float]] = []
        for chunk, score in results:
            title = normalize_text(chunk.article_title or "")
            text = normalize_text(f"{title}\n{chunk.text[:700]}")
            adjusted = score

            if parsed.vehicle_type == "xe máy":
                if "xe máy chuyên dùng" in title:
                    adjusted -= abs(score) * 0.7 + 100.0
                if any(term in title for term in ["mô tô", "xe gắn máy"]):
                    adjusted += abs(score) * 0.25 + 50.0
                if "phạt tiền từ" in text and "đèn tín hiệu giao thông" in text:
                    adjusted += abs(score) * 0.15 + 25.0

            elif parsed.vehicle_type == "ô tô":
                if "ô tô" in title:
                    adjusted += abs(score) * 0.25 + 50.0
                if any(term in title for term in ["xe máy chuyên dùng", "mô tô", "xe gắn máy"]):
                    adjusted -= abs(score) * 0.7 + 100.0

            elif parsed.vehicle_type == "xe máy chuyên dùng":
                if "xe máy chuyên dùng" in title:
                    adjusted += abs(score) * 0.25 + 50.0

            reranked.append((chunk, adjusted))

        return reranked

    @staticmethod
    def _apply_penalty_focus(
        parsed: ParsedQuery,
        results: list[tuple[Chunk, float]],
    ) -> list[tuple[Chunk, float]]:
        if parsed.intent != "PENALTY_LOOKUP":
            return results

        query = strip_accents(normalize_text(parsed.normalized_query))
        is_red_light = any(term in query for term in ["den do", "den tin hieu", "khong chap hanh hieu lenh"])
        if not is_red_light:
            return results

        reranked: list[tuple[Chunk, float]] = []
        for chunk, score in results:
            text = strip_accents(normalize_text(f"{chunk.article_title or ''}\n{chunk.text[:900]}"))
            adjusted = score
            if "den tin hieu giao thong" in text or "khong chap hanh hieu lenh cua den" in text:
                adjusted += abs(score) * 0.2 + 40.0
            if chunk.document_number == "168/2024/NĐ-CP" and chunk.article in {"6", "7", "8"}:
                adjusted += 20.0
            if chunk.article not in {"6", "7", "8"}:
                adjusted -= abs(score) * 0.35 + 40.0
            reranked.append((chunk, adjusted))
        return reranked

    @staticmethod
    def _filter_primary_penalty_scope(
        parsed: ParsedQuery,
        results: list[tuple[Chunk, float]],
    ) -> list[tuple[Chunk, float]]:
        if parsed.intent != "PENALTY_LOOKUP" or not parsed.vehicle_type:
            return results

        query = strip_accents(normalize_text(parsed.normalized_query))
        is_red_light = any(term in query for term in ["den do", "den tin hieu", "khong chap hanh hieu lenh"])
        if not is_red_light:
            return results

        expected_article = {
            "ô tô": "6",
            "xe máy": "7",
            "xe máy chuyên dùng": "8",
        }.get(parsed.vehicle_type)
        if not expected_article:
            return results

        primary = [
            (chunk, score)
            for chunk, score in results
            if chunk.document_number == "168/2024/NĐ-CP" and chunk.article == expected_article
        ]
        if len(primary) >= 2:
            return primary
        return results

    @staticmethod
    def _apply_amount_focus(
        parsed: ParsedQuery,
        results: list[tuple[Chunk, float]],
    ) -> list[tuple[Chunk, float]]:
        query = strip_accents(normalize_text(parsed.query))
        asks_amount = any(
            term in query
            for term in [
                "bao nhieu",
                "muc thu",
                "muc phi",
                "le phi",
                "phi sat hach",
                "dong",
            ]
        )
        if not asks_amount:
            return results

        reranked: list[tuple[Chunk, float]] = []
        for chunk, score in results:
            text = strip_accents(normalize_text(f"{chunk.article_title or ''}\n{chunk.text[:1200]}"))
            adjusted = score
            if any(term in text for term in ["muc thu", "bieu muc thu", "ban hanh kem theo"]):
                adjusted += abs(score) * 0.35 + 80.0
            if any(term in text for term in ["phat tien tu", "dong"]):
                adjusted += abs(score) * 0.2 + 40.0
            if any(term in text for term in ["hieu luc thi hanh", "khai, thu, nop", "khai thu nop"]):
                adjusted -= abs(score) * 0.25 + 30.0
            reranked.append((chunk, adjusted))

        return reranked

    def _expand_parent_context(
        self,
        results: list[tuple[Chunk, float]],
        top_k: int,
    ) -> list[tuple[Chunk, float]]:
        by_location = {
            (chunk.document_id, chunk.article, chunk.clause, chunk.point): chunk
            for chunk in self.bm25.chunks
        }

        expanded: list[tuple[Chunk, float]] = []
        seen: set[str] = set()
        for chunk, score in results:
            if chunk.point:
                parent = by_location.get((chunk.document_id, chunk.article, chunk.clause, None))
                if parent and parent.chunk_id not in seen:
                    expanded.append((parent, score + 0.001))
                    seen.add(parent.chunk_id)
            if chunk.chunk_id not in seen:
                expanded.append((chunk, score))
                seen.add(chunk.chunk_id)
            if len(expanded) >= top_k:
                break

        return expanded[:top_k]
