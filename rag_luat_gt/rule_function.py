from __future__ import annotations

from rag_luat_gt.text import normalize_text, strip_accents


def classify_rule_function(text: str, title: str | None = None) -> str:
    normalized = strip_accents(normalize_text(f"{title or ''}\n{text}"))

    if any(
        term in normalized
        for term in [
            "phat tien",
            "tru diem",
            "tuoc quyen",
            "xu phat",
            "vi pham hanh chinh",
            "bi phat",
        ]
    ):
        return "SANCTION"

    if any(term in normalized for term in ["nghiem cam", "khong duoc"]):
        return "PROHIBITION"

    if any(
        term in normalized
        for term in [
            "duoc cap giay phep lai xe",
            "duoc cap chung chi",
            "du dieu kien",
            "du tuoi",
            "tuoi, suc khoe",
            "tuoi suc khoe",
            "duoc dieu khien",
            "duoc phep",
        ]
    ):
        return "ELIGIBILITY"

    if any(term in normalized for term in ["thu tuc", "ho so", "trinh tu", "cap lai", "doi giay phep"]):
        return "PROCEDURE"

    if any(term in normalized for term in ["la gi", "duoc hieu la", "giai thich tu ngu"]):
        return "DEFINITION"

    return "GENERAL"


def effective_rule_function(chunk_rule_function: str | None, text: str, title: str | None = None) -> str:
    if chunk_rule_function and chunk_rule_function != "UNKNOWN":
        return chunk_rule_function
    return classify_rule_function(text, title)
