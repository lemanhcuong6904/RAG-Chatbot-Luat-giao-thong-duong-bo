from __future__ import annotations

import json
import re

from rag_luat_gt.config import (
    OPENAI_API_KEY,
    RAG_SANCTION_LLM_MAX_TOKENS,
    RAG_SANCTION_LLM_MODEL,
    RAG_SANCTION_LLM_PROVIDER,
    RAG_SANCTION_LLM_TEMPERATURE,
    RAG_REQUIRE_LLM,
)
from rag_luat_gt.generation.llm_client import (
    chat_completion,
    is_chat_provider_configured,
    normalize_llm_provider,
    provider_unconfigured_message,
    resolve_llm,
)
from rag_luat_gt.schemas import ChatResponse, ParsedQuery
from rag_luat_gt.text import normalize_text, strip_accents


SYSTEM_PROMPT = """Bạn là trợ lý diễn đạt kết quả xử phạt giao thông đường bộ Việt Nam.

Bạn chỉ được dùng STRUCTURED_SANCTION_PAYLOAD và DETERMINISTIC_ANSWER.
Không tự tính lại, không thêm mức phạt, không thêm điều khoản, không bỏ citation/rule id đã có.
Mỗi kết luận về mức phạt, điểm GPLX, tước GPLX hoặc biện pháp khác phải giữ citation inline ngay sau câu kết luận.
Không dồn toàn bộ citation xuống cuối nếu DETERMINISTIC_ANSWER đã có citation inline.
Nếu payload có trạng thái CONDITIONAL hoặc thiếu điều kiện, phải nói rõ chưa thể chốt một tổng duy nhất.
Trả lời trực tiếp, không bắt buộc tiêu đề Markdown và không thêm mục "Căn cứ pháp lý" nếu claim đã có citation inline.
Không mở đầu bằng công thức dài như "Theo quy định tại..." hoặc "Theo Điều...".

Không thêm mục "Thời điểm áp dụng" hoặc "Lưu ý" vào câu trả lời cuối, trừ khi người dùng hỏi trực tiếp về thời điểm hiệu lực hoặc cảnh báo kỹ thuật.

Văn phong: tự nhiên, ngắn gọn, dễ đọc; bỏ các nhãn kỹ thuật như UNSPECIFIED, MOTORCYCLE nếu không cần thiết.
"""


