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
        return PenaltyResolution(
            lookup=exact,
            fallback_to_rag=exact.status == "NEEDS_CLARIFICATION" and "vehicle_code" in exact.missing_fields,
            debug=debug,
        )

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
            return PenaltyResolution(
                lookup=lookup,
                fallback_to_rag=lookup.status == "NOT_MAPPED"
                or (lookup.status == "NEEDS_CLARIFICATION" and "vehicle_code" in lookup.missing_fields),
                debug=debug,
            )

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
    ambiguous = _ambiguous_penalty_lookup(parsed, query_profile)
    if ambiguous:
        return ambiguous
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
    condition_lookup = _material_condition_lookup(parsed, query_profile, selected)
    if condition_lookup:
        return condition_lookup
    if selected.temporal_status in {"DEFERRED", "CONDITIONAL", "UNRESOLVED"} and selected.temporal_warning:
        return SanctionLookup(status="TEMPORAL_AMBIGUOUS", rules=[selected], warnings=[selected.temporal_warning])
    return SanctionLookup(status="FOUND", rules=[selected])


def _material_condition_lookup(
    parsed: ParsedQuery,
    profile: QueryProfile,
    rule: SanctionRule,
) -> SanctionLookup | None:
    rule_text = _ascii(" ".join([rule.behavior_text or "", rule.source_text or "", rule.parent_clause_text or ""]))
    if not _child_safety_rule(rule_text):
        return None
    if not any(term in profile.text for term in ["tre", "tre em", "con", "chau"]):
        return None

    missing: list[str] = []
    asks_missing_safety_device = _query_asks_missing_child_safety_device(profile.text)
    if not asks_missing_safety_device and not _query_mentions_child_age_height(profile.text):
        missing.append("child_age_height")
    if (
        not asks_missing_safety_device
        and "cung hang ghe voi nguoi lai" in rule_text
        and not _query_mentions_exact_child_seat_position(profile.text)
    ):
        missing.append("seat_position")
    if parsed.event_date is None:
        missing.append("event_date")

    if not missing:
        return None
    warnings = [
        (
            "Can lam ro cac dieu kien vat chat cua quy dinh duoc truy hoi: tuoi/chieu cao cua tre, "
            "vi tri ngoi co dung la cung hang ghe voi nguoi lai hay khong, va thoi diem xay ra hanh vi."
        )
    ]
    return SanctionLookup(status="NEEDS_CLARIFICATION", rules=[rule], missing_fields=missing, warnings=warnings)


