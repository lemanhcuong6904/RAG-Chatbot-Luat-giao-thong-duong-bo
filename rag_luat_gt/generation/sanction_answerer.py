from __future__ import annotations

from rag_luat_gt.sanction.schemas import SanctionLookup, SanctionRule
from rag_luat_gt.schemas import ChatResponse, Citation, ParsedQuery


def _money(value: int | None) -> str:
    if value is None:
        return "không xác định"
    return f"{value:,}".replace(",", ".") + " đồng"


def _fine_text(rule: SanctionRule) -> str:
    if rule.primary_sanction_type == "WARNING":
        return "cảnh cáo"
    if rule.primary_sanction_type == "CONFISCATION":
        return "tịch thu"
    if rule.fine_min is not None and rule.fine_max is not None:
        if rule.fine_min == rule.fine_max:
            return _money(rule.fine_min)
        return f"từ {_money(rule.fine_min)} đến {_money(rule.fine_max)}"
    return "chưa xác định mức tiền"


def _rule_ref(rule: SanctionRule) -> str:
    parts = []
    if rule.article:
        parts.append(f"Điều {rule.article}")
    if rule.clause:
        parts.append(f"Khoản {rule.clause}")
    if rule.point:
        parts.append(f"Điểm {rule.point}")
    return " - ".join(parts) if parts else rule.source_location or "Không rõ điều khoản"


def _citation(rule: SanctionRule) -> Citation:
    text_parts = [part for part in [rule.parent_clause_text, rule.source_text] if part]
    return Citation(
        chunk_id=rule.source_chunk_id or rule.rule_id,
        chunk_type="SANCTION_RULE",
        rule_id=rule.rule_id,
        document_number=rule.document_number,
        document_title=rule.article_title,
        article=rule.article,
        article_title=rule.article_title,
        clause=rule.clause,
        point=rule.point,
        source_file=rule.source_file or "",
        text="\n\n".join(text_parts),
        coverage_status="COMPLETE",
        source_quality=f"STRUCTURED_SANCTION:{rule.validation_status or 'UNKNOWN'}",
        score=rule.confidence,
    )


def build_sanction_response(parsed: ParsedQuery, lookup: SanctionLookup) -> ChatResponse:
    if lookup.status in {
        "UNAVAILABLE",
        "NOT_FOUND",
        "AMBIGUOUS",
        "NEEDS_CLARIFICATION",
        "NOT_MAPPED",
        "TEMPORAL_AMBIGUOUS",
    }:
        return ChatResponse(
            answer=_build_unanswered(parsed, lookup),
            citations=[_citation(rule) for rule in lookup.rules],
            warnings=lookup.warnings,
            answerable=False,
            debug={"parsed_query": parsed.model_dump(), "sanction_lookup": lookup.model_dump()},
        )

    rules = lookup.rules
    citations = [_citation(rule) for rule in rules]
    warnings = list(lookup.warnings)
    for rule in rules:
        if rule.temporal_warning:
            warnings.append(rule.temporal_warning)

    answer = "\n\n".join(_rule_answer(rule, parsed) for rule in rules)
    refs = "\n".join(
        f"{index}. {rule.document_number}: {_rule_ref(rule)} ({rule.rule_id})"
        for index, rule in enumerate(rules, start=1)
    )
    note_lines = [
        "Kết quả được tra từ Structured Sanction Layer và chỉ dùng rule có validation_status=PASS.",
        f"Ngày hiệu lực pháp lý: {parsed.legal_effective_date or parsed.event_date or 'hiện tại'}.",
    ]
    if warnings:
        note_lines.extend(warnings)

    return ChatResponse(
        answer=(
            "### Trả lời\n"
            f"{answer}\n\n"
            "### Căn cứ pháp lý\n"
            f"{refs}\n\n"
            "### Thời điểm áp dụng\n"
            f"{note_lines[1]}\n\n"
            "### Lưu ý\n"
            + "\n".join(f"- {line}" for line in note_lines)
        ),
        citations=citations,
        warnings=warnings,
        answerable=True,
        debug={"parsed_query": parsed.model_dump(), "sanction_lookup": lookup.model_dump()},
    )


def _rule_answer(rule: SanctionRule, parsed: ParsedQuery) -> str:
    points = (
        f" Đồng thời bị trừ {rule.license_points_deducted} điểm giấy phép lái xe."
        if rule.license_points_deducted is not None
        else ""
    )
    suspension = ""
    if rule.license_suspension_min_months is not None or rule.license_suspension_max_months is not None:
        suspension = (
            " Ngoài ra có tước quyền sử dụng giấy phép lái xe"
            f" từ {rule.license_suspension_min_months or '?'}"
            f" đến {rule.license_suspension_max_months or '?'} tháng."
        )
    liable = f" Đối tượng chịu trách nhiệm: {rule.liable_entity_type}." if rule.liable_entity_type else ""
    conditions = f" Điều kiện áp dụng: {', '.join(rule.conditions)}." if rule.conditions else ""
    return (
        f"Với hành vi “{rule.behavior_text}”"
        f" ({', '.join(rule.vehicle_codes) or parsed.vehicle_code or 'không rõ loại phương tiện'}), "
        f"mức xử phạt là {_fine_text(rule)}.{points}{suspension}{liable}{conditions}"
    )


def _build_unanswered(parsed: ParsedQuery, lookup: SanctionLookup) -> str:
    missing = ", ".join(lookup.missing_fields)
    reason = "; ".join(lookup.warnings) or "không tìm thấy rule phù hợp"
    if missing:
        reason = f"thiếu thông tin bắt buộc: {missing}. {reason}"
    return (
        "### Trả lời\n"
        "Tôi chưa đủ căn cứ có cấu trúc để xác định chế tài cho câu hỏi này.\n\n"
        "### Căn cứ pháp lý\n"
        "Không có sanction rule phù hợp để trích dẫn.\n\n"
        "### Thời điểm áp dụng\n"
        f"Đang xét theo ngày {parsed.legal_effective_date or parsed.event_date or 'hiện tại'}.\n\n"
        "### Lưu ý\n"
        f"- {reason}"
    )
