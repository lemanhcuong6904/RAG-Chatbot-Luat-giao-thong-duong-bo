from __future__ import annotations

from rag_luat_gt.schemas import ParsedQuery, QueryPlan
from rag_luat_gt.text import expand_query, normalize_text, strip_accents


def build_query_plan(parsed: ParsedQuery) -> QueryPlan:
    explicit_reference = _has_explicit_reference(parsed)
    strategies = ["EXPANSION"]
    multi_queries: list[str] = []
    step_back_query = None
    hyde_text = None

    if parsed.intent == "PENALTY_LOOKUP":
        strategies.append("STRUCTURED_LOOKUP")
        if len(parsed.violations) >= 2:
            strategies.extend(["DECOMPOSITION", "LEGAL_COMPOSITION"])
        return QueryPlan(
            strategy=_dedupe(strategies),
            use_structured_sanction=True,
            expanded_query=parsed.normalized_query,
            subqueries=_violation_subqueries(parsed),
        )

    if explicit_reference:
        return QueryPlan(
            strategy=_dedupe(["DIRECT", *_temporal_strategies(parsed), "EXPANSION", "HYBRID_RETRIEVAL"]),
            expanded_query=parsed.normalized_query,
            multi_queries=_temporal_multi_queries(parsed),
        )

    temporal_queries = _temporal_multi_queries(parsed)
    if temporal_queries:
        strategies.extend(_temporal_strategies(parsed))
        strategies.append("MULTI_QUERY")
        multi_queries.extend(temporal_queries)

    if _needs_step_back(parsed):
        strategies.append("STEP_BACK")
        step_back_query = _step_back_query(parsed)

    if _should_multi_query(parsed):
        strategies.append("MULTI_QUERY")
        multi_queries = _multi_queries(parsed)

    if _should_hyde(parsed):
        strategies.append("HYDE")
        hyde_text = _hyde_text(parsed)

    strategies.append("HYBRID_RETRIEVAL")
    return QueryPlan(
        strategy=_dedupe(strategies),
        use_structured_sanction=False,
        expanded_query=parsed.normalized_query,
        multi_queries=_dedupe(multi_queries),
        step_back_query=step_back_query,
        hyde_text=hyde_text,
    )


def _has_explicit_reference(parsed: ParsedQuery) -> bool:
    return any([parsed.document_number, parsed.article, parsed.clause, parsed.point])


def _violation_subqueries(parsed: ParsedQuery) -> list[str]:
    vehicle = parsed.vehicle_type or parsed.vehicle_code or "phuong tien"
    return [
        expand_query(f"{vehicle} {violation.raw_span or violation.behavior_text} bi xu phat the nao")
        for violation in parsed.violations
    ]


def _temporal_strategies(parsed: ParsedQuery) -> list[str]:
    return ["TEMPORAL_SOURCE_LOOKUP"] if parsed.temporal_intent in {"EFFECTIVE_DATE_LOOKUP", "APPLICABLE_RULE"} else []


def _temporal_multi_queries(parsed: ParsedQuery) -> list[str]:
    if parsed.temporal_intent not in {"EFFECTIVE_DATE_LOOKUP", "APPLICABLE_RULE"}:
        return []
    q = strip_accents(normalize_text(parsed.query))
    queries = [parsed.query]
    if parsed.temporal_intent == "EFFECTIVE_DATE_LOOKUP":
        queries.extend(
            [
                f"{parsed.query} hieu luc thi hanh ngay co hieu luc valid_from",
                "dieu hieu luc thi hanh quy dinh co hieu luc tu ngay nao",
            ]
        )
    if any(term in q for term in ["chuyen tiep", "phat hien", "xay ra va ket thuc", "thoi diem thuc hien"]):
        queries.extend(
            [
                f"{parsed.query} dieu khoan chuyen tiep thoi diem thuc hien hanh vi vi pham",
                "hanh vi vi pham xay ra va ket thuc truoc ngay co hieu luc sau do moi bi phat hien ap dung nghi dinh dang co hieu luc tai thoi diem thuc hien hanh vi",
            ]
        )
    if "238" in q:
        queries.append("Nghi dinh 238/2026/ND-CP Dieu 20 hieu luc thi hanh Dieu 21 dieu khoan chuyen tiep")
    if "168" in q:
        queries.append("Nghi dinh 168/2024/ND-CP Dieu 53 hieu luc thi hanh Dieu 54 dieu khoan chuyen tiep")
    return _dedupe(expand_query(item) for item in queries)[:6]


def _needs_step_back(parsed: ParsedQuery) -> bool:
    q = strip_accents(normalize_text(parsed.query))
    return any(
        term in q
        for term in [
            "xe uu tien",
            "cuu thuong",
            "nhuong duong",
            "tranh xe",
            "nhieu hanh vi",
            "cung luc",
            "dong thoi",
            "co duoc",
            "duoc phep",
        ]
    )


def _step_back_query(parsed: ParsedQuery) -> str:
    q = strip_accents(normalize_text(parsed.query))
    if any(term in q for term in ["xe uu tien", "cuu thuong", "nhuong duong"]):
        return (
            "quy dinh chung ve chap hanh bao hieu duong bo, den tin hieu giao thong "
            "va nhuong duong cho xe uu tien dang lam nhiem vu"
        )
    if any(term in q for term in ["nhieu hanh vi", "cung luc", "dong thoi"]):
        return "nguyen tac xu phat khi mot ca nhan thuc hien nhieu hanh vi vi pham hanh chinh"
    return "quy tac phap ly nen can ap dung cho tinh huong giao thong duong bo"


