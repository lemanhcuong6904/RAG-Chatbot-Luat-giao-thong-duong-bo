from __future__ import annotations

from rag_luat_gt.retrieval.llm_query_transformer import merge_llm_transform
from rag_luat_gt.retrieval.query_parser import parse_query
from rag_luat_gt.schemas import ChatRequest


def test_llm_transform_merges_multi_query_plan() -> None:
    parsed = parse_query(ChatRequest(query="xe ưu tiên thế nào?"))

    transformed = merge_llm_transform(
        parsed,
        {
            "intent": "GENERAL_LEGAL_QA",
            "query_plan": {
                "strategy": ["EXPANSION", "STEP_BACK", "MULTI_QUERY", "HYDE", "HYBRID_RETRIEVAL"],
                "multi_queries": ["quy định về xe ưu tiên", "người tham gia giao thông nhường đường xe ưu tiên"],
                "step_back_query": "nguyên tắc nhường đường cho xe ưu tiên",
                "hyde_text": "quy định pháp luật về xe ưu tiên đang làm nhiệm vụ",
            },
        },
    )

    assert transformed.query_plan
    assert "MULTI_QUERY" in transformed.query_plan.strategy
    assert transformed.query_plan.step_back_query == "nguyên tắc nhường đường cho xe ưu tiên"
    assert transformed.query_plan.hyde_text == "quy định pháp luật về xe ưu tiên đang làm nhiệm vụ"


def test_llm_transform_does_not_loosen_explicit_legal_reference() -> None:
    parsed = parse_query(ChatRequest(query="Khoản 4 Điều 7 Nghị định 168/2024/NĐ-CP quy định gì?"))

    transformed = merge_llm_transform(
        parsed,
        {
            "query_plan": {
                "strategy": ["MULTI_QUERY", "HYDE", "HYBRID_RETRIEVAL"],
                "multi_queries": ["quy định xử phạt xe máy"],
                "hyde_text": "văn bản giả định",
            }
        },
    )

    assert transformed.query_plan
    assert transformed.query_plan.strategy == ["DIRECT", "EXPANSION", "HYBRID_RETRIEVAL"]
    assert transformed.query_plan.multi_queries == []
    assert transformed.query_plan.hyde_text is None


def test_llm_transform_can_replace_violation_facts() -> None:
    parsed = parse_query(ChatRequest(query="xe máy vượt đèn đỏ và không đội mũ bị phạt thế nào?"))

    transformed = merge_llm_transform(
        parsed,
        {
            "intent": "PENALTY_LOOKUP",
            "violations": [
                {
                    "behavior_code": "A",
                    "behavior_text": "vượt đèn đỏ",
                    "raw_span": "vượt đèn đỏ",
                    "catalog_code": "TRAFFIC_SIGNAL_NONCOMPLIANCE",
                },
                {
                    "behavior_code": "B",
                    "behavior_text": "không đội mũ",
                    "raw_span": "không đội mũ",
                    "catalog_code": "NO_HELMET",
                },
            ],
            "query_plan": {
                "strategy": ["EXPANSION", "DECOMPOSITION", "STRUCTURED_LOOKUP", "LEGAL_COMPOSITION"],
                "use_structured_sanction": True,
            },
        },
    )

    assert len(transformed.violations) == 2
    assert transformed.behavior_code == "A"
    assert transformed.query_plan
    assert transformed.query_plan.use_structured_sanction
