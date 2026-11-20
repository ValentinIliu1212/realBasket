"""Provider selection: OpenAI vs Azure OpenAI (no network calls)."""

import openai
import pytest

from real_basket.agents.orchestrator import AzureOpenAIModel, create_model
from real_basket.core import llm
from real_basket.core.settings import get_settings

AZURE = {"OPENAI_API_TYPE": "azure", "OPENAI_API_VERSION": "2024-02-15-preview",
         "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com/", "AZURE_OPENAI_API_KEY": "azure-key",
         "AZURE_COMPLETION_MODEL": "gpt-4o", "AZURE_EMBEDDING_MODEL": "text-embedding-3-large"}
OPENAI = {"OPENAI_API_TYPE": "", "AZURE_OPENAI_ENDPOINT": "", "AZURE_OPENAI_API_KEY": "",
          "AZURE_COMPLETION_MODEL": "", "AZURE_EMBEDDING_MODEL": "",
          "OPENAI_API_KEY": "sk-test", "OPENAI_MODEL_ID": "gpt-4o-mini",
          "EMBEDDING_MODEL_ID": "text-embedding-3-small"}


@pytest.fixture
def env(monkeypatch):
    def apply(values):
        for k, v in values.items():
            monkeypatch.setenv(k, v)
        get_settings.cache_clear()
        return get_settings()
    yield apply
    get_settings.cache_clear()


def test_azure_settings_are_used(env):
    s = env({**OPENAI, **AZURE})
    assert llm.use_azure(s) and llm.is_configured(s)
    assert llm.completion_model_id(s) == "gpt-4o"
    assert llm.embedding_model_id(s) == "text-embedding-3-large"
    assert llm.client_kwargs(s) == {"api_key": "azure-key", "azure_endpoint": "https://example.openai.azure.com/",
                                    "api_version": "2024-02-15-preview"}
    assert isinstance(llm.sync_client(s), openai.AzureOpenAI)
    model = create_model()
    assert isinstance(model, AzureOpenAIModel)
    assert model.config["model_id"] == "gpt-4o"


def test_azure_key_falls_back_to_openai_key(env):
    s = env({**OPENAI, **AZURE, "AZURE_OPENAI_API_KEY": "", "OPENAI_API_KEY": "shared-key"})
    assert llm.api_key(s) == "shared-key"


def test_plain_openai_is_default(env):
    s = env(OPENAI)
    assert not llm.use_azure(s) and llm.is_configured(s)
    assert llm.completion_model_id(s) == "gpt-4o-mini"
    assert llm.client_kwargs(s) == {"api_key": "sk-test"}
    model = create_model()
    assert not isinstance(model, AzureOpenAIModel)


def test_placeholder_key_is_not_configured(env):
    s = env({**OPENAI, "OPENAI_API_KEY": "sk-..."})
    assert not llm.is_configured(s)