def _should_multi_query(parsed: ParsedQuery) -> bool:
    if parsed.intent in {"PENALTY_LOOKUP", "ARTICLE_LOOKUP"}:
        return False
    if parsed.intent == "DRIVER_AGE_REQUIREMENT" and _has_vehicle_capacity(parsed.query):
        return True
    if parsed.intent == "DRIVER_LICENSE" and parsed.license_classes:
        return True
    if _is_csgt_stop_reason_rights_query(parsed.query):
        return True
    if parsed.answer_mode == "ENUMERATION":
        return True
    q = strip_accents(normalize_text(parsed.query))
    return len(q.split()) <= 8 or any(term in q for term in ["quy dinh", "the nao", "khi nao", "nhung gi"])


def _multi_queries(parsed: ParsedQuery) -> list[str]:
    query = parsed.query
    variants = [query]
    vehicle = parsed.vehicle_type or ""
    q = strip_accents(normalize_text(query))

    if parsed.intent == "DRIVER_AGE_REQUIREMENT":
        variants.extend(
            [
                f"{vehicle} do tuoi toi thieu duoc cap giay phep lai xe",
                "dieu kien tuoi suc khoe nguoi lai xe duoc cap giay phep lai xe",
            ]
        )
        if _has_vehicle_capacity(query):
            variants.extend(
                [
                    f"{query} xe gan may dong co nhiet dung tich khong lon hon 50 cm3 Dieu 34 khoan 1 diem g nguoi du 16 tuoi Dieu 59 khoan 1 diem a",
                    f"{query} hang A1 hang A xe mo to hai banh dung tich xi lanh cong suat dong co dien",
                    "giay phep lai xe hang A1 hang A xe mo to hai banh dung tich xi lanh 125 cm3 11 kW",
                    "xe gan may van toc thiet ke khong lon hon 50 km/h dong co dien cong suat khong lon hon 04 kW",
                    "nguoi du 18 tuoi tro len duoc cap giay phep lai xe hang A1 A",
                ]
            )
    elif parsed.intent == "DRIVER_LICENSE" and parsed.license_classes:
        classes = " ".join(f"hang {item}" for item in parsed.license_classes)
        variants.extend(
            [
                f"giay phep lai xe {classes} cap cho nguoi lai xe",
                f"{classes} duoc dieu khien loai xe nao dieu 57",
            ]
        )
    elif parsed.intent == "LICENSE_POINT_BALANCE":
        variants.extend(
            [
                "diem cua giay phep lai xe bao gom bao nhieu diem",
                "quy dinh ve 12 diem cua giay phep lai xe",
            ]
        )
    elif any(term in q for term in ["xe uu tien", "cuu thuong"]):
        variants.extend(
            [
                "quy dinh ve xe uu tien dang phat tin hieu uu tien",
                "nguoi tham gia giao thong phai nhuong duong cho xe uu tien",
            ]
        )
    elif _is_csgt_stop_reason_rights_query(query):
        variants.extend(
            [
                "quyen nguoi dieu khien phuong tien duoc thong bao can cu dung phuong tien de kiem tra kiem soat",
                "can cu dung phuong tien kiem tra kiem soat noi dung ket qua kiem tra hanh vi vi pham bien phap xu ly dieu 72",
            ]
        )
    else:
        variants.extend(
            [
                f"{query} quy dinh phap luat giao thong duong bo",
                f"{query} dieu kien nghia vu truong hop ap dung",
            ]
        )

    limit = 6 if parsed.intent == "DRIVER_AGE_REQUIREMENT" and _has_vehicle_capacity(query) else 4
    return _dedupe(expand_query(variant) for variant in variants)[:limit]


def _has_vehicle_capacity(query: str) -> bool:
    q = strip_accents(normalize_text(query))
    return any(term in q for term in ["cm3", "cm³", "cc", "xi lanh", "dung tich", "kw", "cong suat"])


def _is_csgt_stop_reason_rights_query(query: str) -> bool:
    q = strip_accents(normalize_text(query))
    has_authority = any(term in q for term in ["csgt", "canh sat giao thong", "luc luong tuan tra"])
    has_stop_context = any(term in q for term in ["dung xe", "dung phuong tien", "kiem tra", "kiem soat"])
    asks_reason = any(term in q for term in ["ly do", "can cu", "duoc biet", "duoc thong bao", "quyen"])
    return has_authority and has_stop_context and asks_reason


def _should_hyde(parsed: ParsedQuery) -> bool:
    if parsed.intent not in {"GENERAL_LEGAL_QA", "ENUMERATION"}:
        return False
    q = strip_accents(normalize_text(parsed.query))
    return len(q.split()) <= 6


def _hyde_text(parsed: ParsedQuery) -> str:
    return (
        "Van ban phap luat giao thong duong bo quy dinh ve khai niem, dieu kien, "
        "nghia vu va truong hop ap dung lien quan den cau hoi: "
        f"{parsed.query}"
    )


def _dedupe(values) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value:
            continue
        key = strip_accents(normalize_text(str(value)))
        if key in seen:
            continue
        seen.add(key)
        result.append(str(value))
    return result
