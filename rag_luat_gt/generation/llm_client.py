from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from rag_luat_gt.config import (
    OPENAI_API_KEY,
    RAG_LOCAL_LLM_API_KEY,
    RAG_LOCAL_LLM_BASE_URL,
)


LOCAL_LLM_PROVIDERS = {"local", "local_openai", "qwen", "qwen_local"}
CHAT_LLM_PROVIDERS = {"openai", *LOCAL_LLM_PROVIDERS}
_REQUEST_LLM_PROVIDER: ContextVar[str | None] = ContextVar("request_llm_provider", default=None)
_REQUEST_LLM_MODEL: ContextVar[str | None] = ContextVar("request_llm_model", default=None)


def normalize_llm_provider(provider: str | None) -> str:
    return (provider or "").strip().lower().replace("-", "_")


def is_local_llm_provider(provider: str | None) -> bool:
    return normalize_llm_provider(provider) in LOCAL_LLM_PROVIDERS


def is_chat_llm_provider(provider: str | None) -> bool:
    return normalize_llm_provider(provider) in CHAT_LLM_PROVIDERS


def set_request_llm(provider: str | None, model: str | None) -> None:
    _REQUEST_LLM_PROVIDER.set(normalize_llm_provider(provider) if provider else None)
    _REQUEST_LLM_MODEL.set(model.strip() if isinstance(model, str) and model.strip() else None)


def resolve_llm(provider: str, model: str) -> tuple[str, str]:
    return _REQUEST_LLM_PROVIDER.get() or provider, _REQUEST_LLM_MODEL.get() or model


def is_chat_provider_configured(provider: str | None) -> bool:
    normalized = normalize_llm_provider(provider)
    if normalized == "openai":
        return bool(OPENAI_API_KEY)
    if normalized in LOCAL_LLM_PROVIDERS:
        return bool(RAG_LOCAL_LLM_BASE_URL)
    return False


def provider_unconfigured_message(provider: str | None) -> str:
    normalized = normalize_llm_provider(provider)
    if normalized == "openai":
        return "OPENAI_API_KEY is not configured"
    if normalized in LOCAL_LLM_PROVIDERS:
        return "RAG_LOCAL_LLM_BASE_URL is not configured"
    return f"Unsupported LLM provider: {provider}"


def chat_completion(
    *,
    provider: str,
    model: str,
    temperature: float,
    max_tokens: int,
    messages: list[dict[str, str]],
) -> str:
    from openai import OpenAI

    normalized = normalize_llm_provider(provider)
    if normalized == "openai":
        client = OpenAI(api_key=OPENAI_API_KEY)
    elif normalized in LOCAL_LLM_PROVIDERS:
        client = OpenAI(api_key=RAG_LOCAL_LLM_API_KEY or "local", base_url=RAG_LOCAL_LLM_BASE_URL)
    else:
        raise RuntimeError(f"Unsupported LLM provider: {provider}")

    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""
