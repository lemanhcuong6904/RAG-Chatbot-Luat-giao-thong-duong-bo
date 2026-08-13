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
            strategy=["DIRECT", "EXPANSION", "HYBRID_RETRIEVAL"],
            expanded_query=parsed.normalized_query,
        )

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
        multi_queries=multi_queries,
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
                    f"{query} hang A1 hang A xe mo to hai banh dung tich xi lanh cong suat dong co dien",
                    "giay phep lai xe hang A1 hang A xe mo to hai banh dung tich xi lanh 125 cm3 11 kW",
                    "xe gan may van toc thiet ke khong lon hon 50 km/h dong co dien cong suat khong lon hon 04 kW",
                    "nguoi du 18 tuoi tro len duoc cap giay phep lai xe hang A1 A",
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
    return any(term in q for term in ["cm3", "cm³", "xi lanh", "dung tich", "kw", "cong suat"])


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
