from __future__ import annotations

from rag_luat_gt.generation.structured_sanction_llm import maybe_render_structured_sanction_with_llm
from rag_luat_gt.schemas import ChatResponse, ParsedQuery


def test_structured_sanction_llm_renderer_rewrites_answer(monkeypatch) -> None:
    import rag_luat_gt.generation.structured_sanction_llm as renderer

    monkeypatch.setattr(renderer, "RAG_SANCTION_LLM_PROVIDER", "openai")
    monkeypatch.setattr(renderer, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(renderer, "_render_with_openai", lambda *_args, **_kwargs: "### Trả lời\nCâu trả lời mượt hơn.")

    response = ChatResponse(
        answer="deterministic",
        citations=[],
        answerable=True,
        debug={"sanction_lookup": {"status": "FOUND", "rules": []}},
    )

    rendered = maybe_render_structured_sanction_with_llm(
        ParsedQuery(query="q", normalized_query="q"),
        response,
    )

    assert rendered.answer == "### Trả lời\nCâu trả lời mượt hơn."
    assert rendered.debug
    assert rendered.debug["structured_sanction_llm"]["enabled"] is True


def test_structured_sanction_llm_renderer_falls_back_on_error(monkeypatch) -> None:
    import rag_luat_gt.generation.structured_sanction_llm as renderer

    def fail(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(renderer, "RAG_SANCTION_LLM_PROVIDER", "openai")
    monkeypatch.setattr(renderer, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(renderer, "_render_with_openai", fail)

    response = ChatResponse(
        answer="deterministic",
        citations=[],
        answerable=True,
        debug={"sanction_lookup": {"status": "FOUND", "rules": []}},
    )

    rendered = maybe_render_structured_sanction_with_llm(
        ParsedQuery(query="q", normalized_query="q"),
        response,
    )

    assert rendered.answer == "deterministic"
    assert rendered.warnings
