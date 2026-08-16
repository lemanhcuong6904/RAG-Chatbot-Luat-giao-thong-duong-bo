from __future__ import annotations

from rag_luat_gt.citation_format import short_ref
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


def _inline_ref(rule: SanctionRule) -> str:
    return f"[{short_ref(rule)}]"


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


def _point_citation(rule: SanctionRule) -> Citation | None:
    if rule.document_number != "168/2024/NĐ-CP" or rule.license_points_deducted is None:
        return None
    point_ref = _point_reference(rule)
    if not point_ref:
        return None
    clause, point, text = point_ref
    return Citation(
        chunk_id=f"ND168_A{rule.article}_K{clause}_P{point}_POINTS_FOR_{rule.rule_id}",
        chunk_type="SANCTION_POINT_RULE",
        rule_id=rule.rule_id,
        document_number=rule.document_number,
        document_title="Nghị định số 168/2024/NĐ-CP",
        article=rule.article,
        article_title=rule.article_title,
        clause=clause,
        point=point,
        source_file=rule.source_file or "",
        text=text,
        coverage_status="COMPLETE",
        source_quality="STRUCTURED_SANCTION:POINT_CLOSURE",
        score=rule.confidence,
    )


def _point_reference(rule: SanctionRule) -> tuple[str, str, str] | None:
    if rule.article == "6":
        text_by_point = {
            "a": "a) Thực hiện hành vi quy định tại điểm h, điểm i khoản 3; điểm a, điểm b, điểm c, điểm d, điểm đ, điểm g khoản 4; điểm a, điểm b, điểm c, điểm d, điểm đ, điểm e, điểm g, điểm i, điểm k, điểm n, điểm o khoản 5 Điều này bị trừ điểm giấy phép lái xe 02 điểm;",
            "b": "b) Thực hiện hành vi quy định tại điểm h khoản 5; khoản 6; điểm b khoản 7; điểm b, điểm c, điểm d khoản 9 Điều này bị trừ điểm giấy phép lái xe 04 điểm;",
            "c": "c) Thực hiện hành vi quy định tại điểm p khoản 5; điểm a, điểm c khoản 7; khoản 8 Điều này bị trừ điểm giấy phép lái xe 06 điểm;",
            "d": "d) Thực hiện hành vi quy định tại điểm a khoản 9, khoản 10, điểm đ khoản 11 Điều này bị trừ điểm giấy phép lái xe 10 điểm.",
        }
        point = _article6_point_reference(rule)
        return ("16", point, text_by_point[point]) if point else None
    if rule.article == "7":
        text_by_point = {
            "a": "a) Thực hiện hành vi quy định tại điểm b khoản 3; khoản 5; điểm b, điểm c, điểm d khoản 6; điểm a khoản 7 Điều này bị trừ điểm giấy phép lái xe 02 điểm;",
            "b": "b) Thực hiện hành vi quy định tại điểm đ khoản 4; điểm a khoản 6; điểm c, điểm d, điểm đ khoản 7; điểm a khoản 8 Điều này bị trừ điểm giấy phép lái xe 04 điểm;",
            "c": "c) Thực hiện hành vi quy định tại điểm b khoản 7, điểm c khoản 9 Điều này bị trừ điểm giấy phép lái xe 06 điểm;",
            "d": "d) Thực hiện hành vi quy định tại điểm b khoản 8, khoản 10 Điều này bị trừ điểm giấy phép lái xe 10 điểm.",
        }
        point = _article7_point_reference(rule)
        return ("13", point, text_by_point[point]) if point else None
    return None


def _article6_point_reference(rule: SanctionRule) -> str | None:
    ref = (rule.clause, rule.point)
    if ref in {("3", "h"), ("3", "i"), ("4", "a"), ("4", "b"), ("4", "c"), ("4", "d"), ("4", "đ"), ("4", "g"), ("5", "a"), ("5", "b"), ("5", "c"), ("5", "d"), ("5", "đ"), ("5", "e"), ("5", "g"), ("5", "i"), ("5", "k"), ("5", "n"), ("5", "o")}:
        return "a"
    if rule.clause == "6" or ref in {("5", "h"), ("7", "b"), ("9", "b"), ("9", "c"), ("9", "d")}:
        return "b"
    if rule.clause == "8" or ref in {("5", "p"), ("7", "a"), ("7", "c")}:
        return "c"
    if rule.clause == "10" or ref in {("9", "a"), ("11", "đ")}:
        return "d"
    return None


