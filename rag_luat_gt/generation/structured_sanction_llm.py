from __future__ import annotations

import json

from rag_luat_gt.config import (
    OPENAI_API_KEY,
    RAG_SANCTION_LLM_MAX_TOKENS,
    RAG_SANCTION_LLM_MODEL,
    RAG_SANCTION_LLM_PROVIDER,
    RAG_SANCTION_LLM_TEMPERATURE,
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
    if RAG_SANCTION_LLM_PROVIDER != "openai" or not OPENAI_API_KEY or not response.answerable:
        return response
    if not response.debug:
        return response
    payload = {
        key: value
        for key, value in response.debug.items()
        if key in {"sanction_lookup", "sanction_composition"}
    }
    if not payload:
        return response

    try:
        response.answer = _render_with_openai(parsed, response.answer, payload)
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
        response.warnings.append(f"Structured sanction LLM render failed, used deterministic answer: {exc}")
        response.debug.setdefault("structured_sanction_llm", {})["error"] = str(exc)
    return response


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
