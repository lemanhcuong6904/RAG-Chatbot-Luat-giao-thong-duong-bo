from __future__ import annotations

from rag_luat_gt.retrieval.reranker import BGEReranker
from rag_luat_gt.schemas import Chunk, ParsedQuery


class _FakeModel:
    def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        assert len(pairs) == 2
        return [-1.0, 2.0]


def _chunk(chunk_id: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id="doc",
        text=chunk_id,
        retrieval_text=chunk_id,
        source_file="source.md",
    )


def test_reranker_returns_only_cross_encoder_candidates() -> None:
    reranker = object.__new__(BGEReranker)
    reranker.model = _FakeModel()
    parsed = ParsedQuery(query="q", normalized_query="q")
    results = [(_chunk("a"), 0.9), (_chunk("b"), 0.8), (_chunk("c"), 999.0)]

    reranked = reranker.rerank(parsed, results, top_n=2)

    assert [chunk.chunk_id for chunk, _score in reranked] == ["b", "a"]
