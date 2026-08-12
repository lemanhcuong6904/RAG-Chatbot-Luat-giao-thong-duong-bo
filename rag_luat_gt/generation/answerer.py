from __future__ import annotations

import re

from rag_luat_gt.config import OPENAI_API_KEY, RAG_LLM_PROVIDER, RAG_REQUIRE_LLM
from rag_luat_gt.generation.openai_provider import generate_with_openai
from rag_luat_gt.legal_notes import legal_notes
from rag_luat_gt.rule_function import effective_rule_function
from rag_luat_gt.schemas import ChatResponse, Citation, Chunk, ParsedQuery
from rag_luat_gt.text import normalize_text, strip_accents, tokenize


def _legal_ref(citation: Citation) -> str:
    if citation.chunk_type == "APPENDIX":
        return "Phụ lục"

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
        chunk_type=chunk.chunk_type,
        document_number=chunk.document_number,
        document_title=chunk.document_title,
        article=chunk.article,
        article_title=chunk.article_title,
        clause=chunk.clause,
        point=chunk.point,
        parent_id=chunk.parent_id,
        sibling_group_id=chunk.sibling_group_id,
        source_file=chunk.source_file,
        text=chunk.text,
        rule_function=effective_rule_function(chunk.rule_function, chunk.text, chunk.article_title),
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

    query = strip_accents(normalize_text(parsed.evidence_validation_query or parsed.query))
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

    if parsed.desired_rule_function == "ELIGIBILITY":
        top_functions = [
            effective_rule_function(chunk.rule_function, chunk.text, chunk.article_title)
            for chunk, _score in results[:6]
        ]
        has_positive_basis = "ELIGIBILITY" in top_functions
        only_sanction_basis = bool(top_functions) and all(rule_function == "SANCTION" for rule_function in top_functions)
        if not has_positive_basis:
            notes.append("Chưa tìm thấy quy định trực tiếp xác lập điều kiện được phép.")
        if only_sanction_basis:
            notes.append(
                "Nguồn truy xuất chỉ chứa quy định xử phạt; quy định xử phạt không chứng minh hành vi được phép."
            )

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
    if parsed.intent == "PENALTY_LOOKUP" and not parsed.vehicle_code and _has_vehicle_scope_note(legal_notes):
        return _build_vehicle_scope_answer(parsed, citations, legal_notes)

    evidence_limit = 30 if parsed.retrieval_mode == "EXHAUSTIVE" else 3
    refs_limit = 30 if parsed.retrieval_mode == "EXHAUSTIVE" else 5
    evidence = "\n\n".join(
        f"- {_legal_ref(citations[index])}: {chunk.text[:900]}"
        for index, (chunk, _score) in enumerate(results[:evidence_limit])
    )
    refs = "\n".join(
        f"{index + 1}. {citation.document_number or citation.document_title}: {_legal_ref(citation)}"
        for index, citation in enumerate(citations[:refs_limit])
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


def _exact_reference_target(parsed: ParsedQuery, citations: list[Citation]) -> Citation | None:
    if not parsed.document_number or not parsed.article:
        return None

    def matches(citation: Citation) -> bool:
        if citation.document_number != parsed.document_number:
            return False
        if citation.article != parsed.article:
            return False
        if parsed.clause and citation.clause != parsed.clause:
            return False
        if parsed.point and citation.point != parsed.point:
            return False
        return True

    exact = [citation for citation in citations if matches(citation)]
    if not exact:
        return None
    if parsed.point:
        return next((citation for citation in exact if citation.chunk_type == "POINT"), exact[0])
    if parsed.clause:
        return next((citation for citation in exact if citation.chunk_type == "CLAUSE"), exact[0])
    return next((citation for citation in exact if citation.chunk_type == "ARTICLE"), exact[0])


def _build_exact_reference_answer(parsed: ParsedQuery, citations: list[Citation]) -> str | None:
    target = _exact_reference_target(parsed, citations)
    if not target:
        return None

    label_parts = []
    if target.point:
        label_parts.append(f"Điểm {target.point}")
    if target.clause:
        label_parts.append(f"Khoản {target.clause}")
    if target.article:
        label_parts.append(f"Điều {target.article}")
    label = " ".join(label_parts) or "Quy định được hỏi"
    ref = _short_ref(target)
    return (
        "### Trả lời\n"
        f"{label} {target.document_number or target.document_title} quy định:\n\n"
        f"{target.text.strip()} [{ref}]\n\n"
        "### Căn cứ pháp lý\n"
        f"1. {ref}"
    )


def _has_vehicle_scope_note(notes: list[str]) -> bool:
    return any("chưa nêu rõ loại phương tiện" in note for note in notes)


def _build_vehicle_scope_answer(
    parsed: ParsedQuery,
    citations: list[Citation],
    notes: list[str],
) -> str:
    grouped: dict[str, list[Citation]] = {}
    for citation in citations:
        if citation.document_number != "168/2024/NĐ-CP" or citation.article not in {"6", "7", "8", "9"}:
            continue
        grouped.setdefault(citation.article or "", []).append(citation)

    labels = {
        "6": "ô tô và xe tương tự ô tô",
        "7": "mô tô, xe gắn máy và xe tương tự",
        "8": "xe máy chuyên dùng",
        "9": "xe thô sơ",
    }
    lines: list[str] = []
    for article in sorted(grouped, key=int):
        points = [
            item
            for item in grouped[article]
            if item.chunk_type == "POINT" and item.clause and _citation_matches_query_focus(parsed, item)
        ]
        points_by_clause: dict[str, list[Citation]] = {}
        for point in points:
            points_by_clause.setdefault(point.clause or "", []).append(point)

        for clause_no, clause_points in sorted(points_by_clause.items(), key=lambda item: _numeric_key(item[0])):
            clause = next(
                (
                    item
                    for item in grouped[article]
                    if item.chunk_type == "CLAUSE" and item.clause == clause_no
                ),
                None,
            )
            if not clause:
                continue
            point_refs = ", ".join(f"Điểm {point.point}" for point in clause_points if point.point)
            citation_refs = "; ".join(_short_ref(point) for point in clause_points)
            lines.append(
                f"- **{labels.get(article, 'nhóm phương tiện liên quan')}**: "
                f"{_extract_fine_text(clause.text)}"
                f"{' (' + point_refs + ')' if point_refs else ''} [{citation_refs}]."
            )

    note_text = "\n".join(f"- {note}" for note in notes)
    date_line = parsed.legal_effective_date or parsed.event_date or parsed.as_of_date or "ngày hiện tại"
    return (
        "### Trả lời\n"
        "Câu hỏi chưa nêu rõ loại phương tiện, nên mức xử phạt cần tách theo từng nhóm xe:\n\n"
        f"{chr(10).join(lines) if lines else 'Chưa đủ nguồn trực tiếp để trình bày từng nhánh.'}\n\n"
        "### Thời điểm áp dụng\n"
        f"Đang xét theo ngày hiệu lực pháp lý {date_line}.\n\n"
        "### Lưu ý\n"
        f"{note_text}"
    )


def _numeric_key(value: str) -> tuple[int, str]:
    return (int(value), value) if value.isdigit() else (999, value)


def _extract_fine_text(text: str) -> str:
    match = re.search(r"Phạt tiền từ\s+[\d.]+\s+đồng\s+đến\s+[\d.]+\s+đồng", text, flags=re.IGNORECASE)
    if match:
        return match.group(0)
    first_sentence = re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)[0]
    return first_sentence.rstrip(".")


