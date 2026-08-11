from __future__ import annotations

from rag_luat_gt.config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    RAG_OPENAI_MAX_TOKENS,
    RAG_OPENAI_TEMPERATURE,
)
from rag_luat_gt.schemas import Chunk, ParsedQuery


SYSTEM_PROMPT = """Bạn là chatbot hỏi đáp luật giao thông đường bộ Việt Nam.
Chỉ sử dụng LEGAL_CONTEXT và LEGAL_NOTES được cung cấp.
Không tự bổ sung số văn bản, số Điều, Khoản, Điểm, mức phạt, ngày hiệu lực hoặc điều kiện pháp lý nếu không có trong nguồn.
Nếu nguồn không đủ rõ, nói rõ là chưa đủ căn cứ.
Nếu câu hỏi yêu cầu liệt kê toàn bộ một tập hợp, chỉ trả lời là đầy đủ khi LEGAL_CONTEXT có EXPANSION_STATUS: COMPLETE. Nếu context chỉ có một phần danh sách, không suy đoán các mục còn thiếu.
Khi LEGAL_NOTES có nội dung về hiệu lực hoặc văn bản sửa đổi, phải phản ánh trong mục "Thời điểm áp dụng" hoặc "Lưu ý".
Trả lời bằng tiếng Việt, ngắn gọn, có cấu trúc:
#### Trả lời
#### Căn cứ pháp lý
#### Thời điểm áp dụng
#### Lưu ý
"""


def _expansion_metadata(results: list[tuple[Chunk, float]]) -> tuple[str, int, int]:
    expected = 0
    actual = 0
    included_ids = {chunk.chunk_id for chunk, _score in results}
    for chunk, _score in results:
        if chunk.children_ids:
            expected += len(chunk.children_ids)
            actual += len([child_id for child_id in chunk.children_ids if child_id in included_ids])
    if not expected:
        return "UNKNOWN", 0, 0
    return ("COMPLETE" if expected == actual else "PARTIAL", expected, actual)


def _context_from_chunks(parsed: ParsedQuery, results: list[tuple[Chunk, float]]) -> str:
    expansion_status, expected_children, actual_children = _expansion_metadata(results)
    header = "\n".join(
        [
            f"QUERY_INTENT: {parsed.primary_intent or parsed.intent}",
            f"ANSWER_MODE: {parsed.answer_mode}",
            f"ACTOR: {parsed.actor or ''}",
            f"LIABLE_ENTITY_TYPE: {parsed.liable_entity_type or ''}",
            f"VEHICLE_CODE: {parsed.vehicle_code or ''}",
            f"BEHAVIOR_CODE: {parsed.behavior_code or ''}",
            f"BEHAVIOR_TEXT_QUERY: {parsed.behavior_text_query or ''}",
            f"CONDITIONS: {', '.join(parsed.conditions)}",
            f"EXPANSION_STATUS: {expansion_status}",
            f"EXPECTED_CHILD_COUNT: {expected_children}",
            f"ACTUAL_CHILD_COUNT: {actual_children}",
        ]
    )
    blocks = []
    for index, (chunk, _score) in enumerate(results, start=1):
        blocks.append(
            "\n".join(
                [
                    f"[SOURCE {index}]",
                    f"chunk_id: {chunk.chunk_id}",
                    f"chunk_type: {chunk.chunk_type}",
                    f"parent_id: {chunk.parent_id or ''}",
                    f"sibling_group_id: {chunk.sibling_group_id or ''}",
                    f"children_count: {len(chunk.children_ids)}",
                    f"document_number: {chunk.document_number or ''}",
                    f"document_title: {chunk.document_title or ''}",
                    f"article: {chunk.article or ''}",
                    f"article_title: {chunk.article_title or ''}",
                    f"clause: {chunk.clause or ''}",
                    f"point: {chunk.point or ''}",
                    f"valid_from: {chunk.valid_from or ''}",
                    f"valid_to: {chunk.valid_to or ''}",
                    f"coverage_status: {chunk.coverage_status}",
                    f"source_quality: {chunk.source_quality}",
                    f"temporal_status: {chunk.metadata.get('temporal_status', '')}",
                    "content:",
                    chunk.text,
                ]
            )
        )
    return header + "\n\n" + "\n\n".join(blocks)


def generate_with_openai(
    parsed: ParsedQuery,
    results: list[tuple[Chunk, float]],
    legal_notes: list[str] | None = None,
) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    notes_text = "\n".join(f"- {note}" for note in legal_notes or []) or "(không có)"
    user_prompt = (
        f"QUESTION:\n{parsed.query}\n\n"
        f"QUERY_INTENT: {parsed.primary_intent or parsed.intent}\n"
        f"ANSWER_MODE: {parsed.answer_mode}\n"
        f"EVENT_DATE: {parsed.event_date or ''}\n"
        f"LEGAL_EFFECTIVE_DATE: {parsed.legal_effective_date or ''}\n"
        f"AS_OF_DATE: {parsed.as_of_date or ''}\n\n"
        f"LEGAL_NOTES:\n{notes_text}\n\n"
        f"LEGAL_CONTEXT:\n{_context_from_chunks(parsed, results)}"
    )

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=RAG_OPENAI_TEMPERATURE,
        max_tokens=RAG_OPENAI_MAX_TOKENS,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content or ""
