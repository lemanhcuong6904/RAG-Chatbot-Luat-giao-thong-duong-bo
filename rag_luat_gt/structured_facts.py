from __future__ import annotations

from datetime import date
import re

from rag_luat_gt.config import MARKDOWN_DIR
from rag_luat_gt.citation_format import normalize_inline_legal_refs, short_ref
from rag_luat_gt.schemas import ChatResponse, Citation, ParsedQuery
from rag_luat_gt.text import normalize_text, strip_accents


LAW36_PART1_SOURCE = MARKDOWN_DIR / "36-2024-QH15_Phan-1_Dieu-1-23.md"
LAW36_SOURCE = MARKDOWN_DIR / "36-2024-QH15_Phan-2_Dieu-24-89.md"
LAW35_SOURCE = MARKDOWN_DIR / "35-2024-QH15_Luat-Duong-bo.md"
ND165_SOURCE = MARKDOWN_DIR / "165-2024-ND-CP_Huong-dan-Luat-Duong-bo.md"
ND168_SOURCE = MARKDOWN_DIR / "168-2024-ND-CP_Xu-phat-TTATGT-Tru-diem-GPLX.md"
ND238_SOURCE = MARKDOWN_DIR / "238-2026-ND-CP_Sua-doi-ND-168-2024.md"


def build_structured_fact_answer(parsed: ParsedQuery) -> ChatResponse | None:
    query = strip_accents(normalize_text(parsed.query))
    builders = [
        _invalid_explicit_provision_answer,
        _multi_reference_exact_answer,
        _temporal_source_fact_answer,
        _csgt_stop_authority_answer,
        _sanction_limitation_period_answer,
        _source_traffic_fact_answer,
        _common_traffic_direct_answer,
        _traffic_rule_catalog_answer,
        _child_safety_amendment_answer,
        _law36_child_safety_effective_date_answer,
        _license_c1_scope_answer,
        _license_points_answer,
        _license_validity_answer,
        _priority_vehicle_order_answer,
        _priority_vehicle_rights_answer,
        _plate_auction_starting_price_answer,
        _road_database_answer,
        _national_roads_not_decentralized_answer,
    ]
    for builder in builders:
        response = builder(parsed, query)
        if response:
            return response
    return None


def _invalid_explicit_provision_answer(parsed: ParsedQuery, query: str) -> ChatResponse | None:
    if not parsed.document_number or not parsed.article:
        return None
    if parsed.temporal_intent == "EFFECTIVE_DATE_LOOKUP":
        return None
    if not any(term in query for term in ["quy dinh", "noi dung", "liet ke", "la gi", "nhung gi"]):
        return None
    source_file = _source_file_for_reference(parsed.document_number, parsed.article)
    if source_file is None:
        return None
    article_data = _extract_article(source_file, parsed.article)
    if article_data is None:
        return None
    if parsed.clause and _clause_bounds(article_data[1], parsed.clause) is None:
        return _unanswerable_response(
            parsed,
            (
                f"Không có khoản {parsed.clause} Điều {parsed.article} {parsed.document_number} theo bộ nguồn hiện có. "
                "Cần kiểm tra lại căn cứ."
            ),
            {"invalid_provision": "clause"},
        )
    if parsed.clause and parsed.point and _extract_point_from_article(article_data[1], parsed.clause, parsed.point) is None:
        return _unanswerable_response(
            parsed,
            (
                f"Không có điểm {parsed.point} khoản {parsed.clause} Điều {parsed.article} {parsed.document_number} "
                "theo bộ nguồn hiện có. Cần kiểm tra lại căn cứ."
            ),
            {"invalid_provision": "point"},
        )
    return None


def _csgt_stop_authority_answer(parsed: ParsedQuery, query: str) -> ChatResponse | None:
    if parsed.intent != "AUTHORITY_LOOKUP":
        return None
    if not any(term in query for term in ["csgt", "canh sat giao thong"]):
        return None
    if not any(term in query for term in ["dung xe", "dung phuong tien", "kiem tra", "kiem soat"]):
        return None
    if _driver_stop_reason_right_query(query):
        return None
    article = _extract_article(LAW36_SOURCE, "66")
    if article is None:
        return None
    article_title, article_lines = article
    intro, items = _numbered_article_items(article_lines)
    if not items:
        return None

    item_citations = [
        _citation(
            f"L36_A66_K{number}_CSGT_STOP_AUTHORITY",
            "36/2024/QH15",
            "Luật Trật tự, an toàn giao thông đường bộ",
            "66",
            article_title,
            number,
            None,
            LAW36_SOURCE,
            f"{number}. {text}",
            "AUTHORITY_RULE",
        )
        for number, text in items
    ]

    if _asks_csgt_stop_basis_list(parsed, query):
        lines = [f'{intro.rstrip(":")} [Luật 36/2024/QH15, Điều 66]:']
        lines.extend(f"- {text} [{short_ref(citation)}]" for (_number, text), citation in zip(items, item_citations, strict=True))
        return _response(parsed, "\n".join(lines), item_citations, {"provision": "L36_A66_ALL"})

    technical_citations = _csgt_technical_detection_citations()
    if _csgt_system_detection_query(query) and technical_citations:
        citations = [item_citations[0], *technical_citations]
        conclusion = (
            "Có, nếu thông tin hoặc dữ liệu từ hệ thống giám sát, camera, phương tiện hoặc thiết bị kỹ thuật nghiệp vụ "
            "làm phát sinh căn cứ xác định có hành vi vi phạm. CSGT được dừng phương tiện khi phát hiện hoặc có căn cứ "
            f"xác định hành vi vi phạm [{short_ref(item_citations[0])}]; các biện pháp phát hiện vi phạm gồm vận hành, "
            f"sử dụng hệ thống giám sát/camera và phương tiện, thiết bị kỹ thuật nghiệp vụ [{short_ref(technical_citations[0])}; "
            f"{short_ref(technical_citations[1])}]."
        )
        return _response(parsed, conclusion, citations, {"provision": "L36_A66_K1_A67_K1_K2"})

    citation = item_citations[0]
    conclusion = (
        "Có. CSGT được dừng phương tiện để kiểm tra, kiểm soát khi phát hiện hành vi vi phạm pháp luật "
        "hoặc có căn cứ xác định có hành vi vi phạm pháp luật về trật tự, an toàn giao thông đường bộ hoặc vi phạm pháp luật khác "
        f"[{short_ref(citation)}]."
    )
    return _response(parsed, conclusion, [citation], {"provision": "L36_A66_K1"})


def _sanction_limitation_period_answer(parsed: ParsedQuery, query: str) -> ChatResponse | None:
    if parsed.intent != "PROCEDURE_LOOKUP":
        return None
    if "thoi hieu xu phat" not in query:
        return None
    citation = _citation(
        "ND168_A04_K1_LIMITATION_PERIOD",
        "168/2024/NĐ-CP",
        "Nghị định số 168/2024/NĐ-CP",
        "4",
        "Thời hiệu xử phạt vi phạm hành chính; hành vi vi phạm hành chính đã kết thúc, hành vi vi phạm hành chính đang thực hiện",
        "1",
        None,
        ND168_SOURCE,
        "1. Thời hiệu xử phạt vi phạm hành chính về trật tự, an toàn giao thông trong lĩnh vực giao thông đường bộ là 01 năm.",
        "PROCEDURE_RULE",
    )
    conclusion = (
        "Thời hiệu xử phạt vi phạm hành chính về trật tự, an toàn giao thông trong lĩnh vực giao thông đường bộ là **01 năm** "
        f"[{short_ref(citation)}]."
    )
    return _response(parsed, conclusion, [citation], {"provision": "ND168_A04_K1"})


def _temporal_source_fact_answer(parsed: ParsedQuery, query: str) -> ChatResponse | None:
    child_effective = _nd168_child_safety_sanction_effective_date_answer(parsed, query)
    if child_effective:
        return child_effective
    law36_child_effective = _law36_child_safety_effective_date_answer(parsed, query)
    if law36_child_effective:
        return law36_child_effective
    transition = _nd238_transition_applicable_rule_answer(parsed, query)
    if transition:
        return transition
    return None


