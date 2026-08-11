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

Nếu muốn bật dense retrieval BGE-M3 + Qdrant local:

```powershell
conda activate nlp
python -m rag_luat_gt.ingestion.build_index
python -m rag_luat_gt.ingestion.build_dense_index
```

`build_index` ghi `corpus_hash/chunking_version` vào manifest và tự xóa ready marker của Qdrant để tránh dùng dense index cũ với BM25/chunk mới. Sau khi build dense thành công, hệ thống chỉ bật dense retrieval khi ready marker khớp manifest hiện tại.

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
- exact filter theo văn bản/Điều/Khoản/Điểm, sau đó vẫn rank theo nội dung truy vấn;
- lọc ngày hiệu lực cơ bản theo metadata văn bản/chunk/provision note;
- BGE-M3 dense retrieval với Qdrant local/từ xa;
- stale dense-index guard bằng `corpus_hash` và `chunking_version`;
- coverage-aware metadata (`COMPLETE`, `PARTIAL`, `MISSING_APPENDIX`, `MISSING_TABLE`, `MISSING_PAGES`, `UNKNOWN`);
- evidence gate cơ bản để abstain khi nguồn yếu hoặc corpus thiếu phụ lục/bảng;
- FastAPI và Streamlit UI.

Chưa có trong MVP:

- reranker;
- legal version graph/amendment resolver đầy đủ cấp provision;
- claim-level citation verifier;
- golden evaluation set.
