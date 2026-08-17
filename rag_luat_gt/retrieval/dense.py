from __future__ import annotations

from datetime import date

from qdrant_client.http import models

from rag_luat_gt.config import embedding_settings_for_preset
from rag_luat_gt.retrieval.qdrant_store import qdrant_client
from rag_luat_gt.schemas import Chunk, ParsedQuery


def _date_or_none(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _effective_at(chunk: Chunk, event_date: str | None) -> bool:
    if not event_date:
        return True
    target = _date_or_none(event_date)
    if not target:
        return True
    valid_from = _date_or_none(chunk.valid_from)
    valid_to = _date_or_none(chunk.valid_to)
    if valid_from and target < valid_from:
        return False
    if valid_to and target >= valid_to:
        return False
    return True


def _should_filter_effective(parsed: ParsedQuery) -> bool:
    if _transition_source_query(parsed):
        return False
    return parsed.temporal_intent in {"APPLICABLE_RULE", "HISTORICAL_RULE", "FUTURE_RULE", "CURRENT_RULE"}


def _transition_source_query(parsed: ParsedQuery) -> bool:
    query = (parsed.query or "").casefold()
    return any(
        term in query
        for term in [
            "chuyển tiếp",
            "chuyen tiep",
            "xảy ra và kết thúc",
            "xay ra va ket thuc",
            "mới bị phát hiện",
            "moi bi phat hien",
            "đang xem xét giải quyết",
            "dang xem xet giai quyet",
            "thời điểm thực hiện hành vi",
            "thoi diem thuc hien hanh vi",
        ]
    )


def _matches_metadata(chunk: Chunk, parsed: ParsedQuery) -> bool:
    if parsed.document_number and chunk.document_number != parsed.document_number:
        return False
    if parsed.article and chunk.article != parsed.article:
        return False
    if parsed.clause and chunk.clause != parsed.clause:
        return False
    if parsed.point and chunk.point != parsed.point:
        return False
    return True


def _datetime(value: str) -> str:
    return f"{value}T00:00:00Z"


def _query_filter(parsed: ParsedQuery) -> models.Filter | None:
    must: list[models.Condition] = []
    must_not: list[models.Condition] = []
    for field, value in [
        ("document_number", parsed.document_number),
        ("article", parsed.article),
        ("clause", parsed.clause),
        ("point", parsed.point),
    ]:
        if value:
            must.append(models.FieldCondition(key=field, match=models.MatchValue(value=value)))

    if _should_filter_effective(parsed) and parsed.legal_effective_date:
        target = _datetime(parsed.legal_effective_date)
        must_not.append(
            models.FieldCondition(
                key="valid_from",
                range=models.DatetimeRange(gt=target),
            )
        )
        must_not.append(
            models.FieldCondition(
                key="valid_to",
                range=models.DatetimeRange(lte=target),
            )
        )

    return models.Filter(must=must or None, must_not=must_not or None) if must or must_not else None


class DenseRetriever:
    def __init__(self, preset: str | None = None, *, allow_model_override: bool = False) -> None:
        self.settings = embedding_settings_for_preset(preset, allow_model_override=allow_model_override)
        self.preset = self.settings.preset
        self.collection_name = self.settings.collection
        self.client = qdrant_client()
        self.embedder = None

    def available(self) -> bool:
        collections = {item.name for item in self.client.get_collections().collections}
        return self.collection_name in collections

    def search(self, parsed: ParsedQuery, top_k: int = 8) -> list[tuple[Chunk, float]]:
        if not self.available():
            return []

        if self.embedder is None:
            from rag_luat_gt.embedding.bge_m3 import BGEM3Embedder

            self.embedder = BGEM3Embedder(
                model_name=self.settings.model,
                query_instruction=self.settings.query_instruction,
                document_instruction=self.settings.document_instruction,
            )

        vector = self.embedder.encode_query(parsed.normalized_query)
        try:
            hits = self.client.query_points(
                collection_name=self.collection_name,
                query=vector,
                query_filter=_query_filter(parsed),
                limit=top_k * 3,
                with_payload=True,
            ).points
        except Exception:
            hits = self.client.query_points(
                collection_name=self.collection_name,
                query=vector,
                limit=top_k * 6,
                with_payload=True,
            ).points

        results: list[tuple[Chunk, float]] = []
        for hit in hits:
            if not hit.payload:
                continue
            chunk = Chunk(**hit.payload)
            if not _matches_metadata(chunk, parsed):
                continue
            if _should_filter_effective(parsed) and not _effective_at(chunk, parsed.legal_effective_date):
                continue
            results.append((chunk, float(hit.score)))
            if len(results) >= top_k:
                break
        return results
