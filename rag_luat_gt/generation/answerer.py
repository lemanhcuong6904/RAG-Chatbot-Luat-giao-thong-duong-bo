from __future__ import annotations

from datetime import date
import re

from rag_luat_gt.config import OPENAI_API_KEY, RAG_LLM_PROVIDER, RAG_REQUIRE_LLM
from rag_luat_gt.citation_format import (
    normalize_inline_legal_refs,
    replace_source_markers,
    short_ref as format_short_ref,
)
from rag_luat_gt.generation.openai_provider import generate_with_openai
from rag_luat_gt.legal_notes import legal_notes
from rag_luat_gt.rule_function import effective_rule_function
from rag_luat_gt.schemas import ChatResponse, Citation, Chunk, ParsedQuery
from rag_luat_gt.text import normalize_text, strip_accents, tokenize


def _legal_ref(citation: Citation) -> str:
    if citation.chunk_type == "APPENDIX":
        return "Phụ lục"

    parts = []
    if citation.article:
        text = f"Điều {citation.article}"
        if citation.article_title:
            text += f" ({citation.article_title})"
        parts.append(text)
    if citation.clause:
        parts.append(f"Khoản {citation.clause}")
    if citation.point:
        parts.append(f"Điểm {citation.point}")
    return " - ".join(parts) if parts else "Không xác định điều khoản"


def _citation_from_result(chunk: Chunk, score: float) -> Citation:
    return Citation(
        chunk_id=chunk.chunk_id,
        chunk_type=chunk.chunk_type,
        document_number=chunk.document_number,
        document_title=chunk.document_title,
        article=chunk.article,
        article_title=chunk.article_title,
        clause=chunk.clause,
        point=chunk.point,
        parent_id=chunk.parent_id,
        sibling_group_id=chunk.sibling_group_id,
        source_file=chunk.source_file,
        text=chunk.text,
        rule_function=effective_rule_function(chunk.rule_function, chunk.text, chunk.article_title),
        coverage_status=chunk.coverage_status,
        source_quality=chunk.source_quality,
        score=score,
    )


def _evidence_gate(
    parsed: ParsedQuery,
    results: list[tuple[Chunk, float]],
) -> tuple[bool, list[str]]:
    notes: list[str] = []
    if not results:
        return False, ["Không tìm thấy nguồn phù hợp trong index."]

    query = strip_accents(normalize_text(parsed.evidence_validation_query or parsed.query))
    query_tokens = {token for token in tokenize(query) if len(token) >= 3}
    evidence_tokens = {
        token
        for chunk, _score in results[:5]
        for token in tokenize(strip_accents(normalize_text(chunk.retrieval_text)))
        if len(token) >= 3
    }
    overlap = len(query_tokens & evidence_tokens) / max(len(query_tokens), 1)

    has_legal_ref = any([parsed.document_number, parsed.article, parsed.clause, parsed.point])
    if overlap < 0.12 and not has_legal_ref:
        notes.append("Độ khớp giữa câu hỏi và nguồn truy xuất quá thấp.")

    asks_amount = any(term in query for term in ["bao nhieu", "muc phat", "phat bao nhieu", "dong"])
    has_amount_evidence = any(
        "đồng" in chunk.text.lower() or "dong" in strip_accents(normalize_text(chunk.text))
        for chunk, _score in results[:5]
    )
    if parsed.intent == "PENALTY_LOOKUP" and asks_amount and not has_amount_evidence:
        notes.append("Nguồn truy xuất chưa có mức tiền phạt cụ thể.")

    if parsed.desired_rule_function == "ELIGIBILITY":
        top_functions = [
            effective_rule_function(chunk.rule_function, chunk.text, chunk.article_title)
            for chunk, _score in results[:6]
        ]
        has_positive_basis = "ELIGIBILITY" in top_functions
        only_sanction_basis = bool(top_functions) and all(rule_function == "SANCTION" for rule_function in top_functions)
        if not has_positive_basis:
            notes.append("Chưa tìm thấy quy định trực tiếp xác lập điều kiện được phép.")
        if only_sanction_basis:
            notes.append(
                "Nguồn truy xuất chỉ chứa quy định xử phạt; quy định xử phạt không chứng minh hành vi được phép."
            )

    asks_missing_appendix = _asks_missing_appendix_or_table(query)
    weak_coverage = [
        chunk.coverage_status
        for chunk, _score in results[:5]
        if chunk.coverage_status in {"MISSING_APPENDIX", "MISSING_TABLE", "MISSING_PAGES", "PARTIAL"}
    ]
    if asks_missing_appendix and weak_coverage:
        notes.append(
            "Corpus hiện có nguồn không đầy đủ cho phần phụ lục/bảng/trang được hỏi: "
            + ", ".join(sorted(set(weak_coverage)))
            + "."
        )

    return not notes, notes


def _asks_missing_appendix_or_table(query: str) -> bool:
    if any(term in query for term in ["phu luc", "bieu mau", "mau so"]):
        return True
    if any(term in query for term in ["bang lai", "bang c", "bang d", "bang a", "bang b", "gplx", "giay phep lai xe"]):
        return False
    return any(term in query for term in ["bang gia", "bang muc", "bang so", "bang 1", "bang 2", "bang 3"])


