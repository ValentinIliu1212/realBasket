# RealBasket – Detailed Architecture

*MCP + Weaviate + Agent Service v3 – technical deep dive for peers – status 11/2026*

## 1. Purpose in One Minute

RealBasket builds an **Essential Living Cost Index (ECLI)** from five essential expenditure groups and compares it with the official German consumer price index (**VPI, Destatis**). It explains *why* the two differ, category by category.

| Group (code) | German label |
|---|---|
| `food` | Lebensmittel |
| `housing_energy` | Wohnen / Energie |
| `mobility` | Mobilität |
| `health` | Gesundheit |
| `communication` | Kommunikation |

The demo figures (hackathon deck) are ECLI **2,93 %** YoY vs. VPI **2,83 %**, a deviation of **+0,11 PP**. The biggest driver is **Mobilität**.

> **Design principle:** *non-deterministic shell, deterministic core.* The LLM selects tools and writes German prose. Python computes **every** number. A guardrail checks each figure in the answer against tool results.

## 2. Data Basis

- **Sources:** only the reference PDFs in `reports/real-data` (setting `KNOWLEDGE_DIR`), read **without an LLM** by `data/real_data.py` – **only during the import** into SQLite. At runtime every figure is read from SQLite.
- **Content of the PDFs:**
  - monthly base amounts per group (Destatis EVS 2023) and modelled monthly costs in EUR, 11/2024–10/2026;
  - the VPI rebased to 11/2024 = 100;
  - immowelt asking rents for the 15 largest cities (Jan vs. Oct 2026), including a 75 m² flat;
  - per federal state, either the covered cities or "Keine verifizierte Monatsreihe".
- **There is no synthetic or demo data.** `load_basket()` raises `RealDataError` if the SQLite database or the imported dataset is missing (no fallback, no implicit import).
- **Deliberately not provided, so never estimated:** rent per federal state, net salaries and live updates after 10/2026. `DESTATIS_GENESIS_TOKEN` is reserved but nothing uses it.

**The 11 import checks in `build_dataset()`** (an import is written to SQLite only if all of them pass):

1. Base amounts add up to the printed SUMME.
2. The first month equals the base basket.
3. The monthly series has no gaps.
4. Row sums are consistent.
5. The ECLI recomputed by the engine matches the printed ECLI (tolerance 0.051).
6. Both ECLI tables agree.
7. Printed yearly rates are reproduced (tolerance 0.06).
8. Values do not conflict across the reports.
9. The VPI is present for every month.
10. City rents are recomputed (change and 75 m² rent).
11. State coverage is consistent with the city table.

## 3. Runtime Architecture (4 Containers)

```
 Browser
    |  http://127.0.0.1:8501
+---v-------------------------------------------------------------+
| realbasket-ui        Streamlit  (ui/app.py)                     |
|                      talks ONLY to agent_service.client (HTTP)  |
+---+-------------------------------------------------------------+
    |  REALBASKET_AGENT_URL = http://realbasket-agent:8002
+---v-------------------------------------------------------------+
| realbasket-agent     FastAPI "RealBasket Agent" v3.0.0  :8002   |
|                      /health  /chat  /tools/{name} (allow-list) |
|                      Strands Agent + guardrail + trace          |
+---+-------------------------------------------------------------+
    |  REALBASKET_MCP_URL = http://realbasket-mcp:8001/mcp
+---v-------------------------------------------------------------+
| realbasket-mcp       FastMCP "realbasket"  streamable-http :8001|
|                      12 tools; deterministic core (core/, data/)|
+------+--------------------------+-------------------------------+
       |                          |
  SQLite (volume)            Weaviate 1.32.3  :8080 / gRPC :50051
  realbasket.sqlite3         collection RealBasketDocuments
  SINGLE READ SOURCE:        (text chunks, client-side vectors)
  dataset + provenance
       ^ import (11 checks)       ^ index (text only)
       +---- reports/real-data/*.pdf (read-only mount) ----+
```

**Key rule:** the UI holds **no data access and no LLM key**. Every interaction goes UI → Agent API → MCP. Only the MCP container reads the PDFs, SQLite and Weaviate. At runtime all figures come from **SQLite**; the PDFs are read only by the import (and served as originals for download).

## 4. Source Layout (`src/real_basket/`)

