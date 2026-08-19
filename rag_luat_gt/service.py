from __future__ import annotations

from rag_luat_gt.config import (
    RAG_LLM_MODEL,
    RAG_LLM_PROVIDER,
    RAG_STRUCTURED_TABLE_ENABLED,
    RAG_STRUCTURED_TABLE_USE_WITH_LLM,
    RAG_STRUCTURED_FACT_ENABLED,
    RAG_STRUCTURED_FACT_USE_WITH_LLM,
    RAG_STRUCTURED_LOOKUP_ENABLED,
    RAG_STRUCTURED_SANCTION_REQUIRE_LLM_PLAN,
    SANCTION_ENABLED,
)
from rag_luat_gt.citation_format import ensure_claim_citations, normalize_inline_legal_refs
from rag_luat_gt.generation.answerer import build_answer
from rag_luat_gt.generation.llm_client import is_chat_provider_configured, resolve_llm, set_request_llm
from rag_luat_gt.generation.multi_sanction_answerer import build_multi_sanction_response
from rag_luat_gt.generation.sanction_answerer import build_sanction_response
from rag_luat_gt.generation.structured_sanction_llm import maybe_render_structured_sanction_with_llm
from rag_luat_gt.retrieval.hybrid import HybridRetriever
from rag_luat_gt.retrieval.llm_query_transformer import transform_query_with_llm
from rag_luat_gt.retrieval.query_parser import parse_query
from rag_luat_gt.retrieval.query_router import QueryRouteDecision, apply_route_decision, direct_route_response, route_query
from rag_luat_gt.sanction.composition_engine import compose_sanctions
from rag_luat_gt.sanction.repository import SanctionRepository
from rag_luat_gt.sanction.structured_resolver import resolve_penalty_query
from rag_luat_gt.structured_facts import build_structured_fact_answer
from rag_luat_gt.schemas import ChatRequest, ChatResponse, ParsedQuery
from rag_luat_gt.structured_tables import build_structured_table_answer
from rag_luat_gt.text import normalize_text, strip_accents


