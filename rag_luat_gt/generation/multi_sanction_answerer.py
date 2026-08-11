from __future__ import annotations

from rag_luat_gt.generation.sanction_answerer import _citation, _fine_text, _money, _rule_ref
from rag_luat_gt.sanction.schemas import SanctionComposition, SanctionRule, ViolationResolution
from rag_luat_gt.schemas import ChatResponse, Citation, ParsedQuery


def build_multi_sanction_response(parsed: ParsedQuery, composition: SanctionComposition) -> ChatResponse:
    citations = _citations(composition)
    warnings = list(dict.fromkeys(composition.warnings))
    answerable = any(resolution.selected_rule or resolution.rules for resolution in composition.resolutions)

    return ChatResponse(
        answer=(
            "### Trả lời\n"
            f"{_summary(composition)}\n\n"
            "### Từng hành vi\n"
            f"{_violation_lines(composition.resolutions)}\n\n"
            "### Tổng hợp chế tài\n"
            f"{_money_lines(composition)}\n"
            f"{_point_line(composition)}\n\n"
            "### Căn cứ pháp lý\n"
            f"{_reference_lines(composition)}\n\n"
            "### Thời điểm áp dụng\n"
            f"Đang xét theo ngày {parsed.legal_effective_date or parsed.event_date or 'hiện tại'}.\n\n"
            "### Lưu ý\n"
            f"{_notes(composition)}"
        ),
        citations=citations,
        warnings=warnings,
        answerable=answerable,
        debug={"parsed_query": parsed.model_dump(), "sanction_composition": composition.model_dump()},
    )


def _summary(composition: SanctionComposition) -> str:
    if composition.status == "RESOLVED":
        return (
            "Có. Khi một người thực hiện nhiều hành vi vi phạm, tiền phạt được xác định theo từng hành vi; "
            "có thể cộng các khung tiền phạt của những hành vi độc lập. Điểm GPLX không cộng cơ học, mà áp dụng "
            "quy tắc composition riêng."
        )
    return (
        "Có thể xác định theo từng hành vi, nhưng tình huống này chưa đủ dữ kiện để chốt một tổng tiền duy nhất. "
        "Hệ thống giữ các nhánh điều kiện thay vì chọn bừa một mức phạt."
    )


def _violation_lines(resolutions: list[ViolationResolution]) -> str:
    lines: list[str] = []
    for index, resolution in enumerate(resolutions, start=1):
        label = resolution.raw_span or resolution.behavior_text
        if resolution.selected_rule:
            rule = resolution.selected_rule
            points = (
                f", trừ {rule.license_points_deducted} điểm GPLX"
                if rule.license_points_deducted is not None
                else ""
            )
            lines.append(
                f"{index}. {label}: {_fine_text(rule)}{points} "
                f"({rule.document_number}, {_rule_ref(rule)})."
            )
        elif resolution.status == "CONDITIONAL" and resolution.rules:
            alternatives = "; ".join(
                f"{_condition_label(rule)}: {_fine_text(rule)} ({rule.document_number}, {_rule_ref(rule)})"
                for rule in resolution.rules
            )
            lines.append(f"{index}. {label}: cần phân nhánh điều kiện. {alternatives}.")
        else:
            lines.append(f"{index}. {label}: chưa resolve được rule phù hợp.")
    return "\n".join(lines)


def _money_lines(composition: SanctionComposition) -> str:
    if composition.money.status == "RESOLVED":
        return (
            f"- Tổng khung tiền phạt: từ {_money(composition.money.min_total)} "
            f"đến {_money(composition.money.max_total)}.\n"
            f"- Mức trung bình tham khảo khi không có tình tiết tăng nặng/giảm nhẹ: "
            f"{_money(composition.money.default_total)}."
        )
    if composition.money_branches:
        lines = ["- Chưa có một tổng duy nhất vì còn thiếu điều kiện về dung tích/công suất xe:"]
        for branch in composition.money_branches:
            lines.append(
                f"- {branch.label}: từ {_money(branch.min_total)} đến {_money(branch.max_total)}; "
                f"mức trung bình tham khảo {_money(branch.default_total)}."
            )
        return "\n".join(lines)
    return "- Chưa đủ dữ kiện để tổng hợp tiền phạt."


def _point_line(composition: SanctionComposition) -> str:
    points = composition.license_points.points_deducted
    if points is None:
        return "- Điểm GPLX: chưa đủ dữ kiện để xác định."
    if points == 0:
        return "- Điểm GPLX: các rule đã resolve không có trừ điểm."
    return (
        f"- Điểm GPLX: mức trừ áp dụng theo quy tắc lấy hành vi có số điểm trừ cao nhất, hiện là {points} điểm; "
        "không cộng số điểm trừ của từng hành vi."
    )


def _reference_lines(composition: SanctionComposition) -> str:
    rules = _rules_for_citation(composition)
    if not rules:
        return "Không có sanction rule phù hợp để trích dẫn."
    return "\n".join(
        f"{index}. {rule.document_number}: {_rule_ref(rule)} ({rule.rule_id})"
        for index, rule in enumerate(rules, start=1)
    )


def _notes(composition: SanctionComposition) -> str:
    notes = [
        "- Tiền phạt được trình bày theo từng hành vi độc lập; tổng tiền là tổng các khung tiền đã resolve.",
        "- Điểm GPLX dùng chính sách MAX_POINTS_SAME_DECISION, không cộng số điểm trừ.",
    ]
    for resolution in composition.resolutions:
        for missing in resolution.missing_conditions:
            notes.append(f"- Thiếu điều kiện: {missing}.")
    for warning in composition.warnings:
        notes.append(f"- {warning}")
    return "\n".join(dict.fromkeys(notes))


def _citations(composition: SanctionComposition) -> list[Citation]:
    return [_citation(rule) for rule in _rules_for_citation(composition)]


def _rules_for_citation(composition: SanctionComposition) -> list[SanctionRule]:
    rules: list[SanctionRule] = []
    seen: set[str] = set()
    for resolution in composition.resolutions:
        candidates = [resolution.selected_rule] if resolution.selected_rule else resolution.rules
        for rule in candidates:
            if rule and rule.rule_id not in seen:
                rules.append(rule)
                seen.add(rule.rule_id)
    return rules


def _condition_label(rule: SanctionRule) -> str:
    if rule.article == "18" and rule.clause == "5" and rule.point == "a":
        return "xe đến 125 cm3 hoặc đến 11 kW"
    if rule.article == "18" and rule.clause == "7" and rule.point == "b":
        return "xe trên 125 cm3 hoặc trên 11 kW"
    return rule.source_location or rule.rule_id
