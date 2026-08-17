from __future__ import annotations

from datetime import date

from rag_luat_gt.retrieval.query_parser import parse_query
from rag_luat_gt.schemas import ChatRequest


def test_parse_query_separates_event_and_reference_dates() -> None:
    parsed = parse_query(
        ChatRequest(
            query="Xe máy vượt đèn đỏ ngày 10/08/2026 bị phạt bao nhiêu?",
            as_of_date=date(2026, 8, 20),
        )
    )

    assert parsed.event_date == "2026-08-10"
    assert parsed.as_of_date == "2026-08-20"
    assert parsed.legal_effective_date == "2026-08-10"
    assert parsed.query_reference_date == "2026-08-20"


def test_parse_query_ignores_invalid_explicit_date() -> None:
    parsed = parse_query(
        ChatRequest(
            query="Ngày 32/13/2026 xe máy vượt đèn đỏ bị phạt bao nhiêu?",
            event_date=date(2026, 8, 10),
        )
    )

    assert parsed.event_date == "2026-08-10"
    assert parsed.legal_effective_date == "2026-08-10"


def test_parse_query_detects_enumeration_mode() -> None:
    parsed = parse_query(
        ChatRequest(query="Cơ sở dữ liệu về trật tự an toàn giao thông bao gồm những gì?")
    )

    assert parsed.intent == "ENUMERATION"
    assert parsed.answer_mode == "ENUMERATION"
    assert parsed.retrieval_mode == "EXHAUSTIVE"
    assert parsed.answer_scope == "ALL_CHILDREN"


def test_penalty_enumeration_keeps_penalty_primary_intent() -> None:
    parsed = parse_query(ChatRequest(query="Các mức phạt nào áp dụng cho xe máy vượt đèn đỏ?"))

    assert parsed.intent == "PENALTY_LOOKUP"
    assert parsed.primary_intent == "PENALTY_LOOKUP"
    assert parsed.answer_mode == "ENUMERATION"
    assert parsed.retrieval_mode == "EXHAUSTIVE"


def test_parse_query_maps_behavior_catalog_alias() -> None:
    parsed = parse_query(ChatRequest(query="Xe máy đi sai làn bị phạt bao nhiêu?"))

    assert parsed.intent == "PENALTY_LOOKUP"
    assert parsed.vehicle_code == "MOTORCYCLE"
    assert parsed.behavior_text_query == "làn đường"


def test_parse_query_detects_driver_age_requirement() -> None:
    parsed = parse_query(ChatRequest(query="Người từ bao nhiêu tuổi được phép điều khiển ô tô?"))

    assert parsed.intent == "DRIVER_AGE_REQUIREMENT"
    assert parsed.vehicle_code == "CAR"
    assert parsed.desired_rule_function == "ELIGIBILITY"
    assert "MINIMUM_AGE" in parsed.requested_facets


def test_article_content_about_transition_is_not_effective_date_lookup() -> None:
    parsed = parse_query(
        ChatRequest(
            query="Điều 21 Nghị định 238/2026/NĐ-CP quy định gì về hành vi xảy ra trước ngày nghị định có hiệu lực?"
        )
    )

    assert parsed.intent == "ARTICLE_LOOKUP"
    assert parsed.temporal_intent == "DOCUMENT_CONTENT"


def test_behavior_catalog_expands_common_helmet_abbreviations() -> None:
    parsed = parse_query(ChatRequest(query="Ko đội mbh khi đi xe máy bị phạt bao nhiêu?"))

    assert parsed.intent == "PENALTY_LOOKUP"
    assert parsed.vehicle_code == "MOTORCYCLE"
    assert parsed.behavior_code is not None
    assert "MU_BAO_HIEM" in parsed.behavior_code


def test_parse_query_detects_license_class_scope_before_age_intent() -> None:
    parsed = parse_query(ChatRequest(query="Bằng B được lái những loại ô tô nào?"))

    assert parsed.intent == "DRIVER_LICENSE"
    assert parsed.answer_mode == "FACTOID"
    assert parsed.retrieval_mode == "FACTOID"
    assert parsed.license_classes == ["B"]
    assert "LICENSE_SCOPE" in parsed.requested_facets


def test_parse_query_detects_fee_lookup_before_driver_license() -> None:
    parsed = parse_query(ChatRequest(query="Tổng lệ phí thi sát hạch lái xe A1 là bao nhiêu?"))

    assert parsed.intent == "FEE_LOOKUP"


def test_parse_query_distinguishes_bicycle_from_electric_bicycle() -> None:
    bicycle = parse_query(ChatRequest(query="Đi xe đạp cần đội mũ bảo hiểm hay không?"))
    electric_bicycle = parse_query(ChatRequest(query="Đi xe đạp máy cần đội mũ bảo hiểm hay không?"))

    assert bicycle.vehicle_type == "xe đạp"
    assert bicycle.vehicle_code == "BICYCLE"
    assert electric_bicycle.vehicle_type == "xe đạp máy"
    assert electric_bicycle.vehicle_code == "BICYCLE"


def test_responsibility_question_with_nhung_gi_is_enumeration() -> None:
    parsed = parse_query(
        ChatRequest(query="Khi xảy ra tai nạn giao thông, người điều khiển phương tiện có những nghĩa vụ gì?")
    )

    assert parsed.intent == "ENUMERATION"
    assert parsed.answer_mode == "ENUMERATION"
    assert parsed.retrieval_mode == "EXHAUSTIVE"


def test_parse_query_does_not_detect_car_inside_highway() -> None:
    parsed = parse_query(ChatRequest(query="Tren cao toc chay qua toc do 35 km/h bi tru diem khong?"))

    assert parsed.intent == "PENALTY_LOOKUP"
    assert parsed.vehicle_type is None
    assert parsed.vehicle_code is None


def test_transition_question_is_not_routed_as_penalty_lookup() -> None:
    parsed = parse_query(
        ChatRequest(
            query=(
                "Một vi phạm xảy ra và kết thúc ngày 14/08/2026 nhưng đến 16/08/2026 mới bị phát hiện "
                "thì áp dụng Nghị định 168 hay Nghị định 238?"
            )
        )
    )

    assert parsed.intent != "PENALTY_LOOKUP"
    assert parsed.temporal_intent == "APPLICABLE_RULE"
    assert parsed.event_date == "2026-08-14"
    assert parsed.query_plan is not None
    assert "TEMPORAL_SOURCE_LOOKUP" in parsed.query_plan.strategy


def test_before_date_temporal_cue_uses_previous_day() -> None:
    parsed = parse_query(
        ChatRequest(
            query="Hành vi vi phạm đã kết thúc trước ngày 01/01/2025 nhưng sau đó mới bị phát hiện thì áp dụng gì?"
        )
    )

    assert parsed.event_date == "2024-12-31"
    assert parsed.legal_effective_date == "2024-12-31"


def test_urban_speed_question_does_not_treat_dong_dan_cu_as_money() -> None:
    parsed = parse_query(ChatRequest(query="Trong khu đông dân cư, ô tô trên đường đôi được chạy tối đa bao nhiêu?"))

    assert parsed.intent == "SPEED_RULE"
    assert "FINE" not in parsed.requested_facets


def test_short_age_capacity_query_detects_driver_age_requirement() -> None:
    parsed = parse_query(ChatRequest(query="16t chạy xe 50cc được chưa?"))

    assert parsed.intent == "DRIVER_AGE_REQUIREMENT"
