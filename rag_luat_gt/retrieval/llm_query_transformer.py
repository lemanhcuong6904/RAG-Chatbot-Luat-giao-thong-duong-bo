from __future__ import annotations

import json
import re
from typing import Any

from rag_luat_gt.config import (
    OPENAI_API_KEY,
    RAG_PRERAG_MAX_TOKENS,
    RAG_PRERAG_MODEL,
    RAG_PRERAG_PROVIDER,
    RAG_PRERAG_TEMPERATURE,
)
from rag_luat_gt.retrieval.query_planner import build_query_plan
from rag_luat_gt.sanction.behavior_catalog import match_behaviors
from rag_luat_gt.schemas import ParsedQuery, QueryPlan, ViolationFact
from rag_luat_gt.text import normalize_text, strip_accents


SYSTEM_PROMPT = """Bạn là bộ biến đổi truy vấn Pre-RAG cho chatbot pháp luật giao thông đường bộ Việt Nam.

Nhiệm vụ:
- Chuẩn hóa ý định truy vấn.
- Tách nhiều hành vi vi phạm nếu có.
- Lập query plan: EXPANSION, DECOMPOSITION, STRUCTURED_LOOKUP, LEGAL_COMPOSITION, MULTI_QUERY, STEP_BACK, HYDE, HYBRID_RETRIEVAL.
- Sinh multi_queries, step_back_query, hyde_text chỉ để truy xuất nguồn, không dùng làm câu trả lời pháp lý.

Ràng buộc:
- Không bịa mức phạt, điểm GPLX, điều khoản hoặc kết luận pháp lý.
- Nếu người dùng nêu Điều/Khoản/Điểm/số văn bản rõ ràng, không được làm loãng bằng multi-query/hyde.
- Penalty query đã map được structured sanction thì ưu tiên STRUCTURED_LOOKUP.
- Trả về JSON hợp lệ duy nhất, không markdown.
"""


