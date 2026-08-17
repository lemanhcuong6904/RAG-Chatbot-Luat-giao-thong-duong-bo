from __future__ import annotations

from datetime import date

from rag_luat_gt.retrieval.query_parser import parse_query
from rag_luat_gt.schemas import ChatRequest
from rag_luat_gt.structured_facts import build_structured_fact_answer


def _answer(query: str, *, event_date: date | None = None):
    parsed = parse_query(ChatRequest(query=query, event_date=event_date))
    response = build_structured_fact_answer(parsed)
    assert response is not None
    return response


def test_child_safety_amendment_after_effective_date() -> None:
    response = _answer(
        "Tu 15/08/2026, o to cho tre em duoi 10 tuoi cao duoi 1,35m khong co thiet bi an toan bi phat the nao?",
        event_date=date(2026, 8, 15),
    )

    assert "phạt cảnh cáo" in response.answer
    assert "15/08/2026" in response.answer
    assert {citation.document_number for citation in response.citations} == {"238/2026/NĐ-CP"}


def test_license_points_are_not_blocked_by_bang_lai_word() -> None:
    response = _answer("Một bằng lái xe có bao nhiêu điểm?")

    assert "12 điểm" in response.answer
    assert response.citations[0].document_number == "36/2024/QH15"
    assert response.citations[0].article == "58"


def test_license_points_restore_after_twelve_months() -> None:
    response = _answer("GPLX chưa bị trừ hết điểm và không bị trừ điểm trong 12 tháng thì sao?")

    assert "phục hồi đủ **12 điểm**" in response.answer
    assert response.citations[0].clause == "2"


def test_license_points_after_all_points_deducted() -> None:
    response = _answer("Bị trừ hết điểm bằng lái thì sau bao lâu mới được kiểm tra để phục hồi?")

    assert "ít nhất 06 tháng" in response.answer
    assert response.citations[0].clause == "3"


def test_license_point_fact_does_not_shadow_specific_penalty_query() -> None:
    parsed = parse_query(ChatRequest(query="Xe máy vượt đèn đỏ bị trừ bao nhiêu điểm giấy phép lái xe?"))

    assert build_structured_fact_answer(parsed) is None


def test_multi_exact_reference_returns_all_requested_points() -> None:
    response = _answer(
        "Diem b khoan 9 va diem b khoan 16 Dieu 6 Nghi dinh 168/2024/ND-CP quy dinh gi ve oto vuot den do?"
    )

    refs = {(citation.article, citation.clause, citation.point) for citation in response.citations}
    assert ("6", "9", "b") in refs
    assert ("6", "16", "b") in refs
    assert "18.000.000" in response.answer
    assert "04 điểm" in response.answer


def test_structured_traffic_rule_facts_avoid_sanction_noise() -> None:
    slow = _answer("Xe chạy chậm hơn các xe khác thì nên đi ở phía nào của đường?")
    overtaking = _answer("Những trường hợp nào không được vượt xe?")
    high_beam = _answer("Khi nào phải tắt đèn chiếu xa và chuyển sang đèn chiếu gần?")
    transport = _answer("Kinh doanh vận tải hành khách bằng ô tô có những loại hình nào?")

    assert slow.citations[0].document_number == "36/2024/QH15"
    assert slow.citations[0].article == "13"
    assert slow.citations[0].clause == "1"
    assert "bên phải" in slow.answer

    assert overtaking.citations[0].article == "14"
    assert overtaking.citations[0].clause == "6"
    assert "Trên cầu hẹp" in overtaking.answer
    assert "Trong hầm đường bộ" in overtaking.answer

    assert high_beam.citations[0].article == "20"
    assert high_beam.citations[0].clause == "2"
    assert "gặp xe đi ngược chiều" in high_beam.answer

    assert transport.citations[0].document_number == "35/2024/QH15"
    assert transport.citations[0].article == "56"
    assert transport.citations[0].clause == "6"
    assert "xe buýt" in transport.answer


def test_license_c1_scope() -> None:
    response = _answer("Bằng C1 lái xe tải có khối lượng toàn bộ bao nhiêu kg?")

    assert "trên 3.500 kg đến 7.500 kg" in response.answer
    assert response.citations[0].article == "57"


def test_priority_vehicle_order_and_rights_are_separate() -> None:
    order = _answer("Thứ tự xe ưu tiên khi qua đường giao nhau như thế nào?")
    rights = _answer("Xe ưu tiên có những quyền gì khi đang làm nhiệm vụ?")

    assert "xe chữa cháy" in order.answer
    assert order.citations[0].clause == "2"
    assert "không bị hạn chế tốc độ" in rights.answer
    assert rights.citations[0].clause == "4"


def test_road_database_and_not_decentralized_national_roads() -> None:
    database = _answer("Cơ sở dữ liệu đường bộ bao gồm những loại dữ liệu nào?")
    national_roads = _answer("Các quốc lộ nào không phân cấp cho UBND cấp tỉnh quản lý?")

    assert "thanh toán điện tử giao thông đường bộ" in database.answer
    assert database.citations[0].document_number == "35/2024/QH15"
    assert "Quốc lộ 1" in national_roads.answer
    assert national_roads.citations[0].document_number == "165/2024/NĐ-CP"