def _build_extractive_answer(
    parsed: ParsedQuery,
    results: list[tuple[Chunk, float]],
    citations: list[Citation],
    legal_notes: list[str],
) -> str:
    if parsed.intent == "PENALTY_LOOKUP" and not parsed.vehicle_code and _has_vehicle_scope_note(legal_notes):
        return _build_vehicle_scope_answer(parsed, citations, legal_notes)
    if _has_bicycle_helmet_scope_note(legal_notes):
        return _build_bicycle_helmet_scope_answer(parsed, citations, legal_notes)

    focused = _focused_citations(parsed, citations)
    direct = _build_direct_extractive_answer(parsed, focused)
    if direct:
        return direct

    evidence_limit = 12 if parsed.retrieval_mode == "EXHAUSTIVE" else 2
    selected = focused[:evidence_limit] or citations[:evidence_limit]
    lines = []
    for citation in selected:
        text = _clean_evidence_text(citation.text, limit=700 if parsed.retrieval_mode == "EXHAUSTIVE" else 300)
        lines.append(f"- {text} [{_short_ref(citation)}]")
    return "\n".join(lines)


def _focused_citations(parsed: ParsedQuery, citations: list[Citation]) -> list[Citation]:
    query_tokens = _content_tokens(parsed.evidence_validation_query or parsed.query)
    scored: list[tuple[int, int, Citation]] = []
    for index, citation in enumerate(citations):
        text = f"{citation.article_title or ''} {citation.text}"
        score = len(query_tokens & _content_tokens(text))
        if _citation_matches_query_focus(parsed, citation):
            score += 5
        if parsed.document_number and citation.document_number == parsed.document_number:
            score += 3
        if parsed.article and citation.article == parsed.article:
            score += 3
        if parsed.clause and citation.clause == parsed.clause:
            score += 2
        if citation.chunk_type in {"POINT", "STRUCTURED_PROVISION", "STRUCTURED_TABLE", "SANCTION_RULE"}:
            score += 1
        if score >= 2:
            scored.append((score, index, citation))

    selected = [citation for _score, _index, citation in sorted(scored, key=lambda item: (-item[0], item[1]))]
    return _drop_redundant_parent_citations(parsed, selected)


_FOCUS_STOPWORDS = {
    "ban",
    "bao",
    "bi",
    "bo",
    "cac",
    "can",
    "cho",
    "co",
    "cua",
    "dang",
    "de",
    "den",
    "duoc",
    "gi",
    "hoi",
    "khong",
    "khi",
    "la",
    "lai",
    "luat",
    "nao",
    "neu",
    "nguoi",
    "phai",
    "quy",
    "quy dinh",
    "su",
    "tai",
    "the",
    "thi",
    "tren",
    "trong",
    "ve",
    "voi",
    "xe",
}


def _content_tokens(text: str) -> set[str]:
    return {
        token
        for token in tokenize(strip_accents(normalize_text(text)))
        if len(token) >= 3 and token not in _FOCUS_STOPWORDS
    }


def _drop_redundant_parent_citations(parsed: ParsedQuery, citations: list[Citation]) -> list[Citation]:
    keep_parent_with_amount = parsed.intent == "PENALTY_LOOKUP" or _query_asks_amount(parsed.query)
    child_keys = {
        (citation.document_number, citation.article, citation.clause)
        for citation in citations
        if citation.chunk_type not in {"ARTICLE", "CLAUSE"} and citation.clause
    }
    selected: list[Citation] = []
    seen: set[str] = set()
    for citation in citations:
        if citation.chunk_id in seen:
            continue
        if (
            citation.chunk_type in {"ARTICLE", "CLAUSE"}
            and (citation.document_number, citation.article, citation.clause) in child_keys
            and not (keep_parent_with_amount and _contains_money(citation.text))
        ):
            continue
        selected.append(citation)
        seen.add(citation.chunk_id)
    return selected


def _build_direct_extractive_answer(parsed: ParsedQuery, citations: list[Citation]) -> str | None:
    license_points_answer = _build_license_point_balance_answer(parsed, citations)
    if license_points_answer:
        return license_points_answer

    effective_answer = _build_effective_date_extractive_answer(parsed, citations)
    if effective_answer:
        return effective_answer

    yes_no_answer = _build_yes_no_extractive_answer(parsed, citations)
    if yes_no_answer:
        return yes_no_answer

    return None


def _build_license_point_balance_answer(parsed: ParsedQuery, citations: list[Citation]) -> str | None:
    if parsed.intent != "LICENSE_POINT_BALANCE":
        return None
    citation = next(
        (
            item
            for item in citations
            if item.document_number == "36/2024/QH15" and item.article == "58" and item.clause == "1"
        ),
        None,
    )
    if not citation:
        return None
    text = strip_accents(normalize_text(citation.text))
    if "bao gom 12 diem" not in text and "12 diem" not in text:
        return None
    return f"Mỗi giấy phép lái xe có 12 điểm để quản lý việc chấp hành pháp luật về trật tự, an toàn giao thông đường bộ [{_short_ref(citation)}]."