| Package | Responsibility | Key symbols |
|---|---|---|
| `schemas/` | Domain types | `Category`, `CATEGORY_LABEL_DE`, `RegionType`, `PricePoint`, `CpiPoint`, `ComparisonPoint`, `BasketWeights` (validator: weights sum to 1) |
| `data/` | PDF parser + checks (import only); basket from SQLite | `parse_document`, `build_dataset`, `RealDataset`, `Check`, `load_real_data` (import side); `load_basket` → `sqlite_store.load_dataset`, `Basket` |
| `core/` | Math, settings, LLM config | `index.py`, `investigation.py`, `settings.py`, `llm.py` |
| `knowledge/` | Chunker + local RAG | `ingest.py` (chunking), `search.py` (`KnowledgeBase`, BM25/embedding/RRF) |
| `storage/` | Persistence; **SQLite = single read source** | `sqlite_store.py` (`persist_reference_pdfs`, `load_dataset`, `dataset_info`, `get_observations`), `weaviate_store.py`, `python -m real_basket.storage --mode sql\|vector\|all` |
| `mcp_server/` | MCP tool server + MCP agent | `server.py` (FastMCP), `agent.py` (`ask`), `client.py` (`call_tool`), `client_example.py` |
| `agent_service/` | HTTP gateway v3 | `api.py` (FastAPI), `client.py` (httpx, used by the UI) |
| `agents/` | Prompts, guardrail, trace, local tools | `prompts.py`, `guardrail.py`, `trace.py`, `tools.py`, `orchestrator.py` |
| `reports/` | German PDF reports | `generate_yearly_price_reports`, `generate_rent_report`, `generate_cpi_report`, `generate_all` |
| `ui/` | Dashboard + monitoring | `app.py`, `monitoring.py` |
| `cli.py` | Local CLI | `real-basket-cli` (local orchestrator, **not** via MCP) |

## 5. Deterministic Core

### 5.1 Index math (`core/index.py`)

- `category_indices`: price ratio vs. the base month × 100 (one item per group).
- `essential_index`: the weighted sum of category indices. With the default weights (base amount ÷ total) this is a **Laspeyres-type fixed-weight index**.
- `compare_with_cpi`: the VPI is rebased to the first common month. The outputs are `essential_yoy_pct`, `cpi_yoy_pct` and `deviation_pp`.
- `yoy_pct` matches values **by date**, not by row offset.
- **Fixed base:** the index is always computed on the full series and only then cut to `months`, so rates do not depend on the chosen window. A regression test covers the earlier 2,91 vs. 2,93 issue.

### 5.2 Deviation drivers (`core/investigation.py`)

```
contribution_pp(c) = w_c * (I_c(t) - I_c(t-12)) / E(t-12) * 100
gap_pp(c)          = contribution_pp(c) - w_c * CPI_YoY(t)
sum over c of gap_pp(c) = ECLI_YoY(t) - CPI_YoY(t)      (exact)
```

- The categories are sorted by the size of `gap_pp`; the first one is "the biggest driver" shown in the KPI bar.
- Further functions: `item_changes`, `city_rent_changes`, `state_rent_coverage` and `regional_rent_changes` (with `STATE_NOTE`).

## 6. MCP Server (`mcp_server/server.py`)

- **Setup:** `FastMCP("realbasket", host=MCP_HOST, port=MCP_PORT)`. The defaults are 127.0.0.1:8001; the container uses 0.0.0.0.
- **Transport:** `--transport stdio|streamable-http`. The HTTP endpoint is `/mcp`.
- **Tools only**, no MCP resources or prompts.

| Tool | Parameters | Backed by |
|---|---|---|
| `ingest_reference_pdfs` | – | `sqlite_store.persist_reference_pdfs` (import: PDFs → 11 checks → SQLite) |
| `index_pdf_knowledge` | – | `weaviate_store.ingest_pdf_directory` (write) |
| `search_documents` | `query`, `top_k=5`, `year=0` | Weaviate similarity search |
| `get_observations` | `category`, `region`, `metric`, `start`, `end` | SQLite query |
| `get_prices` | `category='food'`, `months=24` | `agents.tools.fetch_prices` → SQLite |
| `get_cpi` | `months=24` | `fetch_official_cpi` → SQLite |
| `calculate_index` | `months=24` | `calculate_essential_vs_cpi` → SQLite |
| `get_city_rents` | – | `fetch_regional_rents('stadt')` → SQLite |
| `get_dashboard_snapshot` | – | from SQLite: comparison, category indices, breakdown, prices, cities, states, checks, `data_store` (import id + time) |
| `generate_reports` | – | `generate_all` from SQLite into a temp dir, returned as `{filename: base64}` |
| `list_reference_pdfs` | – | file names and sizes |
| `get_reference_pdf` | `filename` | Base64 content; basename + `.pdf` check against path traversal |