def _nd168_child_safety_sanction_effective_date_answer(parsed: ParsedQuery, query: str) -> ChatResponse | None:
    if parsed.temporal_intent != "EFFECTIVE_DATE_LOOKUP":
        return None
    mentions_nd168 = parsed.document_number == "168/2024/NĐ-CP" or "nghi dinh 168" in query or "nd168" in query
    is_target_ref = mentions_nd168 and parsed.article == "6" and parsed.clause == "3"
    is_child_safety_query = "thiet bi an toan" in query and any(term in query for term in ["tre em", "tre ", "1,35", "1.35"])
    if not (is_target_ref and (parsed.point in {None, "m"} or is_child_safety_query)):
        return None

    temporal_citation = _citation(
        "ND168_A53_K2_CHILD_SAFETY_EFFECTIVE",
        "168/2024/NĐ-CP",
        "Nghị định số 168/2024/NĐ-CP",
        "53",
        "Hiệu lực thi hành",
        "2",
        None,
        ND168_SOURCE,
        (
            "2. Điểm m khoản 3 Điều 6, điểm e khoản 4 Điều 26 và điểm b khoản 1 Điều 27 "
            "của Nghị định này có hiệu lực thi hành từ ngày 01 tháng 01 năm 2026."
        ),
        "TEMPORAL_RULE",
    )
    citations = [temporal_citation]
    article_data = _extract_article(ND168_SOURCE, "6")
    if article_data:
        article_title, article_lines = article_data
        point = _extract_point_from_article(article_lines, "3", "m")
        if point:
            clause_intro, point_text = point
            citations.append(
                _citation(
                    "ND168_A06_K3_Pm_CHILD_SAFETY_SOURCE",
                    "168/2024/NĐ-CP",
                    "Nghị định số 168/2024/NĐ-CP",
                    "6",
                    article_title,
                    "3",
                    "m",
                    ND168_SOURCE,
                    f"3. {clause_intro} m) {point_text}",
                    "SANCTION",
                )
            )
    conclusion = (
        "Quy định tại điểm m khoản 3 Điều 6 Nghị định 168/2024/NĐ-CP có hiệu lực từ ngày **01/01/2026** "
        f"[{short_ref(temporal_citation)}]."
    )
    if len(citations) > 1:
        conclusion += f" Nội dung hành vi được quy định tại điểm m khoản 3 Điều 6 [{short_ref(citations[1])}]."
    return _response(parsed, conclusion, citations, {"provision": "ND168_A53_K2_A06_K3_Pm"})


def _nd238_transition_applicable_rule_answer(parsed: ParsedQuery, query: str) -> ChatResponse | None:
    if parsed.temporal_intent != "APPLICABLE_RULE":
        return None
    if "238" not in query:
        return None
    transition_terms = [
        "xay ra va ket thuc",
        "truoc ngay",
        "moi bi phat hien",
        "dang xem xet",
        "thoi diem thuc hien hanh vi",
        "ap dung nghi dinh 168 hay nghi dinh 238",
    ]
    if not any(term in query for term in transition_terms):
        return None

    article_data = _extract_article(ND238_SOURCE, "21")
    if not article_data:
        return None
    article_title, article_lines = article_data
    article21_text = " ".join(line.strip() for line in article_lines if line.strip())
    transition_citation = _citation(
        "ND238_A21_TRANSITION_STRUCTURED",
        "238/2026/NĐ-CP",
        "Sửa đổi, bổ sung một số điều của Nghị định 168/2024/NĐ-CP",
        "21",
        article_title,
        None,
        None,
        ND238_SOURCE,
        article21_text,
        "TEMPORAL_RULE",
    )
    effective_citation = _citation(
        "ND238_A20_K1_EFFECTIVE_STRUCTURED",
        "238/2026/NĐ-CP",
        "Sửa đổi, bổ sung một số điều của Nghị định 168/2024/NĐ-CP",
        "20",
        "Hiệu lực thi hành",
        "1",
        None,
        ND238_SOURCE,
        "1. Nghị định này có hiệu lực thi hành từ ngày 15 tháng 8 năm 2026.",
        "TEMPORAL_RULE",
    )
    event_date = _query_date(parsed)
    if event_date and event_date < date(2026, 8, 15):
        conclusion = (
            f"Hành vi xảy ra và kết thúc ngày {_format_date_vi(event_date)} là trước ngày Nghị định 238/2026/NĐ-CP có hiệu lực "
            f"(15/08/2026), nên nếu sau đó mới bị phát hiện hoặc đang xem xét giải quyết thì áp dụng nghị định đang có hiệu lực "
            f"tại thời điểm thực hiện hành vi; trong tình huống này là Nghị định 168/2024/NĐ-CP, không áp dụng Nghị định 238 "
            f"[{short_ref(transition_citation)}; {short_ref(effective_citation)}]."
        )
    else:
        conclusion = (
            "Điều 21 Nghị định 238/2026/NĐ-CP quy định hành vi vi phạm xảy ra và kết thúc trước ngày Nghị định 238 có hiệu lực, "
            "sau đó mới bị phát hiện hoặc đang xem xét giải quyết, thì áp dụng nghị định đang có hiệu lực tại thời điểm thực hiện hành vi "
            f"[{short_ref(transition_citation)}]."
        )
    return _response(parsed, conclusion, [transition_citation, effective_citation], {"provision": "ND238_A21_A20_K1"})


def _source_traffic_fact_answer(parsed: ParsedQuery, query: str) -> ChatResponse | None:
    explicit_clause = _explicit_law36_clause_fact_answer(parsed, query)
    if explicit_clause:
        return explicit_clause

    stop_parking = _stopping_parking_definition_answer(parsed, query)
    if stop_parking:
        return stop_parking

    clause_fact = _source_clause_fact(parsed, query)
    if clause_fact:
        return clause_fact

    point_fact = _source_point_fact(parsed, query)
    if point_fact:
        return point_fact

    article_fact = _source_article_fact(parsed, query)
    if article_fact:
        return article_fact
    return None


def _explicit_law36_clause_fact_answer(parsed: ParsedQuery, query: str) -> ChatResponse | None:
    if parsed.document_number != "36/2024/QH15" or not parsed.article or not parsed.clause:
        return None
    if parsed.point or not any(term in query for term in ["quy dinh", "nhung", "nao", "gi"]):
        return None
    source_file = LAW36_PART1_SOURCE if parsed.article.isdigit() and int(parsed.article) <= 23 else LAW36_SOURCE
    extracted = _extract_clause_provision(source_file, parsed.article, parsed.clause)
    if extracted is None:
        return None
    article_title, clause_intro, points, source_text = extracted
    citation = _citation(
        f"L36_A{parsed.article}_K{parsed.clause}_EXACT_STRUCTURED",
        "36/2024/QH15",
        "Luật Trật tự, an toàn giao thông đường bộ",
        parsed.article,
        article_title,
        parsed.clause,
        None,
        source_file,
        source_text,
        "TRAFFIC_RULE",
    )
    conclusion = _format_focused_clause_answer(parsed, query, clause_intro, points)
    return _response(
        parsed,
        f"{conclusion} [{short_ref(citation)}].",
        [citation],
        {"provision": f"L36_A{parsed.article}_K{parsed.clause}"},
    )


def _stopping_parking_definition_answer(parsed: ParsedQuery, query: str) -> ChatResponse | None:
    if "csgt" in query or "canh sat giao thong" in query:
        return None
    if not ("dung xe" in query and "do xe" in query):
        return None
    if not any(term in query for term in ["khac nhau", "phan biet", "la gi", "the nao"]):
        return None

    extracted_stop = _extract_clause_provision(LAW36_PART1_SOURCE, "18", "1")
    extracted_parking = _extract_clause_provision(LAW36_PART1_SOURCE, "18", "2")
    if not extracted_stop or not extracted_parking:
        return None
    stop_title, stop_intro, _stop_points, stop_source = extracted_stop
    parking_title, parking_intro, _parking_points, parking_source = extracted_parking
    citations = [
        _citation(
            "L36_A18_K1_STRUCTURED",
            "36/2024/QH15",
            "Luật Trật tự, an toàn giao thông đường bộ",
            "18",
            stop_title,
            "1",
            None,
            LAW36_PART1_SOURCE,
            stop_source,
            "TRAFFIC_RULE",
        ),
        _citation(
            "L36_A18_K2_STRUCTURED",
            "36/2024/QH15",
            "Luật Trật tự, an toàn giao thông đường bộ",
            "18",
            parking_title,
            "2",
            None,
            LAW36_PART1_SOURCE,
            parking_source,
            "TRAFFIC_RULE",
        ),
    ]
    conclusion = (
        f"Dừng xe: {stop_intro} [{short_ref(citations[0])}].\n"
        f"Đỗ xe: {parking_intro} [{short_ref(citations[1])}]."
    )
    return _response(parsed, conclusion, citations, {"provision": "L36_A18_K1_K2"})


