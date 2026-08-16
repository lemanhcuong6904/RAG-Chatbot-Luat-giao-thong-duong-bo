from __future__ import annotations

from pathlib import Path

from rag_luat_gt.ingestion.build_index import build_index
from rag_luat_gt.schemas import ChatRequest
from rag_luat_gt.service import RAGService


_INDEX_BUILT = False


def _service() -> RAGService:
    global _INDEX_BUILT
    if not _INDEX_BUILT:
        root = Path(".").resolve()
        build_index(root / "data" / "markdown", root, invalidate_dense=False)
        _INDEX_BUILT = True
    return RAGService()


def _answer(query: str):
    return _service().answer(
        ChatRequest(
            query=query,
            top_k=8,
            debug=True,
            pre_rag_enabled=False,
            structured_lookup_enabled=False,
        )
    )


def test_license_class_b_scope_uses_article_57_point_d() -> None:
    response = _answer("Bằng B được lái những loại ô tô nào?")

    assert response.answerable
    assert "Hạng B" in response.answer
    assert "đến 08 chỗ" in response.answer
    assert "3.500 kg" in response.answer
    assert "Hạng BE" not in response.answer
    assert "Điều 59" not in response.answer
    assert any(
        citation.document_number == "36/2024/QH15" and citation.article == "57" and citation.point == "d"
        for citation in response.citations
    )


def test_license_age_for_a1_a_b1_b_c1_does_not_include_21_year_branch() -> None:
    response = _answer("Bao nhiêu tuổi thì được cấp bằng A1, A, B1, B hoặc C1?")

    assert response.answerable
    assert "18 tuổi" in response.answer
    assert "21 tuổi" not in response.answer
    assert any(
        citation.document_number == "36/2024/QH15" and citation.article == "59" and citation.point == "b"
        for citation in response.citations
    )


def test_csgt_stop_reason_right_uses_article_72_point_b() -> None:
    response = _answer("Khi bị CSGT dừng xe, người lái có quyền được biết lý do không?")

    assert response.answerable
    assert response.answer.startswith("Có.")
    assert "căn cứ dừng phương tiện" in response.answer
    assert any(
        citation.document_number == "36/2024/QH15" and citation.article == "72" and citation.point == "b"
        for citation in response.citations
    )
    assert not (
        response.citations
        and response.citations[0].document_number == "36/2024/QH15"
        and response.citations[0].article == "18"
    )
