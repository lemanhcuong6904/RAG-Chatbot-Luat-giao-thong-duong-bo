from __future__ import annotations

import json
import re

from rag_luat_gt.config import (
    MANIFEST_PATH,
    RAG_DENSE_ENABLED,
    RAG_EMBEDDING_AVAILABLE_PRESETS,
    RAG_EMBEDDING_PRESET,
    RAG_RERANKER_ENABLED,
    RAG_RERANKER_TOP_N,
    embedding_settings_for_preset,
    normalize_embedding_preset,
)
from rag_luat_gt.license_classes import (
    citation_defined_license_class_hits,
    citation_license_class_hits,
    citation_mentions_any_license_class,
)
from rag_luat_gt.retrieval.bm25 import BM25Retriever
from rag_luat_gt.rule_function import effective_rule_function
from rag_luat_gt.schemas import Chunk, ParsedQuery
from rag_luat_gt.text import normalize_text, strip_accents


RRF_K = 60


def _is_transition_chunk(chunk: Chunk) -> bool:
    text = strip_accents(normalize_text(f"{chunk.article_title or ''}\n{chunk.text[:600]}"))
    return "dieu khoan chuyen tiep" in text or (
        "xay ra va ket thuc" in text and "thoi diem thuc hien hanh vi" in text
    )


def _is_effective_date_chunk(chunk: Chunk) -> bool:
    text = strip_accents(normalize_text(f"{chunk.article_title or ''}\n{chunk.text[:600]}"))
    return "hieu luc thi hanh" in text or "co hieu luc thi hanh tu" in text


