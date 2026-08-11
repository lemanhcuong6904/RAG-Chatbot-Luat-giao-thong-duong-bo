from __future__ import annotations

import json
import pickle
from datetime import date
from pathlib import Path

from rag_luat_gt.config import BM25_PATH, CHUNKS_PATH, DOCUMENTS_PATH
from rag_luat_gt.schemas import Chunk, Document, ParsedQuery
from rag_luat_gt.text import tokenize


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


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
    return parsed.temporal_intent in {"APPLICABLE_RULE", "HISTORICAL_RULE", "FUTURE_RULE", "CURRENT_RULE"}


class BM25Retriever:
    def __init__(
        self,
        bm25_path: Path = BM25_PATH,
        chunks_path: Path = CHUNKS_PATH,
        documents_path: Path = DOCUMENTS_PATH,
    ) -> None:
        if bm25_path.exists():
            with bm25_path.open("rb") as file:
                payload = pickle.load(file)
            self.bm25 = payload["bm25"]
            self.chunks = [Chunk(**row) for row in payload["chunks"]]
        else:
            rows = _load_jsonl(chunks_path)
            self.chunks = [Chunk(**row) for row in rows]
            self.bm25 = None
        self.documents = [Document(**row) for row in _load_jsonl(documents_path)]

    def search(self, parsed: ParsedQuery, top_k: int = 8) -> list[tuple[Chunk, float]]:
        if not self.bm25 or not self.chunks:
            return self._exact_lookup(parsed)[:top_k]

        candidate_ids = {chunk.chunk_id for chunk, _score in self._exact_lookup(parsed)}
        has_filter = bool(candidate_ids)
        if self._has_explicit_reference(parsed) and not has_filter:
            return []
        tokens = tokenize(parsed.normalized_query)
        scores = self.bm25.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)

        results: list[tuple[Chunk, float]] = []
        for index, score in ranked:
            chunk = self.chunks[index]
            if has_filter and chunk.chunk_id not in candidate_ids:
                continue
            if score <= 0 and not has_filter:
                continue
            if _should_filter_effective(parsed) and not _effective_at(chunk, parsed.legal_effective_date):
                continue
            results.append((chunk, float(score) + self._reference_boost(parsed, chunk)))
            if len(results) >= top_k:
                break
        return results

    def _exact_lookup(self, parsed: ParsedQuery) -> list[tuple[Chunk, float]]:
        if not any([parsed.document_number, parsed.article, parsed.clause, parsed.point]):
            return []

        results: list[tuple[Chunk, float]] = []
        for chunk in self.chunks:
            if _should_filter_effective(parsed) and not _effective_at(chunk, parsed.legal_effective_date):
                continue
            if parsed.document_number and chunk.document_number != parsed.document_number:
                continue
            if parsed.article and chunk.article != parsed.article:
                continue
            if parsed.clause and chunk.clause != parsed.clause:
                continue
            if parsed.point and chunk.point != parsed.point:
                continue
            results.append((chunk, self._reference_boost(parsed, chunk)))
        return results

    @staticmethod
    def _reference_boost(parsed: ParsedQuery, chunk: Chunk) -> float:
        boost = 0.0
        if parsed.document_number and chunk.document_number == parsed.document_number:
            boost += 0.4
        if parsed.article and chunk.article == parsed.article:
            boost += 0.3
        if parsed.clause and chunk.clause == parsed.clause:
            boost += 0.2
        if parsed.point and chunk.point == parsed.point:
            boost += 0.1
        return boost

    @staticmethod
    def _has_explicit_reference(parsed: ParsedQuery) -> bool:
        return any([parsed.document_number, parsed.article, parsed.clause, parsed.point])