def _source_clause_fact(parsed: ParsedQuery, query: str) -> ChatResponse | None:
    provision: tuple[str, str, str, str, object, str] | None = None
    if _truck_bed_allowed_query(query):
        provision = ("36/2024/QH15", "Luật Trật tự, an toàn giao thông đường bộ", "28", "1", LAW36_SOURCE, "TRAFFIC_RULE")
    elif _lane_change_rule_query(query):
        provision = ("36/2024/QH15", "Luật Trật tự, an toàn giao thông đường bộ", "13", "2", LAW36_PART1_SOURCE, "TRAFFIC_RULE")
    elif _turnaround_forbidden_places_query(query):
        provision = ("36/2024/QH15", "Luật Trật tự, an toàn giao thông đường bộ", "15", "4", LAW36_PART1_SOURCE, "TRAFFIC_RULE")
    elif _reverse_forbidden_places_query(query):
        provision = ("36/2024/QH15", "Luật Trật tự, an toàn giao thông đường bộ", "16", "2", LAW36_PART1_SOURCE, "TRAFFIC_RULE")
    elif _night_horn_forbidden_query(query):
        provision = ("36/2024/QH15", "Luật Trật tự, an toàn giao thông đường bộ", "21", "2", LAW36_PART1_SOURCE, "TRAFFIC_RULE")
    elif _tunnel_light_query(query):
        provision = ("36/2024/QH15", "Luật Trật tự, an toàn giao thông đường bộ", "26", "1", LAW36_SOURCE, "TRAFFIC_RULE")
    elif _tunnel_stop_parking_query(query):
        provision = ("36/2024/QH15", "Luật Trật tự, an toàn giao thông đường bộ", "26", "2", LAW36_SOURCE, "TRAFFIC_RULE")
    elif _child_pedestrian_crossing_query(query):
        provision = ("36/2024/QH15", "Luật Trật tự, an toàn giao thông đường bộ", "30", "2", LAW36_SOURCE, "TRAFFIC_RULE")
    elif _motorcycle_prohibited_while_running_query(query):
        provision = ("36/2024/QH15", "Luật Trật tự, an toàn giao thông đường bộ", "33", "3", LAW36_SOURCE, "TRAFFIC_RULE")
    elif _driver_papers_query(query):
        provision = ("36/2024/QH15", "Luật Trật tự, an toàn giao thông đường bộ", "56", "1", LAW36_SOURCE, "TRAFFIC_RULE")
    elif _highway_breakdown_warning_query(query):
        provision = ("36/2024/QH15", "Luật Trật tự, an toàn giao thông đường bộ", "25", "2", LAW36_SOURCE, "TRAFFIC_RULE")
    if provision is None:
        return None

    document_number, document_title, article, clause, source_file, rule_function = provision
    extracted = _extract_clause_provision(source_file, article, clause)
    if extracted is None:
        return None
    article_title, clause_intro, points, source_text = extracted
    citation = _citation(
        f"{document_number.replace('/', '_').replace('-', '_')}_A{article}_K{clause}_STRUCTURED",
        document_number,
        document_title,
        article,
        article_title,
        clause,
        None,
        source_file,
        source_text,
        rule_function,
    )
    conclusion = _format_focused_clause_answer(parsed, query, clause_intro, points)
    if _night_horn_forbidden_query(query) or _tunnel_stop_parking_query(query):
        conclusion = f"Không. {conclusion}"
    elif _child_pedestrian_crossing_query(query):
        conclusion = f"Không được tự qua đường. {conclusion}"
    elif _tunnel_light_query(query):
        conclusion = f"Phải bật đèn chiếu gần. {conclusion}"
    conclusion = f"{conclusion} [{short_ref(citation)}]."
    return _response(parsed, conclusion, [citation], {"provision": f"{document_number}_A{article}_K{clause}"})


def _source_point_fact(parsed: ParsedQuery, query: str) -> ChatResponse | None:
    provision: tuple[str, str, str, str, str, object, str] | None = None
    if _self_drive_rental_vehicle_query(query):
        provision = ("35/2024/QH15", "Luật Đường bộ", "78", "1", "a", LAW35_SOURCE, "TRAFFIC_RULE")
    elif _self_drive_rental_license_query(query):
        provision = ("35/2024/QH15", "Luật Đường bộ", "78", "2", "a", LAW35_SOURCE, "TRAFFIC_RULE")
    elif _fixed_route_passenger_transport_query(query):
        provision = ("35/2024/QH15", "Luật Đường bộ", "56", "7", None, LAW35_SOURCE, "TRAFFIC_RULE")
    elif _road_protection_land_width_query(query):
        provision = ("165/2024/NĐ-CP", "Nghị định số 165/2024/NĐ-CP", "10", "1", "a", ND165_SOURCE, "TRAFFIC_RULE")
    if provision is None:
        return None
    document_number, document_title, article, clause, point, source_file, rule_function = provision
    article_data = _extract_article(source_file, article)
    if not article_data:
        return None
    article_title, article_lines = article_data
    if point is None:
        extracted_clause = _extract_clause_provision(source_file, article, clause)
        if extracted_clause is None:
            return None
        article_title, clause_intro, points, source_text = extracted_clause
        citation = _citation(
            f"{document_number.replace('/', '_').replace('-', '_')}_A{article}_K{clause}_STRUCTURED",
            document_number,
            document_title,
            article,
            article_title,
            clause,
            None,
            source_file,
            source_text,
            rule_function,
        )
        conclusion = _format_clause_answer(clause_intro, points)
        return _response(parsed, f"{conclusion} [{short_ref(citation)}].", [citation], {"provision": f"{document_number}_A{article}_K{clause}"})
    extracted = _extract_point_from_article(article_lines, clause, point)
    if extracted is None:
        return None
    clause_intro, point_text = extracted
    source_text = f"{clause}. {clause_intro} {point}) {point_text}".strip()
    citation = _citation(
        f"{document_number.replace('/', '_').replace('-', '_')}_A{article}_K{clause}_P{point}_STRUCTURED",
        document_number,
        document_title,
        article,
        article_title,
        clause,
        point,
        source_file,
        source_text,
        rule_function,
    )
    conclusion = f"{point_text} [{short_ref(citation)}]."
    return _response(parsed, conclusion, [citation], {"provision": f"{document_number}_A{article}_K{clause}_P{point}"})


def _source_article_fact(parsed: ParsedQuery, query: str) -> ChatResponse | None:
    if not (
        parsed.document_number == "238/2026/NĐ-CP"
        and parsed.article == "21"
        and any(term in query for term in ["quy dinh gi", "dieu khoan chuyen tiep", "hanh vi"])
    ):
        return None
    article_data = _extract_article(ND238_SOURCE, "21")
    if not article_data:
        return None
    article_title, article_lines = article_data
    source_text = " ".join(line.strip() for line in article_lines if line.strip())
    citation = _citation(
        "ND238_A21_STRUCTURED",
        "238/2026/NĐ-CP",
        "Sửa đổi, bổ sung một số điều của Nghị định 168/2024/NĐ-CP",
        "21",
        article_title,
        None,
        None,
        ND238_SOURCE,
        source_text,
        "TEMPORAL_RULE",
    )
    return _response(parsed, f"{source_text} [{short_ref(citation)}].", [citation], {"provision": "ND238_A21"})


def _truck_bed_allowed_query(query: str) -> bool:
    return "thung xe" in query and any(term in query for term in ["o to cho hang", "xe tai", "cho nguoi"])


def _lane_change_rule_query(query: str) -> bool:
    return "chuyen lan" in query and any(term in query for term in ["can lam", "dung quy dinh", "phai", "nhu the nao"])


def _turnaround_forbidden_places_query(query: str) -> bool:
    return "quay dau" in query and any(term in query for term in ["noi nao", "nhung noi", "khong duoc", "cam"])


def _reverse_forbidden_places_query(query: str) -> bool:
    return "lui xe" in query and any(term in query for term in ["cho nao", "nhung cho", "noi nao", "khong duoc", "cam"])


def _night_horn_forbidden_query(query: str) -> bool:
    return "coi" in query and "khu dong dan cu" in query and any(term in query for term in ["ban dem", "22 gio", "05 gio", "5 gio"])


def _tunnel_light_query(query: str) -> bool:
    return "ham duong bo" in query and any(term in query for term in ["bat loai den", "den nao", "bat den", "chieu gan"])


def _tunnel_stop_parking_query(query: str) -> bool:
    return "ham duong bo" in query and any(term in query for term in ["dung", "do xe", "dung xe", "dung hoac do"])


def _child_pedestrian_crossing_query(query: str) -> bool:
    return any(term in query for term in ["tre duoi 7", "tre em duoi 7", "duoi 7 tuoi"]) and any(
        term in query for term in ["qua duong", "sang duong"]
    )


def _motorcycle_prohibited_while_running_query(query: str) -> bool:
    if any(term in query for term in ["phat", "muc phat", "xu phat", "tru diem"]):
        return False
    has_vehicle = any(term in query for term in ["xe may", "mo to", "gan may"])
    asks_prohibited = any(term in query for term in ["khong duoc", "bi cam", "cam nhung", "hanh vi nao"])
    return has_vehicle and asks_prohibited and any(term in query for term in ["khi dang chay", "dang chay", "dang dieu khien", "nguoi lai"])


def _driver_papers_query(query: str) -> bool:
    if any(term in query for term in ["phat", "muc phat", "xu phat"]):
        return False
    has_driver = any(term in query for term in ["nguoi lai", "lai xe", "dieu khien"])
    has_paper = "giay to" in query and any(term in query for term in ["mang theo", "phai mang", "can mang", "nhung gi"])
    return has_driver and has_paper


def _self_drive_rental_vehicle_query(query: str) -> bool:
    if "tu lai" not in query:
        return False
    if not any(term in query for term in ["cho thue", "thue xe", "thue phuong tien"]):
        return False
    return any(term in query for term in ["xe nao", "loai xe", "phuong tien nao", "bao gom", "gom"])


def _self_drive_rental_license_query(query: str) -> bool:
    return "tu lai" in query and any(
        term in query for term in ["khong co bang", "khong co giay phep", "bang phu hop", "gplx phu hop"]
    )


