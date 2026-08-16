from __future__ import annotations

from rag_luat_gt.generation.llm_client import (
    is_chat_llm_provider,
    is_local_llm_provider,
    normalize_llm_provider,
    provider_unconfigured_message,
)


def test_qwen_local_provider_aliases_are_supported() -> None:
    assert normalize_llm_provider("qwen-local") == "qwen_local"
    assert is_local_llm_provider("qwen_local")
    assert is_local_llm_provider("qwen")
    assert is_chat_llm_provider("qwen_local")
    assert is_chat_llm_provider("openai")


def test_unknown_provider_reports_clear_configuration_error() -> None:
    assert provider_unconfigured_message("unknown") == "Unsupported LLM provider: unknown"