def _ambiguous_penalty_lookup(parsed: ParsedQuery, profile: QueryProfile) -> SanctionLookup | None:
    missing: list[str] = []
    warning: str | None = None

    if _speed_query(profile) and "qua toc do" in profile.text and _query_speed_interval(profile.text) is None:
        missing.append("speed_excess_kmh")
        if not parsed.vehicle_code:
            missing.append("vehicle_code")
        warning = "Can lam ro loai phuong tien va muc vuot qua toc do tinh bang km/h."
    elif _alcohol_query(profile) and _query_alcohol_interval(profile.text) is None:
        missing.append("alcohol_concentration")
        if not parsed.vehicle_code:
            missing.append("vehicle_code")
        warning = "Can lam ro loai phuong tien va nong do con do duoc trong mau hoac khi tho."
    elif _overloaded_passenger_query(profile):
        if not parsed.vehicle_code:
            missing.append("vehicle_code")
        if not _query_mentions_passenger_count(profile.text):
            missing.append("passenger_count")
        warning = "Can lam ro loai phuong tien, so nguoi thuc te cho va so nguoi vuot qua quy dinh."
    elif _paperwork_query(profile):
        if not parsed.vehicle_code:
            missing.append("vehicle_code")
        if not _query_mentions_paper_type(profile.text):
            missing.append("paper_type")
        warning = "Can lam ro loai phuong tien va loai giay to khong mang/khong co."
    elif _parking_query(profile):
        if not parsed.vehicle_code:
            missing.append("vehicle_code")
        if not _query_mentions_parking_location(profile.text):
            missing.append("parking_location")
        warning = "Can lam ro loai phuong tien va vi tri/tinh huong dung, do xe cu the."
    elif _highway_wrong_lane_query(profile):
        if not parsed.vehicle_code:
            missing.append("vehicle_code")
        missing.append("lane_behavior")
        warning = "Can lam ro loai phuong tien va hanh vi sai lan cu the tren duong cao toc."
    elif _cargo_overload_query(profile):
        if not parsed.vehicle_code:
            missing.append("vehicle_code")
        if not _query_mentions_load_ratio(profile.text):
            missing.append("load_ratio")
        if not _query_mentions_liable_actor(profile.text):
            missing.append("liable_actor")
        warning = "Can lam ro loai phuong tien, ty le qua tai va chu the bi xu phat la nguoi lai hay chu xe."
    elif _generic_lighting_query(profile):
        if not parsed.vehicle_code:
            missing.append("vehicle_code")
        if not _query_mentions_lighting_context(profile.text):
            missing.append("lighting_context")
        warning = "Can lam ro loai phuong tien va boi canh khong bat den/den khong dung quy dinh."
    elif _plate_query(profile):
        if not parsed.vehicle_code:
            missing.append("vehicle_code")
        if not _query_mentions_plate_issue(profile.text):
            missing.append("plate_issue")
        warning = "Can lam ro loai phuong tien va loi bien so cu the."
    elif _insurance_query(profile):
        if not parsed.vehicle_code:
            missing.append("vehicle_code")
        warning = "Can lam ro loai phuong tien va loai bao hiem/giay chung nhan bao hiem."
    elif _underage_query(profile):
        if not parsed.vehicle_code:
            missing.append("vehicle_code")
        if not _query_mentions_age(profile.text):
            missing.append("driver_age")
        warning = "Can lam ro loai phuong tien va tuoi nguoi dieu khien."
    elif _passenger_pickup_query(profile):
        if not parsed.vehicle_code:
            missing.append("vehicle_code")
        if not _query_mentions_pickup_context(profile.text):
            missing.append("pickup_dropoff_context")
        warning = "Can lam ro loai xe khach va boi canh don/tra khach sai quy dinh."
    elif _falling_cargo_query(profile):
        if not parsed.vehicle_code:
            missing.append("vehicle_code")
        if not _query_mentions_cargo_context(profile.text):
            missing.append("cargo_context")
        warning = "Can lam ro loai phuong tien va tinh huong hang roi/vang khoi xe."
    elif _wrong_way_query(profile):
        if not parsed.vehicle_code:
            missing.append("vehicle_code")
        if not _query_mentions_wrong_way_context(profile.text):
            missing.append("road_context")
        warning = "Can lam ro loai phuong tien va boi canh di nguoc chieu."

    if not missing:
        return None
    return SanctionLookup(
        status="NEEDS_CLARIFICATION",
        missing_fields=list(dict.fromkeys(missing)),
        warnings=[warning or "Can bo sung dieu kien bat buoc de xac dinh che tai."],
    )


def _overloaded_passenger_query(profile: QueryProfile) -> bool:
    return any(term in profile.text for term in ["cho qua nguoi", "cho qua so nguoi", "qua nguoi"])


def _cargo_overload_query(profile: QueryProfile) -> bool:
    return any(term in profile.text for term in ["qua tai", "cho qua tai", "qua kho tai trong", "vuot tai trong"])


def _query_mentions_load_ratio(text: str) -> bool:
    return "%" in text or re.search(r"\b\d+\s*(?:phan tram|tan|kg)\b", text) is not None


def _query_mentions_liable_actor(text: str) -> bool:
    return any(term in text for term in ["nguoi lai", "tai xe", "chu xe", "don vi kinh doanh", "ca nhan", "to chuc"])


def _generic_lighting_query(profile: QueryProfile) -> bool:
    return any(term in profile.text for term in ["khong bat den", "khong mo den", "den xe", "khong co den"])


