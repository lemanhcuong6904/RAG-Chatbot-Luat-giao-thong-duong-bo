from __future__ import annotations

import json

from rag_luat_gt.config import (
    OPENAI_API_KEY,
    RAG_SANCTION_LLM_MAX_TOKENS,
    RAG_SANCTION_LLM_MODEL,
    RAG_SANCTION_LLM_PROVIDER,
    RAG_SANCTION_LLM_TEMPERATURE,
    RAG_REQUIRE_LLM,
)
from rag_luat_gt.schemas import ChatResponse, ParsedQuery


SYSTEM_PROMPT = """Bạn là trợ lý diễn đạt kết quả xử phạt giao thông đường bộ Việt Nam.

Bạn chỉ được dùng STRUCTURED_SANCTION_PAYLOAD và DETERMINISTIC_ANSWER.
Không tự tính lại, không thêm mức phạt, không thêm điều khoản, không bỏ citation/rule id đã có.
Nếu payload có trạng thái CONDITIONAL hoặc thiếu điều kiện, phải nói rõ chưa thể chốt một tổng duy nhất.
Giữ cấu trúc Markdown với các mục:
### Trả lời
### Căn cứ pháp lý
### Thời điểm áp dụng
### Lưu ý

Văn phong: tự nhiên, ngắn gọn, dễ đọc; bỏ các nhãn kỹ thuật như UNSPECIFIED, MOTORCYCLE nếu không cần thiết.
"""


def maybe_render_structured_sanction_with_llm(
    parsed: ParsedQuery,
    response: ChatResponse,
) -> ChatResponse:
    if not response.debug:
        return response

    if RAG_SANCTION_LLM_PROVIDER != "openai":
        _mark_skip(response, f"provider={RAG_SANCTION_LLM_PROVIDER}")
        if RAG_REQUIRE_LLM and response.answerable:
            _replace_with_required_error(response, "RAG_SANCTION_LLM_PROVIDER is not openai.")
        return response

    if not OPENAI_API_KEY:
        _mark_skip(response, "OPENAI_API_KEY is not configured")
        if RAG_REQUIRE_LLM and response.answerable:
            _replace_with_required_error(response, "OPENAI_API_KEY is not configured.")
        return response

    if not response.answerable:
        _mark_skip(response, "response is not answerable")
        return response

    payload = {
        key: value
        for key, value in response.debug.items()
        if key in {"sanction_lookup", "sanction_composition"}
    }
    if not payload:
        _mark_skip(response, "structured sanction payload is empty")
        if RAG_REQUIRE_LLM and response.answerable:
            _replace_with_required_error(response, "Structured sanction payload is empty.")
        return response

    try:
        response.answer = _render_with_openai(parsed, _sanction_render_prompt(response.answer), payload)
        render_debug = response.debug.setdefault("structured_sanction_llm", {})
        render_debug.update(
            {
                "enabled": True,
                "provider": "openai",
                "model": RAG_SANCTION_LLM_MODEL,
                "temperature": RAG_SANCTION_LLM_TEMPERATURE,
            }
        )
    except Exception as exc:
        if RAG_REQUIRE_LLM:
            _replace_with_required_error(response, f"Structured sanction LLM render failed: {exc}")
        else:
            response.warnings.append(f"Structured sanction LLM render failed, used deterministic answer: {exc}")
        response.debug.setdefault("structured_sanction_llm", {})["error"] = str(exc)
    return response


def _sanction_render_prompt(deterministic_answer: str) -> str:
    return (
        deterministic_answer
        + "\n\nYêu cầu diễn đạt: viết tự nhiên như tư vấn trực tiếp cho người hỏi; "
        "không bê nguyên mô tả bucket rule nếu câu trả lời đã có nhãn hành vi ngắn hơn; "
        "không hiện mã nội bộ như CAR, UNSPECIFIED, rule_id; không thêm chế tài ngoài payload."
    )


def _mark_skip(response: ChatResponse, reason: str) -> None:
    response.debug.setdefault("structured_sanction_llm", {}).update({"enabled": False, "skip_reason": reason})


def _replace_with_required_error(response: ChatResponse, error: str) -> None:
    response.answer = (
        "### Trả lời\n"
        "Hệ thống đang được cấu hình bắt buộc sinh câu trả lời bằng LLM, nhưng bước diễn đạt LLM cho kết quả xử phạt chưa thực hiện được. "
        "Tôi không trả fallback cứng để tránh nhầm với câu trả lời đã được sinh hoàn chỉnh.\n\n"
        "### Căn cứ pháp lý\n"
        "Đã có dữ liệu xử phạt có cấu trúc trong debug/citation, nhưng chưa render bằng LLM.\n\n"
        "### Lưu ý\n"
        f"- Lỗi LLM: {error}"
    )
    response.answerable = False
    response.warnings.append(error)


def _render_with_openai(
    parsed: ParsedQuery,
    deterministic_answer: str,
    payload: dict,
) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    user_prompt = json.dumps(
        {
            "QUESTION": parsed.query,
            "LEGAL_EFFECTIVE_DATE": parsed.legal_effective_date,
            "DETERMINISTIC_ANSWER": deterministic_answer,
            "STRUCTURED_SANCTION_PAYLOAD": payload,
        },
        ensure_ascii=False,
    )
    result = client.chat.completions.create(
        model=RAG_SANCTION_LLM_MODEL,
        temperature=RAG_SANCTION_LLM_TEMPERATURE,
        max_tokens=RAG_SANCTION_LLM_MAX_TOKENS,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    return result.choices[0].message.content or deterministic_answer
