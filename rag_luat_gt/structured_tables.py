from __future__ import annotations

import re
from dataclasses import dataclass

from rag_luat_gt.config import MARKDOWN_DIR
from rag_luat_gt.citation_format import inline_ref, normalize_inline_legal_refs
from rag_luat_gt.schemas import ChatResponse, Citation, ParsedQuery
from rag_luat_gt.text import normalize_text, strip_accents


SAFE_DISTANCE_SOURCE = MARKDOWN_DIR / "38-2024-TT-BGTVT_Toc-do-Khoang-cach-an-toan.md"


@dataclass(frozen=True)
class DistanceRow:
    label: str
    distance_m: int
    lower: float | None = None
    upper: float | None = None
    lower_inclusive: bool = False
    upper_inclusive: bool = True

    def matches(self, speed: float) -> bool:
        if self.lower is not None:
            if self.lower_inclusive and speed < self.lower:
                return False
            if not self.lower_inclusive and speed <= self.lower:
                return False
        if self.upper is not None:
            if self.upper_inclusive and speed > self.upper:
                return False
            if not self.upper_inclusive and speed >= self.upper:
                return False
        return True


def build_structured_table_answer(parsed: ParsedQuery) -> ChatResponse | None:
    query = strip_accents(normalize_text(parsed.query))
    speed_rule = _speed_rule_answer(parsed, query)
    if speed_rule:
        return speed_rule

    if "khoang cach" not in query or "toc do" not in query:
        return None
    speed = _speed_kmh(query)
    if speed is None:
        return None

    rows = _safe_distance_rows()
    if not rows:
        return None

    citation = _safe_distance_citation(rows)
    row = next((item for item in rows if item.matches(speed)), None)
    if row:
        answer = (
            f"Với tốc độ lưu hành {speed:g} km/h trong điều kiện mặt đường khô ráo, tầm nhìn bảo đảm, "
            f"khoảng cách an toàn tối thiểu với xe liền trước là {row.distance_m} m "
            f"{inline_ref(citation)}."
        )
        return ChatResponse(
            answer=answer,
            citations=[citation],
            debug={"parsed_query": parsed.model_dump(), "structured_table": {"table": "TT38_ARTICLE_11_TABLE_3"}},
        )

    if speed < 60:
        answer = (
            f"Với tốc độ dưới 60 km/h như {speed:g} km/h, Thông tư 38/2024/TT-BGTVT không ấn định một số mét cố định "
            "trong Bảng 3; người lái xe phải chủ động giữ khoảng cách an toàn phù hợp với xe liền trước theo mật độ "
            f"phương tiện, tình hình giao thông thực tế để bảo đảm an toàn {inline_ref(citation)}."
        )
        return ChatResponse(
            answer=answer,
            citations=[citation],
            debug={"parsed_query": parsed.model_dump(), "structured_table": {"table": "TT38_ARTICLE_11_TABLE_3"}},
        )
    return None


