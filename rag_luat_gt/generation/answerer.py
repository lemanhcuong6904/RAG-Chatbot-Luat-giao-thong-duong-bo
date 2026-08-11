from __future__ import annotations

from rag_luat_gt.config import OPENAI_API_KEY, RAG_LLM_PROVIDER
from rag_luat_gt.generation.openai_provider import generate_with_openai
from rag_luat_gt.legal_notes import legal_notes
from rag_luat_gt.schemas import ChatResponse, Citation, Chunk, ParsedQuery


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
        score=score,
    )


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
    date_line = parsed.event_date or parsed.as_of_date or "ngày hiện tại"
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
        f"Truy vấn đang xét theo ngày {parsed.event_date or parsed.as_of_date or 'hiện tại'}.\n\n"
        "### Lưu ý\n"
        f"{note_text}"
    )
