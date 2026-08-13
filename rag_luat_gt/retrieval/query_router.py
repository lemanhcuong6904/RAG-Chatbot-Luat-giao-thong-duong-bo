from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from rag_luat_gt.config import (
    OPENAI_API_KEY,
    RAG_QUERY_ROUTER_MAX_TOKENS,
    RAG_QUERY_ROUTER_MODEL,
    RAG_QUERY_ROUTER_PROVIDER,
    RAG_QUERY_ROUTER_TEMPERATURE,
)
from rag_luat_gt.retrieval.query_planner import build_query_plan
from rag_luat_gt.schemas import ChatResponse, ParsedQuery, QueryPlan
from rag_luat_gt.text import normalize_text, strip_accents


Route = Literal["SMALL_TALK", "OUT_OF_SCOPE", "RAG"]
RetrievalStrategy = Literal[
    "NONE",
    "FACTOID",
    "EXPAND_PARENT",
    "EXPAND_PARENT_SIBLINGS",
    "EXHAUSTIVE_ARTICLE",
]


class QueryRouteDecision(BaseModel):
    route: Route = "RAG"
    legal_domain: Literal["traffic_law", "other_law", "non_legal", "unknown"] = "unknown"
    intent: str = "GENERAL_LEGAL_QA"
    retrieval_strategy: RetrievalStrategy = "FACTOID"
    needs_parent: bool = False
    needs_siblings: bool = False
    needs_children: bool = False
    use_structured_sanction: bool = False
    question_rewrite: str | None = None
    direct_answer: str | None = None
    reason: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


SYSTEM_PROMPT = """Bạn là query router cho chatbot pháp luật giao thông đường bộ Việt Nam.

Nhiệm vụ:
- Phân loại câu hỏi trước khi retrieval.
- Không trả lời kết luận pháp lý cho câu hỏi luật; chỉ lập kế hoạch retrieval.
- Chỉ trả direct_answer cho SMALL_TALK hoặc OUT_OF_SCOPE.

Route:
- SMALL_TALK: chào hỏi, cảm ơn, hỏi khả năng hỗ trợ thông thường.
- OUT_OF_SCOPE: không liên quan đến pháp luật giao thông đường bộ Việt Nam.
- RAG: cần tra cứu luật giao thông đường bộ.

Retrieval strategy:
- FACTOID: câu hỏi một ý, chỉ cần nguồn gần nhất.
- EXPAND_PARENT: cần thêm parent để hiểu leaf/chunk.
- EXPAND_PARENT_SIBLINGS: cần parent và các sibling cùng khoản/nhóm.
- EXHAUSTIVE_ARTICLE: câu hỏi liệt kê/toàn bộ nghĩa vụ/trách nhiệm/quyền/thủ tục/bao gồm những gì.

Ràng buộc:
- Trả JSON hợp lệ duy nhất, không markdown.
- legal_domain phải là traffic_law nếu câu hỏi thuộc luật giao thông đường bộ.
- OUT_OF_SCOPE dùng direct_answer từ chối nhẹ bằng tiếng Việt.
- SMALL_TALK dùng direct_answer ngắn gọn, tự nhiên bằng tiếng Việt; phải hướng người dùng đặt câu hỏi
  về pháp luật giao thông đường bộ Việt Nam. Không trả lời chung chung kiểu "Tôi có thể giúp gì cho bạn hôm nay?".
  Ví dụ: "Chào bạn. Bạn có thể đặt câu hỏi liên quan đến pháp luật giao thông đường bộ Việt Nam; mình sẽ hỗ trợ tra cứu quy định, mức phạt, điểm GPLX và căn cứ pháp lý."
"""


ALLOWED_INTENTS = {
    "GENERAL_LEGAL_QA",
    "PENALTY_LOOKUP",
    "LICENSE_POINT_BALANCE",
    "DRIVER_AGE_REQUIREMENT",
    "ENUMERATION",
    "DRIVER_LICENSE",
    "REGISTRATION",
    "SPEED_RULE",
    "FEE_LOOKUP",
    "AMENDMENT_COMPARE",
    "ARTICLE_LOOKUP",
}


def route_query(parsed: ParsedQuery) -> tuple[ParsedQuery, QueryRouteDecision, dict[str, Any]]:
    fallback = _rule_route(parsed)
    if RAG_QUERY_ROUTER_PROVIDER != "openai":
        routed = apply_route_decision(parsed, fallback)
        return routed, fallback, {"enabled": False, "provider": RAG_QUERY_ROUTER_PROVIDER, "decision": fallback.model_dump()}
    if not OPENAI_API_KEY:
        routed = apply_route_decision(parsed, fallback)
        return routed, fallback, {
            "enabled": True,
            "provider": "openai",
            "error": "OPENAI_API_KEY is not configured",
            "fallback_decision": fallback.model_dump(),
        }

    try:
        payload = _call_openai(parsed)
        decision = QueryRouteDecision.model_validate(payload)
        routed = apply_route_decision(parsed, decision)
        return routed, decision, {
            "enabled": True,
            "provider": "openai",
            "model": RAG_QUERY_ROUTER_MODEL,
            "decision": decision.model_dump(),
            "raw_payload": payload,
        }
    except (ValidationError, json.JSONDecodeError, Exception) as exc:
        routed = apply_route_decision(parsed, fallback)
        return routed, fallback, {
            "enabled": True,
            "provider": "openai",
            "model": RAG_QUERY_ROUTER_MODEL,
            "error": str(exc),
            "fallback_decision": fallback.model_dump(),
        }


