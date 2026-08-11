from __future__ import annotations

from datetime import date

import requests
import streamlit as st

from rag_luat_gt.schemas import ChatRequest
from rag_luat_gt.service import RAGService


API_BASE = "http://127.0.0.1:8010"
DEFAULT_MODE = "Direct"


@st.cache_resource(show_spinner="Đang tải RAG service...")
def get_service() -> RAGService:
    return RAGService()


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
    event_date = st.date_input("Ngày áp dụng", value=date.today())
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
        "event_date": event_date.isoformat(),
        "top_k": top_k,
        "debug": debug,
    }

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
                for citation in data["citations"][:6]:
                    label = citation.get("document_number") or citation.get("document_title")
                    ref_parts = [
                        f"Điều {citation['article']}" if citation.get("article") else None,
                        f"Khoản {citation['clause']}" if citation.get("clause") else None,
                        f"Điểm {citation['point']}" if citation.get("point") else None,
                    ]
                    ref = " - ".join(part for part in ref_parts if part)
                    with st.expander(f"{label} | {ref}"):
                        st.write(f"Source: {citation['source_file']}")
                        st.write(f"Chunk: {citation['chunk_id']}")
                        st.write(f"Score: {citation.get('score')}")
            if debug and data.get("debug"):
                st.subheader("Debug")
                st.json(data["debug"])
            st.session_state.messages.append({"role": "assistant", "content": data["answer"]})
