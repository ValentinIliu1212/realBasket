# 🧺 RealBasket

> *What does living really cost?* An agentic AI system that captures prices of essential living costs
> (food, rent, energy, mobility), builds a realistic **essential living cost index** and compares it
> with the official **Consumer Price Index (CPI)**.

**Important:** A deviation does not mean that the official CPI is wrong. The two indices use different
baskets of goods and different weightings.

> **Data:** the essential basket, the CPI (VPI) and the rents of the 15 largest cities are **real data** read
> deterministically from the reference PDFs in `reports/real-data` (ECLI model calculation: Destatis EVS 2023
> expenditure + official price indices, 11/2024–10/2026) and re-checked in code (11 checks), then
> **imported into SQLite**. At runtime every figure is read from SQLite (`data_store/realbasket.sqlite3`); the PDFs
> are only read by the import (`python -m real_basket.storage --mode sql`). There is **no synthetic demo data**:
> without the import the app shows an error instead of numbers. The sources contain no rent per
> federal state and no net salaries – these are reported as "not in the reference data", never estimated.
> The UI is fully German.

## Start for the presentation from Valentin's laptop (Windows + Podman, 5 PowerShell windows)

The app consists of four processes: **Weaviate** (vector DB, Podman), **MCP server** (port 8001),
**Agent API** (port 8002) and the **Streamlit UI** (port 8501). The UI only talks to the Agent API; if
that is not running, the UI shows *"RealBasket Agent API not reachable (http://127.0.0.1:8002)"*.