def apply_route_decision(parsed: ParsedQuery, decision: QueryRouteDecision) -> ParsedQuery:
    if decision.route != "RAG":
        return parsed

    updates: dict[str, Any] = {}
    if decision.intent in ALLOWED_INTENTS:
        updates["intent"] = decision.intent
        updates["primary_intent"] = decision.intent
    if decision.question_rewrite:
        updates["retrieval_query"] = decision.question_rewrite
        updates["normalized_query"] = decision.question_rewrite

    if decision.retrieval_strategy == "EXHAUSTIVE_ARTICLE":
        updates.setdefault("intent", "ENUMERATION")
        updates.setdefault("primary_intent", "ENUMERATION")
        updates["answer_mode"] = "ENUMERATION"
        updates["retrieval_mode"] = "EXHAUSTIVE"
        updates["answer_scope"] = "ALL_CHILDREN"
    elif decision.retrieval_strategy in {"EXPAND_PARENT_SIBLINGS"}:
        updates["retrieval_mode"] = "EXHAUSTIVE"
        updates["answer_scope"] = "ALL_CHILDREN"
        if decision.intent == "ENUMERATION":
            updates["answer_mode"] = "ENUMERATION"

    routed = parsed.model_copy(update=updates)
    plan = build_query_plan(routed)
    if decision.use_structured_sanction:
        plan.use_structured_sanction = True
        if "STRUCTURED_LOOKUP" not in plan.strategy:
            plan.strategy.insert(0, "STRUCTURED_LOOKUP")
    if decision.retrieval_strategy == "EXHAUSTIVE_ARTICLE" and "EXHAUSTIVE_ARTICLE" not in plan.strategy:
        plan.strategy.insert(0, "EXHAUSTIVE_ARTICLE")
    routed.query_plan = plan
    return routed


def direct_route_response(decision: QueryRouteDecision) -> ChatResponse | None:
    if decision.route == "SMALL_TALK":
        answer = decision.direct_answer or (
            "Chào bạn. Bạn có thể đặt câu hỏi liên quan đến pháp luật giao thông đường bộ Việt Nam; "
            "mình sẽ hỗ trợ tra cứu quy định, mức phạt, điểm GPLX và căn cứ pháp lý."
        )
        return ChatResponse(answer=answer, citations=[], answerable=True, debug={"query_router": decision.model_dump()})
    if decision.route == "OUT_OF_SCOPE":
        answer = decision.direct_answer or (
            "Tôi chỉ hỗ trợ các câu hỏi về pháp luật giao thông đường bộ Việt Nam. "
            "Bạn có thể hỏi về mức phạt, giấy phép lái xe, quy tắc tham gia giao thông hoặc căn cứ pháp lý liên quan."
        )
        return ChatResponse(answer=answer, citations=[], answerable=False, debug={"query_router": decision.model_dump()})
    return None


def _rule_route(parsed: ParsedQuery) -> QueryRouteDecision:
    q = strip_accents(normalize_text(parsed.query))
    if _is_minimal_greeting(q):
        return QueryRouteDecision(
            route="SMALL_TALK",
            legal_domain="non_legal",
            retrieval_strategy="NONE",
            direct_answer=(
                "Chào bạn. Bạn có thể đặt câu hỏi liên quan đến pháp luật giao thông đường bộ Việt Nam; "
                "mình sẽ hỗ trợ tra cứu quy định, mức phạt, điểm GPLX và căn cứ pháp lý."
            ),
            reason="minimal greeting fallback",
            confidence=0.9,
        )
    if _is_minimal_capability_question(q):
        return QueryRouteDecision(
            route="SMALL_TALK",
            legal_domain="non_legal",
            retrieval_strategy="NONE",
            direct_answer=(
                "Mình hỗ trợ các câu hỏi về pháp luật giao thông đường bộ Việt Nam: quy tắc tham gia giao thông, "
                "mức phạt, điểm GPLX, điều kiện lái xe, đăng ký xe, biển số và căn cứ pháp lý. "
                "Bạn hãy gửi tình huống hoặc nội dung cần tra cứu."
            ),
            reason="minimal capability fallback",
            confidence=0.9,
        )

    return QueryRouteDecision(
        route="RAG",
        legal_domain="unknown",
        intent=parsed.intent,
        retrieval_strategy="FACTOID",
        needs_parent=False,
        needs_siblings=False,
        needs_children=False,
        use_structured_sanction=parsed.intent == "PENALTY_LOOKUP",
        reason="minimal fallback; use LLM router for semantic routing",
        confidence=0.0,
    )


def _is_minimal_greeting(query_ascii: str) -> bool:
    normalized = _minimal_meta_key(query_ascii)
    return normalized in {"hi", "hello", "chao", "xin chao", "xin chao ban", "chao ban"}


def _is_minimal_capability_question(query_ascii: str) -> bool:
    normalized = _minimal_meta_key(query_ascii)
    return normalized in {"ban co the lam gi", "ban co the lam nhung gi"}


def _minimal_meta_key(query_ascii: str) -> str:
    return re.sub(r"\s+", " ", query_ascii.strip(" \t\r\n?.!,;:")).strip()


def _call_openai(parsed: ParsedQuery) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=RAG_QUERY_ROUTER_MODEL,
        temperature=RAG_QUERY_ROUTER_TEMPERATURE,
        max_tokens=RAG_QUERY_ROUTER_MAX_TOKENS,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _user_prompt(parsed)},
        ],
    )
    content = response.choices[0].message.content or "{}"
    return json.loads(_strip_code_fence(content))


def _user_prompt(parsed: ParsedQuery) -> str:
    return json.dumps(
        {
            "query": parsed.query,
            "current_parse": parsed.model_dump(),
            "output_schema": QueryRouteDecision.model_json_schema(),
        },
        ensure_ascii=False,
    )


def _strip_code_fence(value: str) -> str:
    stripped = value.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, flags=re.DOTALL)
    return match.group(1).strip() if match else stripped
