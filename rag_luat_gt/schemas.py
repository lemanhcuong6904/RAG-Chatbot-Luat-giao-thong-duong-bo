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
    rule_function: str = "UNKNOWN"
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
    pre_rag_enabled: bool = True
    pre_rag_mode: str | None = None
    embedding_preset: str | None = None
    structured_lookup_enabled: bool | None = None
    structured_sanction_enabled: bool | None = None
    llm_provider: str | None = None
    llm_model: str | None = None


class Citation(BaseModel):
    chunk_id: str
    chunk_type: str = "SPAN"
    rule_id: str | None = None
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
    rule_function: str = "UNKNOWN"
    coverage_status: str = "UNKNOWN"
    source_quality: str = "UNKNOWN"
    score: float | None = None
    score_details: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    warnings: list[str] = Field(default_factory=list)
    answerable: bool = True
    debug: dict[str, Any] | None = None


class ViolationFact(BaseModel):
    behavior_code: str
    behavior_text: str
    raw_span: str | None = None
    behavior_contains: str | None = None
    catalog_code: str | None = None
    conditions: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0


class QueryPlan(BaseModel):
    strategy: list[str] = Field(default_factory=list)
    use_structured_sanction: bool = False
    expanded_query: str | None = None
    subqueries: list[str] = Field(default_factory=list)
    multi_queries: list[str] = Field(default_factory=list)
    step_back_query: str | None = None
    hyde_text: str | None = None


class ParsedQuery(BaseModel):
    query: str
    normalized_query: str
    original_query: str | None = None
    retrieval_query: str | None = None
    evidence_validation_query: str | None = None
    intent: str = "GENERAL_LEGAL_QA"
    primary_intent: str | None = None
    answer_mode: str = "FACTOID"
    document_number: str | None = None
    article: str | None = None
    clause: str | None = None
    point: str | None = None
    actor: str | None = None
    liable_entity_type: str | None = None
    vehicle_type: str | None = None
    vehicle_code: str | None = None
    behavior_code: str | None = None
    behavior_text_query: str | None = None
    violations: list[ViolationFact] = Field(default_factory=list)
    desired_rule_function: str | None = None
    conditions: list[str] = Field(default_factory=list)
    requested_facets: list[str] = Field(default_factory=list)
    event_date: str | None = None
    as_of_date: str | None = None
    legal_effective_date: str | None = None
    query_reference_date: str | None = None
    temporal_intent: str = "CURRENT_RULE"
    retrieval_mode: str = "FACTOID"
    answer_scope: str | None = None
    keywords: list[str] = Field(default_factory=list)
    query_plan: QueryPlan | None = None