## 7. Agent Layer

### 7.1 MCP agent (`mcp_server/agent.py::ask`) – used by `/chat`

- Opens `MCPClient(streamablehttp_client(REALBASKET_MCP_URL))`. The default URL is `http://127.0.0.1:8001/mcp`.
- Creates a **new** Strands `Agent("REALBASKET-MCP-ORCHESTRATOR")` for every question, with `MCP_PROMPT` and `tools=client.list_tools_sync()`, i.e. all 12 tools.
- Passes the last 8 history messages as plain text context.
- Returns the answer, the invoked tool names and the raw `agent.messages`.
- **Model:** Azure OpenAI (`AZURE_COMPLETION_MODEL`, e.g. `gpt-4o`) or OpenAI (`OPENAI_MODEL_ID`), temperature 0.2.

### 7.2 Local orchestrator (`agents/orchestrator.py`) – used by the CLI

- `REALBASKET-ORCHESTRATOR` with in-process Strands tools: `collect_category_prices`, `fetch_official_cpi`, `calculate_essential_vs_cpi`, `fetch_regional_rents`, `investigate_deviation` and `search_methodology`.
- `collect_category_prices` delegates to a `REALBASKET-COLLECTOR` **sub-agent** that has only `fetch_prices`.
- `investigate_deviation` and `search_methodology` (local BM25/embedding RAG) exist **only** on this path, not in MCP.

### 7.3 Prompt contract (`agents/prompts.py`)

- Answer in German, with German number formatting and "Prozentpunkte".
- Take numbers **only** from tools and never compute rates. Search results are context, never figures.
- Never claim state rents or net salaries. ECLI costs are *modelled*; city rents are *asking* rents.
- Cite passages as `[Datei S. N]`. Answer with a headline plus at most 5 bullets.
- For *why* questions, start at category level, then drill down to item or region.
- Always end with the `DISCLAIMER`: a deviation does not mean the VPI is wrong.

### 7.4 Number guardrail (`agents/guardrail.py`)

- `answer_figures` extracts numbers that have decimals or a unit (%, PP, Prozentpunkt, €, EUR, Indexpunkt). It skips dates, years 1900–2100 and plain integers.
- `tool_values` collects every number from the `toolResult` blocks, parsing JSON text.
- **Backed if** a tool value matches within half a unit of the written precision (sign-insensitive), or equals 100 × a tool value (weights shown as %), or the user wrote the number in the question.
- `unverified_figures` returns the unbacked figures, and `warning_text` turns them into a German warning. **The answer is flagged, never rewritten.**

### 7.5 Trace compaction (`agents/trace.py`)

`compact_messages()` keeps text (at most 2000 characters), `toolUse` (id, name, input) and `toolResult` status plus only the `error`/`retriever`/`warning` keys and the passage count. Large payloads never cross HTTP to the UI.

## 8. Agent Service v3 (`agent_service/api.py`)

| Endpoint | Behaviour |
|---|---|
| `GET /health` | `{"status":"ok","service":"realbasket-agent"}` (liveness) |
| `POST /chat` | `ChatRequest{question ≤ 12000 chars, history ≤ 20}`. Runs `ask()` in a thread pool, then the guardrail and the trace. Returns `{answer, tools, unverified, figures_checked, trace_messages}` |
| `POST /tools/{tool_name}` | Allow-list `UI_TOOLS`; other names get **404**. Forwards to MCP via `mcp_server.client.call_tool` and returns `{"result": ...}` |

- **`UI_TOOLS`:** `get_dashboard_snapshot`, `list_reference_pdfs`, `get_reference_pdf`, `generate_reports` and `search_documents`.
- **Errors:** agent or MCP failures map to HTTP **502**.
- **UI client** (`agent_service/client.py`): base URL `REALBASKET_AGENT_URL` (default `http://127.0.0.1:8002`), timeout 180 s, and readable `RuntimeError` messages.

