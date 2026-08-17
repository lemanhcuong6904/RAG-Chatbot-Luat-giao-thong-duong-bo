from __future__ import annotations

from rag_luat_gt.retrieval.bm25 import BM25Retriever
from rag_luat_gt.retrieval.query_parser import parse_query
from rag_luat_gt.schemas import ChatRequest, Chunk, ParsedQuery
from rag_luat_gt.service import RAGService


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


def test_transition_query_can_retrieve_future_transition_source() -> None:
    chunk = _future_chunk()
    retriever = object.__new__(BM25Retriever)
    retriever.bm25 = None
    retriever.chunks = [chunk]
    retriever.documents = []
    parsed = ParsedQuery(
        query=(
            "Mot vi pham xay ra va ket thuc ngay 14/08/2026 nhung den 16/08/2026 moi bi phat hien "
            "thi ap dung Nghi dinh 168 hay Nghi dinh 238?"
        ),
        normalized_query="nghi dinh 238 dieu khoan chuyen tiep",
        document_number=chunk.document_number,
        legal_effective_date="2026-08-14",
        temporal_intent="APPLICABLE_RULE",
    )

    assert retriever.search(parsed, top_k=5)


def test_parse_query_marks_amendment_as_document_content_without_event_date() -> None:
    parsed = parse_query(ChatRequest(query="Nghị định 238/2026/NĐ-CP sửa đổi những gì?"))

    assert parsed.temporal_intent == "AMENDMENT_COMPARE"


def test_document_level_effective_date_prefers_effective_article() -> None:
    response = RAGService().answer(
        ChatRequest(
            query="Ngày 01/01/2025 Nghị định 168/2024/NĐ-CP đã có hiệu lực chưa?",
            debug=True,
            pre_rag_enabled=False,
            llm_provider="extractive",
        )
    )

    assert response.answer.startswith("Có.")
    assert "01/01/2025" in response.answer
    assert "Ã" not in response.answer
    assert any(citation.article == "53" and citation.clause == "1" for citation in response.citations)


def test_law35_effective_date_mentions_early_effective_provisions() -> None:
    response = RAGService().answer(
        ChatRequest(
            query="Ngày 01/01/2025 Luật 35/2024/QH15 đã có hiệu lực chưa?",
            debug=True,
            pre_rag_enabled=False,
            llm_provider="extractive",
        )
    )

    assert response.answer.startswith("Có.")
    assert "01/01/2025" in response.answer
    assert "01/10/2024" in response.answer
    assert "Ã" not in response.answer
    assert any(citation.article == "85" for citation in response.citations)


def test_nd238_start_date_query_does_not_use_status_prefix() -> None:
    response = RAGService().answer(
        ChatRequest(
            query="Nghị định 238/2026/NĐ-CP bắt đầu có hiệu lực từ ngày nào?",
            debug=True,
            pre_rag_enabled=False,
            llm_provider="extractive",
        )
    )

    assert not response.answer.startswith(("Có.", "Chưa."))
    assert "15/08/2026" in response.answer
    assert any(citation.document_number == "238/2026/NĐ-CP" and citation.article == "20" and citation.clause == "1" for citation in response.citations)


def test_nd238_effective_status_before_effective_date_is_in_domain() -> None:
    response = RAGService().answer(
        ChatRequest(
            query="Ngày 14/08/2026 Nghị định 238/2026/NĐ-CP đã có hiệu lực chưa?",
            debug=True,
            pre_rag_enabled=False,
            llm_provider="extractive",
        )
    )

    assert response.answerable
    assert response.answer.startswith("Chưa.")
    assert "15/08/2026" in response.answer
    assert any(citation.document_number == "238/2026/NĐ-CP" and citation.article == "20" and citation.clause == "1" for citation in response.citations)


def test_nd238_transition_query_uses_transition_and_effective_articles() -> None:
    response = RAGService().answer(
        ChatRequest(
            query=(
                "Vi phạm xảy ra và kết thúc ngày 14/08/2026 nhưng ngày 16/08/2026 mới bị phát hiện "
                "thì áp dụng Nghị định 168 hay Nghị định 238?"
            ),
            debug=True,
            pre_rag_enabled=False,
            llm_provider="extractive",
        )
    )

    refs = {(citation.document_number, citation.article, citation.clause) for citation in response.citations}
    assert response.answerable
    assert "Nghị định 168" in response.answer
    assert "không áp dụng Nghị định 238" in response.answer
    assert ("238/2026/NĐ-CP", "21", None) in refs
    assert ("238/2026/NĐ-CP", "20", "1") in refs


def test_nd168_deferred_child_safety_sanction_effective_date_uses_article_53_clause_2() -> None:
    response = RAGService().answer(
        ChatRequest(
            query="Điểm m khoản 3 Điều 6 Nghị định 168/2024/NĐ-CP có hiệu lực từ ngày nào?",
            debug=True,
            pre_rag_enabled=False,
            llm_provider="extractive",
        )
    )

    refs = {(citation.document_number, citation.article, citation.clause, citation.point) for citation in response.citations}
    assert "01/01/2026" in response.answer
    assert ("168/2024/NĐ-CP", "53", "2", None) in refs


def test_law36_child_safety_effective_status_uses_article_88_clause_2() -> None:
    response = RAGService().answer(
        ChatRequest(
            query=(
                "Ngày 31/12/2025 quy định về thiết bị an toàn cho trẻ em tại khoản 3 "
                "Điều 10 Luật 36/2024/QH15 đã có hiệu lực chưa?"
            ),
            debug=True,
            pre_rag_enabled=False,
            llm_provider="extractive",
        )
    )

    assert response.answerable
    assert response.answer.startswith("Chưa.")
    assert "01/01/2026" in response.answer
    assert any(citation.document_number == "36/2024/QH15" and citation.article == "88" and citation.clause == "2" for citation in response.citations)
