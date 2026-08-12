from __future__ import annotations

import re
from datetime import date

from rag_luat_gt.schemas import ChatRequest, ParsedQuery, ViolationFact
from rag_luat_gt.sanction.behavior_catalog import behavior_code_from_query, behavior_contains_from_query, match_behaviors
from rag_luat_gt.text import expand_query, normalize_text, strip_accents


DOCUMENT_RE = re.compile(
    r"(\d{1,3})\s*/\s*(\d{4})\s*/\s*([A-Za-zÀ-ỹĐđ-]+)", re.IGNORECASE
)
ARTICLE_RE = re.compile(r"(?:điều|dieu)\s+(\d+[a-z]?)", re.IGNORECASE)
CLAUSE_RE = re.compile(r"(?:khoản|khoan)\s+(\d+)", re.IGNORECASE)
POINT_RE = re.compile(r"(?:điểm|diem)\s+([a-zđ])", re.IGNORECASE)
DMY_DATE_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b")
YMD_DATE_RE = re.compile(r"\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b")
ENUMERATION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bbao\s+gồm\s+(?:những\s+)?gì\b",
        r"\bgồm\s+(?:những\s+)?gì\b",
        r"\bgồm\s+các\b",
        r"\bcác\s+.+\s+nào\b",
        r"\bnhững\s+.+\s+nào\b",
        r"\bliệt\s+kê\b",
        r"\bcó\s+bao\s+nhiêu\b",
        r"\bnhững\s+nội\s+dung\s+nào\b",
    ]
]


def _detect_intent(query: str) -> str:
    q = normalize_text(query)
    q_ascii = strip_accents(q)
    if any(term in q_ascii for term in ["phi", "le phi"]):
        return "FEE_LOOKUP"
    if any(term in q for term in ["phạt", "xử phạt", "mức phạt", "trừ điểm"]) or any(
        term in q_ascii
        for term in [
            "phat",
            "xu phat",
            "muc phat",
            "tru diem",
            "bi tru",
            "tru may diem",
            "tru bao nhieu diem",
            "bi tru may diem",
            "bi tru bao nhieu diem",
        ]
    ):
        return "PENALTY_LOOKUP"
    if "giay phep lai xe" in q_ascii and any(
        term in q_ascii for term in ["bao nhieu diem", "co bao nhieu diem", "may diem", "so diem"]
    ):
        return "LICENSE_POINT_BALANCE"
    if any(
        term in q_ascii
        for term in [
            "bao nhieu tuoi",
            "may tuoi",
            "do tuoi",
            "tuoi toi thieu",
            "tuoi toi da",
            "du tuoi",
            "tu bao nhieu tuoi",
            "duoc phep lai",
            "duoc phep dieu khien",
            "duoc lai",
            "duoc dieu khien",
        ]
    ):
        return "DRIVER_AGE_REQUIREMENT"
    if _is_enumeration_query(query):
        return "ENUMERATION"
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


def _is_enumeration_query(query: str) -> bool:
    q = normalize_text(query)
    q_ascii = strip_accents(q)
    return any(pattern.search(q) or pattern.search(q_ascii) for pattern in ENUMERATION_PATTERNS)


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


def _detect_vehicle_code(query: str) -> str | None:
    q = normalize_text(query)
    q_ascii = strip_accents(q)
    if "xe máy chuyên dùng" in q or "xe may chuyen dung" in q_ascii:
        return "SPECIALIZED_MOTOR_VEHICLE"
    if any(term in q for term in ["ô tô", "xe hơi", "xe con"]) or any(
        term in q_ascii for term in ["o to", "xe hoi", "xe con"]
    ):
        return "CAR"
    if any(term in q for term in ["xe tải"]) or "xe tai" in q_ascii:
        return "TRUCK"
    if any(term in q for term in ["xe khách", "xe buýt"]) or any(term in q_ascii for term in ["xe khach", "xe buyt"]):
        return "BUS"
    if any(term in q for term in ["xe máy", "mô tô", "gắn máy"]) or any(
        term in q_ascii for term in ["xe may", "mo to", "gan may"]
    ):
        return "MOTORCYCLE"
    if "xe đạp" in q or "xe dap" in q_ascii:
        return "BICYCLE"
    if "người đi bộ" in q or "nguoi di bo" in q_ascii:
        return "PEDESTRIAN"
    return None


def _detect_behavior_code(query: str) -> str | None:
    return behavior_code_from_query(query)


def _detect_violations(query: str) -> list[ViolationFact]:
    violations: list[ViolationFact] = []
    for match in match_behaviors(query):
        codes = [str(code) for code in match.get("rule_behavior_codes") or [] if code]
        if not codes:
            continue
        raw_span = str(match.get("matched_alias") or "")
        violations.append(
            ViolationFact(
                behavior_code=codes[0],
                behavior_text=str(match.get("canonical_text") or raw_span or codes[0]),
                raw_span=raw_span or None,
                behavior_contains=str(match.get("behavior_contains") or "") or None,
                catalog_code=str(match.get("catalog_code") or "") or None,
                conditions={"behavior_codes": codes},
                confidence=1.0,
            )
        )
    return violations


