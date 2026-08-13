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


def vehicle_scope_notes(parsed: ParsedQuery, results: list[tuple[Chunk, float]]) -> list[str]:
    if parsed.intent != "PENALTY_LOOKUP" or parsed.vehicle_code:
        return []

    penalty_articles = {
        chunk.article
        for chunk, _score in results[:8]
        if chunk.document_number == "168/2024/NĐ-CP"
        and chunk.article in {"6", "7", "8", "9"}
        and effective_penalty_source(chunk)
    }
    if len(penalty_articles) < 2:
        return []

    labels = {
        "6": "ô tô và xe tương tự ô tô",
        "7": "mô tô, xe gắn máy và xe tương tự",
        "8": "xe máy chuyên dùng",
        "9": "xe thô sơ",
    }
    scopes = ", ".join(labels[article] for article in sorted(penalty_articles, key=int))
    return [
        (
            "Câu hỏi chưa nêu rõ loại phương tiện. Các nguồn truy xuất đang thuộc nhiều phạm vi khác nhau "
            f"({scopes}); không được chọn một mức phạt duy nhất nếu không có nguồn hoặc câu hỏi xác định đúng loại xe."
        )
    ]


def bicycle_helmet_scope_notes(parsed: ParsedQuery, results: list[tuple[Chunk, float]]) -> list[str]:
    query = strip_accents(normalize_text(parsed.query))
    if parsed.vehicle_type != "xe đạp" or not any(term in query for term in ["mu bao hiem", "doi mu"]):
        return []

    top_texts = [
        strip_accents(normalize_text(f"{chunk.article_title or ''}\n{chunk.text[:1200]}"))
        for chunk, _score in results[:8]
    ]
    helmet_texts = [text for text in top_texts if "mu bao hiem" in text]
    if not helmet_texts:
        return []

    machine_or_motor_scope = any(
        any(term in text for term in ["xe dap may", "mo to", "xe gan may", "xe may"])
        for text in helmet_texts
    )
    ordinary_bicycle_scope = any(
        "xe dap" in text
        and "mu bao hiem" in text
        and not any(term in text for term in ["xe dap may", "mo to", "xe gan may", "xe may"])
        for text in helmet_texts
    )
    if machine_or_motor_scope and not ordinary_bicycle_scope:
        return [
            (
                "Câu hỏi nêu xe đạp thông thường. Các nguồn truy xuất về mũ bảo hiểm đang áp dụng cho xe đạp máy, "
                "mô tô hoặc xe gắn máy; không được suy rộng các nguồn này thành nghĩa vụ bắt buộc đội mũ bảo hiểm "
                "đối với xe đạp thông thường."
            )
        ]

    return []


def vehicle_capacity_classification_notes(parsed: ParsedQuery, results: list[tuple[Chunk, float]]) -> list[str]:
    query = strip_accents(normalize_text(parsed.query))
    if parsed.intent != "DRIVER_AGE_REQUIREMENT" or not any(
        term in query for term in ["cm3", "cm³", "xi lanh", "dung tich", "kw", "cong suat"]
    ):
        return []

    top_text = "\n".join(
        strip_accents(normalize_text(f"{chunk.article_title or ''}\n{chunk.text[:1200]}"))
        for chunk, _score in results[:12]
    )
    has_license_classification = (
        "hang a1" in top_text
        and any(term in top_text for term in ["dung tich xi-lanh", "dung tich xi lanh", "125 cm3", "125 cm³"])
    )
    has_age_basis = "nguoi du 18 tuoi tro len duoc cap giay phep lai xe" in top_text
    if has_license_classification and has_age_basis:
        return [
            (
                "Câu hỏi có thông số dung tích/công suất. Phải phân loại phương tiện theo nguồn về hạng giấy phép "
                "lái xe/dung tích trước, rồi mới áp dụng nguồn về độ tuổi; không được đồng nhất xe máy hoặc mô tô "
                "có dung tích nêu trong câu hỏi với xe gắn máy nếu nguồn không thể hiện điều đó."
            )
        ]

    return []


def effective_penalty_source(chunk: Chunk) -> bool:
    text = strip_accents(normalize_text(f"{chunk.article_title or ''}\n{chunk.text[:900]}"))
    return any(term in text for term in ["phat tien", "xu phat", "vi pham", "quay dau", "lui xe"])


def legal_notes(parsed: ParsedQuery, results: list[tuple[Chunk, float]]) -> list[str]:
    return [
        *amendment_notes(parsed, results),
        *missing_amount_notes(parsed, results),
        *vehicle_scope_notes(parsed, results),
        *bicycle_helmet_scope_notes(parsed, results),
        *vehicle_capacity_classification_notes(parsed, results),
    ]