def _query_mentions_lighting_context(text: str) -> bool:
    return any(term in text for term in ["ban dem", "suong mu", "ham", "den chieu sang", "den tin hieu", "den soi bien so"])


def _plate_query(profile: QueryProfile) -> bool:
    return "bien so" in profile.text and any(term in profile.text for term in ["sai", "khong dung", "che", "mo", "khong co", "gia"])


def _query_mentions_plate_issue(text: str) -> bool:
    return any(term in text for term in ["che lap", "khong ro", "khong gan", "gia", "khong dung vi tri", "sai quy cach"])


def _insurance_query(profile: QueryProfile) -> bool:
    return "bao hiem" in profile.text and any(term in profile.text for term in ["khong co", "khong mang", "het han"])


def _underage_query(profile: QueryProfile) -> bool:
    return any(term in profile.text for term in ["chua du tuoi", "khong du tuoi", "duoi tuoi"])


def _query_mentions_age(text: str) -> bool:
    return re.search(r"\b\d+\s*(?:tuoi|t)\b", text) is not None


def _passenger_pickup_query(profile: QueryProfile) -> bool:
    return any(term in profile.text for term in ["don sai cho", "tra sai cho", "don tra khach", "don khach sai", "tra khach sai"])


def _query_mentions_pickup_context(text: str) -> bool:
    return any(term in text for term in ["cao toc", "noi cam", "ben xe", "diem don", "diem tra", "hop dong", "tuyen co dinh"])


def _falling_cargo_query(profile: QueryProfile) -> bool:
    return any(term in profile.text for term in ["hang roi", "hang vang", "roi khoi xe", "nhom khoi xe", "roi xuong duong"])


def _query_mentions_cargo_context(text: str) -> bool:
    return any(term in text for term in ["gay nguy hiem", "gay tai nan", "khong che chan", "container", "vat lieu"])


def _wrong_way_query(profile: QueryProfile) -> bool:
    return any(term in profile.text for term in ["di nguoc chieu", "chay nguoc chieu", "nguoc chieu"])


def _query_mentions_wrong_way_context(text: str) -> bool:
    return any(term in text for term in ["cao toc", "duong mot chieu", "bien cam", "gay tai nan"])


def _query_mentions_passenger_count(text: str) -> bool:
    return re.search(r"\b\d+\s*(?:nguoi|khach|cho)\b", text) is not None or any(
        term in text for term in ["vuot qua", "qua may nguoi", "qua bao nhieu"]
    )


def _paperwork_query(profile: QueryProfile) -> bool:
    return any(term in profile.text for term in ["giay to xe", "khong mang giay to", "khong co giay to"])


def _query_mentions_paper_type(text: str) -> bool:
    return any(term in text for term in ["gplx", "giay phep lai xe", "bang lai", "dang ky", "kiem dinh", "bao hiem"])


def _parking_query(profile: QueryProfile) -> bool:
    return any(term in profile.text for term in ["do xe sai cho", "dung do sai cho", "do sai cho", "dung xe sai cho"])


def _query_mentions_parking_location(text: str) -> bool:
    return any(
        term in text
        for term in [
            "tren cau",
            "gam cau",
            "trong ham",
            "cao toc",
            "giao lo",
            "nga ba",
            "nga tu",
            "via he",
            "long duong",
            "bien cam",
            "noi cam",
            "duong sat",
            "diem dung don",
        ]
    )


def _child_safety_rule(rule_text: str) -> bool:
    return "tre em" in rule_text and (
        "1,35" in rule_text
        or "1.35" in rule_text
        or "135" in rule_text
        or "thiet bi an toan" in rule_text
        or "cung hang ghe voi nguoi lai" in rule_text
    )


def _query_mentions_child_age_height(text: str) -> bool:
    has_age = any(term in text for term in ["duoi 10", "10 tuoi", "tre em duoi"])
    has_height = any(term in text for term in ["1,35", "1.35", "1m35", "135"])
    return has_age and has_height


def _query_mentions_exact_child_seat_position(text: str) -> bool:
    return "cung hang ghe voi nguoi lai" in text or "hang ghe voi nguoi lai" in text