def maybe_render_structured_sanction_with_llm(
    parsed: ParsedQuery,
    response: ChatResponse,
) -> ChatResponse:
    if not response.debug:
        return response

    resolved_provider, resolved_model = resolve_llm(RAG_SANCTION_LLM_PROVIDER, RAG_SANCTION_LLM_MODEL)
    provider = normalize_llm_provider(resolved_provider)
    if provider in {"extractive", "rule", "off", "disabled"}:
        _mark_skip(response, f"provider={RAG_SANCTION_LLM_PROVIDER}")
        if RAG_REQUIRE_LLM and response.answerable:
            _replace_with_required_error(response, "RAG_SANCTION_LLM_PROVIDER is not a chat LLM provider.")
        return response

    if provider == "openai" and not OPENAI_API_KEY:
        error = "OPENAI_API_KEY is not configured"
        _mark_skip(response, error)
        if RAG_REQUIRE_LLM and response.answerable:
            _replace_with_required_error(response, error + ".")
        return response

    if provider != "openai" and not is_chat_provider_configured(provider):
        error = provider_unconfigured_message(provider)
        _mark_skip(response, error)
        if RAG_REQUIRE_LLM and response.answerable:
            _replace_with_required_error(response, error + ".")
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
        deterministic_answer = response.answer
        rendered = _normalize_rendered_answer(
            _render_with_provider(parsed, _sanction_render_prompt(deterministic_answer), payload, provider=provider, model=resolved_model)
        )
        if _render_preserves_required_claims(deterministic_answer, rendered):
            response.answer = rendered
        else:
            response.answer = deterministic_answer
            response.warnings.append("Structured sanction LLM render was discarded because it omitted required claims or added unsupported amounts.")
        render_debug = response.debug.setdefault("structured_sanction_llm", {})
        render_debug.update(
            {
                "enabled": True,
                "provider": provider,
                "model": resolved_model,
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
    deterministic_answer = _strip_non_user_sections(deterministic_answer)
    return (
        deterministic_answer
        + "\n\nYêu cầu diễn đạt: viết tự nhiên như tư vấn trực tiếp cho người hỏi; "
        "không bê nguyên mô tả bucket rule nếu câu trả lời đã có nhãn hành vi ngắn hơn; "
        "không hiện mã nội bộ như CAR, UNSPECIFIED, rule_id; không thêm chế tài ngoài payload; "
        "giữ nguyên citation inline sau từng kết luận mức phạt/điểm, không gom citation xuống cuối; "
        "trả lời trực tiếp, không thêm mục Căn cứ pháp lý riêng nếu citation đã nằm cuối claim; "
        "không đưa các ghi chú kỹ thuật, validation_status hoặc ngày hiệu lực vào câu trả lời cuối."
    )


def _strip_non_user_sections(answer: str) -> str:
    return re.split(r"\n###\s*(?:Thời điểm áp dụng|Lưu ý)\b", answer, maxsplit=1)[0].rstrip()


def _normalize_rendered_answer(answer: str) -> str:
    answer = re.sub(r"^\s*###\s*Trả lời\s*", "", answer, flags=re.IGNORECASE)
    answer = re.split(r"\n\s*###\s*Căn cứ pháp lý\b", answer, maxsplit=1, flags=re.IGNORECASE)[0]
    return answer.strip()


def _render_preserves_required_claims(deterministic: str, rendered: str) -> bool:
    deterministic_norm = _claim_key(deterministic)
    rendered_norm = _claim_key(rendered)
    for points in re.findall(r"tru\s+(\d+)\s+diem", deterministic_norm):
        if f"tru {points} diem" not in rendered_norm:
            return False
    deterministic_amounts = set(re.findall(r"\b\d{1,3}(?:\.\d{3})+\b", deterministic_norm))
    rendered_amounts = set(re.findall(r"\b\d{1,3}(?:\.\d{3})+\b", rendered_norm))
    if not rendered_amounts.issubset(deterministic_amounts):
        return False
    return True


def _claim_key(value: str) -> str:
    normalized = value.replace(",", ".")
    normalized = re.sub(r"\s+", " ", normalized)
    return strip_accents(normalize_text(normalized)).casefold()


def _mark_skip(response: ChatResponse, reason: str) -> None:
    response.debug.setdefault("structured_sanction_llm", {}).update({"enabled": False, "skip_reason": reason})


def _replace_with_required_error(response: ChatResponse, error: str) -> None:
    response.answer = (
        "Hệ thống đang được cấu hình bắt buộc sinh câu trả lời bằng LLM, nhưng bước diễn đạt LLM cho kết quả xử phạt chưa thực hiện được. "
        "Tôi không trả fallback cứng để tránh nhầm với câu trả lời đã được sinh hoàn chỉnh.\n\n"
        "Đã có dữ liệu xử phạt có cấu trúc trong debug/citation, nhưng chưa render bằng LLM.\n\n"
        f"Lỗi LLM: {error}"
    )
    response.answerable = False
    response.warnings.append(error)


def _render_with_openai(
    parsed: ParsedQuery,
    deterministic_answer: str,
    payload: dict,
) -> str:
    return _render_with_chat_provider(parsed, deterministic_answer, payload, provider="openai")


def _render_with_provider(
    parsed: ParsedQuery,
    deterministic_answer: str,
    payload: dict,
    *,
    provider: str,
    model: str,
) -> str:
    if provider == "openai":
        return _render_with_openai(parsed, deterministic_answer, payload)
    return _render_with_chat_provider(parsed, deterministic_answer, payload, provider=provider, model=model)


def _render_with_chat_provider(
    parsed: ParsedQuery,
    deterministic_answer: str,
    payload: dict,
    *,
    provider: str,
    model: str = RAG_SANCTION_LLM_MODEL,
) -> str:
    user_prompt = json.dumps(
        {
            "QUESTION": parsed.query,
            "LEGAL_EFFECTIVE_DATE": parsed.legal_effective_date,
            "DETERMINISTIC_ANSWER": deterministic_answer,
            "STRUCTURED_SANCTION_PAYLOAD": payload,
        },
        ensure_ascii=False,
    )
    return chat_completion(
        provider=provider,
        model=model,
        temperature=RAG_SANCTION_LLM_TEMPERATURE,
        max_tokens=RAG_SANCTION_LLM_MAX_TOKENS,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    ) or deterministic_answer
