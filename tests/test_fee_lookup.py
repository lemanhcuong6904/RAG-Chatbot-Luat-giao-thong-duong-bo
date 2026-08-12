from __future__ import annotations

from rag_luat_gt.schemas import ChatRequest
from rag_luat_gt.service import RAGService


def test_service_answers_a1_driving_test_fee_total() -> None:
    response = RAGService().answer(
        ChatRequest(query="Tổng lệ phí thi sát hạch lái xe A1 là bao nhiêu?", debug=True, top_k=8)
    )

    assert response.answerable
    assert response.debug
    assert response.debug["parsed_query"]["intent"] == "FEE_LOOKUP"
    assert "130.000 đồng" in response.answer
    assert "60.000 đồng" in response.answer
    assert "70.000 đồng" in response.answer
    assert "154/2025/TT-BTC" in response.answer
