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
Khi LEGAL_NOTES có nội dung về hiệu lực hoặc văn bản sửa đổi, phải phản ánh trong mục "Thời điểm áp dụng" hoặc "Lưu ý".
Trả lời bằng tiếng Việt, ngắn gọn, có cấu trúc:
### Trả lời
### Căn cứ pháp lý
### Thời điểm áp dụng
### Lưu ý
"""


def _context_from_chunks(results: list[tuple[Chunk, float]]) -> str:
    blocks = []
    for index, (chunk, score) in enumerate(results, start=1):
        blocks.append(
            "\n".join(
                [
                    f"[SOURCE {index}]",
                    f"chunk_id: {chunk.chunk_id}",
                    f"document_number: {chunk.document_number or ''}",
                    f"document_title: {chunk.document_title or ''}",
                    f"article: {chunk.article or ''}",
                    f"article_title: {chunk.article_title or ''}",
                    f"clause: {chunk.clause or ''}",
                    f"point: {chunk.point or ''}",
                    f"valid_from: {chunk.valid_from or ''}",
                    f"valid_to: {chunk.valid_to or ''}",
                    f"score: {score}",
                    "content:",
                    chunk.text[:1800],
                ]
            )
        )
    return "\n\n".join(blocks)


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
        f"EVENT_DATE: {parsed.event_date or ''}\n"
        f"AS_OF_DATE: {parsed.as_of_date or ''}\n\n"
        f"LEGAL_NOTES:\n{notes_text}\n\n"
        f"LEGAL_CONTEXT:\n{_context_from_chunks(results)}"
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