def test_source_traffic_facts_use_primary_law_sources() -> None:
    stopping = _answer("Dừng xe và đỗ xe khác nhau thế nào?")
    truck_bed = _answer("Những trường hợp nào được chở người trên thùng xe ô tô chở hàng?")
    motorcycle = _answer("Người lái xe máy không được làm gì khi đang chạy?")
    papers = _answer("Người lái xe ô tô phải mang theo giấy tờ gì khi tham gia giao thông?")

    assert {(citation.article, citation.clause) for citation in stopping.citations} == {("18", "1"), ("18", "2")}
    assert truck_bed.citations[0].article == "28"
    assert truck_bed.citations[0].clause == "1"
    assert "diễu hành theo đoàn" in truck_bed.answer
    assert motorcycle.citations[0].article == "33"
    assert motorcycle.citations[0].clause == "3"
    assert "Buông cả hai tay" in motorcycle.answer
    assert papers.citations[0].article == "56"
    assert papers.citations[0].clause == "1"
    assert "Chứng nhận kiểm định" in papers.answer


def test_source_fact_for_self_drive_rental_and_highway_breakdown() -> None:
    rental = _answer("Dịch vụ cho thuê phương tiện để tự lái gồm những xe nào?")
    breakdown = _answer("Trên cao tốc xe bị hỏng không thể vào làn dừng khẩn cấp thì đặt cảnh báo bao xa?")
    transition = _answer("Điều 21 Nghị định 238/2026/NĐ-CP quy định gì về hành vi xảy ra trước ngày nghị định có hiệu lực?")

    assert rental.citations[0].document_number == "35/2024/QH15"
    assert rental.citations[0].article == "78"
    assert rental.citations[0].point == "a"
    assert "ô tô chở người dưới 08 chỗ" in rental.answer
    assert breakdown.citations[0].article == "25"
    assert "150 mét" in breakdown.answer
    assert transition.citations[0].document_number == "238/2026/NĐ-CP"
    assert transition.citations[0].article == "21"
    assert "thời điểm thực hiện hành vi" in transition.answer


def test_direct_rule_facts_do_not_fall_back_to_sanctions() -> None:
    lane = _answer("Khi chuyển làn cần làm gì để đúng quy định?")
    turnaround = _answer("Những nơi nào không được quay đầu xe?")
    reverse = _answer("Những chỗ nào không được lùi xe?")
    horn = _answer("Ban đêm có được bấm còi trong khu đông dân cư không?")
    tunnel_light = _answer("Đi trong hầm đường bộ thì ô tô, xe máy phải bật loại đèn nào?")
    tunnel_stop = _answer("Có được dừng hoặc đỗ xe trong hầm đường bộ không?")

    assert lane.citations[0].article == "13"
    assert lane.citations[0].clause == "2"
    assert turnaround.citations[0].article == "15"
    assert turnaround.citations[0].clause == "4"
    assert reverse.citations[0].article == "16"
    assert reverse.citations[0].clause == "2"
    assert horn.answer.startswith("Không.")
    assert horn.citations[0].article == "21"
    assert horn.citations[0].clause == "2"
    assert tunnel_light.answer.startswith("Phải bật đèn chiếu gần.")
    assert tunnel_light.citations[0].article == "26"
    assert tunnel_light.citations[0].clause == "1"
    assert tunnel_stop.answer.startswith("Không.")
    assert tunnel_stop.citations[0].article == "26"
    assert tunnel_stop.citations[0].clause == "2"


def test_priority_order_child_crossing_and_rental_grounding() -> None:
    priority = _answer("Thứ tự ưu tiên của các xe ưu tiên khi qua đường giao nhau là như thế nào?")
    child = _answer("Trẻ dưới 7 tuổi tự qua đường có được không?")
    fixed_route = _answer("Xe khách tuyến cố định được hiểu như thế nào?")
    rental_license = _answer("Đơn vị cho thuê xe tự lái có được giao xe cho người không có bằng phù hợp không?")

    assert "Đoàn xe tang" in priority.answer
    assert priority.citations[0].article == "27"
    assert priority.citations[0].clause == "2"
    assert child.answer.startswith("Không được tự qua đường.")
    assert child.citations[0].article == "30"
    assert child.citations[0].clause == "2"
    assert "từ 08 chỗ trở lên" in fixed_route.answer
    assert fixed_route.citations[0].article == "56"
    assert fixed_route.citations[0].clause == "7"
    assert "giấy phép lái xe đang còn điểm" in rental_license.answer
    assert rental_license.citations[0].article == "78"
    assert rental_license.citations[0].clause == "2"
    assert rental_license.citations[0].point == "a"


def test_nonexistent_explicit_clause_fails_closed() -> None:
    parsed = parse_query(ChatRequest(query="Khoản 9 Điều 21 Nghị định 238/2026/NĐ-CP quy định gì?"))
    response = build_structured_fact_answer(parsed)

    assert response is not None
    assert not response.answerable
    assert response.citations == []
    assert "Không có khoản 9 Điều 21" in response.answer
