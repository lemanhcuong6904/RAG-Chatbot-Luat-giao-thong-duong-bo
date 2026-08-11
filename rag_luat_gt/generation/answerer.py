from __future__ import annotations

from rag_luat_gt.config import OPENAI_API_KEY, RAG_LLM_PROVIDER
from rag_luat_gt.generation.openai_provider import generate_with_openai
from rag_luat_gt.legal_notes import legal_notes
from rag_luat_gt.schemas import ChatResponse, Citation, Chunk, ParsedQuery
from rag_luat_gt.text import normalize_text, strip_accents, tokenize


def _legal_ref(citation: Citation) -> str:
    parts = []
    if citation.article:
        text = f"Điều {citation.article}"
        if citation.article_title:
            text += f" ({citation.article_title})"
        parts.append(text)
    if citation.clause:
        parts.append(f"Khoản {citation.clause}")
    if citation.point:
        parts.append(f"Điểm {citation.point}")
    return " - ".join(parts) if parts else "Không xác định điều khoản"


def _citation_from_result(chunk: Chunk, score: float) -> Citation:
    return Citation(
        chunk_id=chunk.chunk_id,
        document_number=chunk.document_number,
        document_title=chunk.document_title,
        article=chunk.article,
        article_title=chunk.article_title,
        clause=chunk.clause,
        point=chunk.point,
        source_file=chunk.source_file,
        text=chunk.text,
        coverage_status=chunk.coverage_status,
        source_quality=chunk.source_quality,
        score=score,
    )


def _evidence_gate(
    parsed: ParsedQuery,
    results: list[tuple[Chunk, float]],
) -> tuple[bool, list[str]]:
    notes: list[str] = []
    if not results:
        return False, ["Không tìm thấy nguồn phù hợp trong index."]

    query = strip_accents(normalize_text(parsed.normalized_query))
    query_tokens = {token for token in tokenize(query) if len(token) >= 3}
    evidence_tokens = {
        token
        for chunk, _score in results[:5]
        for token in tokenize(strip_accents(normalize_text(chunk.retrieval_text)))
        if len(token) >= 3
    }
    overlap = len(query_tokens & evidence_tokens) / max(len(query_tokens), 1)

    has_legal_ref = any([parsed.document_number, parsed.article, parsed.clause, parsed.point])
    if overlap < 0.12 and not has_legal_ref:
        notes.append("Độ khớp giữa câu hỏi và nguồn truy xuất quá thấp.")

    asks_amount = any(term in query for term in ["bao nhieu", "muc phat", "phat bao nhieu", "dong"])
    has_amount_evidence = any(
        "đồng" in chunk.text.lower() or "dong" in strip_accents(normalize_text(chunk.text))
        for chunk, _score in results[:5]
    )
    if parsed.intent == "PENALTY_LOOKUP" and asks_amount and not has_amount_evidence:
        notes.append("Nguồn truy xuất chưa có mức tiền phạt cụ thể.")

    asks_missing_appendix = any(term in query for term in ["phu luc", "bieu mau", "mau so", "bang"])
    weak_coverage = [
        chunk.coverage_status
        for chunk, _score in results[:5]
        if chunk.coverage_status in {"MISSING_APPENDIX", "MISSING_TABLE", "MISSING_PAGES", "PARTIAL"}
    ]
    if asks_missing_appendix and weak_coverage:
        notes.append(
            "Corpus hiện có nguồn không đầy đủ cho phần phụ lục/bảng/trang được hỏi: "
            + ", ".join(sorted(set(weak_coverage)))
            + "."
        )

    return not notes, notes


def _build_extractive_answer(
    parsed: ParsedQuery,
    results: list[tuple[Chunk, float]],
    citations: list[Citation],
    legal_notes: list[str],
) -> str:
    evidence = "\n\n".join(
        f"- {_legal_ref(citations[index])}: {chunk.text[:900]}"
        for index, (chunk, _score) in enumerate(results[:3])
    )
    refs = "\n".join(
        f"{index + 1}. {citation.document_number or citation.document_title}: {_legal_ref(citation)}"
        for index, citation in enumerate(citations[:5])
    )
    date_line = parsed.legal_effective_date or parsed.event_date or parsed.as_of_date or "ngày hiện tại"
    notes = "\n".join(f"- {note}" for note in legal_notes)
    note_block = f"\n\n{notes}" if notes else ""

    return (
        "### Trả lời\n"
        "Dưới đây là các căn cứ liên quan nhất tìm được trong corpus.\n\n"
        f"{evidence}\n\n"
        "### Căn cứ pháp lý\n"
        f"{refs}\n\n"
        "### Thời điểm áp dụng\n"
        f"Kết quả đã lọc sơ bộ theo ngày {date_line} dựa trên metadata hiệu lực cấp văn bản/chunk."
        f"{note_block}\n\n"
        "### Lưu ý\n"
        "Với câu hỏi về mức phạt hoặc quy định có văn bản sửa đổi, cần kiểm tra kỹ các nguồn được dẫn."
    )


