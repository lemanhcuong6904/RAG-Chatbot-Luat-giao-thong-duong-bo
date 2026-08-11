from __future__ import annotations

from datetime import date
import re

from rag_luat_gt.schemas import Chunk, ParsedQuery
from rag_luat_gt.text import normalize_text, strip_accents


ND_238_EFFECTIVE_FROM = date(2026, 8, 15)
MONEY_RE = re.compile(r"\b\d{1,3}(?:\.\d{3})+\s*(?:đồng|dong)\b", re.IGNORECASE)


def _date_or_none(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def amendment_notes(parsed: ParsedQuery, results: list[tuple[Chunk, float]]) -> list[str]:
    event_date = _date_or_none(parsed.legal_effective_date or parsed.event_date)
    if not event_date or event_date < ND_238_EFFECTIVE_FROM:
        return []

    question = strip_accents(normalize_text(parsed.query))
    has_auto_red_light = (
        parsed.vehicle_type == "ô tô"
        and any(term in question for term in ["den do", "den tin hieu", "vuot den do"])
    )
    has_168_article_6_clause_9 = any(
        chunk.document_number == "168/2024/NĐ-CP"
        and chunk.article == "6"
        and chunk.clause == "9"
        for chunk, _score in results
    )

    if has_auto_red_light and has_168_article_6_clause_9:
        return [
            (
                f"Tại ngày {event_date.isoformat()}, Nghị định 238/2026/NĐ-CP "
                "đã có hiệu lực và có sửa đổi, bổ sung một số nội dung của Nghị định 168/2024/NĐ-CP. "
                "Trong corpus hiện tại, Nghị định 238/2026/NĐ-CP không thể hiện việc sửa trực tiếp "
                "Điều 6 Khoản 9 Điểm b về hành vi ô tô không chấp hành hiệu lệnh của đèn tín hiệu giao thông; "
                "vì vậy căn cứ chính cho hành vi này vẫn là Nghị định 168/2024/NĐ-CP, Điều 6 Khoản 9 Điểm b."
            )
        ]

    return []


def missing_amount_notes(parsed: ParsedQuery, results: list[tuple[Chunk, float]]) -> list[str]:
    question = strip_accents(normalize_text(parsed.query))
    asks_amount = any(
        term in question
        for term in [
            "muc thu",
            "muc phi",
            "le phi",
            "phi sat hach",
            "bao nhieu tien",
            "dong",
        ]
    )
    if not asks_amount:
        return []

    combined_text = "\n".join(chunk.text for chunk, _score in results[:8])
    combined_ascii = strip_accents(normalize_text(combined_text))
    has_money_amount = bool(MONEY_RE.search(combined_text) or MONEY_RE.search(combined_ascii))
    refers_external_table = any(
        term in combined_ascii
        for term in [
            "bieu muc thu",
            "ban hanh kem theo thong tu",
            "quy dinh tai bieu",
        ]
    )

    if refers_external_table and not has_money_amount:
        return [
            (
                "Nguồn truy xuất chỉ viện dẫn Biểu mức thu phí, lệ phí ban hành kèm theo văn bản, "
                "nhưng corpus hiện tại chưa có biểu/bảng mức thu tương ứng. Vì vậy hệ thống không đủ "
                "căn cứ để kết luận con số cụ thể."
            )
        ]

    return []


def legal_notes(parsed: ParsedQuery, results: list[tuple[Chunk, float]]) -> list[str]:
    return [
        *amendment_notes(parsed, results),
        *missing_amount_notes(parsed, results),
    ]
