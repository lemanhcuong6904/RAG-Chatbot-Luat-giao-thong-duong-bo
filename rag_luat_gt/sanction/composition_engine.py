from __future__ import annotations

from rag_luat_gt.sanction.schemas import (
    LicensePointAggregation,
    MoneyAggregation,
    MoneyBranch,
    SanctionComposition,
    SanctionRule,
    ViolationResolution,
)


def compose_sanctions(resolutions: list[ViolationResolution]) -> SanctionComposition:
    warnings: list[str] = []
    for resolution in resolutions:
        warnings.extend(resolution.warnings)

    selected_rules = [resolution.selected_rule for resolution in resolutions if resolution.selected_rule]
    unresolved = [resolution for resolution in resolutions if resolution.status != "RESOLVED"]
    money_branches = _conditional_money_branches(resolutions)

    if unresolved:
        money = MoneyAggregation(status="CONDITIONAL")
        status = "CONDITIONAL"
    else:
        money = _sum_money(selected_rules)
        status = "RESOLVED"

    return SanctionComposition(
        status=status,
        money=money,
        money_branches=money_branches,
        license_points=_max_license_points(selected_rules, resolutions),
        resolutions=resolutions,
        warnings=warnings,
    )


def _sum_money(rules: list[SanctionRule]) -> MoneyAggregation:
    fine_rules = [rule for rule in rules if rule.fine_min is not None and rule.fine_max is not None]
    if len(fine_rules) != len(rules):
        return MoneyAggregation(status="CONDITIONAL")
    min_total = sum(rule.fine_min or 0 for rule in fine_rules)
    max_total = sum(rule.fine_max or 0 for rule in fine_rules)
    return MoneyAggregation(
        status="RESOLVED",
        min_total=min_total,
        max_total=max_total,
        default_total=sum(_midpoint(rule) for rule in fine_rules),
    )


def _max_license_points(
    selected_rules: list[SanctionRule],
    resolutions: list[ViolationResolution],
) -> LicensePointAggregation:
    point_values = [
        rule.license_points_deducted
        for rule in selected_rules
        if rule.license_points_deducted is not None
    ]
    for resolution in resolutions:
        if resolution.status == "CONDITIONAL":
            point_values.extend(
                rule.license_points_deducted
                for rule in resolution.rules
                if rule.license_points_deducted is not None
            )
    if not point_values:
        return LicensePointAggregation(status="RESOLVED", points_deducted=0)
    return LicensePointAggregation(status="RESOLVED", points_deducted=max(point_values))


def _conditional_money_branches(resolutions: list[ViolationResolution]) -> list[MoneyBranch]:
    branches: list[MoneyBranch] = []
    conditional = [resolution for resolution in resolutions if resolution.status == "CONDITIONAL" and resolution.rules]
    if len(conditional) != 1:
        return branches

    base_rules = [resolution.selected_rule for resolution in resolutions if resolution.selected_rule]
    base_rules = [rule for rule in base_rules if rule]
    for alternative in conditional[0].rules:
        rules = [*base_rules, alternative]
        if any(rule.fine_min is None or rule.fine_max is None for rule in rules):
            continue
        branches.append(
            MoneyBranch(
                label=_branch_label(alternative),
                min_total=sum(rule.fine_min or 0 for rule in rules),
                max_total=sum(rule.fine_max or 0 for rule in rules),
                default_total=sum(_midpoint(rule) for rule in rules),
                rule_ids=[rule.rule_id for rule in rules],
            )
        )
    return branches


def _midpoint(rule: SanctionRule) -> int:
    if rule.fine_min is None or rule.fine_max is None:
        return 0
    return int((rule.fine_min + rule.fine_max) / 2)


def _branch_label(rule: SanctionRule) -> str:
    if rule.article == "18" and rule.clause == "5" and rule.point == "a":
        return "Xe máy đến 125 cm3 hoặc đến 11 kW"
    if rule.article == "18" and rule.clause == "7" and rule.point == "b":
        return "Xe máy trên 125 cm3 hoặc trên 11 kW"
    return rule.source_location or rule.rule_id
