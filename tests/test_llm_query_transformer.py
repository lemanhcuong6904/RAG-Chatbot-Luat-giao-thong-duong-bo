from __future__ import annotations

from rag_luat_gt.retrieval.llm_query_transformer import merge_llm_transform
from rag_luat_gt.retrieval.query_parser import parse_query
from rag_luat_gt.schemas import ChatRequest


def test_llm_transform_merges_multi_query_plan() -> None:
    parsed = parse_query(ChatRequest(query="xe ưu tiên thế nào?"))

    transformed = merge_llm_transform(
        parsed,
        {
            "intent": "GENERAL_LEGAL_QA",
            "query_plan": {
                "strategy": ["EXPANSION", "STEP_BACK", "MULTI_QUERY", "HYDE", "HYBRID_RETRIEVAL"],
                "multi_queries": ["quy định về xe ưu tiên", "người tham gia giao thông nhường đường xe ưu tiên"],
                "step_back_query": "nguyên tắc nhường đường cho xe ưu tiên",
                "hyde_text": "quy định pháp luật về xe ưu tiên đang làm nhiệm vụ",
            },
        },
    )

    assert transformed.query_plan
    assert "MULTI_QUERY" in transformed.query_plan.strategy
    assert transformed.query_plan.step_back_query == "nguyên tắc nhường đường cho xe ưu tiên"
    assert transformed.query_plan.hyde_text == "quy định pháp luật về xe ưu tiên đang làm nhiệm vụ"


def test_llm_transform_does_not_loosen_explicit_legal_reference() -> None:
    parsed = parse_query(ChatRequest(query="Khoản 4 Điều 7 Nghị định 168/2024/NĐ-CP quy định gì?"))
    original_query = parsed.normalized_query

    transformed = merge_llm_transform(
        parsed,
        {
            "intent": "PENALTY_LOOKUP",
            "retrieval_query": "quy định xử phạt xe máy",
            "normalized_query": "quy định xử phạt xe máy",
            "query_plan": {
                "strategy": ["MULTI_QUERY", "HYDE", "HYBRID_RETRIEVAL"],
                "multi_queries": ["quy định xử phạt xe máy"],
                "hyde_text": "văn bản giả định",
            }
        },
    )

    assert transformed.query_plan
    assert transformed.query_plan.strategy == ["DIRECT", "EXPANSION", "HYBRID_RETRIEVAL"]
    assert transformed.query_plan.multi_queries == []
    assert transformed.query_plan.hyde_text is None
    assert transformed.intent == parsed.intent
    assert transformed.normalized_query == original_query


def test_llm_transform_can_replace_violation_facts() -> None:
    parsed = parse_query(ChatRequest(query="xe máy vượt đèn đỏ và không đội mũ bị phạt thế nào?"))

    transformed = merge_llm_transform(
        parsed,
        {
            "intent": "PENALTY_LOOKUP",
            "violations": [
                {
                    "behavior_code": "A",
                    "behavior_text": "vượt đèn đỏ",
                    "raw_span": "vượt đèn đỏ",
                    "catalog_code": "TRAFFIC_SIGNAL_NONCOMPLIANCE",
                },
                {
                    "behavior_code": "B",
                    "behavior_text": "không đội mũ",
                    "raw_span": "không đội mũ",
                    "catalog_code": "NO_HELMET",
                },
            ],
            "query_plan": {
                "strategy": ["EXPANSION", "DECOMPOSITION", "STRUCTURED_LOOKUP", "LEGAL_COMPOSITION"],
                "use_structured_sanction": True,
            },
        },
    )

    assert len(transformed.violations) == 2
    assert transformed.behavior_code == "KHONG_CHAP_HANH_HIEU_LENH_CUA_DEN_TIN_HIEU_GIAO_THONG"
    assert transformed.query_plan
    assert transformed.query_plan.use_structured_sanction