def _short_ref(citation: Citation) -> str:
    parts = [citation.document_number or citation.document_title or "Nguồn"]
    if citation.article:
        parts.append(f"Điều {citation.article}")
    if citation.clause:
        parts.append(f"Khoản {citation.clause}")
    if citation.point:
        parts.append(f"Điểm {citation.point}")
    return ", ".join(parts)


def _vehicle_scope_citations(parsed: ParsedQuery, citations: list[Citation]) -> list[Citation]:
    grouped: dict[str, list[Citation]] = {}
    for citation in citations:
        if citation.document_number != "168/2024/NĐ-CP" or citation.article not in {"6", "7", "8", "9"}:
            continue
        grouped.setdefault(citation.article or "", []).append(citation)

    selected: list[Citation] = []
    seen: set[str] = set()
    for article in sorted(grouped, key=int):
        points = [
            item
            for item in grouped[article]
            if item.chunk_type == "POINT" and item.clause and _citation_matches_query_focus(parsed, item)
        ]
        points_by_clause: dict[str, list[Citation]] = {}
        for point in points:
            points_by_clause.setdefault(point.clause or "", []).append(point)

        for clause_no, clause_points in sorted(points_by_clause.items(), key=lambda item: _numeric_key(item[0])):
            clause = next(
                (
                    item
                    for item in grouped[article]
                    if item.chunk_type == "CLAUSE" and item.clause == clause_no
                ),
                None,
            )
            for item in [clause, *clause_points]:
                if item and item.chunk_id not in seen:
                    selected.append(item)
                    seen.add(item.chunk_id)

    return selected or citations


