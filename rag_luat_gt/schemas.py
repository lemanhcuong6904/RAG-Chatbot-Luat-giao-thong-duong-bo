from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class Document(BaseModel):
    document_id: str
    document_number: str | None = None
    title: str | None = None
    document_type: str | None = None
    issuing_authority: str | None = None
    issue_date: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    source_markdown: str
    source_original: str | list[str] | None = None
    coverage_status: str = "UNKNOWN"
    source_quality: str = "UNKNOWN"
    ocr_quality: str | None = None
    keywords: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Chunk(BaseModel):
    chunk_id: str
    chunk_type: str = "SPAN"
    document_id: str
    document_number: str | None = None
    document_title: str | None = None
    article: str | None = None
    article_title: str | None = None
    clause: str | None = None
    point: str | None = None
    parent_id: str | None = None
    article_id: str | None = None
    sibling_group_id: str | None = None
    order: int = 0
    children_ids: list[str] = Field(default_factory=list)
    heading_path: list[str] = Field(default_factory=list)
    text: str
    retrieval_text: str
    valid_from: str | None = None
    valid_to: str | None = None
    source_file: str
    coverage_status: str = "UNKNOWN"
    source_quality: str = "UNKNOWN"
    ocr_quality: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    query: str
    event_date: date | None = None
    as_of_date: date | None = None
    top_k: int = 8
    debug: bool = False


class Citation(BaseModel):
    chunk_id: str
    chunk_type: str = "SPAN"
    document_number: str | None = None
    document_title: str | None = None
    article: str | None = None
    article_title: str | None = None
    clause: str | None = None
    point: str | None = None
    parent_id: str | None = None
    sibling_group_id: str | None = None
    source_file: str
    text: str
    coverage_status: str = "UNKNOWN"
    source_quality: str = "UNKNOWN"
    score: float | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    warnings: list[str] = Field(default_factory=list)
    answerable: bool = True
    debug: dict[str, Any] | None = None


class ParsedQuery(BaseModel):
    query: str
    normalized_query: str
    intent: str = "GENERAL_LEGAL_QA"
    document_number: str | None = None
    article: str | None = None
    clause: str | None = None
    point: str | None = None
    vehicle_type: str | None = None
    event_date: str | None = None
    as_of_date: str | None = None
    legal_effective_date: str | None = None
    query_reference_date: str | None = None
    retrieval_mode: str = "FACTOID"
    answer_scope: str | None = None
    keywords: list[str] = Field(default_factory=list)
