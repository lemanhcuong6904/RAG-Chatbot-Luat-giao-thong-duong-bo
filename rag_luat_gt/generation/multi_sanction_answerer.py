from __future__ import annotations

from rag_luat_gt.citation_format import short_ref
from rag_luat_gt.generation.sanction_answerer import _citation, _fine_text, _money, _point_citation, _rule_ref
from rag_luat_gt.sanction.schemas import SanctionComposition, SanctionRule, ViolationResolution
from rag_luat_gt.schemas import ChatResponse, Citation, ParsedQuery


def build_multi_sanction_response(parsed: ParsedQuery, composition: SanctionComposition) -> ChatResponse:
    citations = _citations(composition)
    warnings = list(dict.fromkeys(composition.warnings))
    answerable = any(resolution.selected_rule or resolution.rules for resolution in composition.resolutions)

    return ChatResponse(
        answer=(
            f"{_summary(composition, parsed)}\n\n"
            "Từng hành vi:\n"
            f"{_violation_lines(composition.resolutions)}\n\n"
            "Tổng hợp chế tài:\n"
            f"{_money_lines(composition)}\n"
            f"{_point_line(composition)}"
        ),
        citations=citations,
        warnings=warnings,
        answerable=answerable,
        debug={"parsed_query": parsed.model_dump(), "sanction_composition": composition.model_dump()},
    )


def _summary(composition: SanctionComposition, parsed: ParsedQuery) -> str:
    query = parsed.query.casefold()
    if any(term in query for term in ["cộng điểm", "cộng điểm trừ", "thành 8", "cong diem", "cong diem tru"]):
        return (
            "Không. Khi nhiều hành vi bị xử phạt trong cùng một lần, điểm GPLX không cộng cơ học; "
            "áp dụng mức trừ cao nhất trong các hành vi đã resolve [Nghị định 168/2024/NĐ-CP, Điều 50, khoản 1, điểm b]."
        )
    if composition.status == "RESOLVED":
        return (
            "Có. Khi một người thực hiện nhiều hành vi vi phạm, tiền phạt được xác định theo từng hành vi; "
            "có thể cộng các khung tiền phạt của những hành vi độc lập. Điểm GPLX không cộng cơ học, mà áp dụng "
            "mức trừ cao nhất [Nghị định 168/2024/NĐ-CP, Điều 50, khoản 1, điểm b]."
        )
    return (
        "Có thể xác định theo từng hành vi, nhưng tình huống này chưa đủ dữ kiện để chốt một tổng tiền duy nhất. "
        "Hệ thống giữ các nhánh điều kiện thay vì chọn bừa một mức phạt."
    )


def _violation_lines(resolutions: list[ViolationResolution]) -> str:
    lines: list[str] = []
    for index, resolution in enumerate(resolutions, start=1):
        if resolution.selected_rule:
            rule = resolution.selected_rule
            label = resolution.raw_span or resolution.behavior_text or rule.behavior_text
            points = (
                f", trừ {rule.license_points_deducted} điểm GPLX{_inline_point_ref(rule)}"
                if rule.license_points_deducted is not None
                else ""
            )
            lines.append(
                f"{index}. {label}: {_fine_text(rule)}{points} "
                f"{_inline_rule_ref(rule)}."
            )
        elif resolution.status == "CONDITIONAL" and resolution.rules:
            label = resolution.rules[0].behavior_text or resolution.raw_span or resolution.behavior_text
            alternatives = "; ".join(
                f"{_condition_label(rule)}: {_fine_text(rule)} {_inline_rule_ref(rule)}"
                for rule in resolution.rules
            )
            lines.append(f"{index}. {label}: cần phân nhánh điều kiện. {alternatives}.")
        else:
            label = resolution.raw_span or resolution.behavior_text
            lines.append(f"{index}. {label}: chưa resolve được rule phù hợp.")
    return "\n".join(lines)


def _money_lines(composition: SanctionComposition) -> str:
    if composition.money.status == "RESOLVED":
        line = (
            f"- Tổng khung tiền phạt: từ {_money(composition.money.min_total)} "
            f"đến {_money(composition.money.max_total)}."
        )
        if composition.money.default_total is not None:
            line += f" Mức tham chiếu giữa khung: {_money(composition.money.default_total)}."
        return line
    if composition.money_branches:
        lines = ["- Chưa có một tổng duy nhất vì còn thiếu điều kiện về dung tích/công suất xe:"]
        for branch in composition.money_branches:
            lines.append(
                f"- {branch.label}: từ {_money(branch.min_total)} đến {_money(branch.max_total)}."
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
        "không cộng số điểm trừ của từng hành vi [Nghị định 168/2024/NĐ-CP, Điều 50, khoản 1, điểm b]."
    )


def _reference_lines(composition: SanctionComposition) -> str:
    rules = _rules_for_citation(composition)
    if not rules:
        return "Không có sanction rule phù hợp để trích dẫn."
    return "\n".join(
        f"{index}. {rule.document_number}: {_rule_ref(rule)} ({rule.rule_id})"
        for index, rule in enumerate(rules, start=1)
    )


def _inline_rule_ref(rule: SanctionRule) -> str:
    return f"[{short_ref(rule)}]"


def _inline_point_ref(rule: SanctionRule) -> str:
    point_ref = _point_citation(rule)
    return f" [{short_ref(point_ref)}]" if point_ref else ""


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
    citations = [item for rule in _rules_for_citation(composition) for item in [_citation(rule), _point_citation(rule)] if item is not None]
    if composition.license_points.points_deducted is not None and len(_rules_for_citation(composition)) >= 2:
        citations.append(_license_point_composition_citation())
    return _dedupe_citations(citations)


def _license_point_composition_citation() -> Citation:
    return Citation(
        chunk_id="ND168_A50_K1_Pb_STRUCTURED_COMPOSITION",
        chunk_type="SANCTION_POINT_COMPOSITION_RULE",
        document_number="168/2024/NĐ-CP",
        document_title="Nghị định số 168/2024/NĐ-CP",
        article="50",
        article_title="Nguyên tắc, thẩm quyền, trình tự, thủ tục trừ điểm giấy phép lái xe",
        clause="1",
        point="b",
        source_file="data/markdown/168-2024-ND-CP_Xu-phat-TTATGT-Tru-diem-GPLX.md",
        text="b) Trường hợp cá nhân thực hiện nhiều hành vi vi phạm hành chính hoặc vi phạm hành chính nhiều lần mà bị xử phạt trong cùng một lần, nếu có từ 02 hành vi vi phạm trở lên theo quy định bị trừ điểm giấy phép lái xe thì chỉ áp dụng trừ điểm đối với hành vi vi phạm bị trừ nhiều điểm nhất;",
        rule_function="SANCTION",
        coverage_status="COMPLETE",
        source_quality="STRUCTURED_SANCTION:COMPOSITION_RULE",
    )


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
