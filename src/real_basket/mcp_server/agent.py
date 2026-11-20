"""Strands orchestration using only FastMCP-exported tools (no direct Python data tools)."""
from __future__ import annotations

from collections.abc import Sequence

from real_basket.agents.orchestrator import create_model
from real_basket.agents.prompts import DISCLAIMER
from real_basket.mcp_server.client import url

MCP_PROMPT = f"""Du bist der RealBasket-Agent. Antworte immer auf Deutsch, mit prüfbaren Quellenangaben.
Nutze AUSSCHLIESSLICH MCP-Tools für Zahlen und Berechnungen; niemals Zahlen selbst erfinden.
get_dashboard_snapshot liefert verifizierte Indexergebnisse, get_prices und get_observations die Serien.
search_documents liefert ausschließlich Methodik- und Quellenkontext aus Weaviate, NIE Rechenwerte.
Keine regionalen Nettogehälter oder Landesmieten behaupten, solange sie nicht in geprüften Quellen vorliegen.
Die ECLI-Kosten sind MODELLIERT (nicht beobachtete Supermarktpreise); Stadtmieten sind Angebotsmieten.
Am Ende jeder Antwort: {DISCLAIMER}
"""


def ask(question: str, history: Sequence[dict] = ()) -> tuple[str, list[str], list]:
    """Open MCP connection during the agent request; preserve last chat turns as contextual text.

    Returns the answer, the names of the invoked MCP tools and the Strands messages of this turn (for the number
    guardrail and the Monitoring tab)."""
    from strands import Agent
    from strands.tools.mcp import MCPClient
    from mcp.client.streamable_http import streamablehttp_client

    client = MCPClient(lambda: streamablehttp_client(url()))
    with client:
        agent = Agent(name="REALBASKET-MCP-ORCHESTRATOR", system_prompt=MCP_PROMPT,
                      model=create_model(), tools=client.list_tools_sync(), callback_handler=None)
        prior = history[-8:]
        context = "\n".join(f"{('Nutzer' if msg['role']=='user' else 'Assistent')}: {msg['content']}" for msg in prior)
        text = f"Bisheriger Gesprächskontext:\n{context}\n\nNeue Frage: {question}" if context else question
        response = str(agent(text))
        invoked = []
        for msg in agent.messages:
            for block in msg.get("content", []) if isinstance(msg, dict) else []:
                if isinstance(block, dict) and "toolUse" in block:
                    invoked.append(block["toolUse"].get("name", "?"))
        return response, invoked, list(agent.messages)
