from __future__ import annotations

import re

from rag_luat_gt.schemas import ParsedQuery, ViolationFact
from rag_luat_gt.sanction.repository import SanctionRepository
from rag_luat_gt.sanction.schemas import SanctionLookup, SanctionRule, ViolationResolution
from rag_luat_gt.text import normalize_text, strip_accents


def resolve_violations(
    repository: SanctionRepository,
    parsed: ParsedQuery,
) -> list[ViolationResolution]:
    event_date = parsed.legal_effective_date or parsed.event_date or parsed.query_reference_date or ""
    return [_resolve_violation(repository, parsed, violation, event_date) for violation in parsed.violations]


def _resolve_violation(
    repository: SanctionRepository,
    parsed: ParsedQuery,
    violation: ViolationFact,
    event_date: str,
) -> ViolationResolution:
    if violation.catalog_code == "NO_DRIVER_LICENSE":
        return _resolve_no_driver_license(repository, parsed, violation, event_date)

    lookup = repository.lookup(
        event_date=event_date,
        vehicle_code=parsed.vehicle_code,
        behavior_code=violation.behavior_code,
        behavior_contains=violation.behavior_contains,
    )
    if lookup.status in {"NOT_FOUND", "NOT_MAPPED"}:
        scoped = _lookup_violation_behavior_codes(repository, parsed, violation, event_date)
        if scoped:
            return scoped
    return _resolution_from_lookup(violation, lookup)


def _lookup_violation_behavior_codes(
    repository: SanctionRepository,
    parsed: ParsedQuery,
    violation: ViolationFact,
    event_date: str,
) -> ViolationResolution | None:
    codes = [str(code) for code in violation.conditions.get("behavior_codes", []) if code]
    if len(codes) < 2:
        return None
    lookup = repository.lookup_behavior_codes(event_date=event_date, behavior_codes=codes, limit=50)
    if lookup.status != "FOUND":
        return None
    rules = [rule for rule in lookup.rules if not parsed.vehicle_code or parsed.vehicle_code in rule.vehicle_codes]
    if len(rules) == 1:
        return _selected_resolution(violation, rules[0], rules)
    if rules:
        return ViolationResolution(
            status="CONDITIONAL",
            behavior_code=violation.behavior_code,
            behavior_text=violation.behavior_text,
            raw_span=violation.raw_span,
            rules=rules,
            missing_conditions=[],
            warnings=["Có nhiều rule phù hợp với hành vi; cần phân nhánh theo điều kiện áp dụng."],
        )
    return None


def _resolve_no_driver_license(
    repository: SanctionRepository,
    parsed: ParsedQuery,
    violation: ViolationFact,
    event_date: str,
) -> ViolationResolution:
    codes = [str(code) for code in violation.conditions.get("behavior_codes", []) if code]
    lookup = repository.lookup_behavior_codes(event_date=event_date, behavior_codes=codes, limit=50)
    if lookup.status != "FOUND":
        return _resolution_from_lookup(violation, lookup)

    motorcycle_rules = [
        rule
        for rule in lookup.rules
        if rule.article == "18" and (rule.clause, rule.point) in {("5", "a"), ("7", "b")}
    ]
    if parsed.vehicle_code != "MOTORCYCLE":
        return ViolationResolution(
            status="NEEDS_CLARIFICATION",
            behavior_code=violation.behavior_code,
            behavior_text=violation.behavior_text,
            raw_span=violation.raw_span,
            rules=motorcycle_rules,
            missing_conditions=["vehicle_code"],
            warnings=["Hành vi không có GPLX cần xác định đúng loại phương tiện/hạng xe."],
        )

    vehicle_band = _motorcycle_license_band(parsed.query)
    if vehicle_band == "LTE_125CC_OR_11KW":
        selected = _find_rule(motorcycle_rules, clause="5", point="a")
        return _selected_resolution(violation, selected, motorcycle_rules)
    if vehicle_band == "GT_125CC_OR_11KW":
        selected = _find_rule(motorcycle_rules, clause="7", point="b")
        return _selected_resolution(violation, selected, motorcycle_rules)

    return ViolationResolution(
        status="CONDITIONAL",
        behavior_code=violation.behavior_code,
        behavior_text=violation.behavior_text,
        raw_span=violation.raw_span,
        rules=motorcycle_rules,
        missing_conditions=["engine_cc_or_power_kw"],
        warnings=[
            "Hành vi không có GPLX khi đi xe máy phụ thuộc xe đến 125 cm3/11 kW hay trên ngưỡng này."
        ],
    )


def _resolution_from_lookup(violation: ViolationFact, lookup: SanctionLookup) -> ViolationResolution:
    selected = lookup.rules[0] if lookup.status == "FOUND" and len(lookup.rules) == 1 else None
    status = "RESOLVED" if selected else lookup.status
    return ViolationResolution(
        status=status,
        behavior_code=violation.behavior_code,
        behavior_text=violation.behavior_text,
        raw_span=violation.raw_span,
        rules=lookup.rules,
        selected_rule=selected,
        missing_conditions=lookup.missing_fields,
        warnings=lookup.warnings,
    )


def _selected_resolution(
    violation: ViolationFact,
    selected: SanctionRule | None,
    rules: list[SanctionRule],
) -> ViolationResolution:
    if not selected:
        return ViolationResolution(
            status="NOT_FOUND",
            behavior_code=violation.behavior_code,
            behavior_text=violation.behavior_text,
            raw_span=violation.raw_span,
            rules=rules,
            warnings=["Không tìm thấy nhánh điều kiện phù hợp cho hành vi không có GPLX."],
        )
    return ViolationResolution(
        status="RESOLVED",
        behavior_code=violation.behavior_code,
        behavior_text=violation.behavior_text,
        raw_span=violation.raw_span,
        rules=[selected],
        selected_rule=selected,
    )


def _find_rule(rules: list[SanctionRule], *, clause: str, point: str) -> SanctionRule | None:
    return next((rule for rule in rules if rule.clause == clause and rule.point == point), None)


def _motorcycle_license_band(query: str) -> str | None:
    q = strip_accents(normalize_text(query))
    cc_match = re.search(r"\b(\d{2,4})\s*(?:cc|cm3|cm 3|phan khoi)\b", q)
    if cc_match:
        return "LTE_125CC_OR_11KW" if int(cc_match.group(1)) <= 125 else "GT_125CC_OR_11KW"
    kw_match = re.search(r"\b(\d{1,3})\s*kw\b", q)
    if kw_match:
        return "LTE_125CC_OR_11KW" if int(kw_match.group(1)) <= 11 else "GT_125CC_OR_11KW"
    if any(term in q for term in ["tren 125", "lon hon 125", "> 125", "qua 125", "tren 11 kw", "> 11 kw"]):
        return "GT_125CC_OR_11KW"
    if any(
        term in q
        for term in [
            "den 125",
            "duoi 125",
            "khong qua 125",
            "<= 125",
            "125 cm3",
            "125cc",
            "den 11 kw",
            "duoi 11 kw",
            "<= 11 kw",
        ]
    ):
        return "LTE_125CC_OR_11KW"
    return None