def _fixed_route_passenger_transport_query(query: str) -> bool:
    return any(term in query for term in ["xe khach tuyen co dinh", "tuyen co dinh"]) and any(
        term in query for term in ["hieu nhu the nao", "duoc hieu", "la gi"]
    )


def _road_protection_land_width_query(query: str) -> bool:
    return any(term in query for term in ["phan dat de bao ve", "bao ve bao tri duong bo", "khong nho hon 3,0", "khong nho hon 3m"]) and (
        "cao toc" in query or "duong cap i" in query or "ngoai do thi" in query
    )


def _highway_breakdown_warning_query(query: str) -> bool:
    return "cao toc" in query and any(
        term in query
        for term in [
            "no lop",
            "hong xe",
            "su co",
            "bat kha khang",
            "dung khan cap",
            "canh bao",
            "khong the di chuyen",
        ]
    )


def _common_traffic_direct_answer(parsed: ParsedQuery, query: str) -> ChatResponse | None:
    if _alcohol_zero_tolerance_query(query):
        citation = _law36_part1_citation(
            "L36_A09_K2_STRUCTURED",
            "9",
            "Các hành vi bị nghiêm cấm",
            "2",
            None,
            "2. Điều khiển phương tiện tham gia giao thông đường bộ mà trong máu hoặc hơi thở có nồng độ cồn.",
            "PROHIBITION",
        )
        conclusion = (
            "Không. Đã có nồng độ cồn trong máu hoặc hơi thở thì không được điều khiển phương tiện tham gia giao thông đường bộ "
            "[Luật 36/2024/QH15, Điều 9, khoản 2]."
        )
        return _response(parsed, conclusion, [citation], {"provision": "L36_A09_K2"})

    if _phone_while_driving_query(query):
        citation = _law36_part1_citation(
            "L36_A09_K6_STRUCTURED",
            "9",
            "Các hành vi bị nghiêm cấm",
            "6",
            None,
            "6. Dùng tay cầm và sử dụng điện thoại hoặc thiết bị điện tử khác khi điều khiển phương tiện tham gia giao thông đang di chuyển trên đường bộ.",
            "PROHIBITION",
        )
        conclusion = (
            "Không. Khi phương tiện đang di chuyển trên đường bộ, người điều khiển không được dùng tay cầm và sử dụng điện thoại hoặc thiết bị điện tử khác "
            "[Luật 36/2024/QH15, Điều 9, khoản 6]."
        )
        return _response(parsed, conclusion, [citation], {"provision": "L36_A09_K6"})

    if _yellow_light_query(query):
        citation = _law36_part1_citation(
            "L36_A11_K4_PB_STRUCTURED",
            "11",
            "Chấp hành báo hiệu đường bộ",
            "4",
            "b",
            "b) Tín hiệu đèn màu vàng phải dừng lại trước vạch dừng; trường hợp đang đi trên vạch dừng hoặc đã đi qua vạch dừng mà tín hiệu đèn màu vàng thì được đi tiếp; trường hợp tín hiệu đèn màu vàng nhấp nháy, người tham gia giao thông đường bộ được đi nhưng phải quan sát, giảm tốc độ hoặc dừng lại nhường đường cho người đi bộ, xe lăn của người khuyết tật qua đường hoặc các phương tiện khác;",
            "TRAFFIC_RULE",
        )
        conclusion = (
            "Gặp đèn vàng thì phải dừng trước vạch dừng. Nếu đang ở trên vạch dừng hoặc đã qua vạch dừng khi đèn chuyển vàng thì được đi tiếp; đèn vàng nhấp nháy thì được đi nhưng phải quan sát, giảm tốc độ hoặc dừng nhường đường khi cần "
            "[Luật 36/2024/QH15, Điều 11, khoản 4, điểm b]."
        )
        return _response(parsed, conclusion, [citation], {"provision": "L36_A11_K4_PB"})

    if _traffic_signal_priority_query(query):
        citation = _law36_part1_citation(
            "L36_A11_K2_STRUCTURED",
            "11",
            "Chấp hành báo hiệu đường bộ",
            "2",
            None,
            "2. Người tham gia giao thông đường bộ phải chấp hành báo hiệu đường bộ theo thứ tự ưu tiên từ trên xuống dưới như sau: a) Hiệu lệnh của người điều khiển giao thông; b) Tín hiệu đèn giao thông; c) Biển báo hiệu đường bộ; d) Vạch kẻ đường và các dấu hiệu khác trên mặt đường; đ) Cọc tiêu, tường bảo vệ, rào chắn, đinh phản quang, tiêu phản quang, cột Km, cọc H; e) Thiết bị âm thanh báo hiệu đường bộ.",
            "TRAFFIC_RULE",
        )
        conclusion = (
            "Thứ tự ưu tiên là: hiệu lệnh của người điều khiển giao thông; tín hiệu đèn giao thông; biển báo hiệu đường bộ; vạch kẻ đường và dấu hiệu khác trên mặt đường; cọc tiêu/tường bảo vệ/rào chắn/đinh phản quang/tiêu phản quang/cột Km/cọc H; cuối cùng là thiết bị âm thanh báo hiệu đường bộ "
            "[Luật 36/2024/QH15, Điều 11, khoản 2]."
        )
        return _response(parsed, conclusion, [citation], {"provision": "L36_A11_K2"})

    if _horn_allowed_query(query):
        citation = _law36_part1_citation(
            "L36_A21_K1_STRUCTURED",
            "21",
            "Sử dụng tín hiệu còi",
            "1",
            None,
            "1. Chỉ được sử dụng tín hiệu còi của phương tiện tham gia giao thông đường bộ trong các trường hợp sau đây: a) Báo hiệu cho người tham gia giao thông đường bộ khi xuất hiện tình huống có thể mất an toàn giao thông; b) Báo hiệu chuẩn bị vượt xe.",
            "TRAFFIC_RULE",
        )
        conclusion = (
            "Chỉ được bấm còi để báo hiệu khi có tình huống có thể mất an toàn giao thông hoặc để báo hiệu chuẩn bị vượt xe "
            "[Luật 36/2024/QH15, Điều 21, khoản 1]."
        )
        return _response(parsed, conclusion, [citation], {"provision": "L36_A21_K1"})

    if _before_turning_query(query):
        citation = _law36_part1_citation(
            "L36_A15_K2_STRUCTURED",
            "15",
            "Chuyển hướng xe",
            "2",
            None,
            "2. Trước khi chuyển hướng, người điều khiển phương tiện tham gia giao thông đường bộ phải quan sát, bảo đảm khoảng cách an toàn với xe phía sau, giảm tốc độ và có tín hiệu báo hướng rẽ hoặc có tín hiệu bằng tay theo hướng rẽ đối với xe thô sơ không có đèn báo hướng rẽ, chuyển dần sang làn gần nhất với hướng rẽ. Tín hiệu báo hướng rẽ hoặc tín hiệu bằng tay phải sử dụng liên tục trong quá trình chuyển hướng. Khi bảo đảm an toàn, không gây trở ngại cho người và phương tiện khác mới được chuyển hướng.",
            "TRAFFIC_RULE",
        )
        conclusion = (
            "Trước khi rẽ hoặc quay đầu, người điều khiển phải quan sát, bảo đảm khoảng cách an toàn với xe phía sau, giảm tốc độ, bật tín hiệu báo hướng rẽ liên tục, chuyển dần sang làn gần nhất với hướng rẽ và chỉ chuyển hướng khi an toàn, không gây trở ngại cho người hoặc phương tiện khác "
            "[Luật 36/2024/QH15, Điều 15, khoản 2]."
        )
        return _response(parsed, conclusion, [citation], {"provision": "L36_A15_K2"})

    return None


def _law36_part1_citation(
    chunk_id: str,
    article: str,
    article_title: str,
    clause: str | None,
    point: str | None,
    text: str,
    rule_function: str,
) -> Citation:
    return _citation(
        chunk_id,
        "36/2024/QH15",
        "Luật Trật tự, an toàn giao thông đường bộ",
        article,
        article_title,
        clause,
        point,
        LAW36_PART1_SOURCE,
        text,
        rule_function,
    )


def _alcohol_zero_tolerance_query(query: str) -> bool:
    if any(term in query for term in ["phat", "muc phat", "xu phat", "tru diem"]):
        return False
    return any(term in query for term in ["ruou", "bia", "nong do con"]) and any(
        term in query for term in ["lai xe", "dieu khien", "duoc phep", "muc"]
    )


def _phone_while_driving_query(query: str) -> bool:
    if any(term in query for term in ["phat", "muc phat", "tru diem", "diem tru", "cong diem", "thanh 8", "xu phat"]):
        return False
    return any(term in query for term in ["dien thoai", "thiet bi dien tu"]) and any(
        term in query for term in ["dang lai", "lai xe", "dieu khien", "cam"]
    )


def _yellow_light_query(query: str) -> bool:
    return "den vang" in query and any(term in query for term in ["gap", "xu ly", "lam gi", "phai"])


def _traffic_signal_priority_query(query: str) -> bool:
    return any(term in query for term in ["csgt", "nguoi dieu khien giao thong"]) and "den" in query and "bien bao" in query


