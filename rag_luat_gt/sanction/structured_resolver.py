from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from rag_luat_gt.schemas import ParsedQuery, ViolationFact
from rag_luat_gt.sanction.condition_resolver import resolve_violations
from rag_luat_gt.sanction.repository import SanctionRepository
from rag_luat_gt.sanction.schemas import SanctionLookup, SanctionRule, ViolationResolution
from rag_luat_gt.text import expand_query, normalize_text, strip_accents, tokenize


@dataclass
class PenaltyResolution:
    lookup: SanctionLookup | None = None
    resolutions: list[ViolationResolution] = field(default_factory=list)
    fallback_to_rag: bool = True
    debug: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class Interval:
    lower: float | None = None
    upper: float | None = None
    lower_inclusive: bool = False
    upper_inclusive: bool = True

    def contains(self, value: float) -> bool:
        if self.lower is not None:
            if self.lower_inclusive and value < self.lower:
                return False
            if not self.lower_inclusive and value <= self.lower:
                return False
        if self.upper is not None:
            if self.upper_inclusive and value > self.upper:
                return False
            if not self.upper_inclusive and value >= self.upper:
                return False
        return True


STOPWORDS = {
    "nguoi",
    "dieu",
    "khien",
    "phuong",
    "tien",
    "tham",
    "gia",
    "giao",
    "thong",
    "duong",
    "bo",
    "xe",
    "bi",
    "phat",
    "xu",
    "muc",
    "bao",
    "nhieu",
    "the",
    "nao",
    "thi",
    "va",
    "co",
    "diem",
    "giay",
    "phep",
    "lai",
    "quy",
    "dinh",
    "trong",
    "tren",
    "duoi",
    "tu",
    "den",
    "hoac",
    "mot",
    "dong",
    "thoi",
    "vua",
}

PHRASE_HINTS = [
    "den do",
    "den tin hieu",
    "mu bao hiem",
    "giay phep lai xe",
    "nong do con",
    "toc do",
    "qua toc do",
    "dien thoai",
    "nhan tin",
    "dt",
    "thiet bi dien tu",
    "thiet bi an toan",
    "tre em",
    "cao toc",
    "di vao duong cao toc",
    "lan dung xe khan cap",
    "quay dau",
    "di nguoc chieu",
    "dung xe",
    "do xe",
]


def resolve_penalty_query(repository: SanctionRepository, parsed: ParsedQuery) -> PenaltyResolution:
    event_date = parsed.legal_effective_date or parsed.event_date or parsed.query_reference_date or ""
    debug: dict[str, object] = {"resolver": "structured_semantic_v1"}

    if _has_multi_violation_cues(parsed.query):
        resolutions = resolve_violations(repository, parsed)
        resolutions = _augment_with_semantic_segments(repository, parsed, event_date, resolutions)
        resolutions = _dedupe_resolutions(resolutions)
        debug["resolution_statuses"] = [resolution.status for resolution in resolutions]
        if len(resolutions) >= 2:
            return PenaltyResolution(resolutions=resolutions, fallback_to_rag=False, debug=debug)

    exact = _exact_lookup(repository, parsed, event_date)
    if exact and exact.status in {"FOUND", "TEMPORAL_AMBIGUOUS", "NEEDS_CLARIFICATION"}:
        debug["exact_status"] = exact.status
        if not parsed.vehicle_code and parsed.behavior_code and exact.status == "FOUND" and _has_multiple_vehicle_groups(exact.rules):
            debug["sanction_vehicle_scope_split"] = True
        return PenaltyResolution(lookup=exact, fallback_to_rag=False, debug=debug)

    if parsed.violations:
        resolutions = resolve_violations(repository, parsed)
        if _has_multi_violation_cues(parsed.query):
            resolutions = _augment_with_semantic_segments(repository, parsed, event_date, resolutions)
        resolutions = _dedupe_resolutions(resolutions)
        debug["resolution_statuses"] = [resolution.status for resolution in resolutions]
        if len(resolutions) >= 2:
            return PenaltyResolution(resolutions=resolutions, fallback_to_rag=False, debug=debug)
        if len(resolutions) == 1:
            lookup = _lookup_from_resolution(resolutions[0])
            return PenaltyResolution(lookup=lookup, fallback_to_rag=lookup.status == "NOT_MAPPED", debug=debug)

    semantic = semantic_lookup(repository, parsed, event_date=event_date)
    debug["semantic_status"] = semantic.status
    if semantic.status in {"FOUND", "AMBIGUOUS", "NEEDS_CLARIFICATION", "TEMPORAL_AMBIGUOUS"}:
        return PenaltyResolution(lookup=semantic, fallback_to_rag=False, debug=debug)
    return PenaltyResolution(lookup=semantic, fallback_to_rag=True, debug=debug)


