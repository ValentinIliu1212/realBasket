"""LLM model factory for the Strands agent (OpenAI or Azure OpenAI, see `real_basket.core.llm`)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import openai
from strands.models.openai import OpenAIModel

from real_basket.core import llm
from real_basket.core.settings import get_settings


class AzureOpenAIModel(OpenAIModel):
    """Strands OpenAI provider talking to Azure OpenAI (model_id = deployment name).

    Like the base class, a fresh async client is created per request (httpx connections must not be
    shared across asyncio event loops)."""

    @asynccontextmanager
    async def _get_client(self) -> AsyncIterator[Any]:
        async with openai.AsyncAzureOpenAI(**self.client_args) as client:
            yield client


def create_model(temperature: float = 0.2) -> OpenAIModel:
    """Chat model of the MCP agent (`mcp_server.agent.ask`): Azure OpenAI or OpenAI, low temperature."""
    settings = get_settings()
    cls = AzureOpenAIModel if llm.use_azure(settings) else OpenAIModel
    return cls(
        client_args=llm.client_kwargs(settings),
        model_id=llm.completion_model_id(settings),
        params={"temperature": temperature},
    )
