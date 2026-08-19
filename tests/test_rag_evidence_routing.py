from __future__ import annotations

from pathlib import Path

from rag_luat_gt.ingestion.build_index import build_index
from rag_luat_gt.schemas import ChatRequest
from rag_luat_gt.service import RAGService


_INDEX_BUILT = False


def _answer_without_structured_facts(query: str):
    global _INDEX_BUILT
    if not _INDEX_BUILT:
        root = Path(".").resolve()
        build_index(root / "data" / "markdown", root, invalidate_dense=False)
        _INDEX_BUILT = True
    return RAGService().answer(
        ChatRequest(
            query=query,
            top_k=8,
            debug=True,
            pre_rag_enabled=False,
            structured_lookup_enabled=False,
            llm_provider="extractive",
        )
    )


def test_rag_context_for_csgt_stop_basis_uses_article_66_without_structured_facts() -> None:
    response = _answer_without_structured_facts("CSGT được dừng xe để kiểm tra trong những trường hợp nào?")

    assert response.answerable
    assert {(citation.document_number, citation.article, citation.clause) for citation in response.citations[:5]} == {
        ("36/2024/QH15", "66", None),
        ("36/2024/QH15", "66", "1"),
        ("36/2024/QH15", "66", "2"),
        ("36/2024/QH15", "66", "3"),
        ("36/2024/QH15", "66", "4"),
    }


def test_rag_context_for_child_crossing_uses_article_30_without_structured_facts() -> None:
    response = _answer_without_structured_facts("Trẻ dưới 7 tuổi tự qua đường có được không?")

    assert response.answerable
    assert any(
        citation.document_number == "36/2024/QH15" and citation.article == "30" and citation.point == "a"
        for citation in response.citations[:3]
    )
    assert not any(citation.document_number == "36/2024/QH15" and citation.article == "59" for citation in response.citations)


def test_rag_context_for_csgt_technical_detection_includes_article_67_without_structured_facts() -> None:
    response = _answer_without_structured_facts(
        "CSGT có thể dừng xe dựa trên dữ liệu từ hệ thống giám sát hoặc thiết bị kỹ thuật nghiệp vụ không?"
    )

    assert response.answerable
    assert any(citation.document_number == "36/2024/QH15" and citation.article == "66" for citation in response.citations[:5])
    assert any(citation.document_number == "36/2024/QH15" and citation.article == "67" for citation in response.citations[:8])
