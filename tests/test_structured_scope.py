from __future__ import annotations

from rag_luat_gt.retrieval.query_parser import parse_query
from rag_luat_gt.schemas import ChatRequest
from rag_luat_gt import service as service_module
from rag_luat_gt.structured_facts import build_structured_fact_answer


def _answer(query: str):
    response = build_structured_fact_answer(parse_query(ChatRequest(query=query)))
    assert response is not None
    return response


def test_csgt_stop_basis_question_lists_cases_without_yes_no_prefix() -> None:
    response = _answer("CSGT được dừng xe để kiểm tra trong những trường hợp nào?")

    assert not response.answer.startswith("Có.")
    assert "Khi phát hiện hành vi vi phạm pháp luật" in response.answer
    assert "Thực hiện theo mệnh lệnh, kế hoạch tuần tra" in response.answer
    assert "Có tin báo, tố giác" in response.answer
    assert {(citation.article, citation.clause) for citation in response.citations} == {
        ("66", "1"),
        ("66", "2"),
        ("66", "3"),
        ("66", "4"),
    }


def test_child_crossing_factoid_does_not_include_unasked_groups() -> None:
    response = _answer("Trẻ dưới 7 tuổi tự qua đường có được không?")

    assert response.answer.startswith("Không được tự qua đường.")
    assert "Trẻ em dưới 07 tuổi khi đi qua đường phải có người lớn dẫn dắt" in response.answer
    assert "phụ nữ mang thai" not in response.answer
    assert "Người khuyết tật sử dụng xe lăn" not in response.answer


def test_csgt_technical_detection_question_uses_detection_sources() -> None:
    response = _answer("CSGT có thể dừng xe dựa trên dữ liệu từ hệ thống giám sát hoặc thiết bị kỹ thuật nghiệp vụ không?")

    assert response.answer.startswith("Có, nếu")
    assert "hệ thống giám sát" in response.answer
    assert "thiết bị kỹ thuật nghiệp vụ" in response.answer
    assert ("66", "1") in {(citation.article, citation.clause) for citation in response.citations}
    assert any(citation.article == "67" for citation in response.citations)


def test_csgt_stop_authority_does_not_shadow_driver_reason_right() -> None:
    parsed = parse_query(ChatRequest(query="Khi bị CSGT dừng xe, người lái có quyền được biết lý do không?"))

    assert build_structured_fact_answer(parsed) is None


def test_service_skips_deterministic_structured_facts_when_chat_llm_is_configured(monkeypatch) -> None:
    service_module.set_request_llm(None, None)
    monkeypatch.setattr(service_module, "RAG_STRUCTURED_FACT_USE_WITH_LLM", False)
    monkeypatch.setattr(service_module, "RAG_LLM_PROVIDER", "openai")
    monkeypatch.setattr(service_module, "RAG_LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setattr("rag_luat_gt.generation.llm_client.OPENAI_API_KEY", "test-key")

    enabled, reason = service_module._structured_fact_runtime_enabled(True)

    assert not enabled
    assert reason is not None
    assert "chat_llm_provider=openai" in reason


def test_service_keeps_deterministic_structured_facts_for_extractive_mode(monkeypatch) -> None:
    service_module.set_request_llm(None, None)
    monkeypatch.setattr(service_module, "RAG_STRUCTURED_FACT_USE_WITH_LLM", False)
    monkeypatch.setattr(service_module, "RAG_LLM_PROVIDER", "extractive")
    monkeypatch.setattr(service_module, "RAG_LLM_MODEL", "")

    enabled, reason = service_module._structured_fact_runtime_enabled(True)

    assert enabled
    assert reason is None


def test_service_skips_deterministic_structured_tables_when_chat_llm_is_configured(monkeypatch) -> None:
    service_module.set_request_llm(None, None)
    monkeypatch.setattr(service_module, "RAG_STRUCTURED_TABLE_USE_WITH_LLM", False)
    monkeypatch.setattr(service_module, "RAG_LLM_PROVIDER", "openai")
    monkeypatch.setattr(service_module, "RAG_LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setattr("rag_luat_gt.generation.llm_client.OPENAI_API_KEY", "test-key")

    enabled, reason = service_module._structured_table_runtime_enabled(True)

    assert not enabled
    assert reason is not None
    assert "structured_table" in reason
    assert "chat_llm_provider=openai" in reason


def test_service_requires_llm_plan_for_structured_sanction_in_chat_mode(monkeypatch) -> None:
    service_module.set_request_llm(None, None)
    monkeypatch.setattr(service_module, "RAG_STRUCTURED_SANCTION_REQUIRE_LLM_PLAN", True)
    monkeypatch.setattr(service_module, "RAG_LLM_PROVIDER", "openai")
    monkeypatch.setattr(service_module, "RAG_LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setattr("rag_luat_gt.generation.llm_client.OPENAI_API_KEY", "test-key")
    parsed = parse_query(ChatRequest(query="Xe may vuot den do bi phat bao nhieu?")).model_copy(
        update={"intent": "PENALTY_LOOKUP"}
    )

    enabled, reason = service_module._structured_sanction_runtime_enabled(parsed.intent == "PENALTY_LOOKUP", parsed, {}, {})

    assert not enabled
    assert reason is not None
    assert "without_llm_plan" in reason


def test_service_allows_structured_sanction_when_llm_plan_requests_it(monkeypatch) -> None:
    service_module.set_request_llm(None, None)
    monkeypatch.setattr(service_module, "RAG_STRUCTURED_SANCTION_REQUIRE_LLM_PLAN", True)
    monkeypatch.setattr(service_module, "RAG_LLM_PROVIDER", "openai")
    monkeypatch.setattr(service_module, "RAG_LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setattr("rag_luat_gt.generation.llm_client.OPENAI_API_KEY", "test-key")
    parsed = parse_query(ChatRequest(query="Xe may vuot den do bi phat bao nhieu?")).model_copy(
        update={"intent": "PENALTY_LOOKUP"}
    )
    router_debug = {"raw_payload": {"intent": "PENALTY_LOOKUP", "use_structured_sanction": True}}

    enabled, reason = service_module._structured_sanction_runtime_enabled(True, parsed, router_debug, {})

    assert enabled
    assert reason is None
