"""Number guardrail: every figure in an agent answer must be backed by a tool result.

The system prompt forbids own calculations, but a prompt cannot enforce it. This check runs AFTER each answer
(dashboard chat and CLI) and lists the figures that do not appear in any tool result of that turn, so the user
sees them flagged. It does not rewrite the answer (no second LLM call, deterministic, fast).

What is checked
- Numbers with a decimal part ("2,93") and numbers with a unit (%, PP / Prozentpunkte, €, Euro, €/m²).
- A figure counts as backed if a tool value rounds to it at the precision written in the answer (2,9 % is backed by
  2.93), ignoring the sign, or if it equals 100 x a tool value (weights 0.523 -> 52,3 %).
- Not checked: plain integers without unit (counts such as "15 Städte", page numbers), years and dates
  ("10/2026", "31.10.2026", "2026-10"), and numbers the user wrote in the question.

Limits: it verifies figures, not statements (a correct number attached to the wrong group is not detected).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any

# dates / periods are removed before numbers are scanned
_DATES = re.compile(r"\b\d{1,2}\.\d{1,2}\.\d{2,4}\b|\b\d{1,2}/\d{4}\b|\b\d{4}-\d{2}(?:-\d{2})?\b|\b\d{4}–\d{4}\b")
# German format: 1.234,56 | 2,93 | 1.234 (thousands) | also English 2.93
_NUMBER = re.compile(r"(?<![\w.,])[-+−]?(?:\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)(?![\w])")
_UNIT = re.compile(r"^\s*(?:%|PP\b|pp\b|Prozentpunkt|Prozent\b|€|EUR\b|Euro\b|Indexpunkt)")
_TOOL_NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:[eE]-?\d+)?")


def _parse(token: str) -> tuple[float, int]:
    """'1.234,56' -> (1234.56, 2), '2,9' -> (2.9, 1), '2.93' -> (2.93, 2), '1.234' -> (1234.0, 0)."""
    t = token.lstrip("+-−")
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", t):
        t = t.replace(".", "")                              # German thousands separator
    decimals = len(t.split(".")[1]) if "." in t else 0
    return float(t), decimals


def answer_figures(text: str) -> list[tuple[str, float, int]]:
    """Figures in an answer that must be backed: (as written, absolute value, decimals)."""
    clean = _DATES.sub(" ", text)
    figures = []
    for m in _NUMBER.finditer(clean):
        value, decimals = _parse(m.group())
        has_unit = bool(_UNIT.match(clean[m.end():]))
        if decimals == 0 and not has_unit:
            continue                                         # counts, page numbers, years
        if decimals == 0 and 1900 <= value <= 2100:
            continue
        figures.append((m.group().strip(), abs(value), decimals))
    return figures


def _walk(obj: Any) -> Iterable[str]:
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list | tuple):
        for v in obj:
            yield from _walk(v)
    elif isinstance(obj, bool):
        return
    elif isinstance(obj, int | float):
        yield repr(obj)
    elif isinstance(obj, str):
        yield obj


def tool_values(messages: list) -> set[float]:
    """All numbers contained in the tool results (`toolResult` blocks) of Strands agent messages."""
    values: set[float] = set()
    for msg in messages:
        for block in msg.get("content", []) if isinstance(msg, dict) else []:
            if not (isinstance(block, dict) and "toolResult" in block):
                continue
            for text in _walk(block["toolResult"].get("content", [])):
                try:                                         # JSON in text blocks: parse to keep exact floats
                    texts = list(_walk(json.loads(text)))
                except (TypeError, ValueError):
                    texts = [text]
                for t in texts:
                    values.update(abs(float(n)) for n in _TOOL_NUMBER.findall(t))
    return values


def _backed(value: float, decimals: int, sources: set[float]) -> bool:
    tol = 0.5 * 10 ** -decimals + 1e-9
    return any(abs(v - value) <= tol or abs(v * 100 - value) <= tol for v in sources)


def unverified_figures(answer: str, messages: list, question: str = "") -> list[str]:
    """Figures of `answer` that no tool result of `messages` (nor the question) backs - empty list = all fine."""
    sources = tool_values(messages) | {v for _, v, _ in answer_figures(question)}
    return list(dict.fromkeys(tok for tok, value, dec in answer_figures(answer) if not _backed(value, dec, sources)))


def warning_text(figures: list[str]) -> str:
    """German note shown below an answer with unverified figures."""
    return ("⚠️ Nicht durch Tool-Ergebnisse belegt (bitte prüfen): " + ", ".join(figures)) if figures else ""