## 9. Storage Layer

### 9.1 SQLite – single read source (`storage/sqlite_store.py`)

```
documents(
  sha256 PK, filename, pages, data_basis,
  ingested_at DEFAULT CURRENT_TIMESTAMP)

observations(
  document_sha256 FK -> documents, period 'YYYY-MM',
  category, region, metric, value_eur REAL, unit,
  source_page, data_basis,
  PK(document_sha256, period, category, region, metric))
INDEX obs_period(period, category, region)

-- validated dataset: replaced per import, read by load_dataset()
dataset_meta(key, value)   -- import_id, imported_at, base_total, periods
dataset_documents(position, filename)
base_amounts(position, category, amount_eur)
prices(position, period, category, item, price_eur, unit, source)
cpi(position, period, index_value, source)
printed_ecli(period, ecli, ecli_yoy_pct)
city_rents(position, city, state, rent_jan/oct_eur_m2, rent_jan/oct_flat_eur,
           change_pct, source)
state_coverage(position, state, cities_json, verified_state_series, status, source)
checks(position, name, ok, detail)
```

- `persist_reference_pdfs` refuses to write (`ValueError`) if **any** of the 11 checks fails; the previous dataset stays untouched. Dataset and provenance are written in **one transaction**; reruns are idempotent.
- **Costs** are stored with metric `essential_cost`, `EUR/month`, region `Deutschland` and data_basis `modelled`.
- **City rents** are stored with category `Miete`, region "City, State", metric `asking_cold_rent`, `EUR/m2` and data_basis `published_asking_rent`, for months 2026-01 and 2026-10.
- `get_observations`: parameterised filters, at most 10 000 rows.
- **Read side:** `load_dataset()` opens SQLite **read-only**, rebuilds the `RealDataset` losslessly (tested: identical to the PDF import) and caches it per `import_id`, so a re-import is picked up without a restart.
- **No PDF access at runtime:** dashboard, calculation tools, reports and CLI all go through `load_basket()` → SQLite (a test forbids any PDF read). A missing database raises `RealDataError` with the import command.

### 9.2 Weaviate – methodology text search (`storage/weaviate_store.py`)

- **Connection:** `weaviate.connect_to_local(WEAVIATE_HOST, WEAVIATE_HTTP_PORT=8080, WEAVIATE_GRPC_PORT=50051)`, wrapped in LangChain `WeaviateVectorStore`.
- **Collection:** `WEAVIATE_INDEX_NAME`, default `RealBasketDocuments`. Text key `text`; metadata `chunk_id`, `section`, `kind`, `source_file`, `page`, `locations`, `years`.
- **Embeddings:** `AzureOpenAIEmbeddings(AZURE_EMBEDDING_MODEL)`, otherwise `OpenAIEmbeddings(EMBEDDING_MODEL_ID)`. Weaviate runs with `vectorizer none`, so **vectors are computed on the client side**.
- **Idempotent IDs:** `uuid5(NAMESPACE_URL, "realbasket:" + chunk_id)`. Existing IDs are deleted before re-adding.
- **Search:** `search_documents` allows k from 1 to 30 and filters by year after retrieval. Every hit carries a "context only" warning.

### 9.3 Chunking (`knowledge/ingest.py`, shared)

- Repeated page headers are stripped from the pypdf text.
- Prose becomes `note` chunks; non-numeric table cells become `table` chunks.
- **Numeric cells are dropped**, so numbers can never come from RAG.
- Chunks are at most 800 characters, split on sentences.
- The id is `n-` + the first 10 hex characters of the SHA-1 of the normalised text. Duplicates are merged, keeping all their locations and years.

## 10. End-to-End Flows

### 10.1 Dashboard (no LLM)

```
Streamlit snapshot()  [st.cache_data ttl=90s]
 -> POST agent:8002/tools/get_dashboard_snapshot   (allow-list ok)
 -> mcp_server.client.call_tool -> mcp:8001/mcp
 -> load_basket() -> sqlite_store.load_dataset()  (read-only, cached per import)
 -> core.index / core.investigation -> JSON -> charts + KPIs
```

### 10.2 Chat question

