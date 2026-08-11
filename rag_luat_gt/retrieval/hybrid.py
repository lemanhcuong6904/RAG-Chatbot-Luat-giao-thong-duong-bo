from __future__ import annotations

import json

from rag_luat_gt.config import (
    MANIFEST_PATH,
    QDRANT_COLLECTION,
    QDRANT_READY_FILE,
    RAG_DENSE_ENABLED,
    RAG_EMBEDDING_MODEL,
    RAG_RERANKER_ENABLED,
    RAG_RERANKER_TOP_N,
)
from rag_luat_gt.retrieval.bm25 import BM25Retriever
from rag_luat_gt.rule_function import effective_rule_function
from rag_luat_gt.schemas import Chunk, ParsedQuery
from rag_luat_gt.text import normalize_text, strip_accents


RRF_K = 60


class HybridRetriever:
    def __init__(self) -> None:
        self.bm25 = BM25Retriever()
        self.dense = None
        self.dense_error: str | None = None
        self.reranker = None
        self.reranker_error: str | None = None
        self.last_context_trace: list[dict[str, object]] = []
        if RAG_DENSE_ENABLED and self._dense_ready_matches_manifest():
            try:
                from rag_luat_gt.retrieval.dense import DenseRetriever

                self.dense = DenseRetriever()
            except Exception as exc:
                self.dense_error = str(exc)
        elif RAG_DENSE_ENABLED and QDRANT_READY_FILE.exists():
            self.dense_error = "Dense index marker does not match the current BM25 manifest."
        if RAG_RERANKER_ENABLED:
            try:
                from rag_luat_gt.retrieval.reranker import BGEReranker

                self.reranker = BGEReranker()
            except Exception as exc:
                self.reranker_error = str(exc)

    def search(self, parsed: ParsedQuery, top_k: int = 8) -> list[tuple[Chunk, float]]:
        self.last_context_trace = []
        query_variants = self._planned_queries(parsed)
        if len(query_variants) > 1:
            result_sets: list[list[tuple[Chunk, float]]] = []
            for query in query_variants:
                variant = parsed.model_copy(update={"normalized_query": query, "retrieval_query": query})
                result_sets.append(self._search_single_query(variant, top_k=top_k))
            ranked = self._rrf(result_sets)
            ranked = self._apply_preferences(parsed, ranked)
            ranked = self._apply_reranker(parsed, ranked)
            return self._expand_structural_context(parsed, ranked, top_k)

        ranked = self._search_single_query(parsed, top_k=top_k)
        ranked = self._apply_preferences(parsed, ranked)
        ranked = self._apply_reranker(parsed, ranked)
        return self._expand_structural_context(parsed, ranked, top_k)

    def _search_single_query(self, parsed: ParsedQuery, top_k: int) -> list[tuple[Chunk, float]]:
        bm25_results = self.bm25.search(parsed, top_k=top_k * 4)
        dense_results = []
        if self.dense:
            try:
                valid_chunk_ids = {chunk.chunk_id for chunk in self.bm25.chunks}
                dense_results = [
                    (chunk, score)
                    for chunk, score in self.dense.search(parsed, top_k=top_k * 4)
                    if chunk.chunk_id in valid_chunk_ids
                ]
            except Exception as exc:
                self.dense_error = str(exc)

        if not dense_results:
            return bm25_results

        return self._rrf([dense_results, bm25_results])

    @staticmethod
    def _planned_queries(parsed: ParsedQuery) -> list[str]:
        if any([parsed.document_number, parsed.article, parsed.clause, parsed.point]):
            return [parsed.normalized_query]

        queries = [parsed.normalized_query]
        plan = parsed.query_plan
        if plan:
            queries.extend(plan.multi_queries)
            if plan.step_back_query:
                queries.append(plan.step_back_query)
            if plan.hyde_text:
                queries.append(plan.hyde_text)

        seen: set[str] = set()
        result: list[str] = []
        for query in queries:
            key = strip_accents(normalize_text(query))
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(query)
        return result[:6]

    def _apply_reranker(
        self,
        parsed: ParsedQuery,
        results: list[tuple[Chunk, float]],
    ) -> list[tuple[Chunk, float]]:
        if not self.reranker or not results:
            return results
        try:
            return self.reranker.rerank(parsed, results, top_n=RAG_RERANKER_TOP_N)
        except Exception as exc:
            self.reranker_error = str(exc)
            return results

    @staticmethod
    def _dense_ready_matches_manifest() -> bool:
        if not QDRANT_READY_FILE.exists() or not MANIFEST_PATH.exists():
            return False
        try:
            ready = json.loads(QDRANT_READY_FILE.read_text(encoding="utf-8"))
            manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False

        dense = manifest.get("dense") or {}
        return all(
            [
                ready.get("collection") == QDRANT_COLLECTION,
                ready.get("embedding_model") == RAG_EMBEDDING_MODEL,
                ready.get("corpus_hash") == manifest.get("corpus_hash"),
                ready.get("chunking_version") == manifest.get("chunking_version"),
                ready.get("chunks") == manifest.get("chunks"),
                dense.get("corpus_hash") == manifest.get("corpus_hash"),
            ]
        )

    @staticmethod
    def _rrf(result_sets: list[list[tuple[Chunk, float]]]) -> list[tuple[Chunk, float]]:
        chunks: dict[str, Chunk] = {}
        scores: dict[str, float] = {}
        for result_set in result_sets:
            for rank, (chunk, _score) in enumerate(result_set, start=1):
                chunks[chunk.chunk_id] = chunk
                scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (RRF_K + rank)
        return [
            (chunks[chunk_id], score)
            for chunk_id, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)
        ]

    def _apply_preferences(
        self,
        parsed: ParsedQuery,
        results: list[tuple[Chunk, float]],
    ) -> list[tuple[Chunk, float]]:
        if not results:
            return []

        reranked = self._apply_rule_function_preferences(parsed, results)
        reranked = self._apply_license_point_preferences(parsed, reranked)
        reranked = self._apply_vehicle_preferences(parsed, reranked)
        reranked = self._apply_penalty_focus(parsed, reranked)
        reranked = self._apply_behavior_text_focus(parsed, reranked)
        reranked = self._filter_vehicle_penalty_scope(parsed, reranked)
        reranked = self._filter_primary_penalty_scope(parsed, reranked)
        reranked = self._apply_amount_focus(parsed, reranked)
        return sorted(reranked, key=lambda item: item[1], reverse=True)

    @staticmethod
    def _apply_rule_function_preferences(
        parsed: ParsedQuery,
        results: list[tuple[Chunk, float]],
    ) -> list[tuple[Chunk, float]]:
        if not parsed.desired_rule_function:
            return results

        reranked: list[tuple[Chunk, float]] = []
        for chunk, score in results:
            rule_function = effective_rule_function(chunk.rule_function, chunk.text, chunk.article_title)
            adjusted = score
            base = max(abs(score), 1.0)

            if rule_function == parsed.desired_rule_function:
                adjusted += base * 2.5
            elif parsed.desired_rule_function == "ELIGIBILITY" and rule_function == "SANCTION":
                adjusted -= base * 2.0

            if parsed.intent == "DRIVER_AGE_REQUIREMENT":
                text = strip_accents(normalize_text(f"{chunk.article_title or ''}\n{chunk.text[:900]}"))
                if chunk.document_number == "36/2024/QH15":
                    adjusted += base * 1.5
                if chunk.article == "59" and any(term in text for term in ["tuoi", "suc khoe", "duoc cap giay phep"]):
                    adjusted += base * 3.0
                if any(term in text for term in ["phat tien", "xu phat", "vi pham"]):
                    adjusted -= base * 1.5

            reranked.append((chunk, adjusted))

        return reranked

    @staticmethod
    def _apply_license_point_preferences(
        parsed: ParsedQuery,
        results: list[tuple[Chunk, float]],
    ) -> list[tuple[Chunk, float]]:
        if parsed.intent != "LICENSE_POINT_BALANCE":
            return results

        reranked: list[tuple[Chunk, float]] = []
        for chunk, score in results:
            text = strip_accents(normalize_text(f"{chunk.article_title or ''}\n{chunk.text[:900]}"))
            adjusted = score
            base = max(abs(score), 1.0)
            if chunk.document_number == "36/2024/QH15":
                adjusted += base * 1.5
            if chunk.article == "58":
                adjusted += base * 3.0
                if chunk.chunk_type == "ARTICLE":
                    adjusted -= base * 1.5
                if chunk.clause == "1":
                    adjusted += base * 4.0
            if "bao gom 12 diem" in text:
                adjusted += base * 5.0
            elif "diem cua giay phep lai xe" in text:
                adjusted += base * 3.0
            if "phuc hoi du 12 diem" in text and "bao gom 12 diem" not in text:
                adjusted -= base * 0.8
            if any(term in text for term in ["phi", "le phi", "sat hach", "dang ky xe", "bien so"]):
                adjusted -= base * 1.5
            reranked.append((chunk, adjusted))

        return reranked

    @staticmethod
    def _apply_vehicle_preferences(
        parsed: ParsedQuery,
        results: list[tuple[Chunk, float]],
    ) -> list[tuple[Chunk, float]]:
        if not parsed.vehicle_type:
            return results

        reranked: list[tuple[Chunk, float]] = []
        for chunk, score in results:
            title = normalize_text(chunk.article_title or "")
            text = normalize_text(f"{title}\n{chunk.text[:700]}")
            adjusted = score

            if parsed.vehicle_type == "xe máy":
                if "xe máy chuyên dùng" in title:
                    adjusted -= abs(score) * 0.7
                if any(term in title for term in ["mô tô", "xe gắn máy"]):
                    adjusted += abs(score) * 0.25
                if "phạt tiền từ" in text and "đèn tín hiệu giao thông" in text:
                    adjusted += abs(score) * 0.15

            elif parsed.vehicle_type == "ô tô":
                if "ô tô" in title:
                    adjusted += abs(score) * 0.25
                if any(term in title for term in ["xe máy chuyên dùng", "mô tô", "xe gắn máy"]):
                    adjusted -= abs(score) * 0.7

            elif parsed.vehicle_type == "xe máy chuyên dùng":
                if "xe máy chuyên dùng" in title:
                    adjusted += abs(score) * 0.25

            reranked.append((chunk, adjusted))

        return reranked

    @staticmethod
    def _apply_penalty_focus(
        parsed: ParsedQuery,
        results: list[tuple[Chunk, float]],
    ) -> list[tuple[Chunk, float]]:
        if parsed.intent != "PENALTY_LOOKUP":
            return results

        query = strip_accents(normalize_text(parsed.normalized_query))
        is_red_light = any(term in query for term in ["den do", "den tin hieu", "khong chap hanh hieu lenh"])
        if not is_red_light:
            return results

        reranked: list[tuple[Chunk, float]] = []
        for chunk, score in results:
            text = strip_accents(normalize_text(f"{chunk.article_title or ''}\n{chunk.text[:900]}"))
            adjusted = score
            if "den tin hieu giao thong" in text or "khong chap hanh hieu lenh cua den" in text:
                adjusted += abs(score) * 0.2
            if chunk.document_number == "168/2024/NĐ-CP" and chunk.article in {"6", "7", "8"}:
                adjusted += abs(score) * 0.1
            if chunk.article not in {"6", "7", "8"}:
                adjusted -= abs(score) * 0.35
            reranked.append((chunk, adjusted))
        return reranked

    @staticmethod
    def _apply_behavior_text_focus(
        parsed: ParsedQuery,
        results: list[tuple[Chunk, float]],
    ) -> list[tuple[Chunk, float]]:
        if parsed.intent != "PENALTY_LOOKUP":
            return results

        query = strip_accents(normalize_text(parsed.query))
        focus_terms = HybridRetriever._behavior_focus_terms(query)
        if not focus_terms:
            return results

        reranked: list[tuple[Chunk, float]] = []
        for chunk, score in results:
            text = strip_accents(normalize_text(f"{chunk.article_title or ''}\n{chunk.text[:1200]}"))
            adjusted = score
            base = max(abs(score), 1.0)
            if any(term in text for term in focus_terms):
                adjusted += base * (3.0 if chunk.chunk_type == "POINT" else 1.8)
            elif chunk.chunk_type == "CLAUSE" and any(term in query for term in ["bao nhieu", "muc phat"]):
                adjusted -= base * 0.25
            reranked.append((chunk, adjusted))
        return reranked

    @staticmethod
    def _behavior_focus_terms(query_ascii: str) -> list[str]:
        groups = [
            (["dien thoai", "thiet bi dien tu"], ["dien thoai", "thiet bi dien tu"]),
            (["mu bao hiem", "khong doi mu"], ["mu bao hiem"]),
            (["giay phep lai xe", "gplx", "bang lai"], ["giay phep lai xe", "gplx", "bang lai"]),
            (["den do", "den tin hieu"], ["den tin hieu", "khong chap hanh hieu lenh"]),
        ]
        terms: list[str] = []
        for triggers, expansions in groups:
            if any(trigger in query_ascii for trigger in triggers):
                terms.extend(expansions)
        return terms

    @staticmethod
    def _filter_primary_penalty_scope(
        parsed: ParsedQuery,
        results: list[tuple[Chunk, float]],
    ) -> list[tuple[Chunk, float]]:
        if parsed.intent != "PENALTY_LOOKUP" or not parsed.vehicle_type:
            return results

        query = strip_accents(normalize_text(parsed.normalized_query))
        is_red_light = any(term in query for term in ["den do", "den tin hieu", "khong chap hanh hieu lenh"])
        if not is_red_light:
            return results

        expected_article = {
            "ô tô": "6",
            "xe máy": "7",
            "xe máy chuyên dùng": "8",
        }.get(parsed.vehicle_type)
        if not expected_article:
            return results

        primary = [
            (chunk, score)
            for chunk, score in results
            if chunk.document_number == "168/2024/NĐ-CP" and chunk.article == expected_article
        ]
        if len(primary) >= 2:
            return primary
        return results

    @staticmethod
    def _filter_vehicle_penalty_scope(
        parsed: ParsedQuery,
        results: list[tuple[Chunk, float]],
    ) -> list[tuple[Chunk, float]]:
        if parsed.intent != "PENALTY_LOOKUP" or not parsed.vehicle_code:
            return results

        expected_article = {
            "CAR": "6",
            "TRUCK": "6",
            "BUS": "6",
            "MOTORCYCLE": "7",
            "MOPED": "7",
            "SPECIALIZED_MOTOR_VEHICLE": "8",
            "BICYCLE": "9",
        }.get(parsed.vehicle_code)
        if not expected_article:
            return results

        query = strip_accents(normalize_text(parsed.query))
        focus_terms = HybridRetriever._behavior_focus_terms(query)
        if not focus_terms:
            return results

        primary = [
            (chunk, score)
            for chunk, score in results
            if chunk.document_number == "168/2024/NĐ-CP" and chunk.article == expected_article
        ]
        has_behavior_point = any(
            chunk.chunk_type == "POINT"
            and any(term in strip_accents(normalize_text(chunk.text)) for term in focus_terms)
            for chunk, _score in primary
        )
        if len(primary) >= 2 and has_behavior_point:
            return primary
        return results

    @staticmethod
    def _apply_amount_focus(
        parsed: ParsedQuery,
        results: list[tuple[Chunk, float]],
    ) -> list[tuple[Chunk, float]]:
        query = strip_accents(normalize_text(parsed.query))
        asks_amount = any(
            term in query
            for term in [
                "bao nhieu",
                "muc thu",
                "muc phi",
                "le phi",
                "phi sat hach",
                "dong",
            ]
        )
        if not asks_amount:
            return results

        reranked: list[tuple[Chunk, float]] = []
        for chunk, score in results:
            text = strip_accents(normalize_text(f"{chunk.article_title or ''}\n{chunk.text[:1200]}"))
            adjusted = score
            if any(term in text for term in ["muc thu", "bieu muc thu", "ban hanh kem theo"]):
                adjusted += abs(score) * 0.35
            if any(term in text for term in ["phat tien tu", "dong"]):
                adjusted += abs(score) * 0.2
            if any(term in text for term in ["hieu luc thi hanh", "khai, thu, nop", "khai thu nop"]):
                adjusted -= abs(score) * 0.25
            reranked.append((chunk, adjusted))

        return reranked

    def _expand_parent_context(
        self,
        parsed: ParsedQuery,
        results: list[tuple[Chunk, float]],
        top_k: int,
    ) -> list[tuple[Chunk, float]]:
        by_location = {
            (chunk.document_id, chunk.article, chunk.clause, chunk.point): chunk
            for chunk in self.bm25.chunks
        }
        by_id = {chunk.chunk_id: chunk for chunk in self.bm25.chunks}
        focus_terms = self._behavior_focus_terms(strip_accents(normalize_text(parsed.query)))

        expanded: list[tuple[Chunk, float]] = []
        seen: set[str] = set()
        trace: list[dict[str, object]] = []
        for chunk, score in results[:top_k]:
            if chunk.point:
                parent = by_location.get((chunk.document_id, chunk.article, chunk.clause, None))
                if parent and parent.chunk_id not in seen:
                    expanded.append((parent, score + 0.001))
                    seen.add(parent.chunk_id)
                    trace.append(
                        self._context_trace_item(
                            parent,
                            score + 0.001,
                            reason="parent_expansion",
                            anchor_chunk_id=chunk.chunk_id,
                        )
                    )
            if chunk.chunk_id not in seen:
                expanded.append((chunk, score))
                seen.add(chunk.chunk_id)
                trace.append(self._context_trace_item(chunk, score, reason="retrieved"))
            if chunk.children_ids:
                matching_children = self._matching_children(chunk, by_id, focus_terms)
                for child in matching_children:
                    if child.chunk_id in seen:
                        continue
                    child_score = score + 0.0015
                    expanded.append((child, child_score))
                    seen.add(child.chunk_id)
                    trace.append(
                        self._context_trace_item(
                            child,
                            child_score,
                            reason="child_behavior_expansion",
                            anchor_chunk_id=chunk.chunk_id,
                        )
                    )

        self.last_context_trace = trace
        return expanded

    def _expand_structural_context(
        self,
        parsed: ParsedQuery,
        results: list[tuple[Chunk, float]],
        top_k: int,
    ) -> list[tuple[Chunk, float]]:
        if parsed.retrieval_mode == "EXHAUSTIVE":
            return self._expand_exhaustive_context(results, top_k)
        return self._expand_parent_context(parsed, results, top_k)

    def _expand_exhaustive_context(
        self,
        results: list[tuple[Chunk, float]],
        top_k: int,
    ) -> list[tuple[Chunk, float]]:
        by_id = {chunk.chunk_id: chunk for chunk in self.bm25.chunks}
        by_sibling_group: dict[str, list[Chunk]] = {}
        for chunk in self.bm25.chunks:
            if chunk.sibling_group_id:
                by_sibling_group.setdefault(chunk.sibling_group_id, []).append(chunk)

        expanded: list[tuple[Chunk, float]] = []
        seen: set[str] = set()
        trace: list[dict[str, object]] = []
        anchors = self._resolve_exhaustive_anchors(results, by_id)

        for anchor, score in anchors:
            candidates = self._expanded_children(anchor, by_id, by_sibling_group)
            if not candidates:
                candidates = [anchor]

            for candidate in candidates:
                if candidate.chunk_id in seen:
                    continue
                expanded_score = score + self._expansion_bonus(anchor, candidate)
                expanded.append((candidate, expanded_score))
                seen.add(candidate.chunk_id)
                trace.append(
                    self._context_trace_item(
                        candidate,
                        expanded_score,
                        reason=self._expansion_reason(anchor, candidate),
                        anchor_chunk_id=anchor.chunk_id,
                    )
                )

            if len(expanded) >= max(top_k, len(candidates)):
                break

        sorted_expanded = sorted(expanded, key=lambda item: (item[0].order, item[1]))
        trace_by_id = {item["chunk_id"]: item for item in trace}
        self.last_context_trace = [trace_by_id[chunk.chunk_id] for chunk, _score in sorted_expanded if chunk.chunk_id in trace_by_id]
        return sorted_expanded

    @staticmethod
    def _resolve_exhaustive_anchors(
        results: list[tuple[Chunk, float]],
        by_id: dict[str, Chunk],
        max_anchors: int = 2,
    ) -> list[tuple[Chunk, float]]:
        anchors: list[tuple[Chunk, float]] = []
        seen: set[str] = set()
        for chunk, score in results:
            anchor = HybridRetriever._exhaustive_anchor(chunk, by_id)
            if anchor.chunk_id in seen:
                continue
            anchors.append((anchor, score))
            seen.add(anchor.chunk_id)
            if len(anchors) >= max_anchors:
                break
        return anchors

    @staticmethod
    def _exhaustive_anchor(chunk: Chunk, by_id: dict[str, Chunk]) -> Chunk:
        if chunk.chunk_type in {"ARTICLE", "CLAUSE"}:
            return chunk
        if chunk.parent_id and chunk.parent_id in by_id:
            return by_id[chunk.parent_id]
        return chunk

    @staticmethod
    def _expanded_children(
        anchor: Chunk,
        by_id: dict[str, Chunk],
        by_sibling_group: dict[str, list[Chunk]],
    ) -> list[Chunk]:
        if anchor.children_ids:
            children = [by_id[chunk_id] for chunk_id in anchor.children_ids if chunk_id in by_id]
            return [anchor, *children]
        if anchor.sibling_group_id:
            siblings = sorted(
                by_sibling_group.get(anchor.sibling_group_id, []),
                key=lambda chunk: (chunk.order, chunk.chunk_id),
            )
            return [anchor, *siblings] if anchor.chunk_id not in {item.chunk_id for item in siblings} else siblings
        return []

    @staticmethod
    def _matching_children(
        chunk: Chunk,
        by_id: dict[str, Chunk],
        focus_terms: list[str],
    ) -> list[Chunk]:
        if not focus_terms:
            return []
        children = [by_id[chunk_id] for chunk_id in chunk.children_ids if chunk_id in by_id]
        matches = []
        for child in children:
            text = strip_accents(normalize_text(child.text))
            if any(term in text for term in focus_terms):
                matches.append(child)
        return matches[:3]

    @staticmethod
    def _expansion_bonus(anchor: Chunk, candidate: Chunk) -> float:
        if candidate.chunk_id == anchor.chunk_id:
            return 0.002
        return 0.001

    @staticmethod
    def _expansion_reason(anchor: Chunk, candidate: Chunk) -> str:
        if candidate.chunk_id == anchor.chunk_id:
            return "retrieved_anchor"
        if candidate.parent_id == anchor.chunk_id or candidate.chunk_id in anchor.children_ids:
            return "child_expansion"
        if candidate.sibling_group_id and candidate.sibling_group_id == anchor.sibling_group_id:
            return "sibling_expansion"
        return "structural_expansion"

    @staticmethod
    def _context_trace_item(
        chunk: Chunk,
        score: float,
        *,
        reason: str,
        anchor_chunk_id: str | None = None,
    ) -> dict[str, object]:
        return {
            "chunk_id": chunk.chunk_id,
            "reason": reason,
            "anchor_chunk_id": anchor_chunk_id,
            "chunk_type": chunk.chunk_type,
            "document_number": chunk.document_number,
            "article": chunk.article,
            "clause": chunk.clause,
            "point": chunk.point,
            "parent_id": chunk.parent_id,
            "sibling_group_id": chunk.sibling_group_id,
            "children_ids": chunk.children_ids,
            "score": score,
            "preview": chunk.text[:240],
        }