def _requested_facets(query: str) -> list[str]:
    q = strip_accents(normalize_text(query))
    facets: list[str] = []
    asks_deduction = any(
        term in q
        for term in ["tru diem", "bi tru diem", "tru bao nhieu diem", "bi tru bao nhieu diem", "tru may diem"]
    )
    if (
        not asks_deduction
        and "giay phep lai xe" in q
        and any(term in q for term in ["bao nhieu diem", "co bao nhieu diem", "may diem", "so diem"])
    ):
        facets.append("LICENSE_POINT_TOTAL")
    if any(term in q for term in ["bao nhieu tuoi", "may tuoi", "do tuoi", "tuoi toi thieu", "du tuoi"]):
        facets.append("MINIMUM_AGE")
    if any(term in q for term in ["phat bao nhieu", "muc phat", "phat tien", "bao nhieu tien", "dong"]):
        facets.append("FINE")
    if asks_deduction or any(term in q for term in ["diem gplx", "mat may diem"]):
        facets.append("LICENSE_POINTS")
    if any(term in q for term in ["tuoc", "bi tuoc", "tuoc gplx", "tuoc giay phep lai xe"]):
        facets.append("LICENSE_SUSPENSION")
    return facets


def _desired_rule_function(intent: str) -> str | None:
    if intent == "DRIVER_AGE_REQUIREMENT":
        return "ELIGIBILITY"
    if intent == "PENALTY_LOOKUP":
        return "SANCTION"
    return None


def _intent_query_expansion(query: str, intent: str) -> str:
    if intent == "LICENSE_POINT_BALANCE":
        return (
            f"{query} điểm của giấy phép lái xe bao gồm 12 điểm phục hồi đủ 12 điểm "
            "Điều 58 Luật Trật tự an toàn giao thông đường bộ"
        )
    if intent != "DRIVER_AGE_REQUIREMENT":
        return query
    return (
        f"{query} tuổi sức khỏe người điều khiển phương tiện được cấp giấy phép lái xe "
        "hạng B hạng C1 đủ 18 tuổi điều kiện người lái xe"
    )


def _detect_temporal_intent(query: str, intent: str, has_request_event_date: bool) -> str:
    q = strip_accents(normalize_text(query))
    if any(term in q for term in ["hieu luc", "ngay ap dung", "bat dau ap dung"]):
        return "EFFECTIVE_DATE_LOOKUP"
    if any(term in q for term in ["sua doi", "bo sung", "thay the", "bai bo", "sua nhung gi", "noi dung gi"]):
        return "AMENDMENT_COMPARE" if intent == "AMENDMENT_COMPARE" else "DOCUMENT_CONTENT"
    if intent == "PENALTY_LOOKUP":
        return "APPLICABLE_RULE"
    if has_request_event_date or any(term in q for term in ["hien nay", "dang ap dung", "tai thoi diem", "ngay"]):
        return "APPLICABLE_RULE"
    return "DOCUMENT_CONTENT"


def _document_number(query: str) -> str | None:
    match = DOCUMENT_RE.search(query)
    if not match:
        return None
    return f"{match.group(1)}/{match.group(2)}/{match.group(3).upper()}"


def _explicit_date(query: str) -> date | None:
    dmy = DMY_DATE_RE.search(query)
    if dmy:
        day, month, year = map(int, dmy.groups())
        try:
            return date(year, month, day)
        except ValueError:
            return None
    ymd = YMD_DATE_RE.search(query)
    if ymd:
        year, month, day = map(int, ymd.groups())
        try:
            return date(year, month, day)
        except ValueError:
            return None
    return None


def parse_query(request: ChatRequest) -> ParsedQuery:
    query = request.query.strip()
    article = ARTICLE_RE.search(query) or ARTICLE_RE.search(strip_accents(query))
    clause = CLAUSE_RE.search(query) or CLAUSE_RE.search(strip_accents(query))
    point = POINT_RE.search(query) or POINT_RE.search(strip_accents(query))
    point_value = point.group(1).lower() if point and (article or clause) else None
    is_enumeration = _is_enumeration_query(query)
    explicit_event_date = _explicit_date(query)
    event_date = explicit_event_date or request.event_date
    query_reference_date = request.as_of_date or date.today()
    legal_effective_date = event_date or query_reference_date
    intent = _detect_intent(query)
    expanded_query = expand_query(_intent_query_expansion(query, intent))
    behavior_contains = behavior_contains_from_query(query)
    violations = _detect_violations(query)
    temporal_intent = _detect_temporal_intent(query, intent, request.event_date is not None)
    parsed = ParsedQuery(
        query=query,
        original_query=query,
        normalized_query=expanded_query,
        retrieval_query=expanded_query,
        evidence_validation_query=query,
        intent=intent,
        primary_intent=intent,
        answer_mode="ENUMERATION" if is_enumeration else "FACTOID",
        document_number=_document_number(query),
        article=article.group(1) if article else None,
        clause=clause.group(1) if clause else None,
        point=point_value,
        vehicle_type=_detect_vehicle(query),
        vehicle_code=_detect_vehicle_code(query),
        behavior_code=_detect_behavior_code(query),
        behavior_text_query=behavior_contains,
        violations=violations,
        desired_rule_function=_desired_rule_function(intent),
        requested_facets=_requested_facets(query),
        event_date=event_date.isoformat() if event_date else None,
        as_of_date=request.as_of_date.isoformat() if request.as_of_date else None,
        legal_effective_date=legal_effective_date.isoformat(),
        query_reference_date=query_reference_date.isoformat(),
        temporal_intent=temporal_intent,
        retrieval_mode="EXHAUSTIVE" if is_enumeration else "FACTOID",
        answer_scope="ALL_CHILDREN" if is_enumeration else None,
        keywords=[],
    )
    from rag_luat_gt.retrieval.query_planner import build_query_plan

    parsed.query_plan = build_query_plan(parsed)
    return parsed