def test_llm_transform_preserves_catalog_behavior_codes_for_license_violation() -> None:
    parsed = parse_query(
        ChatRequest(
            query=(
                "Một người đi xe máy vượt đèn đỏ, không đội mũ bảo hiểm "
                "và không có giấy phép lái xe bị phạt thế nào?"
            )
        )
    )

    transformed = merge_llm_transform(
        parsed,
        {
            "intent": "PENALTY_LOOKUP",
            "violations": [
                {
                    "behavior_code": "NO_DRIVER_LICENSE",
                    "behavior_text": "không có giấy phép lái xe",
                    "raw_span": "không có giấy phép lái xe",
                    "catalog_code": "NO_DRIVER_LICENSE",
                }
            ],
            "query_plan": {
                "strategy": ["EXPANSION", "DECOMPOSITION", "STRUCTURED_LOOKUP", "LEGAL_COMPOSITION"],
                "use_structured_sanction": True,
            },
        },
    )

    license_violation = next(item for item in transformed.violations if item.catalog_code == "NO_DRIVER_LICENSE")
    assert license_violation.behavior_code.startswith("KHONG_CO_GIAY_PHEP_LAI_XE")
    assert len(license_violation.conditions["behavior_codes"]) == 2


def test_llm_transform_does_not_use_unmapped_penalty_behavior_code_for_structured_lookup() -> None:
    parsed = parse_query(ChatRequest(query="Người điều khiển xe máy bay qua vỉa hè bị phạt bao nhiêu?"))

    transformed = merge_llm_transform(
        parsed,
        {
            "intent": "PENALTY_LOOKUP",
            "behavior_code": "HANH_VI_LLM_TU_SINH",
            "violations": [
                {
                    "behavior_code": "HANH_VI_LLM_TU_SINH",
                    "behavior_text": "bay qua vỉa hè",
                    "raw_span": "bay qua vỉa hè",
                }
            ],
            "query_plan": {
                "strategy": ["EXPANSION", "STRUCTURED_LOOKUP"],
                "use_structured_sanction": True,
            },
        },
    )

    assert transformed.behavior_code is None
    assert transformed.violations[0].behavior_code == "HANH_VI_LLM_TU_SINH"
    assert transformed.violations[0].catalog_code is None


def test_llm_transform_accepts_valid_semantic_focus_fields() -> None:
    parsed = parse_query(ChatRequest(query="Khi bị CSGT dừng xe, người lái có quyền được biết lý do không?"))

    transformed = merge_llm_transform(
        parsed,
        {
            "intent": "GENERAL_LEGAL_QA",
            "retrieval_query": "quyền người điều khiển được thông báo căn cứ dừng phương tiện kiểm tra kiểm soát Điều 72",
            "must_include_terms": ["được thông báo", "căn cứ dừng phương tiện", "kiểm tra, kiểm soát"],
            "must_not_confuse_with": ["dừng xe, đỗ xe", "Điều 18"],
            "query_plan": {
                "strategy": ["EXPANSION", "MULTI_QUERY", "HYBRID_RETRIEVAL", "UNSAFE_UNKNOWN"],
                "multi_queries": ["quyền được thông báo căn cứ dừng phương tiện"],
            },
        },
    )

    assert transformed.retrieval_query.startswith("quyền người điều khiển")
    assert transformed.must_include_terms == ["được thông báo", "căn cứ dừng phương tiện", "kiểm tra, kiểm soát"]
    assert transformed.must_not_confuse_with == ["dừng xe, đỗ xe", "Điều 18"]
    assert transformed.query_plan
    assert "UNSAFE_UNKNOWN" not in transformed.query_plan.strategy


def test_llm_transform_cannot_add_unmentioned_license_classes() -> None:
    parsed = parse_query(ChatRequest(query="Bằng B được lái những loại ô tô nào?"))

    transformed = merge_llm_transform(
        parsed,
        {
            "intent": "DRIVER_LICENSE",
            "license_classes": ["BE", "C1"],
            "must_include_terms": ["Hạng B cấp cho người lái xe"],
        },
    )

    assert transformed.license_classes == ["B"]
    assert transformed.must_include_terms == ["Hạng B cấp cho người lái xe"]
