"""Agent factory: orchestrator agent that uses a collector sub-agent ("agents as tools" pattern)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import openai
from strands import Agent, tool
from strands.models.openai import OpenAIModel

from real_basket.agents.prompts import COLLECTOR_PROMPT, ORCHESTRATOR_PROMPT
from real_basket.agents.tools import (
    calculate_essential_vs_cpi,
    fetch_official_cpi,
    fetch_prices,
    fetch_regional_rents,
    investigate_deviation,
    search_methodology,
)
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
    settings = get_settings()
    cls = AzureOpenAIModel if llm.use_azure(settings) else OpenAIModel
    return cls(
        client_args=llm.client_kwargs(settings),
        model_id=llm.completion_model_id(settings),
        params={"temperature": temperature},
    )


@tool
def collect_category_prices(category: str) -> str:
    """Delegate price collection for one expenditure group of the reference basket ('food', 'housing_energy',
    'mobility', 'health', 'communication') to the specialised Price Collector agent and return its summary."""
    collector = Agent(
        name="REALBASKET-COLLECTOR",
        system_prompt=COLLECTOR_PROMPT,
        model=create_model(),
        tools=[fetch_prices],
        callback_handler=None,
    )
    return str(collector(f"Collect and summarise prices for category '{category}'."))


def create_orchestrator() -> Agent:
    settings = get_settings()
    return Agent(
        name=settings.AGENT_NAME,
        system_prompt=ORCHESTRATOR_PROMPT,
        model=create_model(),
        tools=[collect_category_prices, fetch_official_cpi, calculate_essential_vs_cpi, fetch_regional_rents,
               investigate_deviation, search_methodology],
        callback_handler=None,
    )