def semantic_lookup(
    repository: SanctionRepository,
    parsed: ParsedQuery,
    *,
    event_date: str,
    behavior_text: str | None = None,
) -> SanctionLookup:
    candidates = repository.candidate_rules(
        event_date=event_date,
        vehicle_code=parsed.vehicle_code,
        document_number=parsed.document_number,
        article=parsed.article,
        clause=parsed.clause,
        point=parsed.point,
    )
    if candidates.status != "FOUND":
        return candidates

    query_text = behavior_text or parsed.behavior_text_query or parsed.query
    query_profile = _profile(query_text)
    if not parsed.vehicle_code and _looks_like_vehicle_required_penalty(query_profile):
        scored_all = _score_candidates(query_profile, candidates.rules)
        if scored_all and scored_all[0][0] >= 0.24:
            branch_rules = _vehicle_branch_rules(scored_all)
            if len(branch_rules) >= 2:
                return SanctionLookup(status="FOUND", rules=branch_rules)

    if _requires_speed_band(query_profile) and _query_speed_interval(query_profile.text) is None:
        return SanctionLookup(
            status="NEEDS_CLARIFICATION",
            missing_fields=["speed_excess_kmh"],
            warnings=["Can xac dinh muc vuot qua toc do tinh bang km/h."],
        )

    scored = _score_candidates(query_profile, candidates.rules)
    if not scored or scored[0][0] < 0.24:
        return SanctionLookup(status="NOT_MAPPED", missing_fields=["behavior"])

    top_score = scored[0][0]
    best = [rule for score, rule in scored if score >= top_score - 0.04 and score >= 0.24][:5]
    if len(best) > 1 and _meaningfully_different(best):
        return SanctionLookup(
            status="AMBIGUOUS",
            rules=best,
            missing_fields=["behavior"],
            warnings=["Co nhieu rule co cau truc phu hop; can bo sung dieu kien hanh vi cu the hon."],
        )

    selected = scored[0][1].model_copy(update={"confidence": round(top_score, 3)})
    if selected.temporal_status in {"DEFERRED", "CONDITIONAL", "UNRESOLVED"} and selected.temporal_warning:
        return SanctionLookup(status="TEMPORAL_AMBIGUOUS", rules=[selected], warnings=[selected.temporal_warning])
    return SanctionLookup(status="FOUND", rules=[selected])


def _exact_lookup(repository: SanctionRepository, parsed: ParsedQuery, event_date: str) -> SanctionLookup | None:
    if not (parsed.behavior_code or parsed.behavior_text_query):
        return None
    lookup = repository.lookup(
        event_date=event_date,
        vehicle_code=parsed.vehicle_code,
        behavior_code=parsed.behavior_code,
        behavior_contains=parsed.behavior_text_query,
        document_number=parsed.document_number,
        article=parsed.article,
        clause=parsed.clause,
        point=parsed.point,
    )
    if lookup.status == "NEEDS_CLARIFICATION" and parsed.behavior_code:
        behavior_codes = _behavior_codes_for_scope_lookup(parsed)
        scoped = repository.lookup_behavior_codes(event_date=event_date, behavior_codes=behavior_codes, limit=50)
        if scoped.status == "FOUND" and any(violation.catalog_code == "NO_DRIVER_LICENSE" for violation in parsed.violations):
            return scoped
        if scoped.status == "FOUND" and _has_multiple_vehicle_groups(scoped.rules):
            return scoped
    return lookup


def _behavior_codes_for_scope_lookup(parsed: ParsedQuery) -> list[str]:
    codes: list[str] = []
    for violation in parsed.violations:
        codes.extend(str(code) for code in violation.conditions.get("behavior_codes", []) if code)
    if parsed.behavior_code:
        codes.append(parsed.behavior_code)
    return list(dict.fromkeys(codes))