```
UI chat(question, history)
 -> POST /chat -> thread pool -> ask()
 -> new MCP session + Strands agent (Azure OpenAI)
 -> LLM picks MCP tools (calculate_index, get_prices, search_documents, ...)
 -> German answer
 -> guardrail.unverified_figures + trace.compact_messages
 -> UI: answer, "MCP: tool -> tool", warning, monitoring trace
```

### 10.3 Ingest and indexing (never triggered from the UI)

```
docker/mcp-entrypoint.sh
 1. python -m real_basket.storage --mode sql      -> PDFs -> 11 checks -> SQLite (dataset + provenance)
 2. if REALBASKET_AUTO_INDEX_VECTOR=true:
    python -m real_basket.storage --mode vector   -> chunks -> embeddings -> Weaviate
 3. exec real-basket-mcp --transport streamable-http
```

## 11. User Interface (`ui/app.py`)

- **Imports only `agent_service.client`.** A test enforces that the UI has no data access.
- **Sidebar:** agent URL, reload data, reference-PDF downloads (`list_reference_pdfs`, `get_reference_pdf`) and "Auswertungsberichte generieren" (`generate_reports`).
- **KPI bar:** ECLI YoY, VPI YoY, deviation in PP, biggest driver.

| Tab | Content |
|---|---|
| Index vs. VPI | plotly lines; EUR-per-month area chart |
| Einflussfaktoren | `gap_pp` bars; checks and base amounts |
| Stadtmieten | 15 city rents; state coverage |
| PDF-Suche (Weaviate) | `search_documents`, top 5 |
| MCP-Agent | chat, tool path, guardrail warning, "Neuer Chat" |
| Monitoring | Graphviz path per request (`ui/monitoring.py`) |

**Monitoring:** `Trace`/`Step` objects are built from `trace_messages`. `TOOL_HOPS` maps every MCP tool to its internal hops, and a test checks that the map matches `server.py`. `to_dot()` draws one cluster per container with numbered edges. Up to 30 traces are kept in session state; nothing is persisted.

## 12. Deployment

### 12.1 Docker Compose (project `realbasket`)

| Service | Image / command | Host port | Volumes | Waits for |
|---|---|---|---|---|
| `weaviate` | `weaviate:1.32.3`, vectorizer none | 127.0.0.1:8080, :50051 | `weaviate_data` | – (healthcheck `/v1/.well-known/ready`) |
| `realbasket-mcp` | build `.`, `mcp-entrypoint.sh` | 127.0.0.1:8001 | `realbasket_data:/app/data_store`, PDFs read-only | weaviate healthy |
| `realbasket-agent` | `uvicorn ...agent_service.api:app` | **none** (`expose: 8002`) | – | mcp healthy |
| `realbasket-ui` | `streamlit run ...ui/app.py` | 127.0.0.1:8501 | – | agent healthy |

- **Image:** `python:3.11-slim` with `pip install .`.
- **Secrets:** `.env` is loaded at runtime through `env_file` and excluded from the image by `.dockerignore`.
- **Weaviate on its own:** `docker-compose.weaviate.yml`.

### 12.2 Local development start (README, Windows + Podman)

1. Start Weaviate via Podman (WSL machine `podman-machine-default`).
2. Load `.env`, run `storage --mode sql`, then `--mode vector` once, then `real-basket-mcp --transport streamable-http`.
3. `uvicorn real_basket.agent_service.api:app --port 8002`.
4. `streamlit run src/real_basket/ui/app.py`.
5. Smoke test with `GET /health` and `POST /tools/search_documents`.

Alternative: `docker compose up --build -d`.

## 13. Configuration

| Variable | Default / purpose |
|---|---|
| `OPENAI_API_TYPE` | `azure` selects Azure OpenAI (an endpoint alone also does) |
| `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_API_KEY` | Azure resource; the key comes **only** from `.env` or a secret store |
| `OPENAI_API_VERSION` | `2024-02-15-preview` |
| `AZURE_COMPLETION_MODEL` / `AZURE_EMBEDDING_MODEL` | e.g. `gpt-4o` / `text-embedding-3-large` |
| `OPENAI_API_KEY` / `OPENAI_MODEL_ID` | OpenAI path; `gpt-4o-mini`. Keep the key empty with Azure |
| `KNOWLEDGE_DIR` / `DATA_DIR` | `reports/real-data` / `data_store` |
| `KNOWLEDGE_RETRIEVER` / `KNOWLEDGE_TOP_K` | `auto` / 4 (local RAG) |
| `MCP_HOST` / `MCP_PORT` | 127.0.0.1 / 8001 |
| `REALBASKET_MCP_URL` | `http://127.0.0.1:8001/mcp` |
| `REALBASKET_AGENT_URL` | `http://127.0.0.1:8002` |
| `REALBASKET_SQLITE_PATH` | `data_store/realbasket.sqlite3` – read source of all figures |
| `WEAVIATE_HOST` / `_HTTP_PORT` / `_GRPC_PORT` | localhost / 8080 / 50051 |
| `WEAVIATE_INDEX_NAME` | `RealBasketDocuments` |
| `REALBASKET_AUTO_INDEX_VECTOR` | `false` |

