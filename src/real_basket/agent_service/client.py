"""UI-only synchronous HTTP client to standalone realbasket-agent service."""
from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

import httpx


def url() -> str:
    return os.environ.get("REALBASKET_AGENT_URL", "http://127.0.0.1:8002").rstrip("/")


def _post(endpoint: str, payload: dict, timeout: float = 90) -> dict:
    try:
        response = httpx.post(f"{url()}{endpoint}", json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("detail", exc.response.text)
        except ValueError:
            detail = exc.response.text
        raise RuntimeError(f"RealBasket Agent API {exc.response.status_code}: {detail}") from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"RealBasket Agent API not reachable ({url()}): {exc}") from exc


def call_tool(name: str, **arguments: Any) -> Any:
    return _post(f"/tools/{quote(name, safe='')}", {"arguments": arguments}, timeout=180)["result"]


def ask(question: str, history: list[dict] | None = None) -> tuple[str, list[str]]:
    data = chat(question, history)
    return data["answer"], data.get("tools", [])


def chat(question: str, history: list[dict] | None = None) -> dict:
    """Full /chat response: answer, tools, unverified (guardrail), figures_checked, trace_messages."""
    return _post("/chat", {"question": question, "history": history or []}, timeout=180)
