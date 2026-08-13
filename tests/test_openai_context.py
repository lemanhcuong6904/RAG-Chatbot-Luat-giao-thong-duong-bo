from __future__ import annotations

from rag_luat_gt.generation.openai_provider import _context_from_chunks
from rag_luat_gt.schemas import Chunk, ParsedQuery


def test_openai_context_contains_legal_fields_without_retrieval_scores() -> None:
    parsed = ParsedQuery(
        query="q",
        normalized_query="q",
        primary_intent="LEGAL_QA",
        answer_mode="ENUMERATION",
        actor="DRIVER",
        vehicle_code="MOTORCYCLE",
        behavior_code="WRONG_LANE",
        conditions=["CAUSES_ACCIDENT"],
        event_date="2026-08-11",
        legal_effective_date="2026-08-11",
        as_of_date="2026-08-12",
    )
    parent = Chunk(
        chunk_id="parent",
        chunk_type="CLAUSE",
        document_id="doc",
        document_number="36/2024/QH15",
        article="7",
        clause="1",
        children_ids=["child"],
        text="Khoan 1",
        retrieval_text="Khoan 1",
        source_file="source.md",
        coverage_status="COMPLETE",
        source_quality="VERIFIED_METADATA",
    )
    child = Chunk(
        chunk_id="child",
        chunk_type="POINT",
        document_id="doc",
        document_number="36/2024/QH15",
        article="7",
        clause="1",
        point="a",
        text="Diem a",
        retrieval_text="Diem a",
        source_file="source.md",
        coverage_status="COMPLETE",
        source_quality="VERIFIED_METADATA",
        metadata={"temporal_status": "ACTIVE"},
    )

    context = _context_from_chunks(parsed, [(parent, 99.0), (child, 88.0)])

    assert "QUERY_INTENT: LEGAL_QA" in context
    assert "ANSWER_MODE: ENUMERATION" in context
    assert "EVENT_DATE: 2026-08-11" in context
    assert "EXPANSION_STATUS: COMPLETE" in context
    assert "[LEGAL_GROUP 1]" in context
    assert "group_sources: SOURCE 1, SOURCE 2" in context
    assert "parent_sources: SOURCE 1" in context
    assert "child_or_point_sources: SOURCE 2" in context
    assert "group_contract: Only combine sanctions" in context
    assert "document_number: 36/2024/QH15" in context
    assert "temporal_status: ACTIVE" in context
    assert "score:" not in context
    assert "chunk_id:" not in context
    assert "parent_id:" not in context
    assert "sibling_group_id:" not in context


def test_openai_context_separates_different_vehicle_articles_into_groups() -> None:
    parsed = ParsedQuery(
        query="Vượt đèn đỏ bị trừ bao nhiêu điểm?",
        normalized_query="Vượt đèn đỏ bị trừ bao nhiêu điểm?",
        intent="PENALTY_LOOKUP",
    )
    car_point = Chunk(
        chunk_id="car-point",
        chunk_type="POINT",
        document_id="nd168",
        document_number="168/2024/NĐ-CP",
        article="6",
        article_title="Xử phạt người điều khiển xe ô tô vi phạm quy tắc giao thông đường bộ",
        clause="9",
        point="b",
        text="Không chấp hành hiệu lệnh của đèn tín hiệu giao thông; trừ 4 điểm GPLX.",
        retrieval_text="Không chấp hành hiệu lệnh của đèn tín hiệu giao thông; trừ 4 điểm GPLX.",
        source_file="source.md",
    )
    motorcycle_point = Chunk(
        chunk_id="motorcycle-point",
        chunk_type="POINT",
        document_id="nd168",
        document_number="168/2024/NĐ-CP",
        article="7",
        article_title="Xử phạt người điều khiển xe mô tô, xe gắn máy vi phạm quy tắc giao thông đường bộ",
        clause="7",
        point="c",
        text="Không chấp hành hiệu lệnh của đèn tín hiệu giao thông; trừ 4 điểm GPLX.",
        retrieval_text="Không chấp hành hiệu lệnh của đèn tín hiệu giao thông; trừ 4 điểm GPLX.",
        source_file="source.md",
    )

    context = _context_from_chunks(parsed, [(car_point, 2.0), (motorcycle_point, 1.9)])

    assert "[LEGAL_GROUP 1]" in context
    assert "[LEGAL_GROUP 2]" in context
    assert "group_sources: SOURCE 1" in context
    assert "group_sources: SOURCE 2" in context
    assert "article: 6" in context
    assert "article: 7" in context


def test_factoid_openai_context_does_not_report_partial_expansion() -> None:
    parsed = ParsedQuery(
        query="q",
        normalized_query="q",
        answer_mode="FACTOID",
        retrieval_mode="FACTOID",
    )
    parent = Chunk(
        chunk_id="parent",
        chunk_type="CLAUSE",
        document_id="doc",
        document_number="168/2024/NĐ-CP",
        article="7",
        clause="4",
        children_ids=["child-a", "child-b"],
        text="4. Phạt tiền từ 800.000 đồng đến 1.000.000 đồng.",
        retrieval_text="4. Phạt tiền từ 800.000 đồng đến 1.000.000 đồng.",
        source_file="source.md",
    )

    context = _context_from_chunks(parsed, [(parent, 1.0)])

    assert "ANSWER_MODE: FACTOID" in context
    assert "EXPANSION_STATUS: COMPLETE" in context
    assert "EXPECTED_CHILD_COUNT: 0" in context