## 14. Tech Stack and Quality

- **Runtime:** Python ≥ 3.11, strands-agents[openai] 1.x, mcp ≥ 1.9 (FastMCP), FastAPI + uvicorn, Streamlit + plotly, pandas, pydantic / pydantic-settings, httpx, pypdf, reportlab, weaviate-client ≥ 4.16, langchain-weaviate and langchain-openai.
- **Dev:** pytest, ruff (line length 110) and python-pptx (decks).

| Test | Guards |
|---|---|
| `test_agent_service_v3` | 4 compose services, UI uses the HTTP client only, allow-list 404, `/chat` guardrail, trace compaction |
| `test_compose_mcp_contract` | no forbidden UI imports, `TOOL_HOPS` equals the MCP tools, volumes |
| `test_storage_mcp` | lossless SQLite round trip, no PDF read at runtime, missing-DB error, failed import keeps data, idempotency |
| `test_calculation_consistency` | rates independent of `months` (fixed base) |
| `test_real_data`, `test_index`, `test_investigation` | PDF import, index math, drivers |
| `test_guardrail`, `test_knowledge`, `test_llm` | guardrail, RAG, provider selection |
| `test_monitoring`, `test_pdf_report`, `test_encoding` | traces, PDF output, UTF-8 / mojibake |

## 15. Security Posture

**In place:**

- Host ports bind to **127.0.0.1** only. The Agent API is not published to the host at all.
- Secrets are never baked into the image; `.env` and `*.sqlite3` are listed in `.dockerignore`.
- The UI → `/tools` allow-list exposes 5 read tools. Write tools return 404.
- `get_reference_pdf` blocks path traversal. Request size limits: question ≤ 12 000 characters, history ≤ 20 messages.
- The number guardrail plus "numbers only from tools" contain hallucinated figures.

**Open before any external use:**

- Containers run as **root**: the Dockerfile has no `USER` line.
- There is no authentication or TLS on the Agent API and MCP, and Weaviate allows anonymous access.
- The chat agent sees **all** MCP tools, including `ingest_reference_pdfs` and `index_pdf_knowledge`. The allow-list protects `/tools` only.
- HTTP 502 responses echo exception text.
- `pip install .` without a lock file means builds are not reproducible.
- The guardrail checks figures, not claims.

## 16. Roadmap

| Phase | Content |
|---|---|
| Now | 4 containers: UI → Agent API v3 → MCP → SQLite / Weaviate |
| Next | Harden: non-root user, auth (Entra ID / OAuth 2.1), TLS, a separate tool allow-list for the chat agent, Key Vault |
| A2A | Specialist agents (price collector, deviation analyst, methodology, report) as A2A services with agent cards; the orchestrator as an A2A server |
| Scale | `destatis-genesis` MCP server (live VPI), new sources (state rents, salaries), OpenTelemetry, Azure Container Apps |

## 17. Takeaways for Peers

1. **The LLM never calculates.** Figures come from tested Python and are checked by the guardrail.
2. **MCP is the single data boundary.** UI → Agent API → MCP; the UI has no data access and no key.
3. **Two stores, two jobs.** SQLite is the *single read source of all numbers* (with file + page); Weaviate holds *text for context*, with numeric cells excluded. The PDFs are read only by the import.
4. **Real data only, checked 11 times at import.** Gaps in the sources are stated, not estimated.
5. **Traceable by design.** Compact traces and a Graphviz path for every request in the monitoring tab.
6. **Honest about gaps.** Root containers, no auth/TLS and broad chat tool access are the next items to fix.
