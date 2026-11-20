"""Synchronous MCP gateway for Streamlit; all financial data crosses MCP."""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def url() -> str:
    return os.getenv("REALBASKET_MCP_URL", "http://127.0.0.1:8001/mcp")


async def _call(name: str, arguments: dict[str, Any]) -> Any:
    async with streamablehttp_client(url()) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments)
            if result.isError:
                raise RuntimeError("; ".join(getattr(block, "text", str(block)) for block in result.content))
            if result.structuredContent is not None:
                structured = result.structuredContent
                # Different MCP SDK versions may wrap structured output in 'result'.
                if isinstance(structured, dict) and set(structured) == {"result"}:
                    return structured["result"]
                return structured
            texts = [block.text for block in result.content if getattr(block, "type", "") == "text"]
            if not texts:
                raise RuntimeError(f"MCP tool {name} returned no content")
            return json.loads(texts[0])


def call_tool(name: str, **arguments: Any) -> Any:
    return asyncio.run(_call(name, arguments))