def _article7_point_reference(rule: SanctionRule) -> str | None:
    ref = (rule.clause, rule.point)
    if rule.clause == "5" or ref in {("3", "b"), ("6", "b"), ("6", "c"), ("6", "d"), ("7", "a")}:
        return "a"
    if ref in {("4", "đ"), ("6", "a"), ("7", "c"), ("7", "d"), ("7", "đ"), ("8", "a")}:
        return "b"
    if ref in {("7", "b"), ("9", "c")}:
        return "c"
    if rule.clause == "10" or ref == ("8", "b"):
        return "d"
    return None


def _dedupe_citations(citations: list[Citation]) -> list[Citation]:
    selected: list[Citation] = []
    seen: set[tuple[str, str | None, str | None, str | None, str | None]] = set()
    for citation in citations:
        key = (citation.document_number or "", citation.article, citation.clause, citation.point, citation.rule_id)
        if key in seen:
            continue
        seen.add(key)
        selected.append(citation)
    return selected


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
    citations = _dedupe_citations(
        [item for rule in rules for item in [_citation(rule), _point_citation(rule)] if item is not None]
    )
    warnings = list(lookup.warnings)
    for rule in rules:
        if rule.temporal_warning:
            warnings.append(rule.temporal_warning)

    answer = "\n\n".join(_rule_answer(rule, parsed) for rule in rules)
    return ChatResponse(
        answer=answer,
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
    if rule.behavior_code and rule.behavior_code.startswith("KHONG_CO_GIAY_PHEP_LAI_XE"):
        return "không có giấy phép lái xe"
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
    parent = strip_accents(normalize_text(rule.parent_clause_text or ""))
    if "xe o to" in parent:
        return "xe ô tô"
    if "xe mo to hai banh co dung tich xi-lanh den 125" in parent or "cong suat dong co dien den 11 kw" in parent:
        return "xe mô tô đến 125 cm3 hoặc đến 11 kW"
    if "xe mo to hai banh co dung tich xi-lanh tren 125" in parent or "cong suat dong co dien tren 11 kw" in parent:
        return "xe mô tô trên 125 cm3 hoặc trên 11 kW"
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
    return (
        f"{_rule_answer_base(rule, parsed)}"
        f"{_additional_sanctions_text(rule, parsed)}"
        f"{_remedial_measures_text(rule, parsed)} "
        f"{_inline_ref(rule)}"
    )


def _additional_sanctions_text(rule: SanctionRule, parsed: ParsedQuery) -> str:
    if not _should_render_secondary_actions(parsed):
        return ""
    sanctions = _additional_sanctions_not_already_rendered(rule)
    if not sanctions:
        return ""
    return f" Hình thức xử phạt bổ sung: {_join_items(sanctions)}."


def _remedial_measures_text(rule: SanctionRule, parsed: ParsedQuery) -> str:
    if not _should_render_secondary_actions(parsed):
        return ""
    measures = _clean_items(rule.remedial_measures)
    if not measures:
        return ""
    return f" Biện pháp khắc phục hậu quả: {_join_items(measures)}."


def _should_render_secondary_actions(parsed: ParsedQuery) -> bool:
    query = strip_accents(normalize_text(parsed.query))
    if any(term in query for term in ["bien phap khac phuc", "khac phuc hau qua", "bo sung", "tuoc quyen"]):
        return True
    if "xu phat" in query and "the nao" in query:
        return True
    if parsed.requested_facets and set(parsed.requested_facets).issubset({"FINE", "POINTS"}):
        return False
    if any(term in query for term in ["phat bao nhieu", "muc phat", "phat tien bao nhieu"]):
        return False
    return True


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
        "Tôi chưa đủ căn cứ có cấu trúc để xác định chế tài cho câu hỏi này.\n\n"
        f"Đang xét theo ngày {parsed.legal_effective_date or parsed.event_date or 'hiện tại'}.\n\n"
        f"Lý do: {reason}"
    )