def _augment_with_semantic_segments(
    repository: SanctionRepository,
    parsed: ParsedQuery,
    event_date: str,
    existing: list[ViolationResolution],
) -> list[ViolationResolution]:
    covered = " ".join(
        value
        for item in existing
        for value in [item.raw_span, item.behavior_text]
        if value
    )
    covered_ascii = _ascii(covered)
    result = list(existing)
    for segment in _violation_segments(parsed.query):
        segment_ascii = _ascii(segment)
        if segment_ascii and segment_ascii in covered_ascii:
            continue
        lookup = semantic_lookup(repository, parsed, event_date=event_date, behavior_text=segment)
        if lookup.status not in {"FOUND", "AMBIGUOUS", "NEEDS_CLARIFICATION", "TEMPORAL_AMBIGUOUS"}:
            continue
        result.append(_resolution_from_lookup(segment, lookup))
    return result


def _lookup_from_resolution(resolution: ViolationResolution) -> SanctionLookup:
    if resolution.status == "RESOLVED" and resolution.selected_rule:
        return SanctionLookup(status="FOUND", rules=[resolution.selected_rule], warnings=resolution.warnings)
    status = "AMBIGUOUS" if resolution.status == "CONDITIONAL" else resolution.status
    return SanctionLookup(
        status=status,
        rules=resolution.rules,
        warnings=resolution.warnings,
        missing_fields=resolution.missing_conditions,
    )


def _resolution_from_lookup(raw_span: str, lookup: SanctionLookup) -> ViolationResolution:
    selected = lookup.rules[0] if lookup.status == "FOUND" and len(lookup.rules) == 1 else None
    status = "RESOLVED" if selected else lookup.status
    rule = selected or (lookup.rules[0] if lookup.rules else None)
    return ViolationResolution(
        status=status,
        behavior_code=rule.behavior_code if rule and rule.behavior_code else "SEMANTIC_MATCH",
        behavior_text=rule.behavior_text if rule and rule.behavior_text else raw_span,
        raw_span=raw_span,
        rules=lookup.rules,
        selected_rule=selected,
        missing_conditions=lookup.missing_fields,
        warnings=lookup.warnings,
    )


@dataclass(frozen=True)
class QueryProfile:
    text: str
    tokens: set[str]
    phrases: set[str]


def _profile(text: str) -> QueryProfile:
    expanded = expand_query(text)
    normalized = _ascii(expanded)
    tokens = {token for token in tokenize(expanded) if _ascii(token) not in STOPWORDS}
    tokens = {_ascii(token) for token in tokens if _ascii(token)}
    phrases = {phrase for phrase in PHRASE_HINTS if phrase in normalized}
    return QueryProfile(text=normalized, tokens=tokens, phrases=phrases)


def _score_candidates(profile: QueryProfile, rules: list[SanctionRule]) -> list[tuple[float, SanctionRule]]:
    scored: list[tuple[float, SanctionRule]] = []
    for rule in rules:
        score = _score_rule(profile, rule)
        if score is not None:
            scored.append((score, rule))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored


def _score_rule(profile: QueryProfile, rule: SanctionRule) -> float | None:
    rule_text = _ascii(" ".join([rule.behavior_text or "", " ".join(rule.conditions), rule.article_title or ""]))
    if "gay tai nan" in rule_text and "gay tai nan" not in profile.text and "tai nan" not in profile.text:
        return None
    if _child_safety_query(profile) and not ("tre em" in rule_text and "thiet bi an toan" in rule_text):
        return None
    if _phone_query(profile) and not _phone_rule(rule_text):
        return None
    if _alcohol_query(profile) and "nong do con" not in rule_text:
        return None
    if _speed_query(profile) and not _speed_rule(rule_text):
        return None
    if _highway_entry_query(profile) and "di vao duong cao toc" not in rule_text:
        return None

    condition_score = _condition_score(profile, rule_text)
    if condition_score is None:
        return None

    rule_tokens = {_ascii(token) for token in tokenize(rule_text) if _ascii(token) not in STOPWORDS}
    if not rule_tokens:
        return None
    overlap = profile.tokens & rule_tokens
    lexical = len(overlap) / math.sqrt(max(len(profile.tokens), 1) * max(len(rule_tokens), 1))
    phrase_bonus = 0.0
    for phrase in profile.phrases:
        if phrase in rule_text:
            phrase_bonus += 0.08
    if _child_safety_query(profile):
        phrase_bonus += 0.25
    return lexical + phrase_bonus + condition_score