def _horn_allowed_query(query: str) -> bool:
    return "coi" in query and any(term in query for term in ["duoc phep", "khi nao", "luc nao"])


def _before_turning_query(query: str) -> bool:
    return any(term in query for term in ["truoc khi re", "truoc khi quay dau", "re hoac quay dau"]) and any(
        term in query for term in ["can lam", "lam gi", "phai lam", "nhung gi"]
    )


def _traffic_rule_catalog_answer(parsed: ParsedQuery, query: str) -> ChatResponse | None:
    provision: tuple[str, str, str, str, object] | None = None
    if _slow_vehicle_lane_query(query):
        provision = ("36/2024/QH15", "Luật Trật tự, an toàn giao thông đường bộ", "13", "1", LAW36_PART1_SOURCE)
    elif _no_overtaking_cases_query(query):
        provision = ("36/2024/QH15", "Luật Trật tự, an toàn giao thông đường bộ", "14", "6", LAW36_PART1_SOURCE)
    elif _high_beam_to_low_beam_query(query):
        provision = ("36/2024/QH15", "Luật Trật tự, an toàn giao thông đường bộ", "20", "2", LAW36_PART1_SOURCE)
    elif _passenger_transport_business_types_query(query):
        provision = ("35/2024/QH15", "Luật Đường bộ", "56", "6", LAW35_SOURCE)
    if provision is None:
        return None

    document_number, document_title, article, clause, source_file = provision
    extracted = _extract_clause_provision(source_file, article, clause)
    if extracted is None:
        return None
    article_title, clause_intro, points, source_text = extracted
    citation = _citation(
        f"{document_number.replace('/', '_').replace('-', '_')}_A{article}_K{clause}_STRUCTURED",
        document_number,
        document_title,
        article,
        article_title,
        clause,
        None,
        source_file,
        source_text,
        "TRAFFIC_RULE",
    )
    conclusion = _format_clause_answer(clause_intro, points)
    return _response(parsed, conclusion, [citation], {"provision": f"{document_number}_A{article}_K{clause}"})


def _slow_vehicle_lane_query(query: str) -> bool:
    return any(term in query for term in ["chay cham", "cham hon", "toc do thap hon"]) and any(
        term in query for term in ["phia nao", "ben nao", "ben phai", "lan nao"]
    )


def _no_overtaking_cases_query(query: str) -> bool:
    return "khong duoc vuot" in query and any(term in query for term in ["truong hop", "khi nao", "nhung"])


def _high_beam_to_low_beam_query(query: str) -> bool:
    return "den chieu xa" in query and (
        "tat" in query or "chuyen sang den chieu gan" in query or "bat den chieu gan" in query
    )


def _passenger_transport_business_types_query(query: str) -> bool:
    return "kinh doanh van tai hanh khach" in query and any(
        term in query for term in ["loai hinh", "nhung loai", "gom", "loai nao"]
    )


def _format_clause_answer(clause_intro: str, points: list[tuple[str, str]]) -> str:
    if not points:
        return clause_intro
    lines = [clause_intro]
    lines.extend(f"- {text}" for _, text in points)
    return "\n".join(lines)


def _format_focused_clause_answer(parsed: ParsedQuery, query: str, clause_intro: str, points: list[tuple[str, str]]) -> str:
    if not points or parsed.answer_mode == "ENUMERATION" or _is_clause_list_question(query):
        return _format_clause_answer(clause_intro, points)

    selected = _focused_clause_points(query, points)
    if not selected or len(selected) == len(points):
        return _format_clause_answer(clause_intro, points)
    if len(selected) == 1:
        return _strip_terminal_punctuation(selected[0][1])
    return "\n".join(f"- {_strip_terminal_punctuation(text)}" for _point, text in selected)


def _focused_clause_points(query: str, points: list[tuple[str, str]]) -> list[tuple[str, str]]:
    query_tokens = _focus_tokens(query)
    if not query_tokens:
        return []

    scored: list[tuple[int, int, tuple[str, str]]] = []
    for index, point in enumerate(points):
        _point_name, text = point
        tokens = _focus_tokens(text)
        leading_tokens = _focus_tokens(" ".join(strip_accents(normalize_text(text)).split()[:10]))
        score = len(query_tokens & tokens) + (2 * len(query_tokens & leading_tokens))
        if score:
            scored.append((score, index, point))

    if not scored:
        return []
    scored.sort(key=lambda item: (-item[0], item[1]))
    best = scored[0][0]
    if best < 3:
        return []
    return [point for score, _index, point in scored if score == best]


def _focus_tokens(text: str) -> set[str]:
    stopwords = {
        "ban",
        "bao",
        "cac",
        "can",
        "cho",
        "co",
        "cua",
        "duoc",
        "duoi",
        "gi",
        "hoi",
        "khong",
        "khi",
        "la",
        "mot",
        "nao",
        "nguoi",
        "nhung",
        "phai",
        "quy",
        "quy dinh",
        "sau",
        "thi",
        "the",
        "trong",
        "tuoi",
        "ve",
        "voi",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]+", strip_accents(normalize_text(text)))
        if len(token) >= 3 and token not in stopwords
    }


def _strip_terminal_punctuation(text: str) -> str:
    return text.strip().rstrip(";.")


def _is_clause_list_question(query: str) -> bool:
    return any(
        term in query
        for term in [
            "bao gom",
            "cac truong hop",
            "gom nhung",
            "giay to",
            "hanh vi nao",
            "lam gi",
            "liet ke",
            "mang theo",
            "loai hinh",
            "nhung gi",
            "nhung noi",
            "nhung truong hop",
            "truong hop nao",
        ]
    )


def _numbered_article_items(lines: list[str]) -> tuple[str, list[tuple[str, str]]]:
    intro_lines: list[str] = []
    items: list[tuple[str, str]] = []
    current_number: str | None = None
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        match = re.match(r"^(\d+)\.\s+(.*)", stripped)
        if match:
            if current_number is not None:
                items.append((current_number, " ".join(current_lines).strip()))
            current_number = match.group(1)
            current_lines = [match.group(2).strip()]
        elif current_number is None:
            intro_lines.append(stripped)
        else:
            current_lines.append(stripped)

    if current_number is not None:
        items.append((current_number, " ".join(current_lines).strip()))
    return " ".join(intro_lines).strip(), items


def _asks_csgt_stop_basis_list(parsed: ParsedQuery, query: str) -> bool:
    return parsed.answer_mode == "ENUMERATION" or any(
        term in query for term in ["can cu nao", "khi nao", "truong hop nao", "nhung truong hop nao"]
    )


def _csgt_system_detection_query(query: str) -> bool:
    return any(
        term in query
        for term in [
            "camera",
            "cam thay",
            "coi cam",
            "du lieu",
            "he thong giam sat",
            "phuong tien thiet bi ky thuat",
            "thiet bi ky thuat",
            "thiet bi nghiep vu",
        ]
    )


def _driver_stop_reason_right_query(query: str) -> bool:
    return any(term in query for term in ["co quyen", "duoc biet", "thong bao", "ly do"]) and any(
        term in query for term in ["can cu dung", "ly do", "noi dung va ket qua"]
    )


def _csgt_technical_detection_citations() -> list[Citation]:
    citations: list[Citation] = []
    for clause in ["1", "2"]:
        extracted = _extract_clause_provision(LAW36_SOURCE, "67", clause)
        if extracted is None:
            continue
        article_title, clause_intro, points, source_text = extracted
        citations.append(
            _citation(
                f"L36_A67_K{clause}_DETECTION_METHOD",
                "36/2024/QH15",
                "Luật Trật tự, an toàn giao thông đường bộ",
                "67",
                article_title,
                clause,
                None,
                LAW36_SOURCE,
                source_text,
                "AUTHORITY_RULE",
            )
        )
    return citations


def _multi_reference_exact_answer(parsed: ParsedQuery, query: str) -> ChatResponse | None:
    if not parsed.article:
        return None
    if parsed.document_number != "168/2024/NĐ-CP" and "168" not in query:
        return None
    refs = _explicit_point_clause_refs(query)
    if len(refs) < 2:
        return None

    article = _extract_article(ND168_SOURCE, parsed.article)
    if article is None:
        return None
    article_title, article_lines = article

    citations: list[Citation] = []
    lines: list[str] = []
    for point, clause in refs:
        extracted = _extract_point_from_article(article_lines, clause, point)
        if extracted is None:
            return None
        clause_intro, point_text = extracted
        source_text = f"{clause}. {clause_intro} {point}) {point_text}".strip()
        citations.append(
            _citation(
                f"ND168_A{parsed.article}_K{clause}_P{point}_EXACT",
                "168/2024/NĐ-CP",
                "Nghị định số 168/2024/NĐ-CP",
                parsed.article,
                article_title,
                clause,
                point,
                ND168_SOURCE,
                source_text,
                "EXACT_REFERENCE",
            )
        )
        lines.append(
            f"- Điểm {point} khoản {clause} Điều {parsed.article}: {clause_intro} {point}) {point_text} [{short_ref(citations[-1])}]"
        )

    conclusion = "\n".join(lines)
    return _response(
        parsed,
        conclusion,
        citations,
        {"provision": "ND168_MULTI_EXACT_REFERENCE", "references": ",".join(f"{p}{c}" for p, c in refs)},
    )


