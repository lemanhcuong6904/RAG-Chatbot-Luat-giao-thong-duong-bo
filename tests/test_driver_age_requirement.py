from __future__ import annotations

from pathlib import Path

from rag_luat_gt.generation.answerer import build_answer
from rag_luat_gt.ingestion.build_index import build_index
from rag_luat_gt.retrieval.query_parser import parse_query
from rag_luat_gt.schemas import ChatRequest, Chunk, ParsedQuery
from rag_luat_gt.service import RAGService


def test_driver_age_requirement_uses_eligibility_source() -> None:
    root = Path(".").resolve()
    build_index(root / "data" / "markdown", root, invalidate_dense=False)

    response = RAGService().answer(
        ChatRequest(query="Người từ bao nhiêu tuổi được phép điều khiển ô tô?", top_k=8, debug=True)
    )

    assert response.answerable
    assert "18" in response.answer
    assert any(
        citation.document_number == "36/2024/QH15" and citation.article == "59"
        for citation in response.citations[:5]
    )
    assert not (
        response.citations
        and response.citations[0].document_number == "168/2024/NĐ-CP"
        and response.citations[0].article == "18"
    )


def test_16_year_old_cannot_drive_125cc_motorcycle() -> None:
    response = RAGService().answer(
        ChatRequest(query="Người 16 tuổi có được lái xe máy 125 cm³ không?", top_k=12, debug=True)
    )

    assert response.answerable
    assert "chưa được phép" in response.answer
    assert "125 cm3" in response.answer
    assert "hạng A1" in response.answer
    assert "18 tuổi" in response.answer
    assert any(
        citation.document_number == "36/2024/QH15" and citation.article == "57" and citation.point == "a"
        for citation in response.citations
    )
    assert any(
        citation.document_number == "36/2024/QH15" and citation.article == "59" and citation.point == "b"
        for citation in response.citations
    )
    assert response.debug
    assert response.debug.get("capacity_age_reasoning") is True


def test_eligibility_question_rejects_sanction_only_evidence() -> None:
    parsed = ParsedQuery(
        query="Người từ bao nhiêu tuổi được phép điều khiển ô tô?",
        normalized_query="nguoi tu bao nhieu tuoi duoc phep dieu khien o to",
        intent="DRIVER_AGE_REQUIREMENT",
        desired_rule_function="ELIGIBILITY",
    )
    sanction_chunk = Chunk(
        chunk_id="sanction",
        document_id="nd168",
        document_number="168/2024/NĐ-CP",
        article="18",
        clause="1",
        text="Phạt tiền đối với người từ đủ 16 tuổi đến dưới 18 tuổi điều khiển xe ô tô.",
        retrieval_text="Phạt tiền đối với người từ đủ 16 tuổi đến dưới 18 tuổi điều khiển xe ô tô.",
        source_file="source.md",
    )

    response = build_answer(parsed, [(sanction_chunk, 10.0)])

    assert not response.answerable
    assert any("xử phạt không chứng minh hành vi được phép" in warning for warning in response.warnings)