def _query_asks_missing_child_safety_device(text: str) -> bool:
    return any(term in text for term in ["khong dung thiet bi an toan", "khong su dung thiet bi an toan", "khong co thiet bi an toan"])


def _highway_wrong_lane_query(profile: QueryProfile) -> bool:
    return "cao toc" in profile.text and any(term in profile.text for term in ["sai lan", "di sai lan", "chay sai lan"])


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
    if lookup.status == "NOT_FOUND" and parsed.vehicle_code and parsed.behavior_code:
        scoped = repository.lookup_behavior_codes(
            event_date=event_date,
            behavior_codes=_behavior_codes_for_scope_lookup(parsed),
            limit=50,
        )
        filtered = _filter_rules_for_vehicle(scoped.rules, parsed.vehicle_code) if scoped.status == "FOUND" else []
        if filtered:
            return SanctionLookup(status="FOUND", rules=filtered)
    if lookup.status == "NEEDS_CLARIFICATION" and parsed.behavior_code:
        behavior_codes = _behavior_codes_for_scope_lookup(parsed)
        scoped = repository.lookup_behavior_codes(event_date=event_date, behavior_codes=behavior_codes, limit=50)
        if scoped.status == "FOUND" and parsed.vehicle_code:
            filtered = _filter_rules_for_vehicle(scoped.rules, parsed.vehicle_code)
            if filtered:
                return SanctionLookup(status="FOUND", rules=filtered)
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
    return any(term in profile.text for term in ["nong do con", "ruou", "bia", "mg/l", "miligam"])


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
    inferred = _inferred_vehicle_group(rule)
    if inferred:
        return inferred
    for code in rule.vehicle_codes:
        group = _vehicle_group(code)
        if group in {"CAR", "MOTORCYCLE", "BICYCLE", "SPECIALIZED_MOTOR_VEHICLE", "PEDESTRIAN"}:
            return group
    return _vehicle_group(rule.vehicle_codes[0]) if rule.vehicle_codes else rule.rule_id


def _has_multiple_vehicle_groups(rules: list[SanctionRule]) -> bool:
    groups: set[str] = set()
    for rule in rules:
        inferred = _inferred_vehicle_group(rule)
        if inferred:
            groups.add(inferred)
            continue
        for code in rule.vehicle_codes:
            groups.add(_vehicle_group(code))
    return len(groups) >= 2


def _filter_rules_for_vehicle(rules: list[SanctionRule], vehicle_code: str) -> list[SanctionRule]:
    target = _vehicle_group(vehicle_code)
    return [rule for rule in rules if _rule_vehicle_group(rule) == target]


def _rule_vehicle_group(rule: SanctionRule) -> str | None:
    for code in rule.vehicle_codes:
        group = _vehicle_group(code)
        if group:
            return group
    return _inferred_vehicle_group(rule)


def _inferred_vehicle_group(rule: SanctionRule) -> str | None:
    text = _ascii(" ".join([rule.parent_clause_text or "", rule.source_text or "", rule.behavior_text or ""]))
    if any(term in text for term in ["xe o to", "tuong tu xe o to", "xe cho nguoi bon banh", "xe cho hang bon banh"]):
        return "CAR"
    if any(term in text for term in ["xe mo to", "xe gan may", "tuong tu xe mo to", "tuong tu xe gan may"]):
        return "MOTORCYCLE"
    if "xe may chuyen dung" in text:
        return "SPECIALIZED_MOTOR_VEHICLE"
    if "xe dap" in text:
        return "BICYCLE"
    return None


def _vehicle_group(code: str) -> str:
    if code in {"CAR", "FOUR_WHEEL_PASSENGER", "FOUR_WHEEL_CARGO", "CAR_SIMILAR"}:
        return "CAR"
    if code in {"MOTORCYCLE", "MOPED", "MOTORCYCLE_SIMILAR", "MOPED_SIMILAR"}:
        return "MOTORCYCLE"
    return code


def _ascii(text: str) -> str:
    return strip_accents(normalize_text(text))