ALLOWED_INTENTS = {
    "GENERAL_LEGAL_QA",
    "PENALTY_LOOKUP",
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


def transform_query_with_llm(parsed: ParsedQuery) -> tuple[ParsedQuery, dict[str, Any]]:
    if RAG_PRERAG_PROVIDER != "openai":
        return parsed, {"enabled": False, "provider": RAG_PRERAG_PROVIDER}
    if not OPENAI_API_KEY:
        return parsed, {"enabled": True, "provider": "openai", "error": "OPENAI_API_KEY is not configured"}

    try:
        payload = _call_openai(parsed)
        transformed = merge_llm_transform(parsed, payload)
        return transformed, {"enabled": True, "provider": "openai", "model": RAG_PRERAG_MODEL, "payload": payload}
    except Exception as exc:
        return parsed, {"enabled": True, "provider": "openai", "model": RAG_PRERAG_MODEL, "error": str(exc)}


def merge_llm_transform(parsed: ParsedQuery, payload: dict[str, Any]) -> ParsedQuery:
    explicit_reference = any([parsed.document_number, parsed.article, parsed.clause, parsed.point])
    updates: dict[str, Any] = {}

    intent = payload.get("intent")
    if isinstance(intent, str) and intent in ALLOWED_INTENTS:
        updates["intent"] = intent
        updates["primary_intent"] = intent

    for field in [
        "normalized_query",
        "retrieval_query",
        "evidence_validation_query",
        "vehicle_type",
        "vehicle_code",
        "behavior_code",
        "behavior_text_query",
        "desired_rule_function",
    ]:
        value = payload.get(field)
        if isinstance(value, str) and value.strip():
            updates[field] = value.strip()

    for field in ["requested_facets", "conditions", "keywords"]:
        value = payload.get(field)
        if isinstance(value, list):
            updates[field] = [str(item) for item in value if item]

    violations = _merge_violations(parsed.violations, _violations_from_payload(payload.get("violations")))
    if violations:
        updates["violations"] = violations
        updates.setdefault("behavior_code", violations[0].behavior_code)
        updates.setdefault("behavior_text_query", violations[0].behavior_contains)

    transformed = parsed.model_copy(update=updates)
    plan = _plan_from_payload(transformed, payload.get("query_plan"))
    if explicit_reference:
        plan.multi_queries = []
        plan.step_back_query = None
        plan.hyde_text = None
        plan.strategy = ["DIRECT", "EXPANSION", "HYBRID_RETRIEVAL"]
    transformed.query_plan = plan
    return transformed


def _violations_from_payload(value: Any) -> list[ViolationFact]:
    if not isinstance(value, list):
        return []

    violations: list[ViolationFact] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        behavior_code = str(item.get("behavior_code") or "").strip()
        if not behavior_code or behavior_code in seen:
            continue
        seen.add(behavior_code)
        violations.append(
            ViolationFact(
                behavior_code=behavior_code,
                behavior_text=str(item.get("behavior_text") or item.get("raw_span") or behavior_code),
                raw_span=str(item.get("raw_span") or "") or None,
                behavior_contains=str(item.get("behavior_contains") or "") or None,
                catalog_code=str(item.get("catalog_code") or "") or None,
                conditions=item.get("conditions") if isinstance(item.get("conditions"), dict) else {},
                confidence=float(item.get("confidence") or 1.0),
            )
        )
    return violations


def _merge_violations(
    base_violations: list[ViolationFact],
    llm_violations: list[ViolationFact],
) -> list[ViolationFact]:
    if not llm_violations:
        return base_violations

    merged: list[ViolationFact] = []
    seen: set[str] = set()
    for violation in llm_violations:
        enriched = _enrich_violation_from_catalog(violation)
        base = _matching_base_violation(enriched, base_violations)
        if base:
            enriched = base.model_copy(
                update={
                    "behavior_text": enriched.behavior_text or base.behavior_text,
                    "raw_span": enriched.raw_span or base.raw_span,
                    "confidence": enriched.confidence,
                }
            )
        key = enriched.catalog_code or enriched.behavior_code
        if key in seen:
            continue
        seen.add(key)
        merged.append(enriched)

    for base in base_violations:
        key = base.catalog_code or base.behavior_code
        if key not in seen:
            seen.add(key)
            merged.append(base)
    return merged


def _enrich_violation_from_catalog(violation: ViolationFact) -> ViolationFact:
    probe = " ".join(part for part in [violation.raw_span, violation.behavior_text] if part)
    matches = match_behaviors(probe)
    if not matches:
        return violation

    match = matches[0]
    codes = [str(code) for code in match.get("rule_behavior_codes") or [] if code]
    if not codes:
        return violation

    conditions = dict(violation.conditions)
    conditions.setdefault("behavior_codes", codes)
    return violation.model_copy(
        update={
            "behavior_code": codes[0],
            "behavior_text": str(match.get("canonical_text") or violation.behavior_text),
            "behavior_contains": str(match.get("behavior_contains") or "") or violation.behavior_contains,
            "catalog_code": str(match.get("catalog_code") or "") or violation.catalog_code,
            "conditions": conditions,
        }
    )


def _matching_base_violation(
    violation: ViolationFact,
    base_violations: list[ViolationFact],
) -> ViolationFact | None:
    if violation.catalog_code:
        match = next((base for base in base_violations if base.catalog_code == violation.catalog_code), None)
        if match:
            return match
    if violation.behavior_code:
        match = next((base for base in base_violations if base.behavior_code == violation.behavior_code), None)
        if match:
            return match

    raw = _norm(" ".join(part for part in [violation.raw_span, violation.behavior_text] if part))
    if not raw:
        return None
    return next(
        (
            base
            for base in base_violations
            if raw in _norm(" ".join(part for part in [base.raw_span, base.behavior_text] if part))
            or _norm(str(base.raw_span or base.behavior_text)) in raw
        ),
        None,
    )


def _norm(value: str) -> str:
    return strip_accents(normalize_text(value))


def _plan_from_payload(parsed: ParsedQuery, value: Any) -> QueryPlan:
    fallback = build_query_plan(parsed)
    if not isinstance(value, dict):
        return fallback

    plan_data = fallback.model_dump()
    if isinstance(value.get("strategy"), list):
        plan_data["strategy"] = [str(item) for item in value["strategy"] if item]
    if isinstance(value.get("use_structured_sanction"), bool):
        plan_data["use_structured_sanction"] = value["use_structured_sanction"]
    for field in ["expanded_query", "step_back_query", "hyde_text"]:
        if isinstance(value.get(field), str):
            plan_data[field] = value[field].strip() or None
    for field in ["subqueries", "multi_queries"]:
        if isinstance(value.get(field), list):
            plan_data[field] = [str(item) for item in value[field] if item]
    return QueryPlan(**plan_data)


def _call_openai(parsed: ParsedQuery) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=RAG_PRERAG_MODEL,
        temperature=RAG_PRERAG_TEMPERATURE,
        max_tokens=RAG_PRERAG_MAX_TOKENS,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _user_prompt(parsed)},
        ],
    )
    content = response.choices[0].message.content or "{}"
    return json.loads(_strip_code_fence(content))


def _user_prompt(parsed: ParsedQuery) -> str:
    return json.dumps(
        {
            "query": parsed.query,
            "current_parse": parsed.model_dump(),
            "output_schema": {
                "intent": "string",
                "normalized_query": "string",
                "retrieval_query": "string",
                "vehicle_type": "string|null",
                "vehicle_code": "string|null",
                "behavior_code": "string|null",
                "behavior_text_query": "string|null",
                "requested_facets": ["string"],
                "violations": [
                    {
                        "behavior_code": "string",
                        "behavior_text": "string",
                        "raw_span": "string",
                        "behavior_contains": "string|null",
                        "catalog_code": "string|null",
                        "conditions": {},
                        "confidence": 1.0,
                    }
                ],
                "query_plan": {
                    "strategy": ["string"],
                    "use_structured_sanction": False,
                    "expanded_query": "string|null",
                    "subqueries": ["string"],
                    "multi_queries": ["string"],
                    "step_back_query": "string|null",
                    "hyde_text": "string|null",
                },
            },
        },
        ensure_ascii=False,
    )


def _strip_code_fence(value: str) -> str:
    stripped = value.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, flags=re.DOTALL)
    return match.group(1).strip() if match else stripped
