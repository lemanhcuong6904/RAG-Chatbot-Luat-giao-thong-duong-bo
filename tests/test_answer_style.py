from __future__ import annotations

from rag_luat_gt.generation.answerer import build_answer
from rag_luat_gt.retrieval.query_parser import parse_query
from rag_luat_gt.schemas import ChatRequest, Chunk, ParsedQuery
from rag_luat_gt.service import RAGService
from rag_luat_gt.structured_facts import build_structured_fact_answer


def _chunk(
    *,
    chunk_id: str,
    text: str,
    document_number: str,
    document_title: str,
    article: str,
    clause: str | None = None,
    point: str | None = None,
    chunk_type: str = "POINT",
    article_title: str = "Xử phạt vi phạm hành chính",
    rule_function: str = "SANCTION",
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        chunk_type=chunk_type,
        document_id=document_number,
        document_number=document_number,
        document_title=document_title,
        article=article,
        article_title=article_title,
        clause=clause,
        point=point,
        text=text,
        retrieval_text=text,
        source_file="test.md",
        rule_function=rule_function,
        coverage_status="COMPLETE",
        source_quality="TEST",
    )


def test_extractive_yes_no_answer_is_direct_and_filters_irrelevant_sources() -> None:
    parsed = ParsedQuery(
        query="Đang lái xe trên đường có được cầm điện thoại để sử dụng không?",
        normalized_query="dang lai xe tren duong co duoc cam dien thoai de su dung khong",
    )
    phone = _chunk(
        chunk_id="phone",
        document_number="168/2024/NĐ-CP",
        document_title="Nghị định số 168/2024/NĐ-CP",
        article="6",
        clause="5",
        point="h",
        text="h) Dùng tay cầm và sử dụng điện thoại hoặc các thiết bị điện tử khác khi điều khiển phương tiện tham gia giao thông đang di chuyển trên đường bộ;",
    )
    taxi = _chunk(
        chunk_id="taxi",
        document_number="158/2024/NĐ-CP",
        document_title="Nghị định số 158/2024/NĐ-CP",
        article="6",
        clause="4",
        point=None,
        text="Cước chuyến đi thông qua sử dụng phần mềm tính tiền có kết nối trực tiếp với hành khách.",
        chunk_type="CLAUSE",
    )

    response = build_answer(parsed, [(phone, 1.0), (taxi, 0.9)])

    assert response.answer.startswith("Không.")
    assert "điện thoại" in response.answer
    assert "158/2024/NĐ-CP" not in response.answer
    assert "[Nghị định 168/2024/NĐ-CP, Điều 6, khoản 5, điểm h]" in response.answer


def test_extractive_effective_date_answer_is_direct() -> None:
    parsed = ParsedQuery(
        query="Ngày 14/08/2026 Nghị định 238/2026/NĐ-CP đã có hiệu lực chưa?",
        normalized_query="ngay 14/08/2026 nghi dinh 238/2026/nd-cp da co hieu luc chua",
    )
    effective = _chunk(
        chunk_id="effective",
        document_number="238/2026/NĐ-CP",
        document_title="Nghị định số 238/2026/NĐ-CP",
        article="20",
        clause="1",
        point=None,
        chunk_type="CLAUSE",
        article_title="Hiệu lực thi hành",
        rule_function="TEMPORAL_RULE",
        text="1. Nghị định này có hiệu lực thi hành từ ngày 15 tháng 8 năm 2026.",
    )

    response = build_answer(parsed, [(effective, 1.0)])

    assert response.answer.startswith("Chưa.")
    assert "[Nghị định 238/2026/NĐ-CP, Điều 20, khoản 1]" in response.answer


def test_common_traffic_questions_use_direct_structured_answers() -> None:
    cases = [
        (
            "Đã uống rượu bia thì có mức nồng độ cồn nào vẫn được phép lái xe không?",
            "Không.",
            "[Luật 36/2024/QH15, Điều 9, khoản 2]",
        ),
        (
            "Khi hiệu lệnh của CSGT, đèn tín hiệu và biển báo khác nhau thì phải ưu tiên chấp hành theo thứ tự nào?",
            "Thứ tự ưu tiên là:",
            "[Luật 36/2024/QH15, Điều 11, khoản 2]",
        ),
        (
            "Gặp đèn vàng thì phải xử lý thế nào?",
            "Gặp đèn vàng thì phải dừng trước vạch dừng.",
            "[Luật 36/2024/QH15, Điều 11, khoản 4, điểm b]",
        ),
        (
            "Khi nào được phép bấm còi?",
            "Chỉ được bấm còi",
            "[Luật 36/2024/QH15, Điều 21, khoản 1]",
        ),
        (
            "Trước khi rẽ hoặc quay đầu xe cần làm những gì?",
            "Trước khi rẽ hoặc quay đầu",
            "[Luật 36/2024/QH15, Điều 15, khoản 2]",
        ),
    ]

    for query, expected_start, expected_ref in cases:
        response = build_structured_fact_answer(parse_query(_request(query)))

        assert response is not None
        assert response.answer.startswith(expected_start)
        assert expected_ref in response.answer
        assert "[SOURCE" not in response.answer
        assert "###" not in response.answer


def test_service_appends_missing_citation_for_structured_clause_answer() -> None:
    response = RAGService().answer(
        ChatRequest(
            query="Xe chạy chậm hơn các xe khác thì nên đi ở phía nào của đường?",
            debug=True,
            pre_rag_enabled=False,
        )
    )

    assert response.answerable
    assert response.answer.endswith("[Luật 36/2024/QH15, Điều 13, khoản 1].")


def _request(query: str):
    from rag_luat_gt.schemas import ChatRequest

    return ChatRequest(query=query)
