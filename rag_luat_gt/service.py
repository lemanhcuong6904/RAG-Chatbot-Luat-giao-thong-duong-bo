from __future__ import annotations

from rag_luat_gt.config import SANCTION_ENABLED
from rag_luat_gt.generation.answerer import build_answer
from rag_luat_gt.generation.multi_sanction_answerer import build_multi_sanction_response
from rag_luat_gt.generation.sanction_answerer import build_sanction_response
from rag_luat_gt.generation.structured_sanction_llm import maybe_render_structured_sanction_with_llm
from rag_luat_gt.retrieval.hybrid import HybridRetriever
from rag_luat_gt.retrieval.llm_query_transformer import transform_query_with_llm
from rag_luat_gt.retrieval.query_parser import parse_query
from rag_luat_gt.sanction.behavior_catalog import behavior_contains_from_query
from rag_luat_gt.sanction.composition_engine import compose_sanctions
from rag_luat_gt.sanction.condition_resolver import resolve_violations
from rag_luat_gt.sanction.repository import SanctionRepository
from rag_luat_gt.schemas import ChatRequest, ChatResponse


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

                dense.embedder = BGEM3Embedder()
            dense.embedder.encode_query("khởi động mô hình truy xuất")
            self.warmup_status = "READY"
            print("[RAG] Dense retrieval model warm-up complete.", flush=True)
        except Exception as exc:
            self.warmup_error = str(exc)
            self.warmup_status = "ERROR"
            print(f"[RAG] Dense retrieval model warm-up failed: {exc}", flush=True)

    def answer(self, request: ChatRequest) -> ChatResponse:
        parsed = parse_query(request)
        parsed, prerag_debug = transform_query_with_llm(parsed)
        routing_debug: dict[str, object] = {
            "sanction_attempted": False,
            "fallback_to_rag": False,
            "pre_rag": prerag_debug,
        }
        if SANCTION_ENABLED and parsed.intent == "PENALTY_LOOKUP":
            if len(parsed.violations) >= 2:
                routing_debug["sanction_attempted"] = True
                resolutions = resolve_violations(self.sanctions, parsed)
                composition = compose_sanctions(resolutions)
                answerable = any(resolution.selected_rule or resolution.rules for resolution in composition.resolutions)
                routing_debug.update(
                    {
                        "sanction_status": composition.status,
                        "sanction_answerable": answerable,
                        "sanction_resolution_statuses": [resolution.status for resolution in composition.resolutions],
                    }
                )
                if not answerable:
                    routing_debug["fallback_to_rag"] = True
                else:
                    response = build_multi_sanction_response(parsed, composition)
                    if request.debug and response.debug is not None:
                        response.debug["routing"] = routing_debug
                    response = maybe_render_structured_sanction_with_llm(parsed, response)
                    if not request.debug:
                        response.debug = None
                    return response
            else:
                lookup = self.sanctions.lookup(
                    event_date=parsed.legal_effective_date or parsed.event_date or parsed.query_reference_date or "",
                    vehicle_code=parsed.vehicle_code,
                    behavior_code=parsed.behavior_code,
                    behavior_contains=parsed.behavior_text_query or behavior_contains_from_query(parsed.query),
                    document_number=parsed.document_number,
                    article=parsed.article,
                    clause=parsed.clause,
                    point=parsed.point,
                )
                routing_debug.update(
                    {
                        "sanction_attempted": True,
                        "sanction_status": lookup.status,
                        "sanction_missing_fields": lookup.missing_fields,
                    }
                )
                explicit_ref = any([parsed.document_number, parsed.article, parsed.clause, parsed.point])
                if lookup.status == "FOUND" or lookup.status in {"NOT_FOUND", "TEMPORAL_AMBIGUOUS"} and explicit_ref:
                    response = build_sanction_response(parsed, lookup)
                    if request.debug and response.debug is not None:
                        response.debug["routing"] = routing_debug
                    response = maybe_render_structured_sanction_with_llm(parsed, response)
                    if not request.debug:
                        response.debug = None
                    return response
                if lookup.status == "NEEDS_CLARIFICATION" and parsed.behavior_code:
                    scoped_lookup = self.sanctions.lookup_behavior_codes(
                        event_date=parsed.legal_effective_date or parsed.event_date or parsed.query_reference_date or "",
                        behavior_codes=[parsed.behavior_code],
                    )
                    routing_debug.update(
                        {
                            "sanction_status": scoped_lookup.status,
                            "sanction_vehicle_scope_split": True,
                        }
                    )
                    if scoped_lookup.status == "FOUND" and _has_multiple_vehicle_groups(scoped_lookup.rules):
                        response = build_sanction_response(parsed, scoped_lookup)
                        if request.debug and response.debug is not None:
                            response.debug["routing"] = routing_debug
                        response = maybe_render_structured_sanction_with_llm(parsed, response)
                        if not request.debug:
                            response.debug = None
                        return response
                routing_debug["fallback_to_rag"] = True

        results = self.retriever.search(parsed, top_k=request.top_k)
        response = build_answer(parsed, results)
        self._attach_score_details(response)
        if request.debug:
            debug = response.debug or {}
            debug["routing"] = routing_debug
            debug["retrieval"] = {
                "bm25_active": self.retriever.bm25.bm25 is not None,
                "dense_active": self.retriever.dense is not None,
                "dense_error": self.retriever.dense_error,
                "reranker_active": self.retriever.reranker is not None,
                "reranker_error": self.retriever.reranker_error,
                "final_candidates": len(results),
                "query_variants": self.retriever._planned_queries(parsed),
                "context_trace": self.retriever.last_context_trace,
            }
            response.debug = debug
        if not request.debug:
            response.debug = None
        return response

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


def _vehicle_group(code: str) -> str:
    if code in {"CAR", "FOUR_WHEEL_PASSENGER", "FOUR_WHEEL_CARGO", "CAR_SIMILAR"}:
        return "CAR"
    if code in {"MOTORCYCLE", "MOPED", "MOTORCYCLE_SIMILAR", "MOPED_SIMILAR"}:
        return "MOTORCYCLE"
    return code