class RAGService:
    def __init__(self) -> None:
        self.retriever = HybridRetriever()
        self.sanctions = SanctionRepository()
        self.warmup_error: str | None = None
        self.warmup_status: str = "NOT_STARTED"

    def warm_up(self) -> None:
        dense = getattr(self.retriever, "dense", None)
        if not dense:
            self.warmup_status = "SKIPPED_DENSE_INACTIVE"
            reason = self.retriever.dense_error or "dense index is not ready or dense retrieval is disabled"
            print(f"[RAG] Warm-up skipped: {reason}", flush=True)
            return
        try:
            self.warmup_status = "LOADING_DENSE_MODEL"
            print("[RAG] Loading dense retrieval model for warm-up...", flush=True)
            if dense.embedder is None:
                from rag_luat_gt.embedding.bge_m3 import BGEM3Embedder

                dense.embedder = BGEM3Embedder(
                    model_name=dense.settings.model,
                    query_instruction=dense.settings.query_instruction,
                    document_instruction=dense.settings.document_instruction,
                )
            dense.embedder.encode_query("khởi động mô hình truy xuất")
            self.warmup_status = "READY"
            print("[RAG] Dense retrieval model warm-up complete.", flush=True)
        except Exception as exc:
            self.warmup_error = str(exc)
            self.warmup_status = "ERROR"
            print(f"[RAG] Dense retrieval model warm-up failed: {exc}", flush=True)

    def answer(self, request: ChatRequest) -> ChatResponse:
        set_request_llm(request.llm_provider, request.llm_model)
        parsed = parse_query(request)
        initial_parsed = parsed
        if _requires_external_law(parsed):
            route_decision = QueryRouteDecision(
                route="OUT_OF_SCOPE",
                legal_domain="other_law",
                retrieval_strategy="NONE",
                direct_answer=_external_law_answer(parsed),
                reason="outside supported traffic-law administrative corpus",
                confidence=0.95,
            )
            direct_response = direct_route_response(route_decision)
            if direct_response:
                if request.debug:
                    direct_response.debug = {
                        **(direct_response.debug or {}),
                        "routing": {
                            "query_router": {"enabled": False, "decision": route_decision.model_dump()},
                            "sanction_attempted": False,
                            "fallback_to_rag": False,
                        },
                    }
                else:
                    direct_response.debug = None
                return _finalize_response(direct_response)
        parsed, route_decision, router_debug = route_query(parsed)
        if (
            route_decision.route == "OUT_OF_SCOPE"
            and _looks_like_traffic_law_query(parsed)
            and not _requires_external_law(parsed)
        ):
            route_decision = route_decision.model_copy(
                update={
                    "route": "RAG",
                    "legal_domain": "traffic_law",
                    "retrieval_strategy": "FACTOID",
                    "reason": f"{route_decision.reason or 'router'}; overridden by local traffic-law taxonomy",
                    "confidence": min(route_decision.confidence, 0.5),
                }
            )
            router_debug = {**router_debug, "out_of_scope_override": True, "override_decision": route_decision.model_dump()}
        direct_response = direct_route_response(route_decision)
        if direct_response:
            if request.debug:
                direct_response.debug = {
                    **(direct_response.debug or {}),
                    "routing": {
                        "query_router": router_debug,
                        "sanction_attempted": False,
                        "fallback_to_rag": False,
                    },
                }
            else:
                direct_response.debug = None
            return _finalize_response(direct_response)

        parsed, prerag_debug = self._maybe_transform_query_with_prerag(
            parsed,
            route_decision,
            request.pre_rag_mode,
            request.pre_rag_enabled,
        )
        parsed = apply_route_decision(parsed, route_decision)
        parsed = _preserve_initial_parse(initial_parsed, parsed)
        structured_lookup_request_enabled = request.structured_lookup_enabled
        structured_fact_base_enabled = (
            RAG_STRUCTURED_FACT_ENABLED
            if structured_lookup_request_enabled is None
            else RAG_STRUCTURED_FACT_ENABLED and structured_lookup_request_enabled
        )
        structured_fact_enabled, structured_fact_skip_reason = _structured_fact_runtime_enabled(
            structured_fact_base_enabled
        )
        structured_table_base_enabled = (
            RAG_STRUCTURED_TABLE_ENABLED
            if structured_lookup_request_enabled is None
            else RAG_STRUCTURED_TABLE_ENABLED and structured_lookup_request_enabled
        )
        structured_table_enabled, structured_table_skip_reason = _structured_table_runtime_enabled(
            structured_table_base_enabled
        )
        if structured_lookup_request_enabled is None:
            structured_sanction_base_enabled = (
                SANCTION_ENABLED
                if request.structured_sanction_enabled is None
                else SANCTION_ENABLED and request.structured_sanction_enabled
            )
        else:
            structured_sanction_base_enabled = SANCTION_ENABLED and structured_lookup_request_enabled
        structured_sanction_enabled, structured_sanction_skip_reason = _structured_sanction_runtime_enabled(
            structured_sanction_base_enabled,
            parsed,
            router_debug,
            prerag_debug,
        )
        if not structured_sanction_enabled:
            parsed = _drop_structured_sanction_plan(parsed)
        routing_debug: dict[str, object] = {
            "sanction_attempted": False,
            "structured_lookup_enabled": structured_fact_enabled or structured_table_enabled or structured_sanction_enabled,
            "structured_lookup_env_enabled": RAG_STRUCTURED_LOOKUP_ENABLED,
            "structured_lookup_request_enabled": structured_lookup_request_enabled,
            "structured_fact_base_enabled": structured_fact_base_enabled,
            "structured_fact_enabled": structured_fact_enabled,
            "structured_fact_skip_reason": structured_fact_skip_reason,
            "structured_table_base_enabled": structured_table_base_enabled,
            "structured_table_enabled": structured_table_enabled,
            "structured_table_skip_reason": structured_table_skip_reason,
            "structured_sanction_enabled": structured_sanction_enabled,
            "structured_sanction_base_enabled": structured_sanction_base_enabled,
            "structured_sanction_skip_reason": structured_sanction_skip_reason,
            "structured_sanction_env_enabled": SANCTION_ENABLED,
            "structured_sanction_request_enabled": request.structured_sanction_enabled,
            "fallback_to_rag": False,
            "query_router": router_debug,
            "pre_rag": prerag_debug,
        }

        fact_response = build_structured_fact_answer(parsed) if structured_fact_enabled else None
        if fact_response:
            if request.debug:
                debug = fact_response.debug or {}
                debug["routing"] = {**routing_debug, "structured_fact_answered": True}
                fact_response.debug = debug
            else:
                fact_response.debug = None
            return _finalize_response(fact_response)

        if structured_sanction_enabled and parsed.intent == "PENALTY_LOOKUP":
            routing_debug["sanction_attempted"] = True
            penalty = resolve_penalty_query(self.sanctions, parsed)
            routing_debug.update(penalty.debug)
            if penalty.resolutions:
                composition = compose_sanctions(penalty.resolutions)
                answerable = any(resolution.selected_rule or resolution.rules for resolution in composition.resolutions)
                routing_debug.update(
                    {
                        "sanction_status": composition.status,
                        "sanction_answerable": answerable,
                        "sanction_resolution_statuses": [resolution.status for resolution in composition.resolutions],
                    }
                )
                if answerable or not penalty.fallback_to_rag:
                    response = build_multi_sanction_response(parsed, composition)
                    if request.debug and response.debug is not None:
                        response.debug["routing"] = routing_debug
                    response = maybe_render_structured_sanction_with_llm(parsed, response)
                    if not request.debug:
                        response.debug = None
                    return _finalize_response(response)
            if penalty.lookup:
                lookup = penalty.lookup
                routing_debug.update(
                    {
                        "sanction_status": lookup.status,
                        "sanction_missing_fields": lookup.missing_fields,
                    }
                )
                explicit_ref = any([parsed.document_number, parsed.article, parsed.clause, parsed.point])
                if lookup.status in {"FOUND", "AMBIGUOUS"} or (
                    lookup.status == "NEEDS_CLARIFICATION" and not penalty.fallback_to_rag
                ) or (
                    lookup.status in {"NOT_FOUND", "TEMPORAL_AMBIGUOUS"} and explicit_ref
                ):
                    response = build_sanction_response(parsed, lookup)
                    if request.debug and response.debug is not None:
                        response.debug["routing"] = routing_debug
                    response = maybe_render_structured_sanction_with_llm(parsed, response)
                    if not request.debug:
                        response.debug = None
                    return _finalize_response(response)
            routing_debug["fallback_to_rag"] = penalty.fallback_to_rag

        table_response = build_structured_table_answer(parsed) if structured_table_enabled else None
        if table_response:
            if request.debug:
                debug = table_response.debug or {}
                debug["routing"] = {**routing_debug, "structured_table_answered": True}
                table_response.debug = debug
            else:
                table_response.debug = None
            return _finalize_response(table_response)

        results = self.retriever.search(parsed, top_k=request.top_k, embedding_preset=request.embedding_preset)
        response = build_answer(parsed, results)
        self._attach_score_details(response)
        if request.debug:
            debug = response.debug or {}
            debug["routing"] = routing_debug
            debug["retrieval"] = {
                "bm25_active": self.retriever.bm25.bm25 is not None,
                "dense_active": self.retriever._dense_for_preset(request.embedding_preset) is not None,
                "dense_error": self.retriever.dense_error,
                "embedding_preset": self.retriever.active_embedding_preset,
                "reranker_active": self.retriever.reranker is not None,
                "reranker_error": self.retriever.reranker_error,
                "final_candidates": len(results),
                "query_variants": self.retriever._planned_queries(parsed),
                "context_trace": self.retriever.last_context_trace,
            }
            response.debug = debug
        if not request.debug:
            response.debug = None
        return _finalize_response(response)

    def _maybe_transform_query_with_prerag(
        self,
        parsed: ParsedQuery,
        route_decision: QueryRouteDecision,
        mode: str | None,
        legacy_enabled: bool,
    ) -> tuple[ParsedQuery, dict[str, object]]:
        explicit_mode = mode is not None
        normalized_mode = _normalize_pre_rag_mode(mode, legacy_enabled)
        if normalized_mode == "disabled":
            return parsed, {"enabled": False, "skip_reason": "disabled_by_request"}
        if normalized_mode == "rule":
            return parsed, {
                "enabled": True,
                "mode": "rule",
                "provider": "rule",
                "skipped": True,
                "skip_reason": "rule_based_mode",
                "query_plan": parsed.query_plan.model_dump() if parsed.query_plan else None,
            }
        if normalized_mode == "llm":
            transformed, debug = transform_query_with_llm(parsed, force_llm=explicit_mode)
            return transformed, {**debug, "mode": "llm"}
        if _router_has_sufficient_rag_plan(route_decision):
            return parsed, {
                "enabled": True,
                "mode": "optimized",
                "skipped": True,
                "skip_reason": "router_plan_sufficient",
                "router_confidence": route_decision.confidence,
            }
        transformed, debug = transform_query_with_llm(parsed, force_llm=explicit_mode)
        return transformed, {**debug, "mode": "optimized"}

    def _attach_score_details(self, response: ChatResponse) -> None:
        score_trace = getattr(self.retriever, "last_score_trace", {})
        context_by_id = {
            str(item.get("chunk_id")): item
            for item in getattr(self.retriever, "last_context_trace", [])
            if item.get("chunk_id")
        }
        for citation in response.citations:
            details = dict(score_trace.get(citation.chunk_id, {}))
            if citation.chunk_id in context_by_id:
                details["context_reason"] = context_by_id[citation.chunk_id].get("reason")
                details["context_anchor_chunk_id"] = context_by_id[citation.chunk_id].get("anchor_chunk_id")
            if citation.score is not None:
                details["final_citation_score"] = citation.score
            citation.score_details = details


