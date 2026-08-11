from __future__ import annotations

from datetime import date

import requests
import streamlit as st

from rag_luat_gt.schemas import ChatRequest
from rag_luat_gt.service import RAGService


API_BASE = "http://127.0.0.1:8010"


@st.cache_resource(show_spinner="Đang tải RAG service và warm-up model...")
def get_service() -> RAGService:
    service = RAGService()
    service.warm_up()
    return service


def answer_direct(payload: dict) -> dict:
    service = get_service()
    request = ChatRequest(**payload)
    return service.answer(request).model_dump()


def answer_api(api_base: str, payload: dict) -> dict:
    response = requests.post(f"{api_base}/api/v1/chat", json=payload, timeout=120)
    response.raise_for_status()
    return response.json()


st.set_page_config(page_title="RAG Luật giao thông", layout="wide")

with st.sidebar:
    st.header("Thiết lập")
    mode = st.radio("Chế độ chạy", ["Direct", "FastAPI"], index=0, horizontal=True)
    api_base = st.text_input("API", API_BASE, disabled=mode == "Direct")
    use_event_date = st.checkbox("Lọc theo ngày áp dụng", value=False)
    event_date = st.date_input("Ngày áp dụng", value=date.today(), disabled=not use_event_date)
    top_k = st.slider("Top K", min_value=3, max_value=12, value=8)
    debug = st.toggle("Debug", value=False)
    st.divider()
    if mode == "Direct":
        st.caption("Direct mode chạy RAG ngay trong Streamlit, không cần FastAPI.")
    elif st.button("Kiểm tra API"):
        try:
            st.json(requests.get(f"{api_base}/api/v1/health", timeout=10).json())
        except requests.RequestException as exc:
            st.error(str(exc))

if mode == "Direct":
    service = get_service()
    st.sidebar.caption(f"Warm-up: {service.warmup_status}")
    st.sidebar.caption(f"Dense: {'active' if service.retriever.dense is not None else 'inactive'}")
    if service.retriever.dense_error:
        st.sidebar.warning(f"Dense inactive: {service.retriever.dense_error}")
    if service.warmup_error:
        st.sidebar.warning(f"Không thể warm-up model: {service.warmup_error}")

st.title("Chatbot hỏi đáp Luật giao thông đường bộ")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

query = st.chat_input("Nhập câu hỏi về luật giao thông đường bộ")
if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    payload = {
        "query": query,
        "top_k": top_k,
        "debug": debug,
    }
    if use_event_date:
        payload["event_date"] = event_date.isoformat()

    with st.chat_message("assistant"):
        try:
            with st.spinner("Đang truy xuất nguồn và sinh câu trả lời..."):
                data = answer_direct(payload) if mode == "Direct" else answer_api(api_base, payload)
        except Exception as exc:
            st.error(f"Lỗi xử lý câu hỏi: {exc}")
        else:
            st.markdown(data["answer"])
            if data.get("warnings"):
                for warning in data["warnings"]:
                    st.warning(warning)
            if data.get("citations"):
                st.subheader("Nguồn")
                for citation in data["citations"][:12]:
                    label = citation.get("document_number") or citation.get("document_title")
                    ref_parts = [
                        f"Điều {citation['article']}" if citation.get("article") else None,
                        f"Khoản {citation['clause']}" if citation.get("clause") else None,
                        f"Điểm {citation['point']}" if citation.get("point") else None,
                    ]
                    ref = " - ".join(part for part in ref_parts if part)
                    chunk_type = citation.get("chunk_type", "SPAN")
                    with st.expander(f"{label} | {ref} | {chunk_type}"):
                        st.markdown("**Nội dung nguồn**")
                        st.markdown(citation.get("text") or "_Không có nội dung nguồn._")
                        st.divider()
                        st.write(f"Source: {citation['source_file']}")
                        st.write(f"Chunk: {citation['chunk_id']}")
                        if citation.get("rule_id"):
                            st.write(f"Rule: {citation['rule_id']}")
                        st.write(f"Parent: {citation.get('parent_id')}")
                        st.write(f"Sibling group: {citation.get('sibling_group_id')}")
                        st.write(f"Coverage: {citation.get('coverage_status', 'UNKNOWN')}")
                        st.write(f"Source quality: {citation.get('source_quality', 'UNKNOWN')}")
                        st.write(f"Score: {citation.get('score')}")
            if debug and data.get("debug"):
                st.subheader("Debug")
                st.json(data["debug"])
            st.session_state.messages.append({"role": "assistant", "content": data["answer"]})
