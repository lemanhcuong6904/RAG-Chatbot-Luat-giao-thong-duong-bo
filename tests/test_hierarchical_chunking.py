from __future__ import annotations

from rag_luat_gt.ingestion.legal_parser import parse_chunks
from rag_luat_gt.ingestion.normalizer import normalize_document
from rag_luat_gt.retrieval.hybrid import HybridRetriever
from rag_luat_gt.schemas import ParsedQuery


def _sample_chunks():
    document = normalize_document(
        {
            "so_ky_hieu": "36/2024/QH15",
            "title": "Luật test",
            "ngay_co_hieu_luc": "2025-01-01",
        },
        "data/markdown/test.md",
    )
    body = "\n".join(
        [
            "Điều 7. Cơ sở dữ liệu về trật tự, an toàn giao thông đường bộ",
            "1. Cơ sở dữ liệu về trật tự, an toàn giao thông đường bộ bao gồm:",
            "a) Cơ sở dữ liệu về đăng ký xe;",
            "b) Cơ sở dữ liệu về người lái xe;",
            "c) Cơ sở dữ liệu về tai nạn giao thông.",
            "2. Cơ sở dữ liệu được kết nối, chia sẻ.",
        ]
    )
    return parse_chunks(document, body, "data/markdown/test.md")


def test_parse_chunks_adds_hierarchy_metadata() -> None:
    chunks = _sample_chunks()
    clause = next(chunk for chunk in chunks if chunk.chunk_type == "CLAUSE" and chunk.clause == "1")
    points = [chunk for chunk in chunks if chunk.chunk_type == "POINT" and chunk.clause == "1"]

    assert len(points) == 3
    assert clause.children_ids == [chunk.chunk_id for chunk in points]
    assert all(chunk.parent_id == clause.chunk_id for chunk in points)
    assert all(chunk.sibling_group_id == clause.chunk_id for chunk in points)


def test_exhaustive_context_expands_clause_children() -> None:
    retriever = HybridRetriever()
    retriever.bm25.chunks = _sample_chunks()
    clause = next(chunk for chunk in retriever.bm25.chunks if chunk.chunk_type == "CLAUSE" and chunk.clause == "1")
    parsed = ParsedQuery(
        query="Cơ sở dữ liệu bao gồm những gì?",
        normalized_query="co so du lieu bao gom nhung gi",
        intent="ENUMERATION",
        retrieval_mode="EXHAUSTIVE",
        answer_scope="ALL_CHILDREN",
    )

    expanded = retriever._expand_structural_context(parsed, [(clause, 1.0)], top_k=3)

    assert [chunk.chunk_type for chunk, _score in expanded] == ["CLAUSE", "POINT", "POINT", "POINT"]
    assert [chunk.point for chunk, _score in expanded[1:]] == ["a", "b", "c"]
