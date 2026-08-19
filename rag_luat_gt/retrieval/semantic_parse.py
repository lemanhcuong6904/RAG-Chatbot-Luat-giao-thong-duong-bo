from __future__ import annotations

from typing import Any

from rag_luat_gt.license_classes import LICENSE_CLASS_ORDER, extract_license_classes
from rag_luat_gt.schemas import ParsedQuery
from rag_luat_gt.text import normalize_text, strip_accents


ALLOWED_INTENTS = {
    "GENERAL_LEGAL_QA",
    "PENALTY_LOOKUP",
    "LEGAL_RULE_LOOKUP",
    "AUTHORITY_LOOKUP",
    "PROCEDURE_LOOKUP",
    "TEMPORAL_LOOKUP",
    "EXACT_PROVISION_LOOKUP",
    "LICENSE_POINT_BALANCE",
    "DRIVER_AGE_REQUIREMENT",
    "ENUMERATION",
    "DRIVER_LICENSE",
    "REGISTRATION",
    "SPEED_RULE",
    "FEE_LOOKUP",
    "AMENDMENT_COMPARE",
    "ARTICLE_LOOKUP",
}

ALLOWED_VEHICLE_CODES = {
    "CAR",
    "TRUCK",
    "BUS",
    "MOTORCYCLE",
    "MOPED",
    "BICYCLE",
    "PEDESTRIAN",
    "SPECIALIZED_MOTOR_VEHICLE",
}

ALLOWED_PLAN_STRATEGIES = {
    "DIRECT",
    "EXPANSION",
    "STRUCTURED_LOOKUP",
    "DECOMPOSITION",
    "LEGAL_COMPOSITION",
    "MULTI_QUERY",
    "STEP_BACK",
    "HYDE",
    "HYBRID_RETRIEVAL",
    "EXHAUSTIVE_ARTICLE",
}

SAFE_STRING_FIELDS = {
    "normalized_query",
    "retrieval_query",
    "evidence_validation_query",
    "vehicle_type",
    "behavior_text_query",
    "desired_rule_function",
}

SAFE_LIST_FIELDS = {
    "requested_facets",
    "conditions",
    "keywords",
    "must_include_terms",
    "must_not_confuse_with",
}


def validated_semantic_updates(parsed: ParsedQuery, payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    updates: dict[str, Any] = {}
    notes: list[str] = []
    explicit_reference = _has_explicit_reference(parsed)

    intent = payload.get("intent")
    if isinstance(intent, str) and intent in ALLOWED_INTENTS:
        if explicit_reference and intent != parsed.intent:
            notes.append("ignored_intent_for_explicit_reference")
        else:
            updates["intent"] = intent
            updates["primary_intent"] = intent

    for field in SAFE_STRING_FIELDS:
        if explicit_reference and field in {"normalized_query", "retrieval_query", "evidence_validation_query"}:
            continue
        value = _clean_string(payload.get(field), max_len=900)
        if value:
            updates[field] = value

    vehicle_code = _clean_string(payload.get("vehicle_code"), max_len=60)
    if vehicle_code:
        upper_code = vehicle_code.upper()
        if upper_code in ALLOWED_VEHICLE_CODES:
            updates["vehicle_code"] = upper_code
        else:
            notes.append("ignored_unknown_vehicle_code")

    for field in SAFE_LIST_FIELDS:
        values = _clean_list(payload.get(field), max_items=12, max_len=180)
        if values:
            updates[field] = values

    classes = _validated_license_classes(parsed, payload.get("license_classes"))
    if classes:
        updates["license_classes"] = classes

    return updates, notes


def filtered_plan_strategies(value: Any, fallback: list[str]) -> list[str]:
    if not isinstance(value, list):
        return fallback
    selected = [str(item).strip().upper() for item in value if str(item).strip().upper() in ALLOWED_PLAN_STRATEGIES]
    return _dedupe(selected) or fallback


def _validated_license_classes(parsed: ParsedQuery, value: Any) -> list[str]:
    deterministic = extract_license_classes(parsed.query) or parsed.license_classes
    if deterministic:
        return deterministic
    if not isinstance(value, list):
        return []
    allowed = set(LICENSE_CLASS_ORDER)
    selected = [str(item).strip().upper() for item in value if str(item).strip().upper() in allowed]
    return _dedupe(selected)


def _clean_string(value: Any, *, max_len: int) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        return None
    return cleaned[:max_len]


def _clean_list(value: Any, *, max_items: int, max_len: int) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        cleaned = _clean_string(item, max_len=max_len)
        if not cleaned:
            continue
        key = strip_accents(normalize_text(cleaned))
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
        if len(result) >= max_items:
            break
    return result


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = strip_accents(normalize_text(value))
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _has_explicit_reference(parsed: ParsedQuery) -> bool:
    return any([parsed.document_number, parsed.article, parsed.clause, parsed.point])
