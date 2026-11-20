"""LLM provider selection: OpenAI (api.openai.com) or Azure OpenAI.

Azure is used when OPENAI_API_TYPE=azure (or when only AZURE_OPENAI_ENDPOINT is set). On Azure the
"model" is the deployment name: AZURE_COMPLETION_MODEL for chat, AZURE_EMBEDDING_MODEL for embeddings.
"""

from __future__ import annotations

from typing import Any

from real_basket.core.settings import Settings, get_settings


def use_azure(settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    api_type = s.OPENAI_API_TYPE.strip().lower()
    if api_type:
        return api_type in ("azure", "azure_ad", "azuread")
    return bool(s.AZURE_OPENAI_ENDPOINT)


def api_key(settings: Settings | None = None) -> str:
    s = settings or get_settings()
    key = (s.AZURE_OPENAI_API_KEY or s.OPENAI_API_KEY) if use_azure(s) else s.OPENAI_API_KEY
    return "" if key.startswith("sk-...") else key


def is_configured(settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    return bool(api_key(s)) and (not use_azure(s) or bool(s.AZURE_OPENAI_ENDPOINT))


def completion_model_id(settings: Settings | None = None) -> str:
    s = settings or get_settings()
    return (s.AZURE_COMPLETION_MODEL or s.OPENAI_MODEL_ID) if use_azure(s) else s.OPENAI_MODEL_ID


def embedding_model_id(settings: Settings | None = None) -> str:
    s = settings or get_settings()
    return (s.AZURE_EMBEDDING_MODEL or s.EMBEDDING_MODEL_ID) if use_azure(s) else s.EMBEDDING_MODEL_ID


def provider_label(settings: Settings | None = None) -> str:
    s = settings or get_settings()
    return f"Azure OpenAI · {completion_model_id(s)}" if use_azure(s) else f"OpenAI · {completion_model_id(s)}"


def client_kwargs(settings: Settings | None = None) -> dict[str, Any]:
    """Constructor arguments for openai.(Async)OpenAI or openai.(Async)AzureOpenAI."""
    s = settings or get_settings()
    if use_azure(s):
        return {"api_key": api_key(s), "azure_endpoint": s.AZURE_OPENAI_ENDPOINT, "api_version": s.OPENAI_API_VERSION}
    return {"api_key": api_key(s)}


def sync_client(settings: Settings | None = None):
    """Synchronous client (used for embeddings)."""
    import openai

    s = settings or get_settings()
    cls = openai.AzureOpenAI if use_azure(s) else openai.OpenAI
    return cls(**client_kwargs(s))