def _build_yes_no_extractive_answer(parsed: ParsedQuery, citations: list[Citation]) -> str | None:
    query = strip_accents(normalize_text(parsed.query))
    if not any(term in query for term in ["co duoc", "duoc phep", "co phai", "duoc khong"]):
        return None
    citation = next((item for item in citations if item.chunk_type != "ARTICLE"), citations[0] if citations else None)
    if not citation:
        return None
    text = strip_accents(normalize_text(f"{citation.article_title or ''} {citation.text}"))
    if _looks_prohibitive_or_sanction(citation, text):
        return f"Không. {_clean_evidence_text(citation.text, limit=260)} [{_short_ref(citation)}]."
    if "duoc" in text or "cho phep" in text:
        return f"Có. {_clean_evidence_text(citation.text, limit=260)} [{_short_ref(citation)}]."
    return None


def _looks_prohibitive_or_sanction(citation: Citation, normalized_text: str) -> bool:
    return (
        citation.rule_function == "SANCTION"
        or "xu phat" in strip_accents(normalize_text(citation.article_title or ""))
        or any(term in normalized_text for term in ["khong duoc", "nghiem cam", "vi pham", "phat tien"])
    )


def _build_effective_date_extractive_answer(parsed: ParsedQuery, citations: list[Citation]) -> str | None:
    query = strip_accents(normalize_text(parsed.query))
    if "hieu luc" not in query:
        return None
    citation = next((item for item in citations if "hiệu lực" in normalize_text(item.text)), None)
    if not citation:
        return None
    effective_date = _effective_date_from_text(citation.text)
    asked_date = _question_date(parsed)
    effective_text = _effective_text(citation.text)
    document = _short_ref(citation).split(", Điều", maxsplit=1)[0]

    if asked_date and effective_date:
        prefix = "Có." if asked_date >= effective_date else "Chưa."
        return f"{prefix} {document} có hiệu lực từ {effective_text} [{_short_ref(citation)}]."
    if effective_text:
        return f"{document} có hiệu lực từ {effective_text} [{_short_ref(citation)}]."
    return None


