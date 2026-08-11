from __future__ import annotations

from datetime import date

from rag_luat_gt.retrieval.query_parser import parse_query
from rag_luat_gt.schemas import ChatRequest


def test_parse_query_separates_event_and_reference_dates() -> None:
    parsed = parse_query(
        ChatRequest(
            query="Xe máy vượt đèn đỏ ngày 10/08/2026 bị phạt bao nhiêu?",
            as_of_date=date(2026, 8, 20),
        )
    )

    assert parsed.event_date == "2026-08-10"
    assert parsed.as_of_date == "2026-08-20"
    assert parsed.legal_effective_date == "2026-08-10"
    assert parsed.query_reference_date == "2026-08-20"


def test_parse_query_ignores_invalid_explicit_date() -> None:
    parsed = parse_query(
        ChatRequest(
            query="Ngày 32/13/2026 xe máy vượt đèn đỏ bị phạt bao nhiêu?",
            event_date=date(2026, 8, 10),
        )
    )

    assert parsed.event_date == "2026-08-10"
    assert parsed.legal_effective_date == "2026-08-10"