def _explicit_point_clause_refs(query: str) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    patterns = [
        r"\bdiem\s+(?P<point>[a-z])\s+khoan\s+(?P<clause>\d+)\b",
        r"\bkhoan\s+(?P<clause>\d+)\s+diem\s+(?P<point>[a-z])\b",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, query):
            refs.append((match.group("point"), match.group("clause")))

    selected: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for ref in refs:
        if ref not in seen:
            selected.append(ref)
            seen.add(ref)
    return selected


def _extract_article(source_file, article: str) -> tuple[str, list[str]] | None:
    lines = source_file.read_text(encoding="utf-8").splitlines()
    start = None
    for index, line in enumerate(lines):
        normalized = strip_accents(normalize_text(line))
        if re.match(rf"^###\s+dieu\s+{re.escape(article)}\b", normalized):
            start = index
            break
    if start is None:
        return None

    end = len(lines)
    for index in range(start + 1, len(lines)):
        normalized = strip_accents(normalize_text(lines[index]))
        if re.match(r"^###\s+dieu\s+\d+\b", normalized):
            end = index
            break
    title = re.sub(r"^###\s*", "", lines[start]).strip()
    return title, lines[start + 1 : end]


def _extract_clause_provision(source_file, article: str, clause: str) -> tuple[str, str, list[tuple[str, str]], str] | None:
    article_data = _extract_article(source_file, article)
    if article_data is None:
        return None
    article_title, article_lines = article_data
    bounds = _clause_bounds(article_lines, clause)
    if bounds is None:
        return None
    clause_start, clause_end = bounds
    clause_intro = re.sub(rf"^{re.escape(clause)}\.\s*", "", article_lines[clause_start].strip()).strip()
    points = _extract_points(article_lines, clause_start + 1, clause_end)
    source_lines = [f"{clause}. {clause_intro}"]
    source_lines.extend(f"{point}) {text}" for point, text in points)
    return article_title, clause_intro, points, " ".join(source_lines)


def _extract_point_from_article(lines: list[str], clause: str, point: str) -> tuple[str, str] | None:
    bounds = _clause_bounds(lines, clause)
    if bounds is None:
        return None
    clause_start, clause_end = bounds

    clause_intro = re.sub(rf"^{re.escape(clause)}\.\s*", "", lines[clause_start].strip()).strip()
    point_start = None
    for index in range(clause_start + 1, clause_end):
        if _line_starts_with_point(lines[index], point):
            point_start = index
            break
    if point_start is None:
        return None

    point_end = clause_end
    for index in range(point_start + 1, clause_end):
        if re.match(r"^[a-zA-ZđĐ]\)\s+", lines[index].strip()):
            point_end = index
            break
    point_lines = [line.strip() for line in lines[point_start:point_end] if line.strip()]
    if not point_lines:
        return None
    point_text = re.sub(r"^[a-zA-ZđĐ]\)\s*", "", " ".join(point_lines)).strip()
    return clause_intro, point_text


def _clause_bounds(lines: list[str], clause: str) -> tuple[int, int] | None:
    clause_start = None
    for index, line in enumerate(lines):
        if re.match(rf"^{re.escape(clause)}\.\s+", line.strip()):
            clause_start = index
            break
    if clause_start is None:
        return None

    clause_end = len(lines)
    for index in range(clause_start + 1, len(lines)):
        if re.match(r"^\d+\.\s+", lines[index].strip()):
            clause_end = index
            break
    return clause_start, clause_end


def _extract_points(lines: list[str], start: int, end: int) -> list[tuple[str, str]]:
    points: list[tuple[str, str]] = []
    index = start
    while index < end:
        line = lines[index].strip()
        match = re.match(r"^([a-zA-ZđĐ])\)\s+(.*)", line)
        if not match:
            index += 1
            continue
        point = match.group(1).lower()
        point_lines = [match.group(2).strip()]
        index += 1
        while index < end and not re.match(r"^[a-zA-ZđĐ]\)\s+", lines[index].strip()):
            if lines[index].strip():
                point_lines.append(lines[index].strip())
            index += 1
        points.append((point, " ".join(point_lines).strip()))
    return points


def _line_starts_with_point(line: str, point: str) -> bool:
    stripped = line.strip()
    match = re.match(r"^([a-zA-ZđĐ])\)\s+", stripped)
    if not match:
        return False
    return strip_accents(match.group(1).lower()) == point


def _child_safety_amendment_answer(parsed: ParsedQuery, query: str) -> ChatResponse | None:
    if parsed.temporal_intent == "EFFECTIVE_DATE_LOOKUP":
        return None
    if "o to" not in query:
        return None
    if not any(term in query for term in ["tre em", "tre nho", "con ", "chau ", "1,35", "1.35", "1m35", "135"]):
        return None
    if not any(term in query for term in ["thiet bi an toan", "ghe an toan", "day dai an toan"]):
        return None

    effective = date(2026, 8, 15)
    query_date = _query_date(parsed)
    if query_date and query_date < effective:
        return None

    citations = [
        _citation(
            "ND238_A02_K1_STRUCTURED",
            "238/2026/NĐ-CP",
            "Sửa đổi, bổ sung một số điều của Nghị định 168/2024/NĐ-CP",
            "2",
            "Sửa đổi, bổ sung một số điểm, khoản của Điều 6",
            "1",
            None,
            ND238_SOURCE,
            '1. Bổ sung khoản 1a vào sau khoản 1 như sau: "1a. Phạt cảnh cáo đối với người điều khiển xe ô tô thực hiện hành vi chở trẻ em dưới 10 tuổi và chiều cao dưới 1,35 mét trên xe mà không sử dụng thiết bị an toàn phù hợp cho trẻ em theo quy định (trừ xe ô tô kinh doanh vận tải hành khách)."',
            "SANCTION",
        ),
        _citation(
            "ND238_A20_K1_STRUCTURED",
            "238/2026/NĐ-CP",
            "Sửa đổi, bổ sung một số điều của Nghị định 168/2024/NĐ-CP",
            "20",
            "Hiệu lực thi hành",
            "1",
            None,
            ND238_SOURCE,
            "1. Nghị định này có hiệu lực thi hành từ ngày 15 tháng 8 năm 2026.",
            "TEMPORAL_RULE",
        ),
    ]
    conclusion = (
        "Từ **15/08/2026**, người điều khiển ô tô chở trẻ em dưới 10 tuổi và chiều cao dưới 1,35 m mà không sử dụng thiết bị an toàn phù hợp cho trẻ em "
        "bị **phạt cảnh cáo**, trừ xe ô tô kinh doanh vận tải hành khách [238/2026/NĐ-CP, Điều 2, khoản 1; Điều 20, khoản 1]."
    )
    return _response(parsed, conclusion, citations, {"provision": "ND238_A02_K1_A20_K1"})


def _law36_child_safety_effective_date_answer(parsed: ParsedQuery, query: str) -> ChatResponse | None:
    if parsed.temporal_intent != "EFFECTIVE_DATE_LOOKUP":
        return None
    if parsed.document_number and parsed.document_number != "36/2024/QH15":
        return None
    if parsed.article != "10" or parsed.clause != "3":
        return None
    if not any(term in query for term in ["thiet bi an toan", "tre em", "tre nho", "o to"]):
        return None
    citation = _citation(
        "L36_A88_K2_STRUCTURED",
        "36/2024/QH15",
        "Luật Trật tự, an toàn giao thông đường bộ",
        "88",
        "Hiệu lực thi hành",
        "2",
        None,
        LAW36_SOURCE,
        "2. Khoản 3 Điều 10 của Luật này có hiệu lực thi hành từ ngày 01 tháng 01 năm 2026.",
        "TEMPORAL_RULE",
    )
    asked_date = _query_date(parsed)
    prefix = ""
    if asked_date:
        prefix = "Có. " if asked_date >= date(2026, 1, 1) else "Chưa. "
    conclusion = (
        f"{prefix}Quy định tại **khoản 3 Điều 10** Luật Trật tự, an toàn giao thông đường bộ "
        "có hiệu lực từ **ngày 01/01/2026** [36/2024/QH15: Điều 88, khoản 2]."
    )
    return _response(parsed, conclusion, [citation], {"provision": "L36_A88_K2"})