def _has_multiple_vehicle_groups(rules: list[object]) -> bool:
    groups: set[str] = set()
    for rule in rules:
        for code in getattr(rule, "vehicle_codes", []) or []:
            groups.add(_vehicle_group(str(code)))
    return len(groups) >= 2


def _drop_structured_sanction_plan(parsed: ParsedQuery) -> ParsedQuery:
    if not parsed.query_plan or not parsed.query_plan.use_structured_sanction:
        return parsed
    plan = parsed.query_plan.model_copy(
        update={
            "use_structured_sanction": False,
            "strategy": [item for item in parsed.query_plan.strategy if item != "STRUCTURED_LOOKUP"],
        }
    )
    return parsed.model_copy(update={"query_plan": plan})


def _structured_fact_runtime_enabled(base_enabled: bool) -> tuple[bool, str | None]:
    return _deterministic_lookup_runtime_enabled(
        base_enabled,
        use_with_llm=RAG_STRUCTURED_FACT_USE_WITH_LLM,
        layer_name="structured_fact",
    )


def _structured_table_runtime_enabled(base_enabled: bool) -> tuple[bool, str | None]:
    return _deterministic_lookup_runtime_enabled(
        base_enabled,
        use_with_llm=RAG_STRUCTURED_TABLE_USE_WITH_LLM,
        layer_name="structured_table",
    )