def _citation_matches_query_focus(parsed: ParsedQuery, citation: Citation) -> bool:
    query = strip_accents(normalize_text(parsed.query))
    text = strip_accents(normalize_text(citation.text))

    behavior_groups = [
        (["quay dau", "quay dau xe"], ["quay dau"]),
        (["lui xe"], ["lui xe"]),
        (["dien thoai", "thiet bi dien tu"], ["dien thoai", "thiet bi dien tu"]),
        (["mu bao hiem", "khong doi mu"], ["mu bao hiem"]),
        (["den do", "den tin hieu"], ["den tin hieu"]),
    ]
    condition_groups = [
        (["trong ham", "duong ham", "ham duong bo"], ["trong ham", "duong ham", "ham duong bo"]),
        (["cao toc", "duong cao toc"], ["cao toc", "duong cao toc"]),
        (["via he", "le duong", "long duong"], ["via he", "le duong", "long duong"]),
        (["duong sat", "giao nhau voi duong sat"], ["duong sat", "giao nhau voi duong sat"]),
    ]

    behavior_terms = [
        term
        for triggers, expansions in behavior_groups
        if any(trigger in query for trigger in triggers)
        for term in expansions
    ]
    condition_terms = [
        term
        for triggers, expansions in condition_groups
        if any(trigger in query for trigger in triggers)
        for term in expansions
    ]

    if behavior_terms and not any(term in text for term in behavior_terms):
        return False
    if condition_terms and not any(term in text for term in condition_terms):
        return False
    return bool(behavior_terms or condition_terms)


def _format_vnd(value: int) -> str:
    return f"{value:,}".replace(",", ".") + " đồng"


def _parse_vnd_amount(value: str) -> int:
    return int(value.replace(".", ""))


def _a1_driving_test_fee_evidence(citations: list[Citation]) -> tuple[int, int, Citation] | None:
    for citation in citations:
        normalized = strip_accents(normalize_text(citation.text))
        if citation.document_number != "154/2025/TT-BTC":
            continue
        if not all(term in normalized for term in ["a1", "sat hach ly thuyet", "sat hach thuc hanh"]):
            continue

        block = citation.text
        start = re.search(r"Đối với thi sát hạch lái xe các hạng xe A1", block, flags=re.IGNORECASE)
        if start:
            block = block[start.start() :]
        end = re.search(r"\*\*b\)|Đối với thi sát hạch lái xe ô tô", block, flags=re.IGNORECASE)
        if end:
            block = block[: end.start()]

        theory = re.search(r"Sát hạch lý thuyết:\s*\*\*(\d{1,3}(?:\.\d{3})*)\s*đồng/lần\*\*", block)
        practice = re.search(r"Sát hạch thực hành:\s*\*\*(\d{1,3}(?:\.\d{3})*)\s*đồng/lần\*\*", block)
        if theory and practice:
            return _parse_vnd_amount(theory.group(1)), _parse_vnd_amount(practice.group(1)), citation
    return None