def _condition_score(profile: QueryProfile, rule_text: str) -> float | None:
    score = 0.0
    query_speed = _query_speed_interval(profile.text)
    if _speed_query(profile):
        rule_speed = _rule_speed_interval(rule_text)
        if not rule_speed or not query_speed:
            return None
        if not _intervals_match(query_speed, rule_speed):
            return None
        score += 0.35

    query_alcohol = _query_alcohol_interval(profile.text)
    if _alcohol_query(profile):
        rule_alcohol = _rule_alcohol_interval(rule_text)
        if not rule_alcohol or not query_alcohol:
            return None
        if not _intervals_match(query_alcohol, rule_alcohol):
            return None
        score += 0.35
    return score


def _intervals_match(query: Interval, rule: Interval) -> bool:
    if _interval_same_bounds(query, rule):
        return True
    if query.lower is not None and query.upper is not None:
        probe_low = query.lower if query.lower_inclusive else query.lower + 0.001
        probe_high = query.upper if query.upper_inclusive else query.upper - 0.001
        return rule.contains(probe_low) and rule.contains(probe_high)
    if query.lower is not None and query.upper is None:
        return rule.contains(query.lower + 0.001) and rule.upper is None
    if query.lower is None and query.upper is not None:
        return rule.contains(query.upper)
    return False


def _interval_same_bounds(left: Interval, right: Interval) -> bool:
    lower_same = (left.lower is None and right.lower is None) or _same_bound(left.lower, right.lower)
    upper_same = (left.upper is None and right.upper is None) or _same_bound(left.upper, right.upper)
    return lower_same and upper_same


def _same_bound(left: float | None, right: float | None) -> bool:
    if left is None or right is None:
        return False
    return abs(left - right) < 0.001


def _query_speed_interval(text: str) -> Interval | None:
    return _parse_interval(text, unit=r"(?:km/h|kmh)")


def _rule_speed_interval(text: str) -> Interval | None:
    if "toc do" not in text:
        return None
    return _parse_interval(text, unit=r"(?:km/h|kmh)")


def _query_alcohol_interval(text: str) -> Interval | None:
    if "nong do con" not in text and "mg/l" not in text and "miligam" not in text:
        return None
    return _parse_interval(text, unit=r"(?:mg/l|miligam(?:/1)?(?:\s+lit)?)")


def _rule_alcohol_interval(text: str) -> Interval | None:
    if "nong do con" not in text:
        return None
    decimal = re.search(r"\d+[,.]\d+", text)
    breath_text = text
    if decimal:
        breath_text = text[max(0, decimal.start() - 40) : decimal.end() + 40]
    return _parse_interval(breath_text, unit=r"(?:mg/l|miligam(?:/1)?(?:\s+lit)?)")


def _parse_interval(text: str, *, unit: str) -> Interval | None:
    number = r"(\d+(?:[,.]\d+)?)"
    value = lambda raw: float(raw.replace(",", "."))
    patterns = [
        (rf"(?:tu|tren)\s+0?{number}\s*{unit}\s+den\s+(?:duoi\s+)?0?{number}\s*{unit}", False, True),
        (rf"vuot qua\s+0?{number}\s*{unit}\s+den\s+0?{number}\s*{unit}", False, True),
    ]
    for pattern, lower_inclusive, upper_inclusive in patterns:
        match = re.search(pattern, text)
        if match:
            return Interval(value(match.group(1)), value(match.group(2)), lower_inclusive, upper_inclusive)

    upper = re.search(rf"(?:chua vuot qua|khong qua|den|duoi)\s+0?{number}\s*{unit}", text)
    if upper:
        return Interval(upper=value(upper.group(1)), upper_inclusive="duoi" not in upper.group(0))

    lower = re.search(rf"(?:tren|vuot qua|hon)\s+0?{number}\s*{unit}", text)
    if lower:
        return Interval(lower=value(lower.group(1)), lower_inclusive=False)

    exact = re.search(rf"\b0?{number}\s*{unit}", text)
    if exact:
        point = value(exact.group(1))
        return Interval(point, point, True, True)
    return None


def _requires_speed_band(profile: QueryProfile) -> bool:
    return _speed_query(profile) and "qua toc do" in profile.text


def _looks_like_vehicle_required_penalty(profile: QueryProfile) -> bool:
    return bool(profile.tokens & {"vuot", "den", "do", "toc", "nong", "con", "dien", "thoai", "cao"})


def _speed_query(profile: QueryProfile) -> bool:
    return "toc do" in profile.text or "qua toc do" in profile.text


