"""FastAPI gateway: UI -> agent API -> MCP; no direct financial access in UI.

/chat is the LLM-backed Strands agent. /tools/{name} passes deterministic requests to MCP.
Both run in thread workers to avoid blocking the ASGI event loop.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool


log = logging.getLogger(__name__)
app = FastAPI(title="RealBasket Agent", version="3.0.0")

# Explicit allow-list: the UI cannot trigger arbitrary MCP operations.
UI_TOOLS = frozenset({
    "get_dashboard_snapshot", "list_reference_pdfs", "get_reference_pdf",
    "generate_reports", "search_documents",
})


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=12000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class ToolRequest(BaseModel):
    arguments: dict = Field(default_factory=dict)


@app.get("/health")
def health() -> dict:
    # Liveness only; readiness is checked through real MCP tool calls.
    return {"status": "ok", "service": "realbasket-agent"}


@app.post("/chat")
async def chat(payload: ChatRequest) -> dict:
    """Answer + invoked tools + number-guardrail result + compact turn messages (for the Monitoring tab)."""
    try:
        # Import lazily so UI tool proxy can run even without LLM credentials.
        from real_basket.mcp_server.agent import ask
        answer, invoked, messages = await run_in_threadpool(
            ask, payload.question, [item.model_dump() for item in payload.history]
        )
    except Exception as exc:
        log.exception("Agent execution failed")
        raise HTTPException(status_code=502, detail=f"Agent/MCP failure: {exc}") from exc
    from real_basket.agents.guardrail import answer_figures, unverified_figures
    from real_basket.agents.trace import compact_messages

    # guardrail runs here: only the agent service sees the full tool results of the turn
    return {"answer": answer, "tools": invoked,
            "unverified": unverified_figures(answer, messages, payload.question),
            "figures_checked": len(answer_figures(answer)),
            "trace_messages": compact_messages(messages)}


@app.post("/tools/{tool_name}")
async def tool_proxy(tool_name: str, payload: ToolRequest) -> dict:
    if tool_name not in UI_TOOLS:
        raise HTTPException(status_code=404, detail="Tool not available through UI gateway")
    try:
        from real_basket.mcp_server.client import call_tool
        result = await run_in_threadpool(call_tool, tool_name, **payload.arguments)
        return {"result": result}
    except Exception as exc:
        log.exception("MCP tool %s failed", tool_name)
        raise HTTPException(status_code=502, detail=f"MCP tool {tool_name} failed: {exc}") from exc