def _speed_rule_answer(parsed: ParsedQuery, query: str) -> ChatResponse | None:
    if "toc do" not in query and not any(term in query for term in ["km/h", "kmh", "chay toi da", "chay toi thieu"]):
        return None
    if "xe gan may" in query and (
        "cao toc" not in query
        or any(term in query for term in ["khong di tren cao toc", "khong tren cao toc", "tru duong cao toc", "ngoai cao toc"])
    ):
        citation = _speed_rule_citation(
            chunk_id="TT38_A07_STRUCTURED",
            article="7",
            article_title="Tốc độ khai thác tối đa cho phép đối với xe máy chuyên dùng, xe gắn máy và các loại xe tương tự tham gia giao thông trên đường bộ (trừ đường cao tốc)",
            clause=None,
            text=(
                "Điều 7. Tốc độ khai thác tối đa cho phép đối với xe máy chuyên dùng, xe gắn máy "
                "và các loại xe tương tự tham gia giao thông trên đường bộ (trừ đường cao tốc)\n\n"
                "Xe máy chuyên dùng, xe gắn máy và các loại xe tương tự khi tham gia giao thông, "
                "tốc độ khai thác tối đa là 40 km/h."
            ),
        )
        return _table_response(
            parsed,
            "Xe gắn máy tham gia giao thông trên đường bộ, trừ đường cao tốc, có tốc độ khai thác tối đa là **40 km/h** [38/2024/TT-BGTVT, Điều 7].",
            citation,
            {"provision": "TT38_A07"},
        )

    if "cao toc" not in query:
        return None
    if any(term in query for term in ["toi thieu", "thap nhat", "min"]):
        citation = _speed_rule_citation(
            chunk_id="TT38_A09_K3_STRUCTURED",
            article="9",
            article_title="Tốc độ khai thác tối đa, tốc độ khai thác tối thiểu cho phép đối với các loại xe cơ giới, xe máy chuyên dùng trên đường cao tốc",
            clause="3",
            text=(
                "Điều 9. Tốc độ khai thác tối đa, tốc độ khai thác tối thiểu cho phép đối với các loại xe cơ giới, "
                "xe máy chuyên dùng trên đường cao tốc\n\n"
                "3. Tốc độ khai thác tối thiểu cho phép trên đường cao tốc là 60 km/h. "
                "Trường hợp đường cao tốc có tốc độ thiết kế 60 km/h thì tốc độ khai thác tối thiểu "
                "thực hiện theo phương án tổ chức giao thông được cấp có thẩm quyền phê duyệt."
            ),
        )
        return _table_response(
            parsed,
            (
                "Tốc độ khai thác tối thiểu cho phép trên đường cao tốc là **60 km/h**. "
                "Nếu đường cao tốc có tốc độ thiết kế 60 km/h thì tốc độ tối thiểu thực hiện theo phương án tổ chức giao thông được phê duyệt [38/2024/TT-BGTVT, Điều 9, khoản 3]."
            ),
            citation,
            {"provision": "TT38_A09_K3"},
        )
    if any(term in query for term in ["toi da", "cao nhat", "max"]):
        citation = _speed_rule_citation(
            chunk_id="TT38_A09_K2_STRUCTURED",
            article="9",
            article_title="Tốc độ khai thác tối đa, tốc độ khai thác tối thiểu cho phép đối với các loại xe cơ giới, xe máy chuyên dùng trên đường cao tốc",
            clause="2",
            text=(
                "Điều 9. Tốc độ khai thác tối đa, tốc độ khai thác tối thiểu cho phép đối với các loại xe cơ giới, "
                "xe máy chuyên dùng trên đường cao tốc\n\n"
                "1. Đường cao tốc phải được đặt biển báo tốc độ khai thác tối đa, tốc độ khai thác tối thiểu.\n"
                "2. Tốc độ khai thác tối đa cho phép trên đường cao tốc là 120 km/h."
            ),
        )
        return _table_response(
            parsed,
            (
                "Tốc độ khai thác tối đa cho phép trên đường cao tốc là **120 km/h**; đường cao tốc phải có biển báo tốc độ khai thác tối đa và tối thiểu [38/2024/TT-BGTVT, Điều 9, khoản 1-2]."
            ),
            citation,
            {"provision": "TT38_A09_K2"},
        )
    return None


def _table_response(
    parsed: ParsedQuery,
    conclusion: str,
    citation: Citation,
    debug_fact: dict[str, str],
) -> ChatResponse:
    answer = (
        _normalize_inline_ref(conclusion, citation)
    )
    return ChatResponse(
        answer=answer,
        citations=[citation],
        debug={"parsed_query": parsed.model_dump(), "structured_table": debug_fact},
    )


def _normalize_inline_ref(answer: str, citation: Citation) -> str:
    if not citation.document_number or not citation.article:
        return answer
    article = re.escape(citation.article)
    clause = re.escape(citation.clause) if citation.clause else None
    patterns = [rf"\[{re.escape(citation.document_number)}:\s*Điều\s+{article}\]"]
    if clause:
        patterns.append(
            rf"\[{re.escape(citation.document_number)}:\s*Điều\s+{article}\s*,?\s*(?:khoản|Khoản)\s+{clause}\]"
        )
    for pattern in patterns:
        answer = re.sub(pattern, inline_ref(citation), answer)
    return normalize_inline_legal_refs(answer, [citation])


