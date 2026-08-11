# RAG Chatbot Luật giao thông đường bộ

MVP local cho hỏi đáp luật giao thông đường bộ Việt Nam dựa trên corpus Markdown trong `data/markdown`.

## Chạy trong Anaconda

Điền API key trong `.env`:

```text
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
RAG_LLM_PROVIDER=openai
```

Nếu `OPENAI_API_KEY` để trống, hệ thống tự dùng chế độ trả lời trích xuất từ nguồn.

```powershell
conda activate nlp
pip install -r requirements.txt
python -m rag_luat_gt.ingestion.build_index
python scripts\run_api.py
```

Mở một terminal khác:

```powershell
conda activate nlp
python scripts\run_ui.py
```

Streamlit mặc định chạy `Direct mode`, tức là không cần bật FastAPI. Chỉ chạy API riêng khi muốn dùng endpoint hoặc Swagger.

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
  "query": "Xe máy vượt đèn đỏ bị phạt bao nhiêu?",
  "event_date": "2026-08-10",
  "top_k": 8,
  "debug": true
}
```

## Trạng thái MVP

Đã có:

- parser YAML metadata;
- parser cấu trúc Chương/Mục/Điều/Khoản/Điểm;
- legal-aware chunking;
- BM25 retrieval với tokenizer giữ số hiệu văn bản;
- exact lookup theo văn bản/Điều/Khoản/Điểm;
- lọc ngày hiệu lực cơ bản theo metadata;
- FastAPI và Streamlit UI.

Chưa có trong MVP:

- dense embedding BGE-M3;
- Qdrant;
- reranker;
- amendment resolver cấp provision.