def _deterministic_lookup_runtime_enabled(
    base_enabled: bool,
    *,
    use_with_llm: bool,
    layer_name: str,
) -> tuple[bool, str | None]:
    if not base_enabled:
        return False, "disabled"
    if use_with_llm:
        return True, None

    provider, model = resolve_llm(RAG_LLM_PROVIDER, RAG_LLM_MODEL)
    if is_chat_provider_configured(provider):
        detail = f"chat_llm_provider={provider}"
        if model:
            detail += f"; model={model}"
        return False, f"skipped_{layer_name}_deterministic_with_{detail}"
    return True, None


def _structured_sanction_runtime_enabled(
    base_enabled: bool,
    parsed: ParsedQuery,
    router_debug: dict[str, object],
    prerag_debug: dict[str, object],
) -> tuple[bool, str | None]:
    if not base_enabled:
        return False, "disabled"
    provider, model = resolve_llm(RAG_LLM_PROVIDER, RAG_LLM_MODEL)
    if not is_chat_provider_configured(provider) or not RAG_STRUCTURED_SANCTION_REQUIRE_LLM_PLAN:
        return True, None
    if parsed.intent != "PENALTY_LOOKUP":
        return False, "not_penalty_lookup"
    if _llm_semantic_plan_uses_structured_sanction(router_debug, prerag_debug):
        return True, None
    detail = f"chat_llm_provider={provider}"
    if model:
        detail += f"; model={model}"
    return False, f"skipped_structured_sanction_without_llm_plan_with_{detail}"


