from __future__ import annotations

from pathlib import Path

from rag_luat_gt.ingestion.build_index import build_index
from rag_luat_gt.retrieval.hybrid import HybridRetriever
from rag_luat_gt.retrieval.query_parser import parse_query
from rag_luat_gt.schemas import ChatRequest
from rag_luat_gt.service import RAGService


def test_parse_query_detects_license_point_balance() -> None:
    parsed = parse_query(ChatRequest(query="Một giấy phép lái xe có bao nhiêu điểm?"))

    assert parsed.intent == "LICENSE_POINT_BALANCE"
    assert parsed.requested_facets == ["LICENSE_POINT_TOTAL"]


def test_license_point_balance_retrieves_article_58_clause_1_first() -> None:
    root = Path(".").resolve()
    build_index(root / "data" / "markdown", root)
    parsed = parse_query(ChatRequest(query="Một giấy phép lái xe có bao nhiêu điểm?"))

    results = HybridRetriever().search(parsed, top_k=8)

    assert results
    first = results[0][0]
    assert first.document_number == "36/2024/QH15"
    assert first.article == "58"
    assert first.clause == "1"
    assert "12 điểm" in first.text


def test_license_point_balance_answer_contains_12_points() -> None:
    root = Path(".").resolve()
    build_index(root / "data" / "markdown", root)

    response = RAGService().answer(ChatRequest(query="Một giấy phép lái xe có bao nhiêu điểm?", top_k=8, debug=True))

    assert response.answerable
    assert "12" in response.answer
    assert not any("không đủ căn cứ" in warning.lower() for warning in response.warnings)
    assert response.citations[0].document_number == "36/2024/QH15"
    assert response.citations[0].article == "58"
