from __future__ import annotations

import re
import unicodedata


TOKEN_RE = re.compile(r"[a-zA-Z0-9À-ỹĐđ]+(?:[/:.-][a-zA-Z0-9À-ỹĐđ]+)*")


LEGAL_SYNONYMS = {
    "bang lai": ["giay phep lai xe", "gplx"],
    "bằng lái": ["giấy phép lái xe", "gplx"],
    "khong bang lai": ["khong co giay phep lai xe", "khong co gplx"],
    "khong co bang lai": ["khong co giay phep lai xe", "khong co gplx"],
    "xe hoi": ["o to", "ô tô"],
    "xe hơi": ["ô tô"],
    "den do": ["không chấp hành hiệu lệnh của đèn tín hiệu giao thông", "vượt đèn đỏ"],
    "đèn đỏ": ["không chấp hành hiệu lệnh của đèn tín hiệu giao thông", "vượt đèn đỏ"],
    "vuot den do": ["khong chap hanh hieu lenh cua den tin hieu giao thong", "vuot den do"],
    "vượt đèn đỏ": ["không chấp hành hiệu lệnh của đèn tín hiệu giao thông", "vượt đèn đỏ"],
    "khong doi mu": ["khong doi mu bao hiem", "khong doi mu bao hiem cho nguoi di mo to xe may"],
    "khong doi mu bao hiem": ["khong doi mu bao hiem cho nguoi di mo to xe may"],
    "nồng độ cồn": ["điều khiển phương tiện trong máu hoặc hơi thở có nồng độ cồn"],
    "nong do con": ["dieu khien phuong tien trong mau hoac hoi tho co nong do con"],
    "xe may": ["xe máy", "mô tô", "gắn máy"],
    "xe máy": ["xe máy", "mô tô", "gắn máy"],
}

SYNONYMS = {key: " ".join(values) for key, values in LEGAL_SYNONYMS.items()}


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
