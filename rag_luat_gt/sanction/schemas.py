from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SanctionRule(BaseModel):
    rule_id: str
    document_number: str | None = None
    article: str | None = None
    article_title: str | None = None
    clause: str | None = None
    point: str | None = None
    actor_code: str | None = None
    vehicle_codes: list[str] = Field(default_factory=list)
    behavior_code: str | None = None
    behavior_text: str | None = None
    conditions: list[str] = Field(default_factory=list)
    primary_sanction_type: str | None = None
    fine_min: int | None = None
    fine_max: int | None = None
    fine_basis: str | None = None
    fine_cap: int | None = None
    currency: str = "VND"
    license_points_deducted: int | None = None
    license_suspension_min_months: int | None = None
    license_suspension_max_months: int | None = None
    additional_sanctions: list[str] = Field(default_factory=list)
    remedial_measures: list[str] = Field(default_factory=list)
    valid_from: str | None = None
    valid_to: str | None = None
    deferred_effective_from: str | None = None
    deferred_scope_text: str | None = None
    source_file: str | None = None
    source_chunk_id: str | None = None
    amendment_source_chunk_id: str | None = None
    source_location: str | None = None
    source_text: str | None = None
    parent_clause_text: str | None = None
    validation_status: str | None = None
    confidence: float | None = None
    amended_by: str | None = None
    base_rule_id: str | None = None
    notes: list[Any] = Field(default_factory=list)
    temporal_warning: str | None = None


class SanctionLookup(BaseModel):
    status: str
    rules: list[SanctionRule] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)

