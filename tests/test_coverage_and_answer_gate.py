from __future__ import annotations

from rag_luat_gt.generation.answerer import build_answer
from rag_luat_gt.ingestion.normalizer import normalize_document
from rag_luat_gt.schemas import Chunk, ParsedQuery


def test_normalize_document_marks_missing_appendix() -> None:
    document = normalize_document(
        {
            "so_ky_hieu": "105/2026/TT-BCA",
            "title": "Thong tu test",
            "phu_luc_co_trong_file": False,
            "ghi_chu_nguon": "Nguon khong chua phu luc bieu mau moi.",
        },
        "data/markdown/test.md",
    )

    assert document.coverage_status == "MISSING_APPENDIX"
    assert document.source_quality == "PARTIAL_SOURCE"


def test_answer_gate_abstains_on_missing_appendix_request() -> None:
    parsed = ParsedQuery(
        query="Phụ lục biểu mẫu gồm những nội dung gì?",
        normalized_query="phu luc bieu mau gom nhung noi dung gi",
        intent="GENERAL_LEGAL_QA",
        legal_effective_date="2026-08-10",
    )
    chunk = Chunk(
        chunk_id="chunk-1",
        document_id="doc-1",
        document_number="105/2026/TT-BCA",
        document_title="Thong tu test",
        text="Điều 1. Quy định chung.",
        retrieval_text="Thong tu test Dieu 1 Quy dinh chung",
        source_file="data/markdown/test.md",
        coverage_status="MISSING_APPENDIX",
        source_quality="PARTIAL_SOURCE",
    )

    response = build_answer(parsed, [(chunk, 1.0)])

    assert not response.answerable
    assert response.warnings