def _speed_rule_citation(
    *,
    chunk_id: str,
    article: str,
    article_title: str,
    clause: str | None,
    text: str,
) -> Citation:
    return Citation(
        chunk_id=chunk_id,
        chunk_type="STRUCTURED_PROVISION",
        document_number="38/2024/TT-BGTVT",
        document_title="Quy định về tốc độ và khoảng cách an toàn",
        article=article,
        article_title=article_title,
        clause=clause,
        source_file=SAFE_DISTANCE_SOURCE.as_posix(),
        text=text,
        rule_function="TRAFFIC_RULE",
        coverage_status="COMPLETE",
        source_quality="STRUCTURED_PROVISION",
    )


def _speed_kmh(query: str) -> float | None:
    match = re.search(r"\b(\d+(?:[,.]\d+)?)\s*(?:km/h|kmh)\b", query)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def _safe_distance_rows() -> list[DistanceRow]:
    if not SAFE_DISTANCE_SOURCE.exists():
        return []
    lines = SAFE_DISTANCE_SOURCE.read_text(encoding="utf-8-sig").splitlines()
    start = next((index for index, line in enumerate(lines) if "Bảng 3. Khoảng cách an toàn" in line), None)
    if start is None:
        return []
    rows: list[DistanceRow] = []
    for line in lines[start + 1 :]:
        if rows and not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2 or "Tốc độ" in cells[0] or set(cells[0]) <= {"-", " "}:
            continue
        distance = re.search(r"\d+", cells[1])
        if not distance:
            continue
        interval = _parse_speed_cell(cells[0])
        if interval:
            rows.append(
                DistanceRow(
                    label=interval.label,
                    distance_m=int(distance.group(0)),
                    lower=interval.lower,
                    upper=interval.upper,
                    lower_inclusive=interval.lower_inclusive,
                    upper_inclusive=interval.upper_inclusive,
                )
            )
    return rows


def _parse_speed_cell(cell: str) -> DistanceRow | None:
    text = strip_accents(normalize_text(cell)).replace("≤", "<=")
    exact = re.search(r"v\s*=\s*(\d+(?:[,.]\d+)?)", text)
    if exact:
        value = float(exact.group(1).replace(",", "."))
        return DistanceRow(label=cell, distance_m=0, lower=value, upper=value, lower_inclusive=True, upper_inclusive=True)
    interval = re.search(r"(\d+(?:[,.]\d+)?)\s*<\s*v\s*<=\s*(\d+(?:[,.]\d+)?)", text)
    if interval:
        return DistanceRow(
            label=cell,
            distance_m=0,
            lower=float(interval.group(1).replace(",", ".")),
            upper=float(interval.group(2).replace(",", ".")),
            lower_inclusive=False,
            upper_inclusive=True,
        )
    return None


def _safe_distance_citation(rows: list[DistanceRow]) -> Citation:
    table = "\n".join(f"| {row.label} | {row.distance_m} |" for row in rows)
    text = (
        "Điều 11. Khoảng cách an toàn giữa hai xe khi tham gia giao thông trên đường bộ\n\n"
        "Bảng 3. Khoảng cách an toàn ứng với tốc độ lưu hành\n"
        "| Tốc độ lưu hành (V km/h) | Khoảng cách an toàn (m) |\n"
        f"{table}\n\n"
        "Khi điều khiển xe chạy với tốc độ dưới 60 km/h, người lái xe, người điều khiển xe máy chuyên dùng phải "
        "chủ động giữ khoảng cách an toàn phù hợp với xe chạy liền trước xe của mình."
    )
    return Citation(
        chunk_id="TT38_A11_TABLE_3",
        chunk_type="STRUCTURED_TABLE",
        document_number="38/2024/TT-BGTVT",
        document_title="Quy định về tốc độ và khoảng cách an toàn",
        article="11",
        article_title="Khoảng cách an toàn giữa hai xe khi tham gia giao thông trên đường bộ",
        clause="2",
        point="a",
        source_file=SAFE_DISTANCE_SOURCE.as_posix(),
        text=text,
        rule_function="TRAFFIC_RULE",
        coverage_status="COMPLETE",
        source_quality="STRUCTURED_TABLE",
    )
