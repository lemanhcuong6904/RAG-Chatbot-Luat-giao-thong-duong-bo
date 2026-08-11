from __future__ import annotations

from rag_luat_gt.retrieval.query_parser import parse_query
from rag_luat_gt.schemas import ChatRequest
from rag_luat_gt.service import RAGService


def test_parse_query_extracts_multiple_violations() -> None:
    parsed = parse_query(
        ChatRequest(
            query=(
                "Một người đi xe máy vượt đèn đỏ, đồng thời không đội mũ bảo hiểm "
                "và không có giấy phép lái xe thì tổng mức phạt thế nào?"
            )
        )
    )

    assert parsed.intent == "PENALTY_LOOKUP"
    assert parsed.vehicle_code == "MOTORCYCLE"
    assert [violation.catalog_code for violation in parsed.violations] == [
        "TRAFFIC_SIGNAL_NONCOMPLIANCE",
        "NO_HELMET",
        "NO_DRIVER_LICENSE",
    ]


def test_multi_violation_missing_license_condition_returns_branches() -> None:
    response = RAGService().answer(
        ChatRequest(
            query=(
                "Một người đi xe máy vượt đèn đỏ, đồng thời không đội mũ bảo hiểm "
                "và không có giấy phép lái xe thì tổng mức phạt được xác định như thế nào? "
                "Có cộng các mức phạt của từng hành vi không?"
            ),
            debug=True,
        )
    )

    assert response.answerable
    assert "4.000.000" in response.answer
    assert "6.000.000" in response.answer
    assert "400.000" in response.answer
    assert "600.000" in response.answer
    assert "6.400.000" in response.answer
    assert "10.600.000" in response.answer
    assert "10.400.000" in response.answer
    assert "14.600.000" in response.answer
    assert "không cộng số điểm trừ" in response.answer
    assert response.debug
    assert response.debug["sanction_composition"]["status"] == "CONDITIONAL"


def test_multi_violation_lte_125cc_resolves_total_money() -> None:
    response = RAGService().answer(
        ChatRequest(
            query=(
                "Một người đi xe máy 110cc vượt đèn đỏ, không đội mũ bảo hiểm "
                "và không có giấy phép lái xe thì tổng mức phạt là bao nhiêu?"
            ),
            debug=True,
        )
    )

    assert response.answerable
    assert "6.400.000" in response.answer
    assert "10.600.000" in response.answer
    assert "8.500.000" in response.answer
    assert response.debug
    assert response.debug["sanction_composition"]["status"] == "RESOLVED"
