# RealBasket – Architecture Summary

*MCP + Weaviate + Agent Service v3 – condensed version of architecture-detailed.pdf – status 11/2026*

## 1. What RealBasket Does

RealBasket builds an **Essential Living Cost Index (ECLI)** from five essential expenditure groups – food, housing / energy, mobility, health and communication – and compares it with the official German consumer price index (**VPI, Destatis**). It explains *why* the two differ, category by category.

Demo figures: ECLI **2,93 %** YoY vs. VPI **2,83 %**, a deviation of **+0,11 PP**; the biggest driver is **Mobilität**.

> **Design principle:** *non-deterministic shell, deterministic core.* The LLM selects tools and writes German prose. Python computes **every** number. A guardrail checks each figure in the answer against tool results.

## 2. Architecture at a Glance

```
 Browser :8501
    |
 realbasket-ui      Streamlit          - no data access, no LLM key
    |  HTTP
 realbasket-agent   FastAPI v3 :8002   - Strands agent + guardrail + trace
    |  MCP (streamable-http /mcp)
 realbasket-mcp     FastMCP :8001      - 12 tools, deterministic core
    |                       |
 SQLite                  Weaviate 1.32.3 :8080
 all figures + source    PDF text chunks only
    ^ import (11 checks)    ^ index (text only)
    +--- reports/real-data/*.pdf (read-only) ---+
```

**Key rule:** every interaction goes UI → Agent API → MCP. Only the MCP container touches SQLite, Weaviate and the PDFs. At runtime all figures come from **SQLite**; the PDFs are read only by the import.

| Service | Role | Key facts |
|---|---|---|
| `realbasket-ui` | Streamlit dashboard | KPI bar, tabs Index vs. VPI, Einflussfaktoren, Stadtmieten, PDF-Suche, MCP-Agent, Monitoring; imports only `agent_service.client` |
| `realbasket-agent` | FastAPI gateway v3 | `GET /health`, `POST /chat` (agent + guardrail + trace), `POST /tools/{name}` with an allow-list of 5 read tools (others → 404); not published to the host |
| `realbasket-mcp` | FastMCP tool server | 12 tools (e.g. `calculate_index`, `get_dashboard_snapshot`, `search_documents`, `get_prices`); runs the import at start-up |
| `weaviate` | Vector store | Collection `RealBasketDocuments`; vectors computed client-side with Azure OpenAI embeddings |

## 3. Data and Storage

- **Sources:** only the reference PDFs in `reports/real-data` (Destatis EVS 2023 base amounts, modelled monthly costs 11/2024–10/2026, VPI rebased to 11/2024 = 100, immowelt asking rents for the 15 largest cities). **No synthetic or demo data.**
- **Import with 11 checks:** sums, first month = base basket, no gaps, row sums, recomputed vs. printed ECLI and yearly rates, cross-report consistency, VPI per month, city rents, state coverage. If any check fails, nothing is written and the previous dataset stays.
- **SQLite – single read source:** validated dataset plus provenance (file + page) in one transaction; opened read-only at runtime and cached per import id. A test forbids PDF reads at runtime.
- **Weaviate – context only:** prose and non-numeric table cells, chunked to ≤ 800 characters. **Numeric cells are dropped**, so numbers can never come from RAG.
- **Not provided, so never estimated:** rent per federal state, net salaries, live data after 10/2026.

## 4. Deterministic Core and Guardrail

- **Index math (`core/index.py`):** Laspeyres-type fixed-weight index (weights = base amount ÷ total); YoY matched by date; always computed on the full series, so rates do not depend on the chosen window.
- **Deviation drivers (`core/investigation.py`):** the per-category gaps add up exactly to the total deviation:

```
gap_pp(c) = w_c * (I_c(t) - I_c(t-12)) / E(t-12) * 100  -  w_c * CPI_YoY(t)
sum over c of gap_pp(c) = ECLI_YoY(t) - CPI_YoY(t)
```

- **Prompt contract:** answer in German, numbers **only** from MCP tools, `search_documents` for method context only, always end with the disclaimer that a deviation does not mean the VPI is wrong.
- **Number guardrail (`agents/guardrail.py`):** extracts figures with decimals or units from the answer and checks them against all `toolResult` values (or the question). Unbacked figures are returned as `unverified` and **flagged, never rewritten**.
- **Monitoring:** compact traces from the agent messages; the UI draws a Graphviz path per request with numbered edges (max. 30 per session, nothing persisted).

## 5. Main Flows

| Flow | Path | LLM |
|---|---|---|
| Dashboard | UI → `/tools/get_dashboard_snapshot` → MCP → SQLite → core → charts + KPIs | no |
| Chat | UI → `/chat` → new Strands agent (Azure OpenAI) → MCP tools → guardrail + trace → UI | yes – tool choice and prose only |
| Import | `mcp-entrypoint.sh`: PDFs → 11 checks → SQLite; optionally chunks → embeddings → Weaviate | no |

## 6. Deployment, Quality and Security

- **Docker Compose:** four services started in health-check order weaviate → mcp → agent → ui; host ports bound to **127.0.0.1**; image `python:3.11-slim`; secrets loaded from `.env` at runtime and excluded from the image.
- **Configuration:** Azure OpenAI (`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_COMPLETION_MODEL`, `AZURE_EMBEDDING_MODEL`), service URLs (`REALBASKET_MCP_URL`, `REALBASKET_AGENT_URL`), `REALBASKET_SQLITE_PATH`, Weaviate host and ports.
- **Tests (pytest + ruff):** UI uses the HTTP client only, allow-list 404, guardrail, lossless SQLite round trip, no runtime PDF reads, fixed-base rates, index math, drivers, chunking without figures, encoding.
- **In place:** localhost-only ports, Agent API not published, read-only `/tools` allow-list, path-traversal protection, request size limits, number guardrail.
- **Open before external use:** containers run as root, no auth / TLS on Agent API and MCP, anonymous Weaviate, chat agent sees all 12 tools (including write tools), 502 responses echo exception text, the guardrail checks figures, not claims.

## 7. Roadmap

| Phase | Content |
|---|---|
| Now | 4 containers: UI → Agent API v3 → MCP → SQLite / Weaviate |
| Next | Harden: non-root user, auth (Entra ID / OAuth 2.1), TLS, separate tool allow-list for the chat agent, Key Vault |
| A2A | Specialist agents (price collector, deviation analyst, methodology, report) as A2A services |
| Scale | `destatis-genesis` MCP server (live VPI), new sources, OpenTelemetry, Azure Container Apps |

## 8. Key Takeaways

1. **The LLM never calculates** – figures come from tested Python and are checked by the guardrail.
2. **MCP is the single data boundary** – the UI has no data access and no key.
3. **Two stores, two jobs** – SQLite holds all numbers with file + page; Weaviate holds text for context only.
4. **Real data only, checked 11 times at import** – gaps in the sources are stated, not estimated.
5. **Traceable by design** – every request is visible as a path in the monitoring tab.
6. **Honest about gaps** – root containers, no auth / TLS and broad chat tool access are next to fix.