def _license_c1_scope_answer(parsed: ParsedQuery, query: str) -> ChatResponse | None:
    if "c1" not in query:
        return None
    if not any(term in query for term in ["khoi luong", "kg", "tan", "tai", "xe nao"]):
        return None
    citation = _citation(
        "L36_A57_K1_PD_STRUCTURED",
        "36/2024/QH15",
        "Luật Trật tự, an toàn giao thông đường bộ",
        "57",
        "Giấy phép lái xe",
        "1",
        "đ",
        LAW36_SOURCE,
        "đ) Hạng C1 cấp cho người lái xe ô tô tải và ô tô chuyên dùng có khối lượng toàn bộ theo thiết kế trên 3.500 kg đến 7.500 kg; các loại xe ô tô tải quy định cho giấy phép lái xe hạng C1 kéo rơ moóc có khối lượng toàn bộ theo thiết kế đến 750 kg; các loại xe quy định cho giấy phép lái xe hạng B;",
        "ELIGIBILITY",
    )
    conclusion = (
        "GPLX hạng C1 áp dụng cho ô tô tải và ô tô chuyên dùng có khối lượng toàn bộ theo thiết kế **trên 3.500 kg đến 7.500 kg**; "
        "đồng thời bao gồm ô tô tải hạng C1 kéo rơ moóc đến 750 kg và các loại xe của hạng B [36/2024/QH15: Điều 57, khoản 1, điểm đ]."
    )
    return _response(parsed, conclusion, [citation], {"provision": "L36_A57_K1_PD"})


def _license_validity_answer(parsed: ParsedQuery, query: str) -> ChatResponse | None:
    if "thoi han" not in query and "bao lau" not in query:
        return None
    if "giay phep lai xe" not in query and "gplx" not in query and "bang" not in query:
        return None
    if "c1" in query:
        return None
    class_patterns = [
        r"\b(?:hang|bang)\s+c\b",
        r"\b(?:hang|bang)\s+d\b",
        r"\bd1\b",
        r"\bd2\b",
        r"\bbe\b",
        r"\bc1e\b",
        r"\bce\b",
        r"\bd1e\b",
        r"\bd2e\b",
        r"\b(?:hang|bang)\s+de\b",
    ]
    if not any(re.search(pattern, query) for pattern in class_patterns):
        return None
    citation = _citation(
        "L36_A57_K5_PC_STRUCTURED",
        "36/2024/QH15",
        "Luật Trật tự, an toàn giao thông đường bộ",
        "57",
        "Giấy phép lái xe",
        "5",
        "c",
        LAW36_SOURCE,
        "c) Giấy phép lái xe các hạng C, D1, D2, D, BE, C1E, CE, D1E, D2E và DE có thời hạn 05 năm kể từ ngày cấp.",
        "ELIGIBILITY",
    )
    conclusion = (
        "GPLX các hạng C, D1, D2, D, BE, C1E, CE, D1E, D2E và DE có thời hạn **05 năm kể từ ngày cấp** [36/2024/QH15: Điều 57, khoản 5, điểm c]."
    )
    return _response(parsed, conclusion, [citation], {"provision": "L36_A57_K5_PC"})


def _license_points_answer(parsed: ParsedQuery, query: str) -> ChatResponse | None:
    if not any(term in query for term in ["giay phep lai xe", "gplx", "bang lai"]):
        return None
    total_loss_query = any(term in query for term in ["bi tru het diem", "tru het diem", "tru sach diem", "tru sach point"])
    specific_violation_query = bool(parsed.behavior_code or parsed.violations) or any(
        term in query
        for term in [
            "vuot den",
            "den do",
            "quay dau",
            "nong do con",
            "qua toc do",
            "vuot toc do",
            "su dung dien thoai",
            "cam dien thoai",
            "phat bao nhieu",
        ]
    )
    if specific_violation_query and not total_loss_query:
        return None
    if "chua bi tru het diem" in query or ("khong bi tru diem" in query and "12 thang" in query):
        citation = _citation(
            "L36_A58_K2_STRUCTURED",
            "36/2024/QH15",
            "Luật Trật tự, an toàn giao thông đường bộ",
            "58",
            "Điểm của giấy phép lái xe",
            "2",
            None,
            LAW36_SOURCE,
            "2. Giấy phép lái xe chưa bị trừ hết điểm và không bị trừ điểm trong thời hạn 12 tháng từ ngày bị trừ điểm gần nhất thì được phục hồi đủ 12 điểm.",
            "LICENSE_POINT",
        )
        conclusion = (
            "Nếu GPLX **chưa bị trừ hết điểm** và **không bị trừ điểm trong 12 tháng** kể từ ngày bị trừ điểm gần nhất, GPLX được phục hồi đủ **12 điểm** [36/2024/QH15: Điều 58, khoản 2]."
        )
        return _response(parsed, conclusion, [citation], {"provision": "L36_A58_K2"})
    if total_loss_query:
        citation = _citation(
            "L36_A58_K3_STRUCTURED",
            "36/2024/QH15",
            "Luật Trật tự, an toàn giao thông đường bộ",
            "58",
            "Điểm của giấy phép lái xe",
            "3",
            None,
            LAW36_SOURCE,
            "3. Trường hợp giấy phép lái xe bị trừ hết điểm thì người có giấy phép lái xe không được điều khiển phương tiện tham gia giao thông đường bộ theo giấy phép lái xe đó. Sau thời hạn ít nhất là 06 tháng kể từ ngày bị trừ hết điểm, người có giấy phép lái xe được tham gia kiểm tra nội dung kiến thức pháp luật về trật tự, an toàn giao thông đường bộ theo quy định tại khoản 7 Điều 61 của Luật này do lực lượng Cảnh sát giao thông tổ chức, có kết quả đạt yêu cầu thì được phục hồi đủ 12 điểm.",
            "LICENSE_POINT",
        )
        conclusion = (
            "Khi GPLX bị trừ hết điểm, người có GPLX không được điều khiển phương tiện theo GPLX đó. Sau **ít nhất 06 tháng** từ ngày bị trừ hết điểm, người đó được dự kiểm tra kiến thức pháp luật; nếu đạt yêu cầu thì được phục hồi đủ **12 điểm** [36/2024/QH15: Điều 58, khoản 3]."
        )
        return _response(parsed, conclusion, [citation], {"provision": "L36_A58_K3"})
    if "diem" in query and any(term in query for term in ["bao nhieu", "may diem", "12 diem"]):
        citation = _citation(
            "L36_A58_K1_STRUCTURED",
            "36/2024/QH15",
            "Luật Trật tự, an toàn giao thông đường bộ",
            "58",
            "Điểm của giấy phép lái xe",
            "1",
            None,
            LAW36_SOURCE,
            "1. Điểm của giấy phép lái xe được dùng để quản lý việc chấp hành pháp luật về trật tự, an toàn giao thông đường bộ của người lái xe trên hệ thống cơ sở dữ liệu về trật tự, an toàn giao thông đường bộ, bao gồm 12 điểm.",
            "LICENSE_POINT",
        )
        conclusion = "Mỗi giấy phép lái xe có **12 điểm** để quản lý việc chấp hành pháp luật về trật tự, an toàn giao thông đường bộ [36/2024/QH15: Điều 58, khoản 1]."
        return _response(parsed, conclusion, [citation], {"provision": "L36_A58_K1"})
    return None


def _priority_vehicle_order_answer(parsed: ParsedQuery, query: str) -> ChatResponse | None:
    if "xe uu tien" not in query:
        return None
    if not any(term in query for term in ["thu tu", "di truoc", "qua duong giao nhau", "uu tien tu"]):
        return None
    extracted = _extract_clause_provision(LAW36_SOURCE, "27", "2")
    if extracted is None:
        return None
    article_title, clause_intro, points, source_text = extracted
    citation = _citation(
        "L36_A27_K2_STRUCTURED",
        "36/2024/QH15",
        "Luật Trật tự, an toàn giao thông đường bộ",
        "27",
        article_title,
        "2",
        None,
        LAW36_SOURCE,
        source_text,
        "TRAFFIC_RULE",
    )
    conclusion = f"{_format_clause_answer(clause_intro, points)} [{short_ref(citation)}]."
    return _response(parsed, conclusion, [citation], {"provision": "L36_A27_K2"})


def _priority_vehicle_rights_answer(parsed: ParsedQuery, query: str) -> ChatResponse | None:
    if "xe uu tien" not in query:
        return None
    if not any(term in query for term in ["quyen", "duoc phep", "khong bi han che", "den giao thong", "nguoc chieu"]):
        return None
    citation = _citation(
        "L36_A27_K4_STRUCTURED",
        "36/2024/QH15",
        "Luật Trật tự, an toàn giao thông đường bộ",
        "27",
        "Xe ưu tiên",
        "4",
        None,
        LAW36_SOURCE,
        "4. Xe ưu tiên quy định tại các điểm a, b, c và d khoản 2 Điều này không bị hạn chế tốc độ; được phép đi không phụ thuộc vào tín hiệu đèn giao thông, đi vào đường ngược chiều, các đường khác có thể đi được; riêng đối với đường cao tốc, chỉ được đi ngược chiều trên làn dừng xe khẩn cấp; phải tuân theo hiệu lệnh của người điều khiển giao thông, biển báo hiệu tạm thời.",
        "TRAFFIC_RULE",
    )
    conclusion = (
        "Xe ưu tiên thuộc các điểm a, b, c, d khoản 2 Điều 27 không bị hạn chế tốc độ, được đi không phụ thuộc tín hiệu đèn giao thông, được đi vào đường ngược chiều và các đường khác có thể đi được; "
        "riêng trên cao tốc chỉ được đi ngược chiều trên làn dừng xe khẩn cấp và vẫn phải tuân theo hiệu lệnh người điều khiển giao thông, biển báo hiệu tạm thời [36/2024/QH15: Điều 27, khoản 4]."
    )
    return _response(parsed, conclusion, [citation], {"provision": "L36_A27_K4"})


