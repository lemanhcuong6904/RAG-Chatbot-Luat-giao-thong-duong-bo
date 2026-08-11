from __future__ import annotations

from rag_luat_gt.retrieval.bm25 import BM25Retriever
from rag_luat_gt.sanction.repository import SanctionRepository
from rag_luat_gt.schemas import ChatRequest, ParsedQuery
from rag_luat_gt.service import RAGService


def test_sanction_repository_finds_motorcycle_red_light_rule() -> None:
    lookup = SanctionRepository().lookup(
        event_date="2026-08-11",
        vehicle_code="MOTORCYCLE",
        behavior_code="KHONG_CHAP_HANH_HIEU_LENH_CUA_DEN_TIN_HIEU_GIAO_THONG",
    )

    assert lookup.status == "FOUND"
    assert len(lookup.rules) == 1
    rule = lookup.rules[0]
    assert rule.document_number == "168/2024/NĐ-CP"
    assert rule.article == "7"
    assert rule.clause == "7"
    assert rule.point == "c"
    assert rule.fine_min == 4_000_000
    assert rule.fine_max == 6_000_000
    assert rule.license_points_deducted == 4


def test_service_uses_structured_sanction_layer_for_penalty_query() -> None:
    response = RAGService().answer(
        ChatRequest(query="Xe máy vượt đèn đỏ bị phạt bao nhiêu và trừ mấy điểm?", debug=True)
    )

    assert response.answerable
    assert "4.000.000 đồng" in response.answer
    assert "6.000.000 đồng" in response.answer
    assert "trừ 4 điểm" in response.answer
    assert response.citations[0].rule_id == "ND168_A07_K7_Pc_UNSPECIFIED_BASE"


def test_penalty_query_with_license_points_phrase_does_not_filter_by_point_g() -> None:
    response = RAGService().answer(
        ChatRequest(
            query="Người điều khiển xe máy vượt đèn đỏ bị phạt bao nhiêu tiền và bị trừ bao nhiêu điểm giấy phép lái xe?",
            debug=True,
        )
    )

    assert response.answerable
    assert "4.000.000 đồng" in response.answer
    assert "6.000.000 đồng" in response.answer
    assert "trừ 4 điểm" in response.answer
    assert response.debug
    assert response.debug["parsed_query"]["point"] is None


def test_penalty_query_without_vehicle_falls_back_to_rag() -> None:
    response = RAGService().answer(ChatRequest(query="Vượt đèn đỏ bị phạt bao nhiêu?", debug=True))

    assert response.answerable
    assert response.debug
    assert response.debug["routing"]["sanction_status"] == "NEEDS_CLARIFICATION"
    assert response.debug["routing"]["fallback_to_rag"] is True


def test_sanction_lookup_without_behavior_fails_closed() -> None:
    lookup = SanctionRepository().lookup(
        event_date="2026-08-16",
        vehicle_code="MOTORCYCLE",
    )

    assert lookup.status == "NOT_MAPPED"
    assert lookup.missing_fields == ["behavior"]


def test_sanction_lookup_respects_explicit_document_number() -> None:
    lookup = SanctionRepository().lookup(
        event_date="2026-08-11",
        vehicle_code="MOTORCYCLE",
        behavior_code="KHONG_CHAP_HANH_HIEU_LENH_CUA_DEN_TIN_HIEU_GIAO_THONG",
        document_number="165/2024/NĐ-CP",
    )

    assert lookup.status == "NOT_FOUND"


def test_deferred_sanction_rule_is_temporally_ambiguous_before_effective_date() -> None:
    lookup = SanctionRepository().lookup(
        event_date="2026-08-16",
        vehicle_code="CAR",
        behavior_code="DIEU_KHIEN_XE_KINH_DOANH_VAN_TAI_HANH_KHACH_XE_VAN_TAI_NOI_BO_KHONG_LAP_THIET_BI_GHI_NHAN_",
        document_number="168/2024/NĐ-CP",
        article="20",
        clause="5",
        point="l",
    )

    assert lookup.status == "TEMPORAL_AMBIGUOUS"
    assert lookup.rules[0].temporal_status == "DEFERRED"


def test_invalid_explicit_legal_reference_does_not_semantic_fallback() -> None:
    parsed = ParsedQuery(
        query="Khoản 99 Điều 6 Nghị định 168 quy định gì?",
        normalized_query="khoan 99 dieu 6 nghi dinh 168 quy dinh gi",
        document_number="168/2024/NĐ-CP",
        article="6",
        clause="99",
        legal_effective_date="2026-08-11",
    )

    assert BM25Retriever().search(parsed, top_k=5) == []