class HybridRetriever:
    def __init__(self) -> None:
        self.bm25 = BM25Retriever()
        self.dense = None
        self.dense_error: str | None = None
        self.active_embedding_preset = RAG_EMBEDDING_PRESET
        self.dense_by_preset: dict[str, object] = {}
        self.dense_errors_by_preset: dict[str, str | None] = {}
        self.reranker = None
        self.reranker_error: str | None = None
        self.last_context_trace: list[dict[str, object]] = []
        self.last_score_trace: dict[str, dict[str, object]] = {}
        if RAG_DENSE_ENABLED:
            self.dense = self._dense_for_preset(RAG_EMBEDDING_PRESET)
            self.dense_error = self.dense_errors_by_preset.get(RAG_EMBEDDING_PRESET)
        if RAG_RERANKER_ENABLED:
            try:
                from rag_luat_gt.retrieval.reranker import BGEReranker

                self.reranker = BGEReranker()
            except Exception as exc:
                self.reranker_error = str(exc)

    def search(self, parsed: ParsedQuery, top_k: int = 8, embedding_preset: str | None = None) -> list[tuple[Chunk, float]]:
        self.last_context_trace = []
        self.last_score_trace = {}
        self.active_embedding_preset = normalize_embedding_preset(embedding_preset)
        dense = self._dense_for_preset(self.active_embedding_preset)
        self.dense = dense if self.active_embedding_preset == RAG_EMBEDDING_PRESET else self.dense
        self.dense_error = self.dense_errors_by_preset.get(self.active_embedding_preset)
        exact_results = self._exact_reference_lookup(parsed, top_k=top_k)
        if exact_results:
            return self._expand_structural_context(parsed, exact_results, top_k)

        query_variants = self._planned_queries(parsed)
        if len(query_variants) > 1:
            result_sets: list[list[tuple[Chunk, float]]] = []
            for query in query_variants:
                variant = parsed.model_copy(update={"normalized_query": query, "retrieval_query": query})
                result_sets.append(self._search_single_query(variant, top_k=top_k, dense=dense))
            ranked = self._rrf(result_sets)
            ranked = self._apply_preferences(parsed, ranked)
            ranked = self._apply_reranker(parsed, ranked)
            return self._expand_structural_context(parsed, ranked, top_k)

        ranked = self._search_single_query(parsed, top_k=top_k, dense=dense)
        ranked = self._apply_preferences(parsed, ranked)
        ranked = self._apply_reranker(parsed, ranked)
        return self._expand_structural_context(parsed, ranked, top_k)

    def _exact_reference_lookup(self, parsed: ParsedQuery, top_k: int) -> list[tuple[Chunk, float]]:
        if not parsed.document_number or not parsed.article:
            return []
        exact = self.bm25.exact_lookup(parsed, top_k=top_k * 4)
        if not exact:
            return []
        boosted = [(chunk, 100.0 + score) for chunk, score in exact]
        self._record_source_scores("exact_reference", boosted)
        self._record_stage_scores("preference_score", boosted)
        return boosted

    def _search_single_query(self, parsed: ParsedQuery, top_k: int, dense: object | None = None) -> list[tuple[Chunk, float]]:
        bm25_results = self.bm25.search(parsed, top_k=top_k * 4)
        dense_results = []
        if dense:
            try:
                valid_chunk_ids = {chunk.chunk_id for chunk in self.bm25.chunks}
                dense_results = [
                    (chunk, score)
                    for chunk, score in dense.search(parsed, top_k=top_k * 4)
                    if chunk.chunk_id in valid_chunk_ids
                ]
            except Exception as exc:
                self.dense_errors_by_preset[self.active_embedding_preset] = str(exc)
                self.dense_error = str(exc)

        self._record_source_scores("bm25", bm25_results)
        self._record_source_scores("dense", dense_results)
        if not dense_results:
            self._record_stage_scores("preference_input", bm25_results)
            return bm25_results

        hybrid = self._rrf([dense_results, bm25_results])
        self._record_stage_scores("rrf_score", hybrid)
        return hybrid

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
        if parsed.must_include_terms:
            queries.append(" ".join(parsed.must_include_terms))

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
            self._record_stage_scores("pre_reranker_score", results)
            reranked = self.reranker.rerank(parsed, results, top_n=RAG_RERANKER_TOP_N)
            self._record_stage_scores("reranker_score", reranked)
            return reranked
        except Exception as exc:
            self.reranker_error = str(exc)
            return results

    def _dense_for_preset(self, preset: str | None):
        if not RAG_DENSE_ENABLED:
            return None
        normalized = normalize_embedding_preset(preset)
        if normalized in self.dense_by_preset:
            return self.dense_by_preset[normalized]
        if not self._dense_ready_matches_manifest(normalized):
            settings = embedding_settings_for_preset(normalized, allow_model_override=normalized == RAG_EMBEDDING_PRESET)
            if settings.ready_file.exists():
                self.dense_errors_by_preset[normalized] = "Dense index marker does not match the current BM25 manifest."
            else:
                self.dense_errors_by_preset[normalized] = "Dense index is not built for this embedding preset."
            return None
        try:
            from rag_luat_gt.retrieval.dense import DenseRetriever

            dense = DenseRetriever(normalized, allow_model_override=normalized == RAG_EMBEDDING_PRESET)
            self.dense_by_preset[normalized] = dense
            self.dense_errors_by_preset[normalized] = None
            return dense
        except Exception as exc:
            self.dense_errors_by_preset[normalized] = str(exc)
            return None

    @staticmethod
    def _dense_ready_matches_manifest(preset: str | None = None) -> bool:
        normalized = normalize_embedding_preset(preset)
        settings = embedding_settings_for_preset(normalized, allow_model_override=normalized == RAG_EMBEDDING_PRESET)
        if not settings.ready_file.exists() or not MANIFEST_PATH.exists():
            return False
        try:
            ready = json.loads(settings.ready_file.read_text(encoding="utf-8"))
            manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False

        dense_indexes = manifest.get("dense_indexes") if isinstance(manifest.get("dense_indexes"), dict) else {}
        dense = dense_indexes.get(normalized) or manifest.get("dense") or {}
        ready_model = ready.get("embedding_model")
        ready_preset = ready.get("embedding_preset") or ("bge_m3" if ready_model == "BAAI/bge-m3" else None)
        ready_vector_size = ready.get("embedding_vector_size") or (1024 if ready_model == "BAAI/bge-m3" else None)
        ready_query_instruction = ready.get("embedding_query_instruction") or ""
        ready_document_instruction = ready.get("embedding_document_instruction") or ""
        return all(
            [
                ready.get("collection") == settings.collection,
                ready_preset == normalized,
                ready_model == settings.model,
                ready_vector_size == settings.vector_size,
                ready_query_instruction == settings.query_instruction,
                ready_document_instruction == settings.document_instruction,
                ready.get("corpus_hash") == manifest.get("corpus_hash"),
                ready.get("chunking_version") == manifest.get("chunking_version"),
                ready.get("chunks") == manifest.get("chunks"),
                dense.get("corpus_hash") == manifest.get("corpus_hash"),
            ]
        )

    def dense_status_by_preset(self) -> dict[str, dict[str, object]]:
        status: dict[str, dict[str, object]] = {}
        for preset in RAG_EMBEDDING_AVAILABLE_PRESETS:
            settings = embedding_settings_for_preset(preset, allow_model_override=preset == RAG_EMBEDDING_PRESET)
            status[preset] = {
                "ready": self._dense_ready_matches_manifest(preset),
                "collection": settings.collection,
                "ready_file": str(settings.ready_file),
                "model": settings.model,
                "vector_size": settings.vector_size,
                "error": self.dense_errors_by_preset.get(preset),
            }
        return status

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
        reranked = self._apply_semantic_focus_preferences(parsed, reranked)
        reranked = self._apply_accident_responsibility_preferences(parsed, reranked)
        reranked = self._apply_license_point_preferences(parsed, reranked)
        reranked = self._apply_license_class_preferences(parsed, reranked)
        reranked = self._apply_driver_rights_preferences(parsed, reranked)
        reranked = self._apply_csgt_stop_basis_preferences(parsed, reranked)
        reranked = self._apply_child_pedestrian_crossing_preferences(parsed, reranked)
        reranked = self._apply_vehicle_preferences(parsed, reranked)
        reranked = self._apply_penalty_focus(parsed, reranked)
        reranked = self._apply_behavior_text_focus(parsed, reranked)
        reranked = self._apply_temporal_source_preferences(parsed, reranked)
        reranked = self._filter_vehicle_penalty_scope(parsed, reranked)
        reranked = self._filter_primary_penalty_scope(parsed, reranked)
        reranked = self._apply_amount_focus(parsed, reranked)
        reranked = sorted(reranked, key=lambda item: item[1], reverse=True)
        self._record_stage_scores("preference_score", reranked)
        return reranked

    @staticmethod
    def _apply_temporal_source_preferences(
        parsed: ParsedQuery,
        results: list[tuple[Chunk, float]],
    ) -> list[tuple[Chunk, float]]:
        if parsed.temporal_intent not in {"EFFECTIVE_DATE_LOOKUP", "APPLICABLE_RULE"}:
            return results

        query = strip_accents(normalize_text(parsed.query))
        transition_query = any(
            term in query
            for term in ["chuyen tiep", "phat hien", "xay ra va ket thuc", "thoi diem thuc hien", "truoc ngay"]
        )
        effective_query = parsed.temporal_intent == "EFFECTIVE_DATE_LOOKUP" or "hieu luc" in query

        reranked: list[tuple[Chunk, float]] = []
        for chunk, score in results:
            text = strip_accents(normalize_text(f"{chunk.article_title or ''}\n{chunk.text[:1400]}"))
            adjusted = score
            base = max(abs(score), 1.0)

            if effective_query and any(term in text for term in ["hieu luc thi hanh", "co hieu luc"]):
                adjusted += base * 5.0
            if transition_query and any(
                term in text
                for term in [
                    "dieu khoan chuyen tiep",
                    "xay ra va ket thuc truoc ngay",
                    "thoi diem thuc hien hanh vi",
                    "sau do moi bi phat hien",
                    "dang xem xet giai quyet",
                ]
            ):
                adjusted += base * 8.0

            if chunk.document_number == "238/2026/NĐ-CP" and "238" in query and chunk.article in {"20", "21"}:
                adjusted += base * 4.0
            if chunk.document_number == "168/2024/NĐ-CP" and "168" in query and chunk.article in {"53", "54"}:
                adjusted += base * 4.0
            if parsed.temporal_intent == "EFFECTIVE_DATE_LOOKUP" and chunk.valid_from:
                adjusted += base * 2.0
            if transition_query and effective_rule_function(chunk.rule_function, chunk.text, chunk.article_title) == "SANCTION":
                adjusted -= base * 1.5

            reranked.append((chunk, adjusted))
        return reranked

    def _record_source_scores(self, source: str, results: list[tuple[Chunk, float]]) -> None:
        score_key = f"{source}_score"
        rank_key = f"{source}_rank"
        for rank, (chunk, score) in enumerate(results, start=1):
            item = self.last_score_trace.setdefault(chunk.chunk_id, {})
            item[score_key] = score
            item[rank_key] = rank

    def _record_stage_scores(self, stage: str, results: list[tuple[Chunk, float]]) -> None:
        rank_key = f"{stage}_rank"
        for rank, (chunk, score) in enumerate(results, start=1):
            item = self.last_score_trace.setdefault(chunk.chunk_id, {})
            item[stage] = score
            item[rank_key] = rank

    @staticmethod
    def _apply_semantic_focus_preferences(
        parsed: ParsedQuery,
        results: list[tuple[Chunk, float]],
    ) -> list[tuple[Chunk, float]]:
        include_terms = [strip_accents(normalize_text(term)) for term in parsed.must_include_terms if term]
        confuse_terms = [strip_accents(normalize_text(term)) for term in parsed.must_not_confuse_with if term]
        if not include_terms and not confuse_terms:
            return results

        reranked: list[tuple[Chunk, float]] = []
        for chunk, score in results:
            text = strip_accents(normalize_text(f"{chunk.article_title or ''}\n{chunk.text[:1400]}"))
            adjusted = score
            base = max(abs(score), 1.0)
            include_hits = sum(1 for term in include_terms if term and term in text)
            confuse_hits = sum(1 for term in confuse_terms if term and term in text)
            if include_hits:
                adjusted += base * min(4.0, include_hits * 1.25)
            if include_terms and not include_hits:
                adjusted -= base * 0.35
            if confuse_hits:
                adjusted -= base * min(3.0, confuse_hits * 1.0)
            reranked.append((chunk, adjusted))
        return reranked

    @staticmethod
    def _apply_rule_function_preferences(
        parsed: ParsedQuery,
        results: list[tuple[Chunk, float]],
    ) -> list[tuple[Chunk, float]]:
        if not parsed.desired_rule_function:
            return results

        query = strip_accents(normalize_text(parsed.query))
        asks_capacity = any(term in query for term in ["cm3", "cm³", "cc", "xi lanh", "dung tich", "kw", "cong suat"])
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
                if asks_capacity and chunk.document_number == "36/2024/QH15" and chunk.article == "57":
                    if any(term in text for term in ["hang a1", "hang a", "dung tich xi-lanh", "dung tich xi lanh"]):
                        adjusted += base * 5.0
                if asks_capacity and chunk.document_number == "36/2024/QH15" and chunk.article == "34":
                    if "xe gan may" in text and any(term in text for term in ["50 km/h", "04 kw", "cong suat"]):
                        adjusted += base * 3.0
                if any(term in text for term in ["phat tien", "xu phat", "vi pham"]):
                    adjusted -= base * 1.5

            reranked.append((chunk, adjusted))

        return reranked

    @staticmethod
    def _apply_accident_responsibility_preferences(
        parsed: ParsedQuery,
        results: list[tuple[Chunk, float]],
    ) -> list[tuple[Chunk, float]]:
        query = strip_accents(normalize_text(parsed.query))
        if "tai nan giao thong" not in query:
            return results
        if not any(term in query for term in ["trach nhiem", "nghia vu", "phai lam gi", "co nhung"]):
            return results

        reranked: list[tuple[Chunk, float]] = []
        for chunk, score in results:
            text = strip_accents(normalize_text(f"{chunk.article_title or ''}\n{chunk.text[:900]}"))
            adjusted = score
            base = max(abs(score), 1.0)
            if chunk.document_number == "36/2024/QH15" and chunk.article == "80":
                adjusted += base * 3.5
                if chunk.chunk_type == "ARTICLE":
                    adjusted += base * 4.0
                if any(term in text for term in ["nguoi dieu khien phuong tien", "nguoi lien quan", "nguoi co mat"]):
                    adjusted += base * 1.5
            elif chunk.document_number == "36/2024/QH15" and chunk.article in {"82", "83"}:
                adjusted -= base * 0.75
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
    def _apply_license_class_preferences(
        parsed: ParsedQuery,
        results: list[tuple[Chunk, float]],
    ) -> list[tuple[Chunk, float]]:
        if parsed.intent not in {"DRIVER_LICENSE", "DRIVER_AGE_REQUIREMENT"} or not parsed.license_classes:
            return results

        expected_article = "57" if parsed.intent == "DRIVER_LICENSE" else "59"
        reranked: list[tuple[Chunk, float]] = []
        for chunk, score in results:
            text = strip_accents(normalize_text(f"{chunk.article_title or ''}\n{chunk.text[:1200]}"))
            adjusted = score
            base = max(abs(score), 1.0)
            hits = (
                citation_defined_license_class_hits(chunk.text, parsed.license_classes)
                if parsed.intent == "DRIVER_LICENSE"
                else citation_license_class_hits(text, parsed.license_classes)
            )

            if chunk.document_number == "36/2024/QH15" and chunk.article == expected_article:
                adjusted += base * 2.0
                if chunk.chunk_type == "POINT" and hits:
                    adjusted += base * (7.0 if len(hits) == len(parsed.license_classes) else 4.0)
                elif chunk.chunk_type == "CLAUSE":
                    adjusted += base * 0.75
            elif chunk.document_number == "36/2024/QH15" and chunk.article in {"57", "59"}:
                adjusted -= base * 1.5

            if chunk.chunk_type == "POINT" and citation_mentions_any_license_class(text) and not hits:
                adjusted -= base * 4.0

            if parsed.intent == "DRIVER_LICENSE" and any(term in text for term in ["tuoi", "suc khoe"]):
                adjusted -= base * 2.5

            reranked.append((chunk, adjusted))

        return reranked

    @staticmethod
    def _apply_driver_rights_preferences(
        parsed: ParsedQuery,
        results: list[tuple[Chunk, float]],
    ) -> list[tuple[Chunk, float]]:
        query = strip_accents(normalize_text(parsed.query))
        has_authority = any(term in query for term in ["csgt", "canh sat giao thong", "luc luong tuan tra"])
        has_stop_context = any(term in query for term in ["dung xe", "dung phuong tien", "kiem tra", "kiem soat"])
        asks_reason = any(term in query for term in ["ly do", "can cu", "duoc biet", "duoc thong bao", "quyen"])
        if not (has_authority and has_stop_context and asks_reason):
            return results

        reranked: list[tuple[Chunk, float]] = []
        for chunk, score in results:
            text = strip_accents(normalize_text(f"{chunk.article_title or ''}\n{chunk.text[:1200]}"))
            adjusted = score
            base = max(abs(score), 1.0)
            if chunk.document_number == "36/2024/QH15" and chunk.article == "72":
                adjusted += base * 4.0
                if chunk.clause == "1":
                    adjusted += base * 2.0
                if chunk.point == "b" and all(
                    term in text for term in ["duoc thong bao", "can cu dung phuong tien", "kiem tra", "kiem soat"]
                ):
                    adjusted += base * 8.0
            if chunk.article == "18" and any(term in text for term in ["dung xe, do xe", "dung xe", "do xe"]):
                adjusted -= base * 3.5
            if chunk.document_number == "168/2024/NĐ-CP" and chunk.rule_function == "SANCTION":
                adjusted -= base * 2.0
            reranked.append((chunk, adjusted))
        return reranked

    @staticmethod
    def _apply_csgt_stop_basis_preferences(
        parsed: ParsedQuery,
        results: list[tuple[Chunk, float]],
    ) -> list[tuple[Chunk, float]]:
        query = strip_accents(normalize_text(parsed.query))
        has_authority = any(term in query for term in ["csgt", "canh sat giao thong", "luc luong tuan tra"])
        has_stop_context = any(term in query for term in ["dung xe", "dung phuong tien", "kiem tra", "kiem soat"])
        asks_driver_right = any(term in query for term in ["ly do", "duoc biet", "duoc thong bao", "quyen"])
        if not (has_authority and has_stop_context) or asks_driver_right:
            return results

        asks_detection_system = any(
            term in query
            for term in [
                "camera",
                "cam thay",
                "coi cam",
                "du lieu",
                "he thong giam sat",
                "phuong tien thiet bi ky thuat",
                "thiet bi ky thuat",
                "thiet bi nghiep vu",
            ]
        )
        reranked: list[tuple[Chunk, float]] = []
        for chunk, score in results:
            text = strip_accents(normalize_text(f"{chunk.article_title or ''}\n{chunk.text[:1200]}"))
            adjusted = score
            base = max(abs(score), 1.0)
            if chunk.document_number == "36/2024/QH15" and chunk.article == "66":
                adjusted += base * 8.0
                if any(term in text for term in ["can cu dung phuong tien", "duoc dung phuong tien"]):
                    adjusted += base * 4.0
            if asks_detection_system and chunk.document_number == "36/2024/QH15" and chunk.article in {"67", "71"}:
                adjusted += base * 6.0
                if any(term in text for term in ["he thong giam sat", "camera", "thiet bi ky thuat nghiep vu"]):
                    adjusted += base * 4.0
            if chunk.document_number == "73/2024/TT-BCA" and chunk.article == "28":
                adjusted -= base * 4.0
            if chunk.article == "18" and any(term in text for term in ["dung xe, do xe", "dung xe", "do xe"]):
                adjusted -= base * 4.0
            reranked.append((chunk, adjusted))
        return reranked

    @staticmethod
    def _apply_child_pedestrian_crossing_preferences(
        parsed: ParsedQuery,
        results: list[tuple[Chunk, float]],
    ) -> list[tuple[Chunk, float]]:
        query = strip_accents(normalize_text(parsed.query))
        is_child_crossing = any(term in query for term in ["tre duoi 7", "tre em duoi 7", "duoi 7 tuoi"]) and any(
            term in query for term in ["qua duong", "sang duong"]
        )
        if not is_child_crossing:
            return results

        reranked: list[tuple[Chunk, float]] = []
        for chunk, score in results:
            text = strip_accents(normalize_text(f"{chunk.article_title or ''}\n{chunk.text[:1200]}"))
            adjusted = score
            base = max(abs(score), 1.0)
            if chunk.document_number == "36/2024/QH15" and chunk.article == "30":
                adjusted += base * 8.0
                if chunk.clause == "2":
                    adjusted += base * 4.0
                if "tre em duoi 07 tuoi" in text and "qua duong" in text:
                    adjusted += base * 6.0
            if chunk.document_number == "36/2024/QH15" and chunk.article in {"57", "59"}:
                adjusted -= base * 6.0
            reranked.append((chunk, adjusted))
        return reranked

    @staticmethod
    def _apply_vehicle_preferences(
        parsed: ParsedQuery,
        results: list[tuple[Chunk, float]],
    ) -> list[tuple[Chunk, float]]:
        if not parsed.vehicle_type:
            return results

        query = strip_accents(normalize_text(parsed.query))
        asks_helmet_for_bicycle = parsed.vehicle_type == "xe đạp" and any(
            term in query for term in ["mu bao hiem", "doi mu"]
        )
        reranked: list[tuple[Chunk, float]] = []
        for chunk, score in results:
            title = normalize_text(chunk.article_title or "")
            text = normalize_text(f"{title}\n{chunk.text[:700]}")
            text_ascii = strip_accents(text)
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

            elif parsed.vehicle_type == "xe đạp":
                if chunk.document_number == "168/2024/NĐ-CP" and chunk.article == "9":
                    adjusted += abs(score) * 0.2
                if asks_helmet_for_bicycle and any(
                    term in text_ascii for term in ["xe dap may", "mo to", "xe gan may", "xe may"]
                ):
                    adjusted -= abs(score) * 0.55

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
        behavior_terms = HybridRetriever._behavior_focus_terms(query)
        condition_terms = HybridRetriever._condition_focus_terms(query)
        focus_terms = [*behavior_terms, *condition_terms]
        if not focus_terms:
            return results

        reranked: list[tuple[Chunk, float]] = []
        for chunk, score in results:
            text = strip_accents(normalize_text(f"{chunk.article_title or ''}\n{chunk.text[:1200]}"))
            adjusted = score
            base = max(abs(score), 1.0)
            behavior_matched = any(term in text for term in behavior_terms)
            condition_matched = any(term in text for term in condition_terms)
            any_matched = behavior_matched or condition_matched
            if behavior_terms and condition_terms and behavior_matched and condition_matched:
                adjusted += base * (7.0 if chunk.chunk_type == "POINT" else 2.2)
            elif any_matched:
                adjusted += base * (3.0 if chunk.chunk_type == "POINT" else 1.8)
                if condition_terms and behavior_matched and not condition_matched:
                    adjusted -= base * (2.0 if chunk.chunk_type == "POINT" else 0.75)
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
            (["quay dau", "quay dau xe"], ["quay dau", "quay dau xe"]),
            (["lui xe"], ["lui xe"]),
        ]
        terms: list[str] = []
        for triggers, expansions in groups:
            if any(trigger in query_ascii for trigger in triggers):
                terms.extend(expansions)
        return terms

    @staticmethod
    def _condition_focus_terms(query_ascii: str) -> list[str]:
        groups = [
            (["trong ham", "duong ham", "ham duong bo"], ["trong ham", "duong ham", "ham duong bo"]),
            (["cao toc", "duong cao toc"], ["cao toc", "duong cao toc"]),
            (["via he", "le duong", "long duong"], ["via he", "le duong", "long duong"]),
            (["cau", "gam cau", "dau cau"], ["cau", "gam cau", "dau cau"]),
            (["duong sat", "giao nhau voi duong sat"], ["duong sat", "giao nhau voi duong sat"]),
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
        focus_terms = [
            *HybridRetriever._behavior_focus_terms(query),
            *HybridRetriever._condition_focus_terms(query),
        ]
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
        temporal_companions = self._temporal_companion_chunks()
        query_ascii = strip_accents(normalize_text(parsed.query))
        focus_terms = [
            *self._behavior_focus_terms(query_ascii),
            *self._condition_focus_terms(query_ascii),
            *[strip_accents(normalize_text(term)) for term in parsed.must_include_terms if term],
        ]

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
            companion = temporal_companions.get(chunk.chunk_id)
            if companion and companion.chunk_id not in seen:
                companion_score = score + 0.0012
                expanded.append((companion, companion_score))
                seen.add(companion.chunk_id)
                trace.append(
                    self._context_trace_item(
                        companion,
                        companion_score,
                        reason="temporal_companion_expansion",
                        anchor_chunk_id=chunk.chunk_id,
                    )
                )
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

        if parsed.intent == "DRIVER_AGE_REQUIREMENT":
            for companion in self._capacity_age_companion_chunks(parsed, by_location):
                if companion.chunk_id in seen:
                    continue
                companion_score = (results[0][1] if results else 0.0) + 0.0018
                expanded.append((companion, companion_score))
                seen.add(companion.chunk_id)
                trace.append(
                    self._context_trace_item(
                        companion,
                        companion_score,
                        reason="capacity_age_companion",
                        anchor_chunk_id=None,
                    )
                )

        self.last_context_trace = trace
        return expanded

    @staticmethod
    def _capacity_age_companion_chunks(
        parsed: ParsedQuery,
        by_location: dict[tuple[str, str | None, str | None, str | None], Chunk],
    ) -> list[Chunk]:
        query = strip_accents(normalize_text(parsed.query)).replace("cm³", "cm3")
        match = re.search(r"\b(\d+(?:[,.]\d+)?)\s*(?:cm3|cc)\b", query)
        if not match:
            return []
        capacity = float(match.group(1).replace(",", "."))
        if capacity > 50:
            return []
        targets = [
            ("QH15_36_2024", "34", "1", "g"),
            ("QH15_36_2024", "59", "1", "a"),
        ]
        return [chunk for target in targets if (chunk := by_location.get(target)) is not None]

    def _temporal_companion_chunks(self) -> dict[str, Chunk]:
        by_document_article: dict[tuple[str, str], list[Chunk]] = {}
        for chunk in self.bm25.chunks:
            if chunk.document_id and chunk.article:
                by_document_article.setdefault((chunk.document_id, chunk.article), []).append(chunk)

        companions: dict[str, Chunk] = {}
        for chunk in self.bm25.chunks:
            if not chunk.document_id or not chunk.article or not _is_transition_chunk(chunk):
                continue
            try:
                previous_article = str(int(chunk.article) - 1)
            except ValueError:
                continue
            candidates = by_document_article.get((chunk.document_id, previous_article), [])
            effective = next((item for item in candidates if _is_effective_date_chunk(item)), None)
            if effective:
                companions[chunk.chunk_id] = effective
        return companions

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
            expanded = [anchor]
            seen = {anchor.chunk_id}

            def add_descendants(parent: Chunk) -> None:
                children = [
                    by_id[chunk_id]
                    for chunk_id in parent.children_ids
                    if chunk_id in by_id and chunk_id not in seen
                ]
                for child in sorted(children, key=lambda chunk: (chunk.order, chunk.chunk_id)):
                    expanded.append(child)
                    seen.add(child.chunk_id)
                    add_descendants(child)

            add_descendants(anchor)
            return expanded
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
