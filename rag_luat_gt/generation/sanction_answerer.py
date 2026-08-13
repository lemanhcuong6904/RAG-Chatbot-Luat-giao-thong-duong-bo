from __future__ import annotations

from rag_luat_gt.sanction.schemas import SanctionLookup, SanctionRule
from rag_luat_gt.schemas import ChatResponse, Citation, ParsedQuery
from rag_luat_gt.text import normalize_text, strip_accents


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
    text_parts.extend(_secondary_statement_texts(rule))
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
        f"{index}. {rule.document_number}: {_rule_ref(rule)}"
        for index, rule in enumerate(rules, start=1)
    )
    return ChatResponse(
        answer=(
            "### Trả lời\n"
            f"{answer}\n\n"
            "### Căn cứ pháp lý\n"
            f"{refs}"
        ),
        citations=citations,
        warnings=warnings,
        answerable=True,
        debug={"parsed_query": parsed.model_dump(), "sanction_lookup": lookup.model_dump()},
    )


def _rule_answer_base(rule: SanctionRule, parsed: ParsedQuery) -> str:
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
    liable = _liable_text(rule)
    return (
        f"Với hành vi “{_behavior_label(rule, parsed)}”"
        f" đối với {_vehicle_label(parsed, rule)}, "
        f"mức xử phạt là {_fine_text(rule)}.{points}{suspension}{liable}"
    )


def _behavior_label(rule: SanctionRule, parsed: ParsedQuery) -> str:
    if rule.behavior_code == "KHONG_CHAP_HANH_HIEU_LENH_CUA_DEN_TIN_HIEU_GIAO_THONG":
        return "không chấp hành hiệu lệnh của đèn tín hiệu giao thông (vượt đèn đỏ)"
    if parsed.behavior_text_query and _is_specific_behavior_label(parsed.behavior_text_query):
        return parsed.behavior_text_query
    if rule.behavior_text:
        return rule.behavior_text
    for violation in parsed.violations:
        codes = [str(code) for code in violation.conditions.get("behavior_codes", []) if code]
        if rule.behavior_code in codes:
            return violation.raw_span or violation.behavior_text
    return parsed.behavior_text_query or "hành vi vi phạm"


def _is_specific_behavior_label(value: str) -> bool:
    normalized = strip_accents(normalize_text(value))
    if len(normalized.split()) >= 5:
        return True
    return any(
        term in normalized
        for term in [
            "quay",
            "vuot",
            "khong chap hanh",
            "khong doi",
            "di sai",
            "nong do",
            "qua toc do",
            "gay tai nan",
        ]
    )


def _vehicle_label(parsed: ParsedQuery, rule: SanctionRule) -> str:
    labels = {
        "CAR": "xe ô tô",
        "FOUR_WHEEL_PASSENGER": "xe chở người bốn bánh có gắn động cơ",
        "FOUR_WHEEL_CARGO": "xe chở hàng bốn bánh có gắn động cơ",
        "CAR_SIMILAR": "xe tương tự xe ô tô",
        "MOTORCYCLE": "xe mô tô, xe gắn máy",
        "MOPED": "xe gắn máy",
        "SPECIALIZED_MOTOR_VEHICLE": "xe máy chuyên dùng",
        "BICYCLE": "xe đạp",
        "PEDESTRIAN": "người đi bộ",
    }
    if parsed.vehicle_code:
        return labels.get(parsed.vehicle_code, parsed.vehicle_type or parsed.vehicle_code)
    for code in rule.vehicle_codes:
        if code in labels:
            return labels[code]
    return parsed.vehicle_type or "loại phương tiện chưa xác định"


def _liable_text(rule: SanctionRule) -> str:
    if not rule.liable_entity_type or rule.liable_entity_type == "UNSPECIFIED":
        return ""
    labels = {
        "DRIVER": "người điều khiển phương tiện",
        "OWNER": "chủ phương tiện",
        "ORGANIZATION": "tổ chức",
        "INDIVIDUAL": "cá nhân",
    }
    return f" Đối tượng chịu trách nhiệm: {labels.get(rule.liable_entity_type, rule.liable_entity_type)}."


def _rule_answer(rule: SanctionRule, parsed: ParsedQuery) -> str:
    return f"{_rule_answer_base(rule, parsed)}{_additional_sanctions_text(rule)}{_remedial_measures_text(rule)}"


def _additional_sanctions_text(rule: SanctionRule) -> str:
    sanctions = _additional_sanctions_not_already_rendered(rule)
    if not sanctions:
        return ""
    return f" Hình thức xử phạt bổ sung: {_join_items(sanctions)}."


def _remedial_measures_text(rule: SanctionRule) -> str:
    measures = _clean_items(rule.remedial_measures)
    if not measures:
        return ""
    return f" Biện pháp khắc phục hậu quả: {_join_items(measures)}."


def _additional_sanctions_not_already_rendered(rule: SanctionRule) -> list[str]:
    sanctions = _clean_items(rule.additional_sanctions)
    if rule.license_suspension_min_months is None and rule.license_suspension_max_months is None:
        return sanctions
    return [sanction for sanction in sanctions if not _looks_like_license_suspension(sanction)]


def _secondary_statement_texts(rule: SanctionRule) -> list[str]:
    statements: list[str] = []
    additional = _clean_items(rule.additional_sanctions)
    remedial = _clean_items(rule.remedial_measures)
    if additional:
        statements.append("Hình thức xử phạt bổ sung: " + _join_items(additional))
    if remedial:
        statements.append("Biện pháp khắc phục hậu quả: " + _join_items(remedial))
    return statements


def _clean_items(items: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = item.strip()
        if value.endswith(";"):
            value = value[:-1].strip()
        key = value.casefold()
        if value and key not in seen:
            cleaned.append(value)
            seen.add(key)
    return cleaned


def _join_items(items: list[str]) -> str:
    return "; ".join(items)


def _looks_like_license_suspension(text: str) -> bool:
    normalized = text.casefold()
    return "tước quyền sử dụng giấy phép lái xe" in normalized or "tước quyền sử dụng giấy phép" in normalized


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
