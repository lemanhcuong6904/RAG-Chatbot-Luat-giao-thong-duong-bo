from __future__ import annotations

import re
from typing import Protocol


class LegalReference(Protocol):
    document_number: str | None
    document_title: str | None
    article: str | None
    clause: str | None
    point: str | None


def short_ref(ref: LegalReference) -> str:
    parts = [_document_label(ref)]
    article = getattr(ref, "article", None)
    clause = getattr(ref, "clause", None)
    point = getattr(ref, "point", None)
    if article:
        parts.append(f"Điều {article}")
    if clause:
        parts.append(f"khoản {clause}")
    if point:
        parts.append(f"điểm {point}")
    return ", ".join(parts)


def inline_ref(ref: LegalReference) -> str:
    return f"[{short_ref(ref)}]"


def replace_source_markers(answer: str, refs: list[LegalReference]) -> str:
    def replace(match: re.Match[str]) -> str:
        index = int(match.group(1)) - 1
        if index < 0 or index >= len(refs):
            return match.group(0)
        return inline_ref(refs[index])

    return re.sub(r"\[SOURCE\s+(\d+)\]", replace, answer, flags=re.IGNORECASE)


def normalize_inline_legal_refs(answer: str, refs: list[LegalReference]) -> str:
    for ref in refs:
        number = getattr(ref, "document_number", None)
        if not number:
            continue
        label = _document_label(ref)
        answer = re.sub(
            rf"\[(?!Luật\s|Nghị định\s|Thông tư\s){re.escape(number)}\s*[:：]\s*",
            f"[{label}, ",
            answer,
            flags=re.IGNORECASE,
        )
        answer = re.sub(
            rf"\[(?!Luật\s|Nghị định\s|Thông tư\s){re.escape(number)}\s*,\s*",
            f"[{label}, ",
            answer,
            flags=re.IGNORECASE,
        )
        answer = re.sub(
            rf"\[(?!Luật\s|Nghị định\s|Thông tư\s){re.escape(number)}\]",
            f"[{label}]",
            answer,
            flags=re.IGNORECASE,
        )
    return answer


def ensure_claim_citations(answer: str, refs: list[LegalReference]) -> str:
    if not refs:
        return answer
    default_ref = inline_ref(refs[0])
    lines = answer.splitlines()
    return "\n".join(_ensure_line_citation(line, default_ref) for line in lines).strip()


def _ensure_line_citation(line: str, default_ref: str) -> str:
    stripped = line.strip()
    if not stripped:
        return line
    if _has_inline_legal_ref(stripped):
        return line
    if not _looks_like_claim_line(stripped):
        return line

    suffix = ""
    if stripped[-1] in ".;:":
        suffix = stripped[-1]
        stripped = stripped[:-1].rstrip()
    return line[: len(line) - len(line.lstrip())] + f"{stripped} {default_ref}{suffix if suffix != ':' else '.'}"


def _has_inline_legal_ref(text: str) -> bool:
    return bool(
        re.search(
            r"\[(?:Luật|Nghị định|Thông tư)\s+[^]]+(?:,\s*Điều\s+[^]]+)?\]",
            text,
            flags=re.IGNORECASE,
        )
    )


def _looks_like_claim_line(text: str) -> bool:
    plain = re.sub(r"^[-*]\s+|^\d+[.)]\s+", "", text).strip()
    if len(plain) < 25:
        return False
    if plain.startswith("|") or set(plain) <= {"-", "|", " "}:
        return False
    if re.match(r"^#{1,6}\s+", plain):
        return False
    low = plain.casefold()
    non_claim_prefixes = (
        "từng hành vi",
        "tổng hợp chế tài",
        "lý do",
        "đang xét theo ngày",
        "không có sanction rule",
    )
    if any(low.startswith(prefix) for prefix in non_claim_prefixes):
        return False
    return any(
        marker in low
        for marker in [
            "phải",
            "không",
            "được",
            "bị",
            "mức",
            "phạt",
            "trừ",
            "bao gồm",
            "gồm",
            "hiệu lực",
            "quy định",
            "điều khiển",
            "tham gia giao thông",
            "giấy phép",
            "tốc độ",
            "khoảng cách",
            "cơ sở dữ liệu",
        ]
    )


def _document_label(ref: LegalReference) -> str:
    number = getattr(ref, "document_number", None)
    title = getattr(ref, "document_title", None) or ""
    if not number:
        return title or "Nguồn"

    title_lower = title.casefold()
    number_upper = number.upper()
    if title_lower.startswith("luật") or "/QH" in number_upper:
        return f"Luật {number}"
    if title_lower.startswith("nghị định") or "/NĐ-CP" in number_upper or "/ND-CP" in number_upper:
        return f"Nghị định {number}"
    if title_lower.startswith("thông tư") or "/TT-" in number_upper:
        return f"Thông tư {number}"
    return number