def _build_fee_lookup_answer(parsed: ParsedQuery, citations: list[Citation]) -> str | None:
    query = strip_accents(normalize_text(parsed.query))
    if parsed.intent != "FEE_LOOKUP":
        return None
    if "sat hach" not in query or "a1" not in query:
        return None
    if not any(term in query for term in ["tong", "bao nhieu", "muc"]):
        return None

    evidence = _a1_driving_test_fee_evidence(citations)
    if not evidence:
        return None

    theory_fee, practice_fee, citation = evidence
    total = theory_fee + practice_fee
    date_line = parsed.legal_effective_date or parsed.event_date or parsed.as_of_date or "hiện tại"
    return (
        "### Trả lời\n"
        f"Thi sát hạch lái xe hạng A1 gồm phí sát hạch lý thuyết {_format_vnd(theory_fee)}/lần "
        f"và phí sát hạch thực hành {_format_vnd(practice_fee)}/lần. Nếu phải nộp cả hai phần, "
        f"tổng phí là {_format_vnd(total)}.\n\n"
        "### Căn cứ pháp lý\n"
        f"1. {citation.document_number or citation.document_title}: {_legal_ref(citation)}\n\n"
        "### Thời điểm áp dụng\n"
        f"Đang xét theo ngày {date_line}.\n\n"
        "### Lưu ý\n"
        "- Trong Thông tư 154/2025/TT-BTC, khoản này được gọi là phí sát hạch lái xe, không phải lệ phí cấp giấy phép lái xe.\n"
        "- Người dự sát hạch phần nào thì nộp phí phần đó."
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
    llm_configured = RAG_LLM_PROVIDER == "openai" and bool(OPENAI_API_KEY)

    exact_answer = _build_exact_reference_answer(parsed, citations)
    if exact_answer and not llm_configured:
        return ChatResponse(
            answer=exact_answer,
            citations=citations,
            warnings=warnings,
            answerable=True,
            debug={"parsed_query": parsed.model_dump(), "legal_notes": notes, "exact_reference_lookup": True},
        )

    if parsed.intent == "PENALTY_LOOKUP" and not parsed.vehicle_code and _has_vehicle_scope_note(notes) and not llm_configured:
        scoped_citations = _vehicle_scope_citations(parsed, citations)
        return ChatResponse(
            answer=_build_vehicle_scope_answer(parsed, scoped_citations, notes),
            citations=scoped_citations,
            warnings=notes,
            answerable=True,
            debug={"parsed_query": parsed.model_dump(), "legal_notes": notes, "vehicle_scope_split": True},
        )

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

    fee_answer = _build_fee_lookup_answer(parsed, citations)
    if fee_answer and not llm_configured:
        return ChatResponse(
            answer=fee_answer,
            citations=citations,
            warnings=warnings,
            answerable=True,
            debug={"parsed_query": parsed.model_dump(), "legal_notes": notes, "fee_lookup": {"resolved": True}},
        )

    if RAG_LLM_PROVIDER == "openai" and OPENAI_API_KEY:
        try:
            llm_limit = 30 if parsed.retrieval_mode == "EXHAUSTIVE" or parsed.answer_mode == "ENUMERATION" else 6
            answer = generate_with_openai(parsed, results[:llm_limit], notes)
        except Exception as exc:
            if RAG_REQUIRE_LLM:
                error = f"OpenAI generation failed and RAG_REQUIRE_LLM=true: {exc}"
                return ChatResponse(
                    answer=_build_llm_required_error_answer(parsed, citations, error),
                    citations=citations,
                    warnings=[*notes, error],
                    answerable=False,
                    debug={"parsed_query": parsed.model_dump(), "legal_notes": notes, "llm_error": str(exc)},
            )
            warnings.append(f"OpenAI generation failed, used extractive fallback: {exc}")
            answer = exact_answer or _build_extractive_answer(parsed, results, citations, notes)
    else:
        if RAG_LLM_PROVIDER == "openai":
            warning = "OPENAI_API_KEY is empty, used extractive fallback."
            if RAG_REQUIRE_LLM:
                return ChatResponse(
                    answer=_build_llm_required_error_answer(parsed, citations, "OPENAI_API_KEY is not configured."),
                    citations=citations,
                    warnings=[*notes, "OPENAI_API_KEY is not configured."],
                    answerable=False,
                    debug={
                        "parsed_query": parsed.model_dump(),
                        "legal_notes": notes,
                        "llm_error": "OPENAI_API_KEY is not configured.",
                    },
                )
            warnings.append(warning)
        answer = exact_answer or _build_extractive_answer(parsed, results, citations, notes)

    return ChatResponse(
        answer=answer,
        citations=citations,
        warnings=warnings,
        answerable=True,
        debug={"parsed_query": parsed.model_dump(), "legal_notes": notes, "exact_reference_lookup": bool(exact_answer)},
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


def _build_llm_required_error_answer(
    parsed: ParsedQuery,
    citations: list[Citation],
    error: str,
) -> str:
    refs = "\n".join(
        f"{index + 1}. {citation.document_number or citation.document_title}: {_legal_ref(citation)}"
        for index, citation in enumerate(citations[:5])
    )
    return (
        "### Trả lời\n"
        "Hệ thống đang được cấu hình bắt buộc sinh câu trả lời bằng LLM, nhưng bước gọi LLM chưa thực hiện được. "
        "Tôi không trả fallback trích xuất để tránh tạo cảm giác đây là câu trả lời đã được diễn đạt hoàn chỉnh.\n\n"
        "### Căn cứ pháp lý đã truy xuất\n"
        f"{refs or 'Không có nguồn đủ mạnh.'}\n\n"
        "### Thời điểm áp dụng\n"
        f"Đang xét theo ngày {parsed.legal_effective_date or parsed.event_date or parsed.as_of_date or 'hiện tại'}.\n\n"
        "### Lưu ý\n"
        f"- Lỗi LLM: {error}"
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
