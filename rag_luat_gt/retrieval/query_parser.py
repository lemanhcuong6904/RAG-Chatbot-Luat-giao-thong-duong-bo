from __future__ import annotations

import re
from datetime import date

from rag_luat_gt.schemas import ChatRequest, ParsedQuery
from rag_luat_gt.text import expand_query, normalize_text, strip_accents


DOCUMENT_RE = re.compile(
    r"(\d{1,3})\s*/\s*(\d{4})\s*/\s*([A-Za-zÀ-ỹĐđ-]+)", re.IGNORECASE
)
ARTICLE_RE = re.compile(r"(?:điều|dieu)\s+(\d+[a-z]?)", re.IGNORECASE)
CLAUSE_RE = re.compile(r"(?:khoản|khoan)\s+(\d+)", re.IGNORECASE)
POINT_RE = re.compile(r"(?:điểm|diem)\s+([a-zđ])", re.IGNORECASE)
DMY_DATE_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b")
YMD_DATE_RE = re.compile(r"\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b")


def _detect_intent(query: str) -> str:
    q = normalize_text(query)
    q_ascii = strip_accents(q)
    if any(term in q for term in ["phạt", "xử phạt", "mức phạt", "trừ điểm"]) or any(
        term in q_ascii for term in ["phat", "xu phat", "muc phat", "tru diem"]
    ):
        return "PENALTY_LOOKUP"
    if any(term in q for term in ["giấy phép lái xe", "gplx", "bằng lái", "sát hạch"]) or any(
        term in q_ascii for term in ["giay phep lai xe", "bang lai", "sat hach"]
    ):
        return "DRIVER_LICENSE"
    if any(term in q for term in ["đăng ký xe", "biển số"]) or any(
        term in q_ascii for term in ["dang ky xe", "bien so"]
    ):
        return "REGISTRATION"
    if any(term in q for term in ["tốc độ", "khoảng cách"]) or any(
        term in q_ascii for term in ["toc do", "khoang cach"]
    ):
        return "SPEED_RULE"
    if any(term in q for term in ["phí", "lệ phí"]) or any(
        term in q_ascii for term in ["phi", "le phi"]
    ):
        return "FEE_LOOKUP"
    if any(term in q for term in ["sửa đổi", "bổ sung", "thay thế", "bãi bỏ"]) or any(
        term in q_ascii for term in ["sua doi", "bo sung", "thay the", "bai bo"]
    ):
        return "AMENDMENT_COMPARE"
    if ARTICLE_RE.search(q) or ARTICLE_RE.search(q_ascii):
        return "ARTICLE_LOOKUP"
    return "GENERAL_LEGAL_QA"


def _detect_vehicle(query: str) -> str | None:
    q = normalize_text(query)
    q_ascii = strip_accents(q)
    if "xe máy chuyên dùng" in q or "xe may chuyen dung" in q_ascii:
        return "xe máy chuyên dùng"
    if any(term in q for term in ["ô tô", "xe hơi", "xe con", "xe tải", "xe khách"]) or any(
        term in q_ascii for term in ["o to", "xe hoi", "xe con", "xe tai", "xe khach"]
    ):
        return "ô tô"
    if any(term in q for term in ["xe máy", "mô tô", "gắn máy"]) or any(
        term in q_ascii for term in ["xe may", "mo to", "gan may"]
    ):
        return "xe máy"
    return None


def _document_number(query: str) -> str | None:
    match = DOCUMENT_RE.search(query)
    if not match:
        return None
    return f"{match.group(1)}/{match.group(2)}/{match.group(3).upper()}"


def _explicit_date(query: str) -> date | None:
    dmy = DMY_DATE_RE.search(query)
    if dmy:
        day, month, year = map(int, dmy.groups())
        return date(year, month, day)
    ymd = YMD_DATE_RE.search(query)
    if ymd:
        year, month, day = map(int, ymd.groups())
        return date(year, month, day)
    return None


def parse_query(request: ChatRequest) -> ParsedQuery:
    query = request.query.strip()
    article = ARTICLE_RE.search(query) or ARTICLE_RE.search(strip_accents(query))
    clause = CLAUSE_RE.search(query) or CLAUSE_RE.search(strip_accents(query))
    point = POINT_RE.search(query) or POINT_RE.search(strip_accents(query))
    effective_date = _explicit_date(query) or request.event_date or request.as_of_date or date.today()
    return ParsedQuery(
        query=query,
        normalized_query=expand_query(query),
        intent=_detect_intent(query),
        document_number=_document_number(query),
        article=article.group(1) if article else None,
        clause=clause.group(1) if clause else None,
        point=point.group(1).lower() if point else None,
        vehicle_type=_detect_vehicle(query),
        event_date=effective_date.isoformat(),
        as_of_date=request.as_of_date.isoformat() if request.as_of_date else None,
        keywords=[],
    )