def _llm_semantic_plan_uses_structured_sanction(
    router_debug: dict[str, object],
    prerag_debug: dict[str, object],
) -> bool:
    raw_route = router_debug.get("raw_payload")
    if isinstance(raw_route, dict) and _payload_requests_structured_sanction(raw_route):
        return True

    prerag_payload = prerag_debug.get("payload")
    if isinstance(prerag_payload, dict) and _payload_requests_structured_sanction(prerag_payload):
        return True
    return False


def _payload_requests_structured_sanction(payload: dict[str, object]) -> bool:
    if payload.get("intent") != "PENALTY_LOOKUP":
        return False
    if payload.get("use_structured_sanction") is True:
        return True
    query_plan = payload.get("query_plan")
    return isinstance(query_plan, dict) and query_plan.get("use_structured_sanction") is True


def _router_has_sufficient_rag_plan(decision: QueryRouteDecision) -> bool:
    if decision.route != "RAG":
        return True
    if decision.confidence < 0.75:
        return False
    if not decision.question_rewrite:
        return False
    if decision.intent not in {
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
    }:
        return False
    return decision.retrieval_strategy in {
        "FACTOID",
        "EXPAND_PARENT",
        "EXPAND_PARENT_SIBLINGS",
        "EXHAUSTIVE_ARTICLE",
    }


def _normalize_pre_rag_mode(mode: str | None, legacy_enabled: bool) -> str:
    if mode is None:
        return "optimized" if legacy_enabled else "disabled"
    normalized = mode.strip().lower().replace("-", "_")
    aliases = {
        "off": "disabled",
        "false": "disabled",
        "disabled": "disabled",
        "rule_based": "rule",
        "rule": "rule",
        "llm": "llm",
        "openai": "llm",
        "optimal": "optimized",
        "optimised": "optimized",
        "optimized": "optimized",
        "toi_uu": "optimized",
    }
    return aliases.get(normalized, "optimized")


