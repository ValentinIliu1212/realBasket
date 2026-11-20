"""Compact, JSON-safe copy of the Strands messages of one chat turn for the Monitoring tab.

The agent service runs the number guardrail itself (it has the full tool results). The UI only needs the shape of
the turn - LLM calls, tool calls with arguments, success / error of each result - so large tool payloads (e.g. the
dashboard snapshot) are reduced to a few status fields before they cross HTTP.
"""
from __future__ import annotations

import json
from typing import Any

MAX_TEXT = 2000
STATUS_KEYS = ("error", "retriever", "warning")


def _payload(result: dict) -> dict | None:
    for block in result.get("content", []) or []:
        if not isinstance(block, dict):
            continue
        if isinstance(block.get("json"), dict):
            return block["json"]
        if isinstance(block.get("text"), str):
            try:
                data = json.loads(block["text"])
            except ValueError:
                continue
            if isinstance(data, dict):
                return data
    return None


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, ensure_ascii=False))


def compact_messages(messages: list) -> list[dict]:
    """[{role, content: [text | toolUse | toolResult(status + small JSON summary)]}] of a chat turn."""
    out: list[dict] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        blocks = []
        for block in msg.get("content", []) or []:
            if not isinstance(block, dict):
                continue
            if isinstance(block.get("text"), str):
                blocks.append({"text": block["text"][:MAX_TEXT]})
            elif isinstance(block.get("toolUse"), dict):
                use = block["toolUse"]
                blocks.append({"toolUse": {"toolUseId": use.get("toolUseId"), "name": use.get("name"),
                                           "input": _jsonable(use.get("input") or {})}})
            elif isinstance(block.get("toolResult"), dict):
                res = block["toolResult"]
                payload = _payload(res) or {}
                summary = {k: _jsonable(payload[k]) for k in STATUS_KEYS if k in payload}
                if isinstance(payload.get("passages"), list):
                    summary["passages"] = len(payload["passages"])
                blocks.append({"toolResult": {"toolUseId": res.get("toolUseId"), "status": res.get("status"),
                                              "content": [{"json": summary}]}})
        out.append({"role": msg.get("role"), "content": blocks})
    return out