def _effective_text(text: str) -> str:
    match = re.search(r"có hiệu lực thi hành từ\s+(ngày\s+[^.;]+)", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return "ngày được nêu trong nguồn"


def _effective_date_from_text(text: str) -> date | None:
    match = re.search(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", text, flags=re.IGNORECASE)
    if not match:
        return None
    return _safe_date(int(match.group(3)), int(match.group(2)), int(match.group(1)))


def _question_date(parsed: ParsedQuery) -> date | None:
    for raw in [parsed.event_date, parsed.query_reference_date, parsed.as_of_date]:
        if raw:
            try:
                return date.fromisoformat(str(raw))
            except ValueError:
                pass
    match = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", parsed.query)
    if match:
        return _safe_date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
    return None


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _query_asks_amount(query: str) -> bool:
    normalized = strip_accents(normalize_text(query))
    return any(term in normalized for term in ["bao nhieu", "muc phat", "phat tien", "dong"])


def _contains_money(text: str) -> bool:
    normalized = strip_accents(normalize_text(text))
    return "dong" in normalized or bool(re.search(r"\d[\d.]*\s*đồng", text, flags=re.IGNORECASE))


def _clean_evidence_text(text: str, *, limit: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^[a-zA-ZđĐ]\)\s*", "", text)
    text = re.sub(r"^\d+\.\s*", "", text)
    if len(text) <= limit:
        return text.rstrip(" ;")
    truncated = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;")
    return truncated + "..."


def _exact_reference_target(parsed: ParsedQuery, citations: list[Citation]) -> Citation | None:
    if not parsed.document_number or not parsed.article:
        return None

    def matches(citation: Citation) -> bool:
        if citation.document_number != parsed.document_number:
            return False
        if citation.article != parsed.article:
            return False
        if parsed.clause and citation.clause != parsed.clause:
            return False
        if parsed.point and citation.point != parsed.point:
            return False
        return True

    exact = [citation for citation in citations if matches(citation)]
    if not exact:
        return None
    if parsed.point:
        return next((citation for citation in exact if citation.chunk_type == "POINT"), exact[0])
    if parsed.clause:
        return next((citation for citation in exact if citation.chunk_type == "CLAUSE"), exact[0])
    return next((citation for citation in exact if citation.chunk_type == "ARTICLE"), exact[0])


def _build_exact_reference_answer(parsed: ParsedQuery, citations: list[Citation]) -> str | None:
    target = _exact_reference_target(parsed, citations)
    if not target:
        return None

    label_parts = []
    if target.point:
        label_parts.append(f"Điểm {target.point}")
    if target.clause:
        label_parts.append(f"Khoản {target.clause}")
    if target.article:
        label_parts.append(f"Điều {target.article}")
    label = " ".join(label_parts) or "Quy định được hỏi"
    ref = _short_ref(target)
    return (
        "### Trả lời\n"
        f"{label} {target.document_number or target.document_title} quy định:\n\n"
        f"{target.text.strip()} [{ref}]\n\n"
        "### Căn cứ pháp lý\n"
        f"1. {ref}"
    )


def _has_vehicle_scope_note(notes: list[str]) -> bool:
    return any("chưa nêu rõ loại phương tiện" in note for note in notes)


def _has_bicycle_helmet_scope_note(notes: list[str]) -> bool:
    return any("xe đạp thông thường" in note and "mũ bảo hiểm" in note for note in notes)


def _build_bicycle_helmet_scope_answer(
    parsed: ParsedQuery,
    citations: list[Citation],
    notes: list[str],
) -> str:
    selected = _bicycle_helmet_scope_citations(citations)
    refs = "\n".join(
        f"{index + 1}. {citation.document_number or citation.document_title}: {_legal_ref(citation)}"
        for index, citation in enumerate(selected[:5])
    )
    note_text = "\n".join(f"- {note}" for note in notes)
    return (
        "### Trả lời\n"
        "Đúng: với câu hỏi về **xe đạp thông thường**, tôi chưa tìm thấy căn cứ trực tiếp trong corpus cho thấy "
        "người đi xe đạp bắt buộc phải đội mũ bảo hiểm.\n\n"
        "Các căn cứ truy xuất được về mũ bảo hiểm đang nói đến **xe đạp máy**, **mô tô** hoặc **xe gắn máy**, "
        "nên không được dùng để kết luận nghĩa vụ bắt buộc đội mũ đối với xe đạp thông thường.\n\n"
        "### Căn cứ pháp lý đã truy xuất\n"
        f"{refs or 'Không có nguồn trực tiếp cho xe đạp thông thường.'}\n\n"
        "### Lưu ý\n"
        f"{note_text}"
    )


def _build_vehicle_scope_answer(
    parsed: ParsedQuery,
    citations: list[Citation],
    notes: list[str],
) -> str:
    grouped: dict[str, list[Citation]] = {}
    for citation in citations:
        if citation.document_number != "168/2024/NĐ-CP" or citation.article not in {"6", "7", "8", "9"}:
            continue
        grouped.setdefault(citation.article or "", []).append(citation)

    labels = {
        "6": "ô tô và xe tương tự ô tô",
        "7": "mô tô, xe gắn máy và xe tương tự",
        "8": "xe máy chuyên dùng",
        "9": "xe thô sơ",
    }
    lines: list[str] = []
    for article in sorted(grouped, key=int):
        points = [
            item
            for item in grouped[article]
            if item.chunk_type == "POINT" and item.clause and _citation_matches_query_focus(parsed, item)
        ]
        points_by_clause: dict[str, list[Citation]] = {}
        for point in points:
            points_by_clause.setdefault(point.clause or "", []).append(point)

        for clause_no, clause_points in sorted(points_by_clause.items(), key=lambda item: _numeric_key(item[0])):
            clause = next(
                (
                    item
                    for item in grouped[article]
                    if item.chunk_type == "CLAUSE" and item.clause == clause_no
                ),
                None,
            )
            if not clause:
                continue
            point_refs = ", ".join(f"Điểm {point.point}" for point in clause_points if point.point)
            citation_refs = "; ".join(_short_ref(point) for point in clause_points)
            lines.append(
                f"- **{labels.get(article, 'nhóm phương tiện liên quan')}**: "
                f"{_extract_fine_text(clause.text)}"
                f"{' (' + point_refs + ')' if point_refs else ''} [{citation_refs}]."
            )

    note_text = "\n".join(f"- {note}" for note in notes)
    date_line = parsed.legal_effective_date or parsed.event_date or parsed.as_of_date or "ngày hiện tại"
    return (
        "### Trả lời\n"
        "Câu hỏi chưa nêu rõ loại phương tiện, nên mức xử phạt cần tách theo từng nhóm xe:\n\n"
        f"{chr(10).join(lines) if lines else 'Chưa đủ nguồn trực tiếp để trình bày từng nhánh.'}\n\n"
        "### Thời điểm áp dụng\n"
        f"Đang xét theo ngày hiệu lực pháp lý {date_line}.\n\n"
        "### Lưu ý\n"
        f"{note_text}"
    )


def _numeric_key(value: str) -> tuple[int, str]:
    return (int(value), value) if value.isdigit() else (999, value)


def _extract_fine_text(text: str) -> str:
    match = re.search(r"Phạt tiền từ\s+[\d.]+\s+đồng\s+đến\s+[\d.]+\s+đồng", text, flags=re.IGNORECASE)
    if match:
        return match.group(0)
    first_sentence = re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)[0]
    return first_sentence.rstrip(".")


def _short_ref(citation: Citation) -> str:
    return format_short_ref(citation)


def _normalize_answer_style(answer: str, citations: list[Citation]) -> str:
    answer = replace_source_markers(answer, citations)
    answer = normalize_inline_legal_refs(answer, citations)
    answer = re.sub(r"^\s*###\s*Trả lời\s*", "", answer, flags=re.IGNORECASE)
    answer = re.split(r"\n\s*###\s*Căn cứ pháp lý\b", answer, maxsplit=1, flags=re.IGNORECASE)[0]
    answer = re.split(r"\n\s*###\s*Căn cứ pháp lý đã truy xuất\b", answer, maxsplit=1, flags=re.IGNORECASE)[0]
    answer = re.split(r"\n\s*###\s*Thời điểm áp dụng\b", answer, maxsplit=1, flags=re.IGNORECASE)[0]
    return answer.strip()


def _vehicle_scope_citations(parsed: ParsedQuery, citations: list[Citation]) -> list[Citation]:
    grouped: dict[str, list[Citation]] = {}
    for citation in citations:
        if citation.document_number != "168/2024/NĐ-CP" or citation.article not in {"6", "7", "8", "9"}:
            continue
        grouped.setdefault(citation.article or "", []).append(citation)

    selected: list[Citation] = []
    seen: set[str] = set()
    for article in sorted(grouped, key=int):
        points = [
            item
            for item in grouped[article]
            if item.chunk_type == "POINT" and item.clause and _citation_matches_query_focus(parsed, item)
        ]
        points_by_clause: dict[str, list[Citation]] = {}
        for point in points:
            points_by_clause.setdefault(point.clause or "", []).append(point)

        for clause_no, clause_points in sorted(points_by_clause.items(), key=lambda item: _numeric_key(item[0])):
            clause = next(
                (
                    item
                    for item in grouped[article]
                    if item.chunk_type == "CLAUSE" and item.clause == clause_no
                ),
                None,
            )
            for item in [clause, *clause_points]:
                if item and item.chunk_id not in seen:
                    selected.append(item)
                    seen.add(item.chunk_id)

    return selected or citations


def _bicycle_helmet_scope_citations(citations: list[Citation]) -> list[Citation]:
    selected: list[Citation] = []
    seen: set[str] = set()
    for citation in citations:
        text = strip_accents(normalize_text(f"{citation.article_title or ''}\n{citation.text[:1200]}"))
        if "mu bao hiem" not in text:
            continue
        if not any(term in text for term in ["xe dap may", "mo to", "xe gan may", "xe may"]):
            continue
        if citation.chunk_id in seen:
            continue
        selected.append(citation)
        seen.add(citation.chunk_id)
    return selected or citations


def _citation_matches_query_focus(parsed: ParsedQuery, citation: Citation) -> bool:
    query = strip_accents(normalize_text(parsed.query))
    text = strip_accents(normalize_text(citation.text))

    behavior_groups = [
        (["quay dau", "quay dau xe"], ["quay dau"]),
        (["lui xe"], ["lui xe"]),
        (["dien thoai", "thiet bi dien tu"], ["dien thoai", "thiet bi dien tu"]),
        (["mu bao hiem", "khong doi mu"], ["mu bao hiem"]),
        (["den do", "den tin hieu"], ["den tin hieu"]),
    ]
    condition_groups = [
        (["trong ham", "duong ham", "ham duong bo"], ["trong ham", "duong ham", "ham duong bo"]),
        (["cao toc", "duong cao toc"], ["cao toc", "duong cao toc"]),
        (["via he", "le duong", "long duong"], ["via he", "le duong", "long duong"]),
        (["duong sat", "giao nhau voi duong sat"], ["duong sat", "giao nhau voi duong sat"]),
    ]

    behavior_terms = [
        term
        for triggers, expansions in behavior_groups
        if any(trigger in query for trigger in triggers)
        for term in expansions
    ]
    condition_terms = [
        term
        for triggers, expansions in condition_groups
        if any(trigger in query for trigger in triggers)
        for term in expansions
    ]

    if behavior_terms and not any(term in text for term in behavior_terms):
        return False
    if condition_terms and not any(term in text for term in condition_terms):
        return False
    return bool(behavior_terms or condition_terms)


def _format_vnd(value: int) -> str:
    return f"{value:,}".replace(",", ".") + " đồng"


def _parse_vnd_amount(value: str) -> int:
    return int(value.replace(".", ""))


def _a1_driving_test_fee_evidence(citations: list[Citation]) -> tuple[int, int, Citation] | None:
    for citation in citations:
        normalized = strip_accents(normalize_text(citation.text))
        if citation.document_number != "154/2025/TT-BTC":
            continue
        if not all(term in normalized for term in ["a1", "sat hach ly thuyet", "sat hach thuc hanh"]):
            continue

        block = citation.text
        start = re.search(r"Đối với thi sát hạch lái xe các hạng xe A1", block, flags=re.IGNORECASE)
        if start:
            block = block[start.start() :]
        end = re.search(r"\*\*b\)|Đối với thi sát hạch lái xe ô tô", block, flags=re.IGNORECASE)
        if end:
            block = block[: end.start()]

        theory = re.search(r"Sát hạch lý thuyết:\s*\*\*(\d{1,3}(?:\.\d{3})*)\s*đồng/lần\*\*", block)
        practice = re.search(r"Sát hạch thực hành:\s*\*\*(\d{1,3}(?:\.\d{3})*)\s*đồng/lần\*\*", block)
        if theory and practice:
            return _parse_vnd_amount(theory.group(1)), _parse_vnd_amount(practice.group(1)), citation
    return None


def _build_fee_lookup_answer(parsed: ParsedQuery, citations: list[Citation]) -> str | None:
    query = strip_accents(normalize_text(parsed.query))
    if parsed.intent != "FEE_LOOKUP":
        return None
    if "sat hach" not in query or "a1" not in query:
        return None
    if not any(term in query for term in ["tong", "bao nhieu", "muc"]):
        return None

    evidence = _a1_driving_test_fee_evidence(citations)
    if not evidence:
        return None

    theory_fee, practice_fee, citation = evidence
    total = theory_fee + practice_fee
    date_line = parsed.legal_effective_date or parsed.event_date or parsed.as_of_date or "hiện tại"
    return (
        "### Trả lời\n"
        f"Thi sát hạch lái xe hạng A1 gồm phí sát hạch lý thuyết {_format_vnd(theory_fee)}/lần "
        f"và phí sát hạch thực hành {_format_vnd(practice_fee)}/lần. Nếu phải nộp cả hai phần, "
        f"tổng phí là {_format_vnd(total)}.\n\n"
        "### Căn cứ pháp lý\n"
        f"1. {citation.document_number or citation.document_title}: {_legal_ref(citation)}\n\n"
        "### Thời điểm áp dụng\n"
        f"Đang xét theo ngày {date_line}.\n\n"
        "### Lưu ý\n"
        "- Trong Thông tư 154/2025/TT-BTC, khoản này được gọi là phí sát hạch lái xe, không phải lệ phí cấp giấy phép lái xe.\n"
        "- Người dự sát hạch phần nào thì nộp phí phần đó."
    )


def build_answer(parsed: ParsedQuery, results: list[tuple[Chunk, float]]) -> ChatResponse:
    if not results:
        return ChatResponse(
            answer=(
                "Tôi chưa đủ căn cứ trong bộ dữ liệu hiện tại để trả lời chính xác. "
                "Bạn có thể nêu rõ văn bản, điều khoản, loại phương tiện hoặc ngày xảy ra hành vi."
            ),
            citations=[],
            warnings=["Không tìm thấy nguồn phù hợp trong index."],
            answerable=False,
        )

    citations = [_citation_from_result(chunk, score) for chunk, score in results]
    notes = legal_notes(parsed, results)
    warnings = []
    llm_configured = RAG_LLM_PROVIDER == "openai" and bool(OPENAI_API_KEY)

    exact_answer = _build_exact_reference_answer(parsed, citations)
    if exact_answer and not llm_configured:
        return ChatResponse(
            answer=_normalize_answer_style(exact_answer, citations),
            citations=citations,
            warnings=warnings,
            answerable=True,
            debug={"parsed_query": parsed.model_dump(), "legal_notes": notes, "exact_reference_lookup": True},
        )

    if parsed.intent == "PENALTY_LOOKUP" and not parsed.vehicle_code and _has_vehicle_scope_note(notes) and not llm_configured:
        scoped_citations = _vehicle_scope_citations(parsed, citations)
        return ChatResponse(
            answer=_normalize_answer_style(_build_vehicle_scope_answer(parsed, scoped_citations, notes), scoped_citations),
            citations=scoped_citations,
            warnings=notes,
            answerable=True,
            debug={"parsed_query": parsed.model_dump(), "legal_notes": notes, "vehicle_scope_split": True},
        )

    if _has_bicycle_helmet_scope_note(notes):
        scoped_citations = _bicycle_helmet_scope_citations(citations)
        return ChatResponse(
            answer=_normalize_answer_style(_build_bicycle_helmet_scope_answer(parsed, scoped_citations, notes), scoped_citations),
            citations=scoped_citations,
            warnings=notes,
            answerable=True,
            debug={"parsed_query": parsed.model_dump(), "legal_notes": notes, "vehicle_scope_mismatch": True},
        )

    gate_passed, gate_notes = _evidence_gate(parsed, results)
    if not gate_passed:
        all_notes = [*notes, *gate_notes]
        return ChatResponse(
            answer=_normalize_answer_style(_build_insufficient_evidence_answer(parsed, citations, all_notes), citations),
            citations=citations,
            warnings=all_notes,
            answerable=False,
            debug={"parsed_query": parsed.model_dump(), "legal_notes": all_notes},
        )

    missing_amount = any("không đủ căn cứ để kết luận con số cụ thể" in note for note in notes)
    if missing_amount:
        return ChatResponse(
            answer=_normalize_answer_style(_build_missing_amount_answer(parsed, citations, notes), citations),
            citations=citations,
            warnings=notes,
            answerable=False,
            debug={"parsed_query": parsed.model_dump(), "legal_notes": notes},
        )

    fee_answer = _build_fee_lookup_answer(parsed, citations)
    if fee_answer:
        return ChatResponse(
            answer=_normalize_answer_style(fee_answer, citations),
            citations=citations,
            warnings=warnings,
            answerable=True,
            debug={"parsed_query": parsed.model_dump(), "legal_notes": notes, "fee_lookup": {"resolved": True}},
        )

    capacity_age_answer = _build_capacity_age_answer(parsed, citations)
    if capacity_age_answer:
        return ChatResponse(
            answer=_normalize_answer_style(capacity_age_answer[0], capacity_age_answer[1]),
            citations=capacity_age_answer[1],
            warnings=notes,
            answerable=True,
            debug={"parsed_query": parsed.model_dump(), "legal_notes": notes, "capacity_age_reasoning": True},
        )

    if RAG_LLM_PROVIDER == "openai" and OPENAI_API_KEY:
        try:
            llm_limit = 30 if parsed.retrieval_mode == "EXHAUSTIVE" or parsed.answer_mode == "ENUMERATION" else 6
            answer = generate_with_openai(parsed, results[:llm_limit], notes)
        except Exception as exc:
            if RAG_REQUIRE_LLM:
                error = f"OpenAI generation failed and RAG_REQUIRE_LLM=true: {exc}"
                return ChatResponse(
                    answer=_normalize_answer_style(_build_llm_required_error_answer(parsed, citations, error), citations),
                    citations=citations,
                    warnings=[*notes, error],
                    answerable=False,
                    debug={"parsed_query": parsed.model_dump(), "legal_notes": notes, "llm_error": str(exc)},
            )
            warnings.append(f"OpenAI generation failed, used extractive fallback: {exc}")
            answer = exact_answer or _build_extractive_answer(parsed, results, citations, notes)
    else:
        if RAG_LLM_PROVIDER == "openai":
            warning = "OPENAI_API_KEY is empty, used extractive fallback."
            if RAG_REQUIRE_LLM:
                return ChatResponse(
                    answer=_normalize_answer_style(
                        _build_llm_required_error_answer(parsed, citations, "OPENAI_API_KEY is not configured."),
                        citations,
                    ),
                    citations=citations,
                    warnings=[*notes, "OPENAI_API_KEY is not configured."],
                    answerable=False,
                    debug={
                        "parsed_query": parsed.model_dump(),
                        "legal_notes": notes,
                        "llm_error": "OPENAI_API_KEY is not configured.",
                    },
                )
            warnings.append(warning)
        answer = exact_answer or _build_extractive_answer(parsed, results, citations, notes)

    return ChatResponse(
        answer=_normalize_answer_style(_normalize_document_names(answer, citations), citations),
        citations=citations,
        warnings=warnings,
        answerable=True,
        debug={"parsed_query": parsed.model_dump(), "legal_notes": notes, "exact_reference_lookup": bool(exact_answer)},
    )


def _build_capacity_age_answer(parsed: ParsedQuery, citations: list[Citation]) -> tuple[str, list[Citation]] | None:
    if parsed.intent != "DRIVER_AGE_REQUIREMENT":
        return None

    age = _age_from_query(parsed.query)
    capacity = _engine_capacity_from_query(parsed.query)
    if age is None or capacity is None:
        return None

    license_evidence = _motorcycle_license_class_for_capacity(capacity, citations)
    age_evidence = _license_age_evidence(citations)
    if not license_evidence or not age_evidence:
        return None

    license_class, license_citation = license_evidence
    minimum_age, age_citation = age_evidence
    selected = _dedupe_citations([license_citation, age_citation])
    refs = "\n".join(
        f"{index + 1}. {citation.document_number or citation.document_title}: {_legal_ref(citation)}"
        for index, citation in enumerate(selected)
    )

    allowed = age >= minimum_age
    conclusion = "được phép" if allowed else "chưa được phép"
    reason = (
        f"Xe mô tô hai bánh {capacity:g} cm3 thuộc phạm vi GPLX hạng {license_class}; "
        f"nguồn về độ tuổi yêu cầu người đủ {minimum_age} tuổi trở lên mới được cấp GPLX hạng {license_class}."
    )
    return (
        "### Trả lời\n"
        f"Người {age:g} tuổi **{conclusion}** lái xe máy {capacity:g} cm3.\n\n"
        f"{reason} [{_short_ref(license_citation)}; {_short_ref(age_citation)}]\n\n"
        "### Căn cứ pháp lý\n"
        f"{refs}",
        selected,
    )


def _age_from_query(query: str) -> float | None:
    q = strip_accents(normalize_text(query))
    match = re.search(r"\b(\d+(?:[,.]\d+)?)\s*tuoi\b", q)
    return float(match.group(1).replace(",", ".")) if match else None


def _engine_capacity_from_query(query: str) -> float | None:
    q = strip_accents(normalize_text(query)).replace("cm³", "cm3")
    match = re.search(r"\b(\d+(?:[,.]\d+)?)\s*(?:cm3|cc)\b", q)
    return float(match.group(1).replace(",", ".")) if match else None


def _motorcycle_license_class_for_capacity(capacity: float, citations: list[Citation]) -> tuple[str, Citation] | None:
    candidates: list[tuple[str, Citation]] = []
    for citation in citations:
        if citation.document_number != "36/2024/QH15" or citation.article != "57":
            continue
        text = strip_accents(normalize_text(citation.text))
        if "hang a1" in text and _covers_upper_bound_capacity(text, capacity):
            candidates.append(("A1", citation))
        if re.search(r"\bhang a\b", text) and _covers_lower_bound_capacity(text, capacity):
            candidates.append(("A", citation))
    return candidates[0] if candidates else None


def _covers_upper_bound_capacity(text: str, capacity: float) -> bool:
    match = re.search(r"(?:den|khong qua)\s+(\d+(?:[,.]\d+)?)\s*cm3", text)
    return bool(match and capacity <= float(match.group(1).replace(",", ".")))


def _covers_lower_bound_capacity(text: str, capacity: float) -> bool:
    match = re.search(r"tren\s+(\d+(?:[,.]\d+)?)\s*cm3", text)
    return bool(match and capacity > float(match.group(1).replace(",", ".")))


def _license_age_evidence(citations: list[Citation]) -> tuple[int, Citation] | None:
    for citation in citations:
        if citation.document_number != "36/2024/QH15" or citation.article != "59":
            continue
        text = strip_accents(normalize_text(citation.text))
        match = re.search(r"nguoi du\s+(\d+)\s+tuoi tro len duoc cap giay phep lai xe hang a1,\s*a", text)
        if match:
            return int(match.group(1)), citation
    return None


def _dedupe_citations(citations: list[Citation]) -> list[Citation]:
    selected: list[Citation] = []
    seen: set[str] = set()
    for citation in citations:
        if citation.chunk_id in seen:
            continue
        selected.append(citation)
        seen.add(citation.chunk_id)
    return selected


def _normalize_document_names(answer: str, citations: list[Citation]) -> str:
    replacements: dict[str, str] = {}
    for citation in citations:
        number = citation.document_number
        title = citation.document_title or ""
        if not number:
            continue
        if "Luật Trật tự, an toàn giao thông đường bộ" in title:
            correct = f"Luật số {number}"
            replacements[number] = correct
            answer = re.sub(rf"\b(?:Nghị\s+quyết|Nghị\s+định|Thông\s+tư)\s+(?:số\s+)?{re.escape(number)}", correct, answer, flags=re.IGNORECASE)
            answer = re.sub(rf"\bLuật\s+Giao\s+thông\s+đường\s+bộ\s+(?:số\s+)?{re.escape(number)}", correct, answer, flags=re.IGNORECASE)
            answer = re.sub(r"\bLuật\s+Giao\s+thông\s+đường\s+bộ\b", "Luật Trật tự, an toàn giao thông đường bộ", answer, flags=re.IGNORECASE)
        elif title.startswith("Luật Đường bộ"):
            correct = f"Luật số {number}"
            replacements[number] = correct
            answer = re.sub(rf"\b(?:Nghị\s+quyết|Nghị\s+định|Thông\s+tư)\s+(?:số\s+)?{re.escape(number)}", correct, answer, flags=re.IGNORECASE)
        elif title.startswith("Nghị định") or "/NĐ-CP" in number:
            correct = f"Nghị định {number}"
            replacements[number] = correct
            answer = re.sub(rf"\b(?:Nghị\s+quyết|Luật|Thông\s+tư)\s+(?:số\s+)?{re.escape(number)}", correct, answer, flags=re.IGNORECASE)
    return answer


def _build_missing_amount_answer(
    parsed: ParsedQuery,
    citations: list[Citation],
    notes: list[str],
) -> str:
    refs = "\n".join(
        f"{index + 1}. {citation.document_number or citation.document_title}: {_legal_ref(citation)}"
        for index, citation in enumerate(citations[:5])
    )
    note_text = "\n".join(f"- {note}" for note in notes)
    return (
        "### Trả lời\n"
        "Tôi chưa đủ căn cứ trong bộ dữ liệu hiện tại để xác định mức tiền cụ thể cho câu hỏi này.\n\n"
        "### Căn cứ pháp lý\n"
        f"{refs}\n\n"
        "### Thời điểm áp dụng\n"
        f"Truy vấn đang xét theo ngày {parsed.legal_effective_date or parsed.event_date or parsed.as_of_date or 'hiện tại'}.\n\n"
        "### Lưu ý\n"
        f"{note_text}"
    )


def _build_llm_required_error_answer(
    parsed: ParsedQuery,
    citations: list[Citation],
    error: str,
) -> str:
    refs = "\n".join(
        f"{index + 1}. {citation.document_number or citation.document_title}: {_legal_ref(citation)}"
        for index, citation in enumerate(citations[:5])
    )
    return (
        "### Trả lời\n"
        "Hệ thống đang được cấu hình bắt buộc sinh câu trả lời bằng LLM, nhưng bước gọi LLM chưa thực hiện được. "
        "Tôi không trả fallback trích xuất để tránh tạo cảm giác đây là câu trả lời đã được diễn đạt hoàn chỉnh.\n\n"
        "### Căn cứ pháp lý đã truy xuất\n"
        f"{refs or 'Không có nguồn đủ mạnh.'}\n\n"
        "### Thời điểm áp dụng\n"
        f"Đang xét theo ngày {parsed.legal_effective_date or parsed.event_date or parsed.as_of_date or 'hiện tại'}.\n\n"
        "### Lưu ý\n"
        f"- Lỗi LLM: {error}"
    )


def _build_insufficient_evidence_answer(
    parsed: ParsedQuery,
    citations: list[Citation],
    notes: list[str],
) -> str:
    refs = "\n".join(
        f"{index + 1}. {citation.document_number or citation.document_title}: {_legal_ref(citation)}"
        for index, citation in enumerate(citations[:5])
    )
    note_text = "\n".join(f"- {note}" for note in notes)
    return (
        "### Trả lời\n"
        "Tôi chưa đủ căn cứ trong bộ dữ liệu hiện tại để trả lời chắc chắn câu hỏi này.\n\n"
        "### Căn cứ pháp lý\n"
        f"{refs or 'Không có nguồn đủ mạnh.'}\n\n"
        "### Thời điểm áp dụng\n"
        f"Đang xét theo ngày hiệu lực pháp lý {parsed.legal_effective_date or 'hiện tại'}.\n\n"
        "### Lưu ý\n"
        f"{note_text}"
    )
