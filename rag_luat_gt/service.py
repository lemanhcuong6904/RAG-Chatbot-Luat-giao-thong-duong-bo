from __future__ import annotations

from rag_luat_gt.generation.answerer import build_answer
from rag_luat_gt.retrieval.hybrid import HybridRetriever
from rag_luat_gt.retrieval.query_parser import parse_query
from rag_luat_gt.schemas import ChatRequest, ChatResponse


class RAGService:
    def __init__(self) -> None:
        self.retriever = HybridRetriever()
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
        results = self.retriever.search(parsed, top_k=request.top_k)
        response = build_answer(parsed, results)
        if not request.debug:
            response.debug = None
        return response