def _looks_like_traffic_law_query(parsed: ParsedQuery) -> bool:
    if parsed.document_number in {
        "35/2024/QH15",
        "36/2024/QH15",
        "165/2024/NĐ-CP",
        "168/2024/NĐ-CP",
        "238/2026/NĐ-CP",
        "38/2024/TT-BGTVT",
    }:
        return True
    if parsed.intent != "GENERAL_LEGAL_QA":
        return True
    if parsed.vehicle_code or parsed.behavior_code or parsed.violations:
        return True
    query = strip_accents(normalize_text(parsed.query))
    traffic_terms = {
        "giao thong",
        "duong bo",
        "xe may",
        "mo to",
        "o to",
        "xe tai",
        "xe khach",
        "xe dap",
        "gplx",
        "giay phep lai xe",
        "bien so",
        "dang ky xe",
        "toc do",
        "cao toc",
        "den do",
        "nong do con",
        "mu bao hiem",
        "dau gia",
        "co so du lieu",
        "quoc lo",
        "phan cap",
        "ubnd cap tinh",
        "xe uu tien",
        "thiet bi an toan",
        "thoi hieu xu phat",
        "tham quyen",
        "csgt",
        "canh sat giao thong",
        "duong cuu nan",
        "coc km",
    }
    return any(term in query for term in traffic_terms)


def _requires_external_law(parsed: ParsedQuery) -> bool:
    query = strip_accents(normalize_text(parsed.query))
    return any(
        term in query
        for term in [
            "phat tu",
            "phat tu bao nhieu",
            "tu bao nhieu nam",
            "bao nhieu nam tu",
            "trach nhiem hinh su",
            "sao chep phan mem",
            "ban quyen phan mem",
            "phan mem trai phep",
            "tau thuy",
            "duong thuy",
            "thuyen",
            "cano",
            "ca no",
            "hang hai",
            "tau hoa",
            "may bay",
            "hang khong",
        ]
    )


def _external_law_answer(parsed: ParsedQuery) -> str:
    query = strip_accents(normalize_text(parsed.query))
    if any(term in query for term in ["tau thuy", "duong thuy", "thuyen", "cano", "ca no", "hang hai", "tau hoa", "may bay", "hang khong"]):
        return (
            "Bộ tài liệu hiện có chỉ hỗ trợ pháp luật giao thông đường bộ Việt Nam. "
            "Câu hỏi này thuộc lĩnh vực ngoài đường bộ nên tôi không đủ căn cứ từ corpus hiện tại để trả lời."
        )
    if any(term in query for term in ["sao chep phan mem", "ban quyen phan mem", "phan mem trai phep"]):
        return (
            "Không có căn cứ về bản quyền phần mềm trong các văn bản giao thông đường bộ đang được cung cấp, "
            "nên không thể xác định mức phạt từ bộ tài liệu này."
        )
    return (
        "Bộ tài liệu hiện có tập trung vào quy tắc và xử phạt hành chính về giao thông đường bộ. "
        "Câu hỏi về phạt tù hoặc trách nhiệm hình sự cần căn cứ pháp luật hình sự ngoài bộ nguồn này."
    )


def _preserve_initial_parse(initial: ParsedQuery, parsed: ParsedQuery) -> ParsedQuery:
    updates: dict[str, object] = {}
    for field in ["vehicle_type", "vehicle_code", "behavior_code", "behavior_text_query"]:
        if getattr(parsed, field) is None and getattr(initial, field) is not None:
            updates[field] = getattr(initial, field)
    if not parsed.violations and initial.violations:
        updates["violations"] = initial.violations
    if not updates:
        return parsed
    return parsed.model_copy(update=updates)


def _finalize_response(response: ChatResponse) -> ChatResponse:
    if response.answerable and response.citations:
        response.answer = ensure_claim_citations(normalize_inline_legal_refs(response.answer, response.citations), response.citations)
    return response


def _vehicle_group(code: str) -> str:
    if code in {"CAR", "FOUR_WHEEL_PASSENGER", "FOUR_WHEEL_CARGO", "CAR_SIMILAR"}:
        return "CAR"
    if code in {"MOTORCYCLE", "MOPED", "MOTORCYCLE_SIMILAR", "MOPED_SIMILAR"}:
        return "MOTORCYCLE"
    return code
