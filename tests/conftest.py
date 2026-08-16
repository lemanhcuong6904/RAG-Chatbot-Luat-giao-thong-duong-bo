from __future__ import annotations

import os


os.environ.setdefault("RAG_QUERY_ROUTER_PROVIDER", "rule")
os.environ.setdefault("RAG_PRERAG_PROVIDER", "rule")
os.environ.setdefault("RAG_LLM_PROVIDER", "extractive")
os.environ.setdefault("RAG_SANCTION_LLM_PROVIDER", "extractive")
os.environ.setdefault("RAG_DENSE_ENABLED", "false")
os.environ.setdefault("RAG_RERANKER_ENABLED", "false")
