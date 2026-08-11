from __future__ import annotations

import re
import unicodedata


TOKEN_RE = re.compile(r"[a-zA-Z0-9À-ỹĐđ]+(?:[/:.-][a-zA-Z0-9À-ỹĐđ]+)*")


SYNONYMS = {
    "bang lai": "giay phep lai xe gplx",
    "bằng lái": "giấy phép lái xe gplx",
    "xe hoi": "o to ô tô",
    "xe hơi": "ô tô",
    "den do": "không chấp hành hiệu lệnh của đèn tín hiệu giao thông vượt đèn đỏ",
    "đèn đỏ": "không chấp hành hiệu lệnh của đèn tín hiệu giao thông vượt đèn đỏ",
    "vuot den do": "không chấp hành hiệu lệnh của đèn tín hiệu giao thông vượt đèn đỏ",
    "vượt đèn đỏ": "không chấp hành hiệu lệnh của đèn tín hiệu giao thông vượt đèn đỏ",
    "xe may": "xe máy mô tô gắn máy",
    "xe máy": "xe máy mô tô gắn máy",
}


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = strip_accents(normalize_text(value))
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    return re.sub(r"\s+", " ", text).strip()


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return stripped.replace("đ", "d").replace("Đ", "D")


def tokenize(text: str) -> list[str]:
    normalized = normalize_text(text)
    no_accents = strip_accents(normalized)
    tokens = TOKEN_RE.findall(normalized)
    tokens.extend(TOKEN_RE.findall(no_accents))
    return _dedupe(tokens)


def expand_query(query: str) -> str:
    normalized = normalize_text(query)
    expanded = [query]
    no_accents = strip_accents(normalized)
    for key, value in SYNONYMS.items():
        if key in normalized or strip_accents(key) in no_accents:
            expanded.append(value)
    return " ".join(_dedupe(expanded))
