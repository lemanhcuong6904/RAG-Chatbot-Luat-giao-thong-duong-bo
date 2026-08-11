from __future__ import annotations

from rag_luat_gt.retrieval.bm25 import BM25Retriever
from rag_luat_gt.retrieval.query_parser import parse_query
from rag_luat_gt.schemas import ChatRequest, Chunk, ParsedQuery


def _future_chunk() -> Chunk:
    return Chunk(
        chunk_id="future-doc",
        document_id="doc",
        document_number="238/2026/NĐ-CP",
        article="1",
        text="Nghị định 238/2026/NĐ-CP sửa đổi một số nội dung.",
        retrieval_text="Nghị định 238/2026/NĐ-CP sửa đổi một số nội dung.",
        valid_from="2026-08-15",
        source_file="source.md",
    )


def test_document_content_query_does_not_filter_future_document() -> None:
    retriever = object.__new__(BM25Retriever)
    retriever.bm25 = None
    retriever.chunks = [_future_chunk()]
    retriever.documents = []
    parsed = ParsedQuery(
        query="Nghị định 238/2026/NĐ-CP sửa đổi những gì?",
        normalized_query="nghi dinh 238/2026/nd-cp sua doi nhung gi",
        document_number="238/2026/NĐ-CP",
        legal_effective_date="2026-08-11",
        temporal_intent="DOCUMENT_CONTENT",
    )

    assert retriever.search(parsed, top_k=5)


def test_applicable_rule_query_filters_future_document() -> None:
    retriever = object.__new__(BM25Retriever)
    retriever.bm25 = None
    retriever.chunks = [_future_chunk()]
    retriever.documents = []
    parsed = ParsedQuery(
        query="Hiện nay Nghị định 238/2026/NĐ-CP đang áp dụng không?",
        normalized_query="hien nay nghi dinh 238/2026/nd-cp dang ap dung khong",
        document_number="238/2026/NĐ-CP",
        legal_effective_date="2026-08-11",
        temporal_intent="APPLICABLE_RULE",
    )

    assert retriever.search(parsed, top_k=5) == []


def test_parse_query_marks_amendment_as_document_content_without_event_date() -> None:
    parsed = parse_query(ChatRequest(query="Nghị định 238/2026/NĐ-CP sửa đổi những gì?"))

    assert parsed.temporal_intent == "AMENDMENT_COMPARE"
