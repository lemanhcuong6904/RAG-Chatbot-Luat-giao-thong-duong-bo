from __future__ import annotations

from rag_luat_gt.retrieval.hybrid import HybridRetriever
from rag_luat_gt.retrieval.query_parser import parse_query
from rag_luat_gt.schemas import ChatRequest


def test_context_trace_records_parent_expansion() -> None:
    parsed = parse_query(ChatRequest(query="Người điều khiển xe máy sử dụng điện thoại khi đang lái xe bị phạt bao nhiêu?"))
    retriever = HybridRetriever()

    results = retriever.search(parsed, top_k=8)

    assert results
    assert retriever.last_context_trace
    assert any(item["reason"] == "parent_expansion" for item in retriever.last_context_trace)
    assert all("parent_id" in item and "sibling_group_id" in item for item in retriever.last_context_trace)


def test_phone_penalty_context_prioritizes_motorcycle_clause_4_point_d() -> None:
    parsed = parse_query(ChatRequest(query="Người điều khiển xe máy sử dụng điện thoại khi đang lái xe bị phạt bao nhiêu?"))
    retriever = HybridRetriever()

    results = retriever.search(parsed, top_k=8)

    assert results[0][0].document_number == "168/2024/NĐ-CP"
    assert results[0][0].article == "7"
    assert results[0][0].clause == "4"
    assert results[1][0].article == "7"
    assert results[1][0].clause == "4"
    assert results[1][0].point == "đ"
    assert "800.000" in results[0][0].text
    assert "1.000.000" in results[0][0].text
    assert "điện thoại" in results[1][0].text
