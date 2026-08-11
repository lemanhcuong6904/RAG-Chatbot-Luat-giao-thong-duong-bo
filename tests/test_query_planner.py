from __future__ import annotations

from rag_luat_gt.retrieval.query_parser import parse_query
from rag_luat_gt.schemas import ChatRequest


def test_planner_uses_structured_decomposition_for_multi_violation_penalty() -> None:
    parsed = parse_query(
        ChatRequest(
            query="Xe máy vượt đèn đỏ, không đội mũ bảo hiểm và không có giấy phép lái xe bị phạt thế nào?"
        )
    )

    assert parsed.query_plan
    assert parsed.query_plan.use_structured_sanction
    assert "DECOMPOSITION" in parsed.query_plan.strategy
    assert "LEGAL_COMPOSITION" in parsed.query_plan.strategy
    assert len(parsed.query_plan.subqueries) == 3


def test_planner_keeps_explicit_reference_direct() -> None:
    parsed = parse_query(ChatRequest(query="Khoản 4 Điều 7 Nghị định 168/2024/NĐ-CP quy định gì?"))

    assert parsed.query_plan
    assert parsed.query_plan.strategy == ["DIRECT", "EXPANSION", "HYBRID_RETRIEVAL"]
    assert parsed.query_plan.multi_queries == []
    assert parsed.query_plan.hyde_text is None


def test_planner_adds_multi_query_and_hyde_for_short_general_query() -> None:
    parsed = parse_query(ChatRequest(query="xe ưu tiên thế nào?"))

    assert parsed.query_plan
    assert "MULTI_QUERY" in parsed.query_plan.strategy
    assert "HYDE" in parsed.query_plan.strategy
    assert parsed.query_plan.multi_queries
    assert parsed.query_plan.hyde_text
