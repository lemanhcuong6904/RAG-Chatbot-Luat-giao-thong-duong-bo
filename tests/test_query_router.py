from __future__ import annotations

import pytest

from rag_luat_gt.retrieval.query_parser import parse_query
from rag_luat_gt.retrieval.query_router import QueryRouteDecision, apply_route_decision, direct_route_response, route_query
from rag_luat_gt.schemas import ChatRequest
from rag_luat_gt.service import _router_has_sufficient_rag_plan
from rag_luat_gt.service import RAGService


def test_service_answers_small_talk_without_retrieval() -> None:
    response = RAGService().answer(ChatRequest(query="Xin chào", debug=True))

    assert response.answerable
    assert not response.citations
    assert "Chào" in response.answer
    assert "pháp luật giao thông đường bộ" in response.answer
    assert "giúp gì cho bạn hôm nay" not in response.answer
    assert response.debug
    assert "retrieval" not in response.debug
    assert response.debug["routing"]["query_router"]["decision"]["route"] == "SMALL_TALK"


def test_service_answers_capability_question_without_retrieval() -> None:
    response = RAGService().answer(ChatRequest(query="Bạn có thể làm những gì?", debug=True))

    assert response.answerable
    assert not response.citations
    assert "pháp luật giao thông đường bộ" in response.answer
    assert "tình huống" in response.answer
    assert response.debug
    assert "retrieval" not in response.debug
    assert response.debug["routing"]["query_router"]["decision"]["route"] == "SMALL_TALK"


@pytest.mark.parametrize(
    ("route", "answerable", "answer"),
    [
        ("SMALL_TALK", True, "Tôi là trợ lý tra cứu luật giao thông đường bộ."),
        ("SMALL_TALK", True, "Bạn có thể hỏi về mức phạt, GPLX hoặc căn cứ pháp lý."),
        ("OUT_OF_SCOPE", False, "Tôi chỉ hỗ trợ pháp luật giao thông đường bộ Việt Nam."),
    ],
)
def test_llm_router_direct_decisions_do_not_need_retrieval(route: str, answerable: bool, answer: str) -> None:
    decision = QueryRouteDecision(
        route=route,
        legal_domain="non_legal" if route == "SMALL_TALK" else "other_law",
        retrieval_strategy="NONE",
        direct_answer=answer,
        confidence=0.9,
    )

    response = direct_route_response(decision)

    assert response is not None
    assert response.answer == answer
    assert response.answerable is answerable
    assert not response.citations


def test_router_plan_can_skip_prerag_when_confident_and_rewritten() -> None:
    decision = QueryRouteDecision(
        route="RAG",
        legal_domain="traffic_law",
        intent="LICENSE_POINT_BALANCE",
        retrieval_strategy="FACTOID",
        question_rewrite="giấy phép lái xe có bao gồm 12 điểm không",
        confidence=0.9,
    )

    assert _router_has_sufficient_rag_plan(decision)


def test_router_plan_needs_prerag_without_rewrite() -> None:
    decision = QueryRouteDecision(
        route="RAG",
        legal_domain="traffic_law",
        intent="LICENSE_POINT_BALANCE",
        retrieval_strategy="FACTOID",
        confidence=0.9,
    )

    assert not _router_has_sufficient_rag_plan(decision)


def test_minimal_rule_fallback_does_not_classify_many_meta_questions() -> None:
    parsed = parse_query(ChatRequest(query="Bạn là ai?"))
    _routed, decision, _debug = route_query(parsed)

    assert decision.route == "RAG"
    assert decision.reason == "minimal fallback; use LLM router for semantic routing"


def test_service_answers_minimal_capability_question_without_retrieval() -> None:
    response = RAGService().answer(ChatRequest(query="Bạn có thể làm những gì?", debug=True))

    assert response.answerable
    assert not response.citations
    assert response.debug
    assert "retrieval" not in response.debug
    assert response.debug["routing"]["query_router"]["decision"]["route"] == "SMALL_TALK"


def test_service_rejects_out_of_scope_question_without_retrieval() -> None:
    decision = QueryRouteDecision(
        route="OUT_OF_SCOPE",
        legal_domain="other_law",
        retrieval_strategy="NONE",
        direct_answer="Tôi chỉ hỗ trợ pháp luật giao thông đường bộ Việt Nam.",
        confidence=0.9,
    )
    response = direct_route_response(decision)

    assert response is not None
    assert not response.answerable
    assert not response.citations
    assert "giao thông đường bộ" in response.answer


@pytest.mark.parametrize(
    "query",
    [
        "Xe máy vượt đèn đỏ bị phạt bao nhiêu?",
        "Một giấy phép lái xe có bao nhiêu điểm?",
        "Khi xảy ra tai nạn giao thông, người điều khiển phương tiện có những nghĩa vụ gì?",
        "Đi xe đạp cần đội mũ bảo hiểm hay không?",
    ],
)
def test_router_keeps_traffic_law_questions_in_rag(query: str) -> None:
    parsed = parse_query(ChatRequest(query=query))
    _routed, decision, _debug = route_query(parsed)

    assert decision.route == "RAG"


def test_router_decision_can_force_exhaustive_article_strategy() -> None:
    parsed = parse_query(ChatRequest(query="Người điều khiển phương tiện có trách nhiệm gì khi tai nạn?"))
    decision = QueryRouteDecision(
        route="RAG",
        legal_domain="traffic_law",
        intent="ENUMERATION",
        retrieval_strategy="EXHAUSTIVE_ARTICLE",
        needs_parent=True,
        needs_siblings=True,
        needs_children=True,
        confidence=0.9,
    )

    routed = apply_route_decision(parsed, decision)

    assert routed.intent == "ENUMERATION"
    assert routed.answer_mode == "ENUMERATION"
    assert routed.retrieval_mode == "EXHAUSTIVE"
    assert routed.answer_scope == "ALL_CHILDREN"
    assert routed.query_plan
    assert "EXHAUSTIVE_ARTICLE" in routed.query_plan.strategy
