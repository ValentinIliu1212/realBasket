"""Standalone MCP server exposing existing RealBasket deterministic tools + storage.

stdio for local clients; streamable-http for remote clients. No A2A requirement.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP('realbasket', host=os.getenv('MCP_HOST', '127.0.0.1'),
              port=int(os.getenv('MCP_PORT', '8001')))


def _reference_dir() -> Path:
    from real_basket.data.real_data import real_data_dir
    return real_data_dir()


@mcp.tool()
def ingest_reference_pdfs() -> dict:
    """Read bundled ECLI reference PDF tables, validate, and persist modeled EUR observations to SQLite."""
    from real_basket.storage.sqlite_store import persist_reference_pdfs
    return persist_reference_pdfs(_reference_dir())


@mcp.tool()
def index_pdf_knowledge() -> dict:
    """Embed explanatory text and document provenance from source PDFs in WeaviateVectorStore."""
    from real_basket.storage.weaviate_store import ingest_pdf_directory
    return ingest_pdf_directory(_reference_dir())


@mcp.tool()
def search_documents(query: str, top_k: int = 5, year: int = 0) -> dict:
    """Semantically search PDF explanations. Results are not authoritative numerical inputs."""
    from real_basket.storage.weaviate_store import search_documents as search
    return search(query, top_k, year)


@mcp.tool()
def get_observations(category: str = '', region: str = '', metric: str = '',
                     start: str = '', end: str = '') -> list[dict]:
    """Retrieve exact, source-attributed EUR rows from SQLite; optional equality and period filters."""
    from real_basket.storage.sqlite_store import get_observations as get
    return get(category, region, metric, start, end)


@mcp.tool()
def get_prices(category: str = 'food', months: int = 24) -> dict:
    """Get PDF-sourced ECLI modelled price series using the existing validated data functions."""
    from real_basket.agents.tools import fetch_prices
    return fetch_prices(category=category, months=months)


@mcp.tool()
def get_cpi(months: int = 24) -> dict:
    """Get PDF-sourced official CPI series rebased to November 2024."""
    from real_basket.agents.tools import fetch_official_cpi
    return fetch_official_cpi(months=months)


@mcp.tool()
def calculate_index(months: int = 24) -> dict:
    """Calculate inflation vs CPI using the existing deterministic engine and validated PDFs."""
    from real_basket.agents.tools import calculate_essential_vs_cpi
    return calculate_essential_vs_cpi(months=months)


@mcp.tool()
def get_city_rents() -> dict:
    """Get published city asking-rent reference values; no synthetic federal-state rents."""
    from real_basket.agents.tools import fetch_regional_rents
    return fetch_regional_rents(region_type='stadt')



@mcp.tool()
def get_dashboard_snapshot() -> dict:
    """Canonical validated dashboard input with series, category weights, YoY and provenance.

    Single deterministic calculation boundary for UI; no local UI arithmetic engine.
    """
    from real_basket.core.index import category_indices, compare_with_cpi, essential_index
    from real_basket.core.investigation import deviation_breakdown, state_rent_coverage, STATE_NOTE
    from real_basket.data.basket import load_basket
    from real_basket.schemas.models import CATEGORY_LABEL_DE

    basket = load_basket()  # raises instead of fabricating or silently falling back
    prices, cpi = basket.prices, basket.cpi
    comparison = compare_with_cpi(essential_index(prices, basket.weights), cpi)
    breakdown = deviation_breakdown(prices, cpi, basket.weights)
    comparison = comparison.rename_axis("period").reset_index()
    comparison["period"] = comparison["period"].astype(str).str[:10]
    cat = category_indices(prices).rename_axis("period").reset_index()
    cat["period"] = cat["period"].astype(str).str[:10]
    return {
        "data_basis": basket.label,
        "documents": basket.real.documents,
        "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail} for c in basket.real.checks],
        "base_amounts": [{"category": c.value, "label": CATEGORY_LABEL_DE[c], "eur": v,
                          "weight": basket.weights.weights[c]} for c, v in basket.real.base_amounts.items()],
        "comparison": json.loads(comparison.to_json(orient="records")),
        "category_indices": json.loads(cat.to_json(orient="records")),
        "breakdown": breakdown,
        "prices": [{"period": str(p.period)[:10], "category": p.category.value,
                    "item": p.item, "eur": p.price, "source": p.source} for p in prices],
        "cities": basket.real.city_rents,
        "states": state_rent_coverage(basket.real),
        "state_note": STATE_NOTE,
        "note": "Euro-Kosten des ECLI sind modelliert; Stadtmieten sind veröffentlichte Angebotsmieten."
    }


@mcp.tool()
def generate_reports() -> dict:
    """Generate deterministic RealBasket reports from validated PDFs; return PDF bytes as Base64."""
    import tempfile
    from real_basket.data.basket import load_basket
    from real_basket.reports.pdf_report import generate_all

    with tempfile.TemporaryDirectory() as tmp:
        return {Path(p).name: base64.b64encode(Path(p).read_bytes()).decode("ascii")
                for p in generate_all(tmp, load_basket())}


@mcp.tool()
def list_reference_pdfs() -> dict:
    """List available immutable source reports and their sizes (not content)."""
    return {"files": [{"filename": p.name, "bytes": p.stat().st_size}
                      for p in sorted(_reference_dir().glob("*.pdf"))]}


@mcp.tool()
def get_reference_pdf(filename: str) -> dict:
    """Fetch one reference PDF by basename as Base64 for download through the UI."""
    if filename != Path(filename).name or not filename.lower().endswith(".pdf"):
        raise ValueError("Invalid PDF filename")
    target = _reference_dir() / filename
    if not target.is_file():
        raise FileNotFoundError(filename)
    return {"filename": filename, "content_base64": base64.b64encode(target.read_bytes()).decode("ascii")}


def main() -> None:
    p = argparse.ArgumentParser(description='RealBasket MCP server')
    p.add_argument('--transport', choices=['stdio','streamable-http'], default='stdio')
    args = p.parse_args()
    mcp.run(transport=args.transport)


if __name__ == '__main__':
    main()