def _speed_rule(rule_text: str) -> bool:
    return "qua toc do" in rule_text and re.search(r"\bkm/h\b|\bkmh\b", rule_text) is not None


def _alcohol_query(profile: QueryProfile) -> bool:
    return "nong do con" in profile.text or "mg/l" in profile.text or "miligam" in profile.text


def _phone_query(profile: QueryProfile) -> bool:
    return (
        "dien thoai" in profile.text
        or "thiet bi dien tu" in profile.text
        or "nhan tin" in profile.text
        or re.search(r"(?<![a-z0-9])dt(?![a-z0-9])", profile.text) is not None
    )


def _child_safety_query(profile: QueryProfile) -> bool:
    return "thiet bi an toan" in profile.text and any(term in profile.text for term in ["tre em", "tre", "con", "chau", "1,35", "1.35"])


def _phone_rule(rule_text: str) -> bool:
    return (
        "su dung dien thoai" in rule_text
        or "dung tay cam va su dung dien thoai" in rule_text
        or "thiet bi dien tu" in rule_text
    )


def _highway_entry_query(profile: QueryProfile) -> bool:
    return "cao toc" in profile.text and re.search(r"\b(?:di|vao|chay)\b.*\bcao toc\b", profile.text) is not None


def _violation_segments(query: str) -> list[str]:
    text = _ascii(query)
    parts = re.split(r"\s*(?:,|;|\+|\bdong thoi\b|\bvua\b|\bva\b)\s*", text)
    segments = []
    for part in parts:
        part = part.strip()
        if len(part.split()) < 2:
            continue
        if any(term in part for term in ["dung hoi", "dung nhac", "chon dai", "cu chon", "khong can hoi", "tra loi"]):
            continue
        if any(term in part for term in ["vuot", "khong", "dung", "su dung", "nong do", "toc do", "cao toc", "dien thoai", "dt", "nhan tin"]):
            segments.append(part)
    return segments


def _has_multi_violation_cues(query: str) -> bool:
    text = _ascii(query)
    return re.search(r"\b(?:dong thoi|vua|va)\b|,|;|\+", text) is not None and len(_violation_segments(query)) >= 2


def _dedupe_resolutions(resolutions: list[ViolationResolution]) -> list[ViolationResolution]:
    seen: set[str] = set()
    result: list[ViolationResolution] = []
    for resolution in resolutions:
        key = resolution.selected_rule.rule_id if resolution.selected_rule else _ascii(resolution.behavior_text)
        if key in seen:
            continue
        seen.add(key)
        result.append(resolution)
    return result


def _meaningfully_different(rules: list[SanctionRule]) -> bool:
    refs = {(rule.article, rule.clause, rule.point, tuple(rule.vehicle_codes)) for rule in rules}
    return len(refs) > 1


def _vehicle_branch_rules(scored: list[tuple[float, SanctionRule]]) -> list[SanctionRule]:
    selected: dict[str, SanctionRule] = {}
    top_score = scored[0][0]
    for score, rule in scored:
        if score < top_score - 0.12 or score < 0.24:
            continue
        group = _primary_vehicle_group(rule)
        if group not in selected:
            selected[group] = rule.model_copy(update={"confidence": round(score, 3)})
    return list(selected.values())


def _primary_vehicle_group(rule: SanctionRule) -> str:
    for code in rule.vehicle_codes:
        group = _vehicle_group(code)
        if group in {"CAR", "MOTORCYCLE", "BICYCLE", "SPECIALIZED_MOTOR_VEHICLE", "PEDESTRIAN"}:
            return group
    return _vehicle_group(rule.vehicle_codes[0]) if rule.vehicle_codes else rule.rule_id


def _has_multiple_vehicle_groups(rules: list[SanctionRule]) -> bool:
    groups: set[str] = set()
    for rule in rules:
        for code in rule.vehicle_codes:
            groups.add(_vehicle_group(code))
    return len(groups) >= 2


def _vehicle_group(code: str) -> str:
    if code in {"CAR", "FOUR_WHEEL_PASSENGER", "FOUR_WHEEL_CARGO", "CAR_SIMILAR"}:
        return "CAR"
    if code in {"MOTORCYCLE", "MOPED", "MOTORCYCLE_SIMILAR", "MOPED_SIMILAR"}:
        return "MOTORCYCLE"
    return code


def _ascii(text: str) -> str:
    return strip_accents(normalize_text(text))