def _plate_auction_starting_price_answer(parsed: ParsedQuery, query: str) -> ChatResponse | None:
    if "bien so" not in query or "gia khoi diem" not in query:
        return None
    citation = _citation(
        "L36_A37_K2_STRUCTURED",
        "36/2024/QH15",
        "Luật Trật tự, an toàn giao thông đường bộ",
        "37",
        "Đấu giá biển số xe",
        "2",
        None,
        LAW36_SOURCE,
        "2. Giá khởi điểm của một biển số xe ô tô đưa ra đấu giá không thấp hơn 40 triệu đồng; giá khởi điểm một biển số xe mô tô, xe gắn máy đưa ra đấu giá không thấp hơn 05 triệu đồng.",
        "FEE_RULE",
    )
    if "o to" in query:
        conclusion = "Giá khởi điểm của một biển số xe ô tô đưa ra đấu giá **không thấp hơn 40 triệu đồng** [36/2024/QH15: Điều 37, khoản 2]."
    elif "mo to" in query or "xe gan may" in query or "xe may" in query:
        conclusion = "Giá khởi điểm của một biển số xe mô tô, xe gắn máy đưa ra đấu giá **không thấp hơn 05 triệu đồng** [36/2024/QH15: Điều 37, khoản 2]."
    else:
        conclusion = "Giá khởi điểm biển số đưa ra đấu giá là **không thấp hơn 40 triệu đồng** với biển số ô tô và **không thấp hơn 05 triệu đồng** với biển số mô tô, xe gắn máy [36/2024/QH15: Điều 37, khoản 2]."
    return _response(parsed, conclusion, [citation], {"provision": "L36_A37_K2"})


def _road_database_answer(parsed: ParsedQuery, query: str) -> ChatResponse | None:
    if "co so du lieu duong bo" not in query:
        return None
    if not any(term in query for term in ["bao gom", "gom nhung", "nhung loai", "du lieu nao"]):
        return None
    citation = _citation(
        "L35_A06_K1_STRUCTURED",
        "35/2024/QH15",
        "Luật Đường bộ",
        "6",
        "Cơ sở dữ liệu đường bộ",
        "1",
        None,
        LAW35_SOURCE,
        "1. Cơ sở dữ liệu đường bộ được thiết kế, xây dựng, vận hành theo Khung kiến trúc tổng thể quốc gia số, bao gồm: a) cơ sở dữ liệu về quy hoạch mạng lưới đường bộ, quy hoạch kết cấu hạ tầng đường bộ; b) cơ sở dữ liệu về tình hình đầu tư, xây dựng kết cấu hạ tầng đường bộ; c) cơ sở dữ liệu về quản lý, vận hành, khai thác, bảo trì, bảo vệ kết cấu hạ tầng đường bộ; d) cơ sở dữ liệu thanh toán điện tử giao thông đường bộ; đ) cơ sở dữ liệu về hoạt động vận tải bằng xe ô tô, trừ một số cơ sở dữ liệu chuyên ngành về hành trình, hình ảnh người lái xe và quản lý thời gian điều khiển.",
        "DATA_RULE",
    )
    conclusion = (
        "Cơ sở dữ liệu đường bộ bao gồm các nhóm dữ liệu về: quy hoạch mạng lưới và kết cấu hạ tầng đường bộ; đầu tư, xây dựng kết cấu hạ tầng đường bộ; "
        "quản lý, vận hành, khai thác, bảo trì, bảo vệ kết cấu hạ tầng đường bộ; thanh toán điện tử giao thông đường bộ; và hoạt động vận tải bằng xe ô tô, trừ các cơ sở dữ liệu chuyên ngành được loại trừ trong điều luật [35/2024/QH15: Điều 6, khoản 1]."
    )
    return _response(parsed, conclusion, [citation], {"provision": "L35_A06_K1"})


def _national_roads_not_decentralized_answer(parsed: ParsedQuery, query: str) -> ChatResponse | None:
    if "quoc lo" not in query or "khong phan cap" not in query:
        return None
    citation = _citation(
        "ND165_A04_K2_STRUCTURED",
        "165/2024/NĐ-CP",
        "Nghị định hướng dẫn Luật Đường bộ",
        "4",
        "Phân cấp quản lý quốc lộ",
        "2",
        None,
        ND165_SOURCE,
        "2. Các quốc lộ không phân cấp, bao gồm: a) Đường cao tốc do Bộ Giao thông vận tải quản lý; b) Quốc lộ 1, đường Hồ Chí Minh để kết nối các tuyến quốc lộ và các tuyến đường bộ khác theo chiều dọc đất nước; c) Quốc lộ có yêu cầu đặc biệt về bảo đảm quốc phòng, an ninh; d) Tuyến, đoạn tuyến quốc lộ Nhà nước đã giao doanh nghiệp nhà nước đầu tư xây dựng, quản lý, vận hành, khai thác, bảo trì; đ) Các trường hợp khác do Thủ tướng Chính phủ quyết định.",
        "ADMIN_RULE",
    )
    conclusion = (
        "Các quốc lộ **không phân cấp** gồm: đường cao tốc do Bộ Giao thông vận tải quản lý; Quốc lộ 1 và đường Hồ Chí Minh dùng để kết nối dọc đất nước; quốc lộ có yêu cầu đặc biệt về quốc phòng, an ninh; "
        "tuyến/đoạn tuyến quốc lộ Nhà nước đã giao doanh nghiệp nhà nước đầu tư, quản lý, vận hành, khai thác, bảo trì; và các trường hợp khác do Thủ tướng Chính phủ quyết định [165/2024/NĐ-CP: Điều 4, khoản 2]."
    )
    return _response(parsed, conclusion, [citation], {"provision": "ND165_A04_K2"})


def _query_date(parsed: ParsedQuery) -> date | None:
    raw = parsed.event_date or parsed.legal_effective_date or parsed.as_of_date
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw))
    except ValueError:
        return None


def _format_date_vi(value: date) -> str:
    return f"{value.day:02d}/{value.month:02d}/{value.year}"


def _citation(
    chunk_id: str,
    document_number: str,
    document_title: str,
    article: str,
    article_title: str,
    clause: str | None,
    point: str | None,
    source_file,
    text: str,
    rule_function: str,
) -> Citation:
    return Citation(
        chunk_id=chunk_id,
        chunk_type="STRUCTURED_PROVISION",
        document_number=document_number,
        document_title=document_title,
        article=article,
        article_title=article_title,
        clause=clause,
        point=point,
        source_file=source_file.as_posix(),
        text=text,
        rule_function=rule_function,
        coverage_status="COMPLETE",
        source_quality="STRUCTURED_PROVISION",
    )


def _response(
    parsed: ParsedQuery,
    conclusion: str,
    citations: list[Citation],
    debug_fact: dict[str, str],
) -> ChatResponse:
    return ChatResponse(
        answer=_normalize_inline_refs(conclusion, citations),
        citations=citations,
        answerable=True,
        debug={"parsed_query": parsed.model_dump(), "structured_fact": debug_fact},
    )


def _unanswerable_response(parsed: ParsedQuery, answer: str, debug_fact: dict[str, str]) -> ChatResponse:
    return ChatResponse(
        answer=answer,
        citations=[],
        answerable=False,
        debug={"parsed_query": parsed.model_dump(), "structured_fact": debug_fact},
    )


def _source_file_for_reference(document_number: str, article: str) -> object | None:
    if document_number == "35/2024/QH15":
        return LAW35_SOURCE
    if document_number == "36/2024/QH15":
        return LAW36_PART1_SOURCE if article.isdigit() and int(article) <= 23 else LAW36_SOURCE
    if document_number == "165/2024/NĐ-CP":
        return ND165_SOURCE
    if document_number == "168/2024/NĐ-CP":
        return ND168_SOURCE
    if document_number == "238/2026/NĐ-CP":
        return ND238_SOURCE
    return None


def _ref(citation: Citation) -> str:
    return short_ref(citation)


def _normalize_inline_refs(answer: str, citations: list[Citation]) -> str:
    for citation in citations:
        if not citation.document_number or not citation.article:
            continue
        article = re.escape(citation.article)
        clause = re.escape(citation.clause) if citation.clause else None
        point = re.escape(citation.point) if citation.point else None
        patterns = []
        if clause and point:
            patterns.append(
                rf"\[{re.escape(citation.document_number)}:\s*Điều\s+{article}\s*,?\s*(?:khoản|Khoản)\s+{clause}\s*,?\s*(?:điểm|Điểm)\s+{point}\]"
            )
        if clause:
            patterns.append(
                rf"\[{re.escape(citation.document_number)}:\s*Điều\s+{article}\s*,?\s*(?:khoản|Khoản)\s+{clause}\]"
            )
        patterns.append(rf"\[{re.escape(citation.document_number)}:\s*Điều\s+{article}\]")
        for pattern in patterns:
            answer = re.sub(pattern, f"[{_ref(citation)}]", answer)
    return normalize_inline_legal_refs(answer, citations)