Prerequisites: `poetry install` and a `.env` in the repo root - see [Setup](#setup).

Open five PowerShell windows and keep all of them open. Every window except window 1 starts in the repo root:

```powershell
cd C:\Users\EILIUVACT\eclipse-workspace\realBasket
```

**Window 1 - Weaviate (ports 8080 / 50051)**

```powershell
# Stop leftovers from earlier runs and reset WSL (avoids the Podman ssh port conflict)
Get-NetTCPConnection -LocalPort 8001,8002,8501 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
Remove-Item Env:DOCKER_HOST -ErrorAction SilentlyContinue
wsl --shutdown

# Run Weaviate in the foreground inside the Podman VM (keeps the VM alive; ports are forwarded to Windows)
wsl -d podman-machine-default -u root -- sh -c "podman rm -f realbasket-weaviate >/dev/null 2>&1; exec podman run --rm --name realbasket-weaviate -p 8080:8080 -p 50051:50051 -e QUERY_DEFAULTS_LIMIT=25 -e AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true -e PERSISTENCE_DATA_PATH=/var/lib/weaviate -e DEFAULT_VECTORIZER_MODULE=none -e ENABLE_MODULES= -e CLUSTER_HOSTNAME=node1 -v realbasket_weaviate_data:/var/lib/weaviate mirror.gcr.io/semitechnologies/weaviate:1.32.3"
```

**Window 2 - load data + MCP server (port 8001)**

```powershell
(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8080/v1/.well-known/ready).StatusCode   # expect 200
Get-Content .env | Where-Object { $_ -match '^\s*[A-Z_]+=' } | ForEach-Object { $k,$v = $_ -split '=',2; Set-Item "Env:$($k.Trim())" $v.Trim() }
poetry run python -m real_basket.storage --mode sql      # import: PDFs -> 11 checks -> SQLite (rerun after PDF changes)
poetry run python -m real_basket.storage --mode vector   # once; the Weaviate volume keeps the index
poetry run real-basket-mcp --transport streamable-http
```

**Window 3 - Agent API (port 8002)**

```powershell
Get-Content .env | Where-Object { $_ -match '^\s*[A-Z_]+=' } | ForEach-Object { $k,$v = $_ -split '=',2; Set-Item "Env:$($k.Trim())" $v.Trim() }
poetry run uvicorn real_basket.agent_service.api:app --host 127.0.0.1 --port 8002
```

**Window 4 - Streamlit UI (port 8501)**

```powershell
poetry run streamlit run src/real_basket/ui/app.py
```

**Window 5 - smoke test, then open http://localhost:8501**

```powershell
(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8002/health).Content   # {"status":"ok","service":"realbasket-agent"}
Invoke-WebRequest -UseBasicParsing -Method Post -ContentType 'application/json' -Body '{"arguments":{"query":"Miete"}}' http://127.0.0.1:8002/tools/search_documents | Select-Object StatusCode
```

Stop: `Ctrl+C` in windows 4, 3, 2 and 1.

Troubleshooting:

| Symptom | Cause / fix |
|---------|-------------|
| `Agent API not reachable (http://127.0.0.1:8002)` | Window 3 not running |
| `SQLite database ... not found` / `no validated dataset` | Import missing: `poetry run python -m real_basket.storage --mode sql` (window 2), then reload |
| `machine not in running state` / `dial tcp 127.0.0.1:<port>` | Stale WSL relay holds the Podman ssh port: `wsl --shutdown`, restart window 1 |
| `toomanyrequests: ... pull rate limit` | Docker Hub limit; use the `mirror.gcr.io/...` image as above |
| Document search fails | Weaviate not ready or vector index missing: check window 1, rerun `--mode vector` |
| `podman compose` finds no provider | Not needed - the steps above use plain `podman` |

> With Docker Desktop instead of Podman, the whole stack also starts with `docker compose up --build -d`
> (see `docker-compose.yml`).

### Start for the presentation from Monika's laptop - TODO

> **TODO:** the configuration of the colleague's laptop is not known yet. Fill in once checked:
>
> - [ ] Container runtime: Docker Desktop or Podman? (`docker --version` / `podman --version`)
> - [ ] With Docker Desktop: try the one-liner `docker compose up --build -d`, then open http://localhost:8501
> - [ ] With Podman: does `podman machine start` work, is WSL2 enabled (`wsl --status`)?
> - [ ] Python >= 3.11 and Poetry >= 2.0 installed? (`python --version`, `poetry --version`)
> - [ ] Ports 8001, 8002, 8080, 8501 and 50051 free on 127.0.0.1? (`Get-NetTCPConnection -LocalPort <port>`)
> - [ ] VPN / proxy: can the laptop reach the Azure OpenAI endpoint and `mirror.gcr.io`?
> - [ ] PowerShell profile: no stray `DOCKER_HOST` set (`$env:DOCKER_HOST` should be empty for Podman)
> - [ ] `.env` with the Azure OpenAI settings copied to the repo root (never commit it)
> - [ ] Document the exact start sequence that worked here

## Features

| Feature | Description |
|---------|-------------|
| Essential living cost index | Weighted index of the 5 basket groups (Lebensmittel, Wohnen / Energie, Verkehr, Gesundheit, Kommunikation), base 11/2024 = 100, adjustable weights |
| Real-data import | `python -m real_basket.storage --mode sql` → `data/real_data.py`: tables of the reference PDFs parsed without LLM, 11 re-checks (sums, gaps, printed ECLI and yearly rates recomputed by the engine, city rents, state coverage, …) |
| SQLite data store | `storage/sqlite_store.py`: **single read source** of all figures (dashboard, MCP tools, PDF reports, CLI). Validated dataset tables + provenance (`documents`, `observations` with file + page); an import is written in one transaction and only if all 11 checks pass |
| CPI comparison | YoY rate of the essential index vs. official VPI, deviation in percentage points |
| Deviation drivers | Exact contribution of every category to the deviation (`core/investigation.py`) |
| City rents | 15 largest cities: real asking rents Jan vs. Oct 2026 (immowelt, from the reference PDF), incl. 75-m² flat |
| Coverage per federal state | 16 states: no verified state rent series in the sources; lists the cities with published rents |
| PDF reports | One PDF per year + city rents + CPI report (German, EUR), generated from the real data |
| AI agent | Strands chat agent that decides itself which tools to call; numbers only from deterministic tools; answers in German |
| Method notes (RAG) | Search over method notes and caveats of reference PDFs (`reports/real-data`), cited with file + page. Context only – figures never come from text search |

## Architecture

Design rationale: [docs/process-redesign.md](docs/process-redesign.md).

Architecture slides in `docs/architecture/`:

| Deck | Content | Rebuild |
|------|---------|---------|
| `RealBasket_Docker_Compose_DE.pptx` / `_EN.pptx` | **Current architecture** (4 slides each, NTT DATA template): cover, diagram `RealBasket-Architektur mit Docker Compose.png`, the four services and data flows, results and next steps | `poetry run python docs/architecture/build_docker_decks.py` (uses `docs/architecture/templates/agentic-ai-strands.pptx`) |
| `RealBasket_Architektur_Ist.pptx` | earlier state (German) | `poetry run python docs/architecture/build_decks.py` |
| `RealBasket_Architektur_Vorschlag_MCP_A2A.pptx` | target proposal with MCP servers and A2A agents (German) | same script |

```
Streamlit UI / CLI ──► Orchestrator Agent REALBASKET-ORCHESTRATOR (LLM chooses the tools)
                         ├─ calculate_essential_vs_cpi  ──► core/index.py          (deterministic)
                         ├─ investigate_deviation       ──► core/investigation.py  (category → item → region)
                         ├─ collect_category_prices     ──► Collector Agent ──► fetch_prices
                         ├─ fetch_official_cpi / fetch_regional_rents (cities + state coverage)
                         └─ search_methodology          ──► knowledge/ (RAG over reference PDFs)
```

- **The agent decides** which tools a question needs and how deep to drill down ("why?" → category, then item
  or region). **Code decides the numbers**: the LLM never calculates rates itself.
- **RAG** (`src/real_basket/knowledge/`):
  - *Ingest* (pypdf): prose paragraphs (method notes, caveats, data-quality hints) and the non-numeric cells of
    tables become passages. Numeric cells are dropped on purpose; passages repeated across yearly reports are
    stored once with all locations.
  - *Search*: `bm25` (offline, German-aware: stemming, compounds such as Kaltmiete → Nettokaltmiete,
    English → German glossary) or `embedding` (OpenAI, fused with BM25). `auto` = embedding if an API key is
    set; embedding errors fall back to BM25. The index `data_store/knowledge/index.json` is rebuilt
    automatically when the PDFs change.

```
src/real_basket/
├── agents/          # orchestrator.py (chat agent + collector sub-agent), prompts.py, tools.py
├── core/
│   ├── index.py         # essential index + CPI comparison
│   ├── investigation.py # deviation drivers, drill-down by item / city, state coverage
│   ├── llm.py           # OpenAI / Azure OpenAI provider
│   └── settings.py      # .env based configuration
├── data/
│   ├── real_data.py     # PDF table parser + 11 re-checks (used by the SQLite import only)
│   └── basket.py        # load_basket(): validated dataset from SQLite, raises RealDataError
├── knowledge/       # RAG: ingest.py (passages), search.py (index, BM25 / embeddings, CLI)
├── storage/         # sqlite_store.py (import + single read source), weaviate_store.py (vector index)
├── reports/pdf_report.py  # PDF generation (reportlab)
├── schemas/models.py
├── ui/app.py        # Streamlit dashboard
└── cli.py           # chat CLI
```

## Setup

Requirements: Python ≥ 3.11, [Poetry](https://python-poetry.org/) ≥ 2.0, an OpenAI API key (only for the agent).

```powershell
git clone https://github.com/ValentinIliu1212/realBasket.git
cd realBasket
poetry install
poetry run pytest
```

Create a `.env` in the repo root (git-ignored, never commit it):

```dotenv
OPENAI_API_KEY=
OPENAI_MODEL_ID=gpt-4o-mini
OPENAI_API_TYPE=azure
OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<your-key>
AZURE_EMBEDDING_MODEL=text-embedding-3-large
AZURE_COMPLETION_MODEL=gpt-4o
```

> Windows: if `poetry` is not on PATH, use `& "$env:APPDATA\Python\Scripts\poetry.exe"` instead.

## Usage

```powershell
# Import the reference PDFs into SQLite (required once and after every PDF change)
poetry run python -m real_basket.storage --mode sql

# Dashboard (http://localhost:8501)
poetry run streamlit run src/real_basket/ui/app.py

# Ask the agent from the command line
poetry run real-basket-cli "Are basic living costs rising faster than official inflation? Why?"
poetry run real-basket-cli "In welchen Großstädten sind die Mieten am stärksten gestiegen?"

# PDF reports from the real data (written to ./reports, git-ignored)
poetry run real-basket-pdf --out reports

# Method notes of the reference PDFs (versioned in ./reports/real-data)
poetry run real-basket-knowledge --rebuild
poetry run real-basket-knowledge --query "Ist Wohnen / Energie die Nettokaltmiete?"
```

Settings in `.env`: `OPENAI_API_KEY`, `OPENAI_MODEL_ID`,
`KNOWLEDGE_DIR` (default `reports/real-data`; source of the real data and the method notes), `KNOWLEDGE_RETRIEVER` (`auto` | `bm25` | `embedding`),
`EMBEDDING_MODEL_ID`, `KNOWLEDGE_TOP_K` (4). Relative paths are resolved against the project root if they do not
exist in the current folder, and `.env` is read from the project root – so the app works from any folder.

> **"0 Dokumente" in the method-notes tab?** Up to commit `cd9772a` the whole `/reports` folder was git-ignored,
> so the reference PDFs never reached other machines. They are now versioned (`reports/real-data/*.pdf`):
> `git pull` and restart Streamlit.

**Azure OpenAI** instead of api.openai.com (an Azure key sent to OpenAI fails with `401 Incorrect API key`):

```dotenv
OPENAI_API_TYPE=azure
OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<key>
AZURE_COMPLETION_MODEL=gpt-4o                  # chat deployment name
AZURE_EMBEDDING_MODEL=text-embedding-3-large   # embedding deployment name (method-note search)
```

The sidebar shows the active provider (`Azure OpenAI · gpt-4o`). Provider selection lives in
`src/real_basket/core/llm.py`.
Without the SQLite import (`python -m real_basket.storage --mode sql`) the dashboard, the agent tools and the PDF
reports stop with an error (no fallback, no implicit import).

### Dashboard tabs

| Tab | Content |
|-----|---------|
| Header | ECLI and VPI year on year, deviation and biggest driver of the latest month + data basis |
| 📈 Index vs. VPI | Both indices (base 11/2024 = 100), YoY rates, modelled monthly costs per group |
| 🧩 Einflussfaktoren | Contribution of each category to the deviation; data checks and base amounts |
| 🏠 Stadtmieten | Published asking rents of the 15 largest cities (Jan/Oct 2026); coverage per federal state |
| 📄 PDF-Suche (Weaviate) | Semantic search over the reference PDFs (passages with file + page; context only) |
| 🤖 MCP-Agent | Chat (German) via the agent service; MCP tools used per answer; guardrail warning for unbacked figures |
| 🛰️ Monitoring | Use-case path of every interaction through the four Docker services (per browser session) |

All data reaches the UI through the agent API (`/tools/{name}`, allow-list) and the MCP server - the UI never
reads PDFs, SQLite or Weaviate directly.

### PDF reports

| File | Content |
|------|---------|
| `realbasket_preise_<year>.pdf` | 2024–2026: modelled monthly costs (EUR) per group + sum; ECLI (recomputed and printed) and VPI |
| `realbasket_miete_staedte.pdf` | Asking rents of the 15 largest cities (€/m², 75 m², Jan vs. Oct 2026); coverage per federal state |
| `realbasket_verbraucherpreisindex.pdf` | VPI vs. ECLI (11/2024 = 100) per month, YoY rates, deviation; data checks |

## Methodology

- **Category index:** mean of item price relatives vs. base month (= 100).
- **Essential index:** weighted sum of category indices. Default weights – real data: expenditure shares of the
  ECLI reference basket (base amounts 11/2024 ÷ 2.174 €: Wohnen / Energie 52,3 %, Lebensmittel 20,1 %, Verkehr
  16,6 %, Kommunikation 6,5 %, Gesundheit 4,5 %).
- **Real-data re-checks** (`data/real_data.py`): base amounts sum to the total, first month = base basket, no
  gaps, row sums, ECLI recomputed by the engine = printed ECLI (≤ 0,05), both ECLI tables agree, printed yearly
  rates reproduced, repeated values identical across reports, VPI present for every month, city rent changes and
  75-m² rents recomputed, federal-state coverage consistent with the city table.
- **CPI comparison:** YoY rates of both indices; deviation = essential YoY − CPI YoY in percentage points (pp).
- **Drivers:** contribution_pp = weight × change of the category index ÷ previous essential index × 100;
  gap_pp = contribution − weight × CPI YoY. The gaps add up to the deviation.
- **Ø across all cities:** unweighted mean (not weighted by population).
- **Federal states:** no state averages are derived from city values (not representative); only the coverage is shown.
- The essential index uses "Wohnen / Energie" of the reference basket (more than the net cold rent); city rents
  are shown separately and do not feed into the index.

## Next steps (hackathon backlog)

> **Current state:** all figures are real data from the reference PDFs (11/2024–10/2026). Not available in the
> sources and therefore not shown: rents per federal state, net salaries / rent burden, live updates.

### 1. Extend the real data
Add live collectors (one module per source under `src/real_basket/data/`) that return `PricePoint` / `CpiPoint`
objects, so the calculations stay unchanged.

| Category | Candidate sources |
|----------|-------------------|
| CPI (official) | Destatis GENESIS API, table `61111-0002` (token in `.env`: `DESTATIS_GENESIS_TOKEN`), Eurostat HICP |
| Food | Destatis sub-indices (food 01.1), supermarket price APIs / web scraping |
| Rent | Destatis rent index, Mietspiegel data, rental portals |
| Rent per state / largest cities | BBSR Angebotsmieten, Destatis Mietenindex per Bundesland, price atlases |
| Net salary per state | Destatis Verdiensterhebung + net calculation, BA Entgeltatlas |
| Energy | Bundesnetzagentur, tariff comparison portals, Destatis energy sub-indices |
| Mobility | Tankerkoenig fuel price API, public transport tariffs (Deutschlandticket) |

- [x] Import the monthly tables of the reference PDFs (`reports/real-data`) as a data source, re-checked in code and stored in SQLite (single read source)
- [ ] Implement `fetch_official_cpi` with the Destatis GENESIS API (live updates beyond 10/2026)
- [x] Generate the PDF reports from the real basket
- [x] Remove the synthetic demo data (no fallback)
- [ ] Verified rent series per federal state and net salaries (new sources) – then rent burden

### 2. Later (out of hackathon scope)
- [ ] Scheduled monitoring with validation, human approval and audit trail (a first version existed as a
      Strands Graph up to commit `f9344ef` and was removed to keep the demo focused)
- [ ] Compare a focus category with the matching CPI sub-index (e.g. energy vs. CPI energy)
- [ ] Household profiles (single, family, commuter), population weighting, rent burden per city
- [ ] CI pipeline (ruff + pytest), Dockerfile

## Contributing

1. Clone the repo and run `poetry install`, then copy `.env.example` to `.env`.
2. Create a feature branch: `git checkout -b feature/<short-name>`.
3. Run `poetry run ruff check .` and `poetry run pytest` before pushing (the suite includes an encoding check:
   every source and doc file must be UTF-8 without broken umlauts).
4. Open a merge/pull request against `main`.

Never commit `.env` or API keys. Generated PDFs (`/reports/*.pdf`) and the local index + SQLite database (`/data_store`) are
git-ignored; the reference PDFs in `reports/real-data` are versioned (source of the real data).
## RealBasket v3: separat deployter Strands-Agent

Mit `docker compose up --build -d` starten vier Dienste:

1. `realbasket-ui` (Streamlit 8501): reiner HTTP-Client zu `realbasket-agent`.
2. `realbasket-agent` (FastAPI 8002, nur internes Docker-Netz): Strands-Orchestrator + MCP Gateway.
3. `realbasket-mcp` (FastMCP 8001): kontrollierte Daten-/Berechnungstools; importiert beim Start die
   Referenz-PDFs nach SQLite und liest alle Zahlen nur aus SQLite (PDFs nur für Import und Download).
4. `weaviate` (8080/50051): semantischer PDF-Index.

Details und Windows-Befehle unter [`docs/AGENT_SERVICE_V3.md`](docs/AGENT_SERVICE_V3.md).

### Monitoring-Tab

Der Tab **🛰️ Monitoring** zeigt für jede Interaktion den Pfad durch die vier Dienste als Graphviz-Diagramm mit
nummerierten Kanten und als Schritttabelle (`src/real_basket/ui/monitoring.py`):

| Vorgang | Pfad |
|---------|------|
| Dashboard / Referenz-PDF / Berichte | UI → Agent-API `/tools/{name}` (Allow-List) → MCP → Rechenkern → SQLite (Download: Original-PDF) – kein LLM |
| Weaviate-Suche | UI → Agent-API → MCP → Embedding-Modell + Weaviate |
| Chatfrage | UI → Agent-API `/chat` → Strands-Agent → LLM-Aufrufe und MCP-Tool-Aufrufe → Zahlen-Guardrail → UI |

Der Verlauf gilt **nur für die aktuelle Browser-Sitzung** (max. 30 Vorgänge, nichts wird gespeichert).

### Zahlen-Guardrail

`/chat` prüft im Agent-Service jede Zahl der Antwort gegen die Tool-Ergebnisse der Frage
(`agents/guardrail.py`) und liefert `unverified`, `figures_checked` und kompakte `trace_messages`
(`agents/trace.py`, ohne große Tool-Payloads). Nicht belegte Zahlen erscheinen im Chat als Warnung.

### Rechenkern: feste Basisperiode

Der Index wird immer auf der **vollständigen Reihe** berechnet (Basis 11/2024 = 100) und erst danach auf
`months` gekürzt; Vorjahresraten vergleichen denselben Kalendermonat (`core/index.py`). Dashboard und
Chat-Tools liefern dadurch dieselben Werte, unabhängig von `months` (`tests/test_calculation_consistency.py`).

Ein PDF-Upload über die Oberfläche ist nicht geplant.
