# RealBasket MCP + WeaviateVectorStore + SQLite

This extends the existing Strands/Streamlit project **without replacing** its current `core/index.py`, PDF parser or dashboard. It adds a standalone MCP server and two persistent stores.

## Architecture

PDFs (`reports/real-data/*.pdf`) → validated parser (11 checks, import only) → **SQLite** (validated dataset = single read source of all figures, plus EUR observations with source PDF, page, modelled/observed provenance) → `load_basket()` / all calculation tools and the `get_observations` MCP tool.

PDFs → existing text-only chunker → OpenAI/Azure embeddings → **WeaviateVectorStore** → `search_documents` MCP tool (retrieval and citations, **not numeric calculations**).

The **existing** `calculate_essential_vs_cpi` and index engine remain authoritative; they read their inputs from SQLite. MCP simply wraps them.

### Local startup

```bash
# Poetry installation / update
poetry lock
poetry install
cp .env.example .env  # if no .env exists; configure OPENAI_API_KEY

docker compose -f docker-compose.weaviate.yml up -d
poetry run python -m real_basket.storage --mode sql
poetry run python -m real_basket.storage --mode vector
poetry run real-basket-mcp --transport streamable-http
# Endpoint: http://127.0.0.1:8001/mcp
```

Or for stdio MCP clients:

```bash
poetry run real-basket-mcp --transport stdio
```

To try an existing Strands agent with MCP tools (requires a reachable model provider):

```bash
poetry run python -m real_basket.mcp_server.client_example
```

Example MCP tool calls: `ingest_reference_pdfs`, `index_pdf_knowledge`, `get_observations(category="Lebensmittel")`, `search_documents(query="Wohnen Energie")`, `get_prices(category="food")`, `get_cpi`, `get_city_rents`, `calculate_index`.

### Important source limitations

* Provided reference PDFs contain **modelled ECLI Euro category costs**, derived from official indices; they are not observed shopping transactions.
* City rents are **published asking rents**, not representative of all tenancies.
* No reliable regional salaries or state-level time series are supplied by the three PDFs. **This implementation does not fabricate them.**
* `persist_reference_pdfs` only imports values that the existing deterministic parser recognizes and all validation checks pass. Other PDF types require an explicit parser/mapping and validation before numbers can be used.
* The vector index intentionally excludes numeric table cells. Citation search is separate from arithmetic.
* The document index is rebuilt by `index_pdf_knowledge` on demand. Changing PDFs requires re-running the ingestion steps.
* For use beyond localhost, protect the MCP endpoint with authentication and HTTPS, and configure Weaviate authentication. The sample Compose enables anonymous access but binds ports to loopback only.
* Original PDFs are retained on disk as the immutable source and are read only by the import; SQLite is the runtime read source. Re-run `python -m real_basket.storage --mode sql` after PDF changes (or to rebuild a lost database).

### Project additions

```
src/real_basket/mcp_server/server.py      MCP tool server
src/real_basket/mcp_server/client_example.py  Agent using MCP client
src/real_basket/storage/sqlite_store.py   Financial observations + provenance
src/real_basket/storage/weaviate_store.py  WeaviateVectorStore ingestion + query
src/real_basket/storage/__main__.py       CLI ingestion
Docker compose: docker-compose.weaviate.yml
Tests: tests/test_storage_mcp.py
```

### Production follow-ups

Separate financial uploads by source type; add explicit salary ingestion with household definition, payroll basis, geography, date, and source-page validation. Put PDFs in immutable object storage, adopt a relational database suitable for concurrent writers, add a review workflow for uncertain OCR/extraction, and secure MCP with authorization and auditing.
