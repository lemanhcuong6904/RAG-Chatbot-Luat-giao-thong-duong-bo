from __future__ import annotations

from rag_luat_gt.config import SANCTION_ENABLED
from rag_luat_gt.generation.answerer import build_answer
from rag_luat_gt.generation.sanction_answerer import build_sanction_response
from rag_luat_gt.retrieval.hybrid import HybridRetriever
from rag_luat_gt.retrieval.query_parser import parse_query
from rag_luat_gt.sanction.behavior_catalog import behavior_contains_from_query
from rag_luat_gt.sanction.repository import SanctionRepository
from rag_luat_gt.schemas import ChatRequest, ChatResponse


class RAGService:
    def __init__(self) -> None:
        self.retriever = HybridRetriever()
        self.sanctions = SanctionRepository()
        self.warmup_error: str | None = None

    def warm_up(self) -> None:
        dense = getattr(self.retriever, "dense", None)
        if not dense:
            return
        try:
            if dense.embedder is None:
                from rag_luat_gt.embedding.bge_m3 import BGEM3Embedder

                dense.embedder = BGEM3Embedder()
            dense.embedder.encode_query("khởi động mô hình truy xuất")
        except Exception as exc:
            self.warmup_error = str(exc)

    def answer(self, request: ChatRequest) -> ChatResponse:
        parsed = parse_query(request)
        routing_debug: dict[str, object] = {"sanction_attempted": False, "fallback_to_rag": False}
        if SANCTION_ENABLED and parsed.intent == "PENALTY_LOOKUP":
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
                if not request.debug:
                    response.debug = None
                return response
            routing_debug["fallback_to_rag"] = True

        results = self.retriever.search(parsed, top_k=request.top_k)
        response = build_answer(parsed, results)
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
            }
            response.debug = debug
        if not request.debug:
            response.debug = None
        return response
