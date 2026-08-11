# RAG Chatbot Luật giao thông đường bộ

MVP local cho hỏi đáp luật giao thông đường bộ Việt Nam dựa trên corpus Markdown trong `data/markdown`.

## Chạy trong Anaconda

Điền API key trong `.env`:

```text
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
RAG_LLM_PROVIDER=openai
SANCTION_ENABLED=true
SANCTION_DB_PATH=structured_sanction_layer/structured_sanction_layer/sanctions.sqlite
```

Nếu `OPENAI_API_KEY` để trống, hệ thống tự dùng chế độ trả lời trích xuất từ nguồn.

```powershell
conda activate nlp
pip install -r requirements.txt
python -m rag_luat_gt.ingestion.build_index
python scripts\run_api.py
```

Nếu muốn bật dense retrieval BGE-M3 + Qdrant local:

```powershell
python -m rag_luat_gt.ingestion.build_index
python -m rag_luat_gt.ingestion.build_dense_index
```

Nếu muốn bật neural reranker:

```text
RAG_RERANKER_ENABLED=true
RAG_RERANKER_MODEL=BAAI/bge-reranker-v2-m3
```

`build_index` ghi `corpus_hash/chunking_version` vào manifest và tự xóa ready marker của Qdrant để tránh dùng dense index cũ với BM25/chunk mới. Sau khi build dense thành công, hệ thống chỉ bật dense retrieval khi ready marker khớp manifest hiện tại.

Mở một terminal khác:

```powershell
python scripts\run_ui.py
```

Streamlit mặc định chạy `Direct mode`, tức là không cần bật FastAPI. Chế độ này warm-up model khi app khởi động để câu hỏi đầu không phải chờ load model.

## API chính

- `GET /api/v1/health`
- `POST /api/v1/chat`
- `GET /api/v1/documents`
- `GET /api/v1/documents/{document_id}`
- `GET /api/v1/chunks/{chunk_id}`
- `POST /api/v1/retrieval/search`

Ví dụ:

```json
{
  "query": "Xe máy vượt đèn đỏ bị phạt bao nhiêu và trừ mấy điểm?",
  "event_date": "2026-08-10",
  "top_k": 8,
  "debug": true
}
```

## Trạng thái

Đã có:

- parser YAML metadata;
- parser cấu trúc Chương/Mục/Điều/Khoản/Điểm;
- hierarchical chunking với `chunk_type`, `parent_id`, `article_id`, `sibling_group_id`, `order`, `children_ids`;
- structural expansion cho câu hỏi liệt kê/exhaustive;
- strict fail-closed khi người dùng hỏi explicit legal reference không tồn tại;
- BM25 retrieval với tokenizer giữ số hiệu văn bản;
- BGE-M3 dense retrieval với Qdrant local/từ xa;
- Qdrant payload indexes cho metadata filter;
- optional `BAAI/bge-reranker-v2-m3` reranker;
- stale dense-index guard bằng `corpus_hash` và `chunking_version`;
- coverage-aware metadata;
- Structured Sanction Layer cho câu hỏi mức phạt/trừ điểm, dùng `sanctions.sqlite`;
- NĐ 238/2026/NĐ-CP được xử lý như amendment/version overlay, không ghi đè lịch sử;
- evidence gate cơ bản;
- FastAPI và Streamlit UI.

Chưa có trong MVP:

- post-generation claim verifier đầy đủ;
- golden evaluation set 300-500 câu;
- BGE-M3 sparse/multi-vector benchmark.
