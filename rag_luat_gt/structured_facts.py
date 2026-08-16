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
        _multi_reference_exact_answer,
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
    return any(term in query for term in ["ruou", "bia", "nong do con"]) and any(
        term in query for term in ["lai xe", "dieu khien", "duoc phep", "muc"]
    )


def _phone_while_driving_query(query: str) -> bool:
    if any(term in query for term in ["phat", "muc phat", "tru diem", "xu phat"]):
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
            f"- Điểm {point} khoản {clause} Điều {parsed.article}: {clause_intro} {point}) {point_text}"
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
    conclusion = (
        "Quy định tại **khoản 3 Điều 10** Luật Trật tự, an toàn giao thông đường bộ có hiệu lực từ **ngày 01/01/2026** [36/2024/QH15: Điều 88, khoản 2]."
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
    citation = _citation(
        "L36_A27_K2_STRUCTURED",
        "36/2024/QH15",
        "Luật Trật tự, an toàn giao thông đường bộ",
        "27",
        "Xe ưu tiên",
        "2",
        None,
        LAW36_SOURCE,
        "2. Xe ưu tiên được quyền đi trước xe khác khi qua đường giao nhau từ bất kỳ hướng nào tới theo thứ tự ưu tiên từ trên xuống dưới: a) xe chữa cháy; b) xe quân sự, công an, kiểm sát làm nhiệm vụ khẩn cấp; đoàn xe có Cảnh sát giao thông dẫn đường; c) xe cứu thương; d) xe hộ đê, xe cứu nạn, cứu hộ, khắc phục sự cố thiên tai, dịch bệnh hoặc tình trạng khẩn cấp.",
        "TRAFFIC_RULE",
    )
    conclusion = (
        "Thứ tự xe ưu tiên được quyền đi trước khi qua đường giao nhau là: **xe chữa cháy**; **xe quân sự, công an, kiểm sát làm nhiệm vụ khẩn cấp và đoàn xe có CSGT dẫn đường**; **xe cứu thương**; "
        "**xe hộ đê, xe cứu nạn/cứu hộ/khắc phục sự cố thiên tai, dịch bệnh hoặc tình trạng khẩn cấp** [36/2024/QH15: Điều 27, khoản 2]."
    )
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
