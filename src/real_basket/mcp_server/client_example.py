"""Example: run the existing Strands agent with remote RealBasket MCP tools.

Run the MCP server first: real-basket-mcp --transport streamable-http
Then: python -m real_basket.mcp_server.client_example
"""
from __future__ import annotations

import os

from real_basket.agents.orchestrator import create_model
from real_basket.agents.prompts import ORCHESTRATOR_PROMPT


def main() -> None:
    from strands import Agent
    from strands.tools.mcp import MCPClient
    from mcp.client.streamable_http import streamablehttp_client

    url = os.getenv('REALBASKET_MCP_URL', 'http://127.0.0.1:8001/mcp')
    mcp = MCPClient(lambda: streamablehttp_client(url))
    with mcp:
        agent = Agent(name='REALBASKET-MCP-ORCHESTRATOR',
                      system_prompt=ORCHESTRATOR_PROMPT + '\nUse MCP numerical tools for numbers; '
                      'Weaviate results provide context only. Cite filename and PDF page. '
                      'Never claim modelled expenses are observed transaction prices.',
                      model=create_model(), tools=mcp.list_tools_sync())
        print(agent('Wie hat sich der ECLI relativ zum VPI entwickelt? Gib die Quellen an.'))


if __name__ == '__main__':
    main()
