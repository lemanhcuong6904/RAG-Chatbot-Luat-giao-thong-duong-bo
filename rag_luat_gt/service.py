from __future__ import annotations

from rag_luat_gt.generation.answerer import build_answer
from rag_luat_gt.retrieval.hybrid import HybridRetriever
from rag_luat_gt.retrieval.query_parser import parse_query
from rag_luat_gt.schemas import ChatRequest, ChatResponse


class RAGService:
    def __init__(self) -> None:
        self.retriever = HybridRetriever()

    def answer(self, request: ChatRequest) -> ChatResponse:
        parsed = parse_query(request)
        results = self.retriever.search(parsed, top_k=request.top_k)
        response = build_answer(parsed, results)
        if not request.debug:
            response.debug = None
        return response
