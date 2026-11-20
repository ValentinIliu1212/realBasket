# 🧺 RealBasket

> *What does living really cost?* An agentic AI system that captures prices of essential living costs
> (food, rent, energy, mobility), builds a realistic **essential living cost index** and compares it
> with the official **Consumer Price Index (CPI)**.

**Important:** A deviation does not mean that the official CPI is wrong. The two indices use different
baskets of goods and different weightings.

> **Data:** the essential basket, the CPI (VPI) and the rents of the 15 largest cities are **real data** read
> deterministically from the reference PDFs in `reports/real-data` (ECLI model calculation: Destatis EVS 2023
> expenditure + official price indices, 11/2024–10/2026) and re-checked in code. There is **no synthetic demo
> data**: without the reference PDFs the app shows an error instead of numbers. The sources contain no rent per
> federal state and no net salaries – these are reported as "not in the reference data", never estimated.
> The UI is fully German.

## Demo in 3 minutes

1. `poetry run streamlit run src/real_basket/ui/app.py` → the header shows essential inflation, VPI, the
   deviation and its **biggest driver** ("Größter Einflussfaktor") at a glance (real data 10/2026: 2,93 % vs. 2,83 %, +0,11 PP, driver
   Verkehr / Mobilität). The expander **Datenprüfung** lists the 11 re-checks of the PDF import.
2. Move the **basket weights** in the sidebar → index, deviation and drivers update immediately (untouched
   sliders = exact expenditure shares of the reference basket).
3. **🧩 Einflussfaktoren**: which category causes the deviation (contributions add up exactly to the deviation).
4. **🏠 Miete Städte**: real asking rents of the 15 largest cities (€/m² and 75-m² flat, Jan vs. Oct 2026) and
   the coverage per federal state (which cities have published rents – no state averages).
5. **📚 Methodenhinweise (RAG)**: search the unstructured reference PDFs, e.g. *"Ist Wohnen / Energie die
   Nettokaltmiete?"* → passage with file and page.
6. **🤖 Chat mit RealBasket**: click an example question; the answer (always German) shows which tools were used.
7. Sidebar **📄 PDF-Berichte**: download the reference PDFs and the German RealBasket reports generated from them.

## Features

| Feature | Description |
|---------|-------------|
| Essential living cost index | Weighted index of the 5 basket groups (Lebensmittel, Wohnen / Energie, Verkehr, Gesundheit, Kommunikation), base 11/2024 = 100, adjustable weights |
| Real-data import | `data/real_data.py`: tables of the reference PDFs parsed without LLM, 11 re-checks (sums, gaps, printed ECLI and yearly rates recomputed by the engine, city rents, state coverage, …) |
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
│   ├── real_data.py     # deterministic import + re-checks of the reference PDF tables
│   └── basket.py        # load_basket(): real data only, raises RealDataError
├── knowledge/       # RAG: ingest.py (passages), search.py (index, BM25 / embeddings, CLI)
├── reports/pdf_report.py  # PDF generation (reportlab)
├── schemas/models.py
├── ui/app.py        # Streamlit dashboard
└── cli.py           # chat CLI
```

## Setup

Requirements: Python ≥ 3.11, [Poetry](https://python-poetry.org/) ≥ 2.0, an OpenAI API key (only for the agent).

```powershell
git clone https://github.com/ValentinIliu1212/real-basket.git
cd real-basket
poetry install
copy .env.example .env   # add your own OPENAI_API_KEY
poetry run pytest
```

> Windows: if `poetry` is not on PATH, use `& "$env:APPDATA\Python\Scripts\poetry.exe"` instead.

### Eclipse (optional)

All files are **UTF-8** (German umlauts, emoji in the UI). `.settings/org.eclipse.core.resources.prefs` and
`.editorconfig` preset UTF-8. If umlauts show up as two odd characters (e.g. an A with tilde instead of ü) in Eclipse, the project still uses the Windows code page:
**Project → Properties → Resource → Text file encoding → Other: UTF-8**, then refresh. Saving a file in that state
breaks it - `tests/test_encoding.py` catches such files.

1. **File → Import… → General → Existing Projects into Workspace**, select the repo folder, leave
   "Copy projects into workspace" unchecked.
2. Install **PyDev** (Eclipse Marketplace), add the Poetry virtualenv interpreter
   (`poetry env info --path` → `Scripts\python.exe`) under **Preferences → PyDev → Interpreters**.
3. Right-click the project → **PyDev → Set as PyDev Project**, add `/real-basket/src` to the PYTHONPATH.
4. Start Streamlit from a terminal (no Eclipse launcher).

## Usage

```powershell
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
Without the reference PDFs the dashboard, the agent tools and the PDF reports stop with an error (no fallback).

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

- [x] Import the monthly tables of the reference PDFs (`reports/real-data`) as a data source, re-checked in code
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

Never commit `.env` or API keys. Generated PDFs (`/reports/*.pdf`) and the local index (`/data_store`) are
git-ignored; the reference PDFs in `reports/real-data` are versioned (source of the real data).
## RealBasket v3: separat deployter Strands-Agent

Mit `docker compose up --build -d` starten vier Dienste:

1. `realbasket-ui` (Streamlit 8501): reiner HTTP-Client zu `realbasket-agent`.
2. `realbasket-agent` (FastAPI 8002, nur internes Docker-Netz): Strands-Orchestrator + MCP Gateway.
3. `realbasket-mcp` (FastMCP 8001): kontrollierte Daten-/Berechnungstools und Original-PDF-Zugriff.
4. `weaviate` (8080/50051): semantischer PDF-Index.

Details und Windows-Befehle unter [`docs/AGENT_SERVICE_V3.md`](docs/AGENT_SERVICE_V3.md).

### Monitoring-Tab

Der Tab **🛰️ Monitoring** zeigt für jede Interaktion den Pfad durch die vier Dienste als Graphviz-Diagramm mit
nummerierten Kanten und als Schritttabelle (`src/real_basket/ui/monitoring.py`):

| Vorgang | Pfad |
|---------|------|
| Dashboard / Referenz-PDF / Berichte | UI → Agent-API `/tools/{name}` (Allow-List) → MCP → Rechenkern / Daten / PDFs – kein LLM |
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
