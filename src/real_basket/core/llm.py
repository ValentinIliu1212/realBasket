"""LLM provider selection for the chat agent: OpenAI (api.openai.com) or Azure OpenAI.

Azure is used when OPENAI_API_TYPE=azure (or when only AZURE_OPENAI_ENDPOINT is set). On Azure the
"model" is the deployment name (AZURE_COMPLETION_MODEL). Embeddings for the Weaviate index are configured in
`storage/weaviate_store.py` (AZURE_EMBEDDING_MODEL / EMBEDDING_MODEL_ID from the environment).
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


def completion_model_id(settings: Settings | None = None) -> str:
    s = settings or get_settings()
    return (s.AZURE_COMPLETION_MODEL or s.OPENAI_MODEL_ID) if use_azure(s) else s.OPENAI_MODEL_ID


def client_kwargs(settings: Settings | None = None) -> dict[str, Any]:
    """Constructor arguments for openai.(Async)OpenAI or openai.(Async)AzureOpenAI."""
    s = settings or get_settings()
    if use_azure(s):
        return {"api_key": api_key(s), "azure_endpoint": s.AZURE_OPENAI_ENDPOINT, "api_version": s.OPENAI_API_VERSION}
    return {"api_key": api_key(s)}