def build_answer(parsed: ParsedQuery, results: list[tuple[Chunk, float]]) -> ChatResponse:
    if not results:
        return ChatResponse(
            answer=(
                "Tôi chưa đủ căn cứ trong bộ dữ liệu hiện tại để trả lời chính xác. "
                "Bạn có thể nêu rõ văn bản, điều khoản, loại phương tiện hoặc ngày xảy ra hành vi."
            ),
            citations=[],
            warnings=["Không tìm thấy nguồn phù hợp trong index."],
            answerable=False,
        )

    citations = [_citation_from_result(chunk, score) for chunk, score in results]
    notes = legal_notes(parsed, results)
    warnings = []

    gate_passed, gate_notes = _evidence_gate(parsed, results)
    if not gate_passed:
        all_notes = [*notes, *gate_notes]
        return ChatResponse(
            answer=_build_insufficient_evidence_answer(parsed, citations, all_notes),
            citations=citations,
            warnings=all_notes,
            answerable=False,
            debug={"parsed_query": parsed.model_dump(), "legal_notes": all_notes},
        )

    missing_amount = any("không đủ căn cứ để kết luận con số cụ thể" in note for note in notes)
    if missing_amount:
        return ChatResponse(
            answer=_build_missing_amount_answer(parsed, citations, notes),
            citations=citations,
            warnings=notes,
            answerable=False,
            debug={"parsed_query": parsed.model_dump(), "legal_notes": notes},
        )

    if RAG_LLM_PROVIDER == "openai" and OPENAI_API_KEY:
        try:
            answer = generate_with_openai(parsed, results[:6], notes)
        except Exception as exc:
            warnings.append(f"OpenAI generation failed, used extractive fallback: {exc}")
            answer = _build_extractive_answer(parsed, results, citations, notes)
    else:
        if RAG_LLM_PROVIDER == "openai":
            warnings.append("OPENAI_API_KEY is empty, used extractive fallback.")
        answer = _build_extractive_answer(parsed, results, citations, notes)

    return ChatResponse(
        answer=answer,
        citations=citations,
        warnings=warnings,
        answerable=True,
        debug={"parsed_query": parsed.model_dump(), "legal_notes": notes},
    )


def _build_missing_amount_answer(
    parsed: ParsedQuery,
    citations: list[Citation],
    notes: list[str],
) -> str:
    refs = "\n".join(
        f"{index + 1}. {citation.document_number or citation.document_title}: {_legal_ref(citation)}"
        for index, citation in enumerate(citations[:5])
    )
    note_text = "\n".join(f"- {note}" for note in notes)
    return (
        "### Trả lời\n"
        "Tôi chưa đủ căn cứ trong bộ dữ liệu hiện tại để xác định mức tiền cụ thể cho câu hỏi này.\n\n"
        "### Căn cứ pháp lý\n"
        f"{refs}\n\n"
        "### Thời điểm áp dụng\n"
        f"Truy vấn đang xét theo ngày {parsed.legal_effective_date or parsed.event_date or parsed.as_of_date or 'hiện tại'}.\n\n"
        "### Lưu ý\n"
        f"{note_text}"
    )


def _build_insufficient_evidence_answer(
    parsed: ParsedQuery,
    citations: list[Citation],
    notes: list[str],
) -> str:
    refs = "\n".join(
        f"{index + 1}. {citation.document_number or citation.document_title}: {_legal_ref(citation)}"
        for index, citation in enumerate(citations[:5])
    )
    note_text = "\n".join(f"- {note}" for note in notes)
    return (
        "### Trả lời\n"
        "Tôi chưa đủ căn cứ trong bộ dữ liệu hiện tại để trả lời chắc chắn câu hỏi này.\n\n"
        "### Căn cứ pháp lý\n"
        f"{refs or 'Không có nguồn đủ mạnh.'}\n\n"
        "### Thời điểm áp dụng\n"
        f"Đang xét theo ngày hiệu lực pháp lý {parsed.legal_effective_date or 'hiện tại'}.\n\n"
        "### Lưu ý\n"
        f"{note_text}"
    )
