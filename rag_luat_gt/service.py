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
            explicit_ref = any([parsed.document_number, parsed.article, parsed.clause, parsed.point])
            if lookup.status in {"FOUND", "AMBIGUOUS", "UNAVAILABLE", "TEMPORAL_AMBIGUOUS"} or (
                lookup.status == "NOT_FOUND" and explicit_ref
            ):
                response = build_sanction_response(parsed, lookup)
                if not request.debug:
                    response.debug = None
                return response

        results = self.retriever.search(parsed, top_k=request.top_k)
        response = build_answer(parsed, results)
        if not request.debug:
            response.debug = None
        return response
