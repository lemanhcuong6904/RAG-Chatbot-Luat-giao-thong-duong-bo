from __future__ import annotations

import pytest

from rag_luat_gt.retrieval.query_parser import parse_query
from rag_luat_gt.schemas import ChatRequest
from rag_luat_gt.service import RAGService
from rag_luat_gt.structured_tables import build_structured_table_answer


def test_safe_distance_table_matches_upper_boundary() -> None:
    response = RAGService().answer(
        ChatRequest(
            query="Chay xe voi toc do 100 km/h thi khoang cach an toan toi thieu la bao nhieu?",
            debug=True,
            pre_rag_enabled=False,
        )
    )

    assert response.answerable
    assert "70 m" in response.answer
    assert "100 m" not in response.answer.replace("100 km/h", "")
    assert response.debug
    assert response.debug["routing"]["structured_table_answered"] is True
    assert response.citations[0].document_number == "38/2024/TT-BGTVT"


@pytest.mark.parametrize(
    ("query", "expected", "article", "clause"),
    [
        ("Xe gắn máy được chạy tốc độ tối đa bao nhiêu khi không đi trên cao tốc?", "40 km/h", "7", None),
        ("Tốc độ tối đa trên đường cao tốc là bao nhiêu?", "120 km/h", "9", "2"),
        ("Tốc độ tối thiểu trên đường cao tốc là bao nhiêu?", "60 km/h", "9", "3"),
    ],
)
def test_structured_speed_rules(query: str, expected: str, article: str, clause: str | None) -> None:
    parsed = parse_query(ChatRequest(query=query))
    response = build_structured_table_answer(parsed)

    assert response is not None
    assert expected in response.answer
    assert response.citations[0].article == article
    assert response.citations[0].clause == clause
