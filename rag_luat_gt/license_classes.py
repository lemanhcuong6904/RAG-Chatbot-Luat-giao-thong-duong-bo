from __future__ import annotations

import re

from rag_luat_gt.text import normalize_text, strip_accents


LICENSE_CLASS_ORDER = [
    "A1",
    "A",
    "B1",
    "B",
    "C1",
    "C",
    "D1",
    "D2",
    "D",
    "BE",
    "C1E",
    "CE",
    "D1E",
    "D2E",
    "DE",
]

_CLASS_PATTERN = re.compile(
    r"(?<![A-Z0-9])(?:C1E|D1E|D2E|A1|B1|C1|BE|CE|DE|D1|D2|A|B|C|D)(?![A-Z0-9])",
    flags=re.IGNORECASE,
)


def extract_license_classes(query: str) -> list[str]:
    ascii_query = strip_accents(query)
    if not re.search(r"\b(?:bang|hang|gplx|giay\s+phep\s+lai\s+xe)\b", ascii_query, flags=re.IGNORECASE):
        return []

    seen: set[str] = set()
    result: list[str] = []
    for match in _CLASS_PATTERN.finditer(ascii_query):
        value = match.group(0).upper()
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def citation_mentions_license_class(text: str, license_class: str) -> bool:
    normalized = strip_accents(normalize_text(text))
    value = re.escape(license_class.lower())
    return re.search(rf"\bhang\s+{value}\b", normalized) is not None


def citation_defines_license_class(text: str, license_class: str) -> bool:
    normalized = strip_accents(normalize_text(text))
    value = re.escape(license_class.lower())
    return re.search(rf"^\s*(?:[a-zd]\)\s*)?hang\s+{value}\b", normalized) is not None


def citation_license_class_hits(text: str, license_classes: list[str]) -> list[str]:
    return [item for item in license_classes if citation_mentions_license_class(text, item)]


def citation_defined_license_class_hits(text: str, license_classes: list[str]) -> list[str]:
    return [item for item in license_classes if citation_defines_license_class(text, item)]


def citation_mentions_any_license_class(text: str) -> bool:
    normalized = strip_accents(normalize_text(text))
    return re.search(r"\bhang\s+(?:a1|a|b1|b|c1|c|d1|d2|d|be|c1e|ce|d1e|d2e|de)\b", normalized) is not None
