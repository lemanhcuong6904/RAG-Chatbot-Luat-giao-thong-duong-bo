from __future__ import annotations

from pathlib import Path

from rag_luat_gt.ingestion.build_index import build_index
from rag_luat_gt.schemas import ChatRequest
from rag_luat_gt.service import RAGService


def test_build_index_and_answer() -> None:
    root = Path(".").resolve()
    manifest = build_index(root / "data" / "markdown", root)
    assert manifest["documents"] > 0
    assert manifest["chunks"] > 0

    service = RAGService()
    response = service.answer(
        ChatRequest(query="Xe máy vượt đèn đỏ bị phạt bao nhiêu?", top_k=3, debug=True)
    )
    assert response.citations
    assert response.answerable

