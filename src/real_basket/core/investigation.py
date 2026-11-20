"""Deterministic drill-down used by the chat agent's `investigate_deviation` tool:
category -> item -> region. The agent decides *whether* and *how deep* to drill down; the numbers come from here.
All inputs are real data from the reference PDFs (reports/real-data)."""

from __future__ import annotations

import pandas as pd

from real_basket.core.index import category_indices, compare_with_cpi, essential_index
from real_basket.data.real_data import RealDataset
from real_basket.schemas.models import BasketWeights, CpiPoint, PricePoint, RegionType

STATE_NOTE = ("Die Referenzberichte enthalten bewusst keine Miete je Bundesland: Stadtwerte begründen keinen "
              "repräsentativen Mietwert für das gesamte Bundesland.")


def deviation_breakdown(prices: list[PricePoint], cpi: list[CpiPoint], weights: BasketWeights) -> dict:
    """Essential index vs CPI for the latest month, incl. the exact contribution of every category.

    contribution_pp: share of the essential YoY rate caused by the category (sums to the essential YoY).
    gap_pp: contribution minus the category's weight x CPI YoY (sums to the deviation).
    Categories are sorted by |gap_pp|, i.e. the biggest driver of the deviation comes first.
    """
    used = {c.value: w for c, w in weights.weights.items() if w > 0}
    comparison = compare_with_cpi(essential_index(prices, weights), cpi).dropna()
    if comparison.empty:
        raise ValueError("Not enough months for a year-over-year comparison (need >= 13)")
    latest, period = comparison.iloc[-1], comparison.index[-1]
    prev = period - pd.DateOffset(months=12)

    cats = category_indices(prices)
    missing = [c for c in used if c not in cats.columns]
    if missing:
        raise ValueError(f"No prices for categories {missing} in this basket")
    ess = (cats[list(used)] * pd.Series(used)).sum(axis=1)
    cpi_yoy = float(latest["cpi_yoy_pct"])
    categories = []
    for c, w in used.items():
        contrib = w * (cats.loc[period, c] - cats.loc[prev, c]) / ess.loc[prev] * 100
        categories.append({
            "category": c, "weight": round(w, 4),
            "yoy_pct": round(float((cats.loc[period, c] / cats.loc[prev, c] - 1) * 100), 2),
            "contribution_pp": round(float(contrib), 2),
            "gap_pp": round(float(contrib - w * cpi_yoy), 2),
        })
    return {
        "period": str(period.date()),
        "essential_yoy_pct": round(float(latest["essential_yoy_pct"]), 2),
        "cpi_yoy_pct": round(cpi_yoy, 2),
        "deviation_pp": round(float(latest["deviation_pp"]), 2),
        "categories": sorted(categories, key=lambda d: -abs(d["gap_pp"])),
    }


def item_changes(prices: list[PricePoint], category: str) -> list[dict]:
    """Year-over-year change of every item of one category at the latest month (previous year matched by date)."""
    result = []
    for item in sorted({p.item for p in prices if p.category.value == category}):
        series = sorted((p for p in prices if p.category.value == category and p.item == item),
                        key=lambda p: p.period)
        last = series[-1]
        prev_period = (pd.Timestamp(last.period) - pd.DateOffset(months=12)).date()
        prev = next((p for p in series if p.period == prev_period), None)
        if prev is None:
            continue
        result.append({"item": item, "period": str(last.period), "price": last.price, "unit": last.unit,
                       "yoy_pct": round((last.price / prev.price - 1) * 100, 2), "source": last.source})
    return sorted(result, key=lambda d: -abs(d["yoy_pct"]))


def city_rent_changes(ds: RealDataset, top: int = 5) -> dict:
    """Published asking rents of the 15 largest cities (reference PDF, immowelt), Jan vs. Oct 2026."""
    changes = sorted(({"region": c["city"], "bundesland": c["state"], "rent_eur_per_m2": c["rent_oct_eur_m2"],
                       "change_pct": c["change_pct"]} for c in ds.city_rents), key=lambda d: -d["change_pct"])
    return {"region_type": RegionType.CITY.value, "change": "Okt 2026 vs. Jan 2026 (Angebotskaltmiete)",
            "strongest": changes[:top], "weakest": changes[-top:],
            "source": ds.city_rents[0]["source"] if ds.city_rents else None}


def state_rent_coverage(ds: RealDataset) -> list[dict]:
    """Per federal state: no verified rent series; the cities of that state with published rents (if any)."""
    by_city = {c["city"]: c for c in ds.city_rents}
    return [{"bundesland": s["state"], "verified_state_series": False, "status": s["status"],
             "cities": [{"city": name, "rent_eur_per_m2": by_city[name]["rent_oct_eur_m2"],
                         "change_pct": by_city[name]["change_pct"]} for name in s["cities"] if name in by_city],
             "source": s["source"]} for s in ds.state_coverage]


def regional_rent_changes(ds: RealDataset, region_type: str = "stadt", top: int = 5) -> dict:
    """Cities: strongest / weakest rent increase. Federal states: coverage only (no state rents in the sources)."""
    if RegionType(region_type) == RegionType.STATE:
        return {"region_type": RegionType.STATE.value, "verified_state_series": False, "note": STATE_NOTE,
                "coverage": state_rent_coverage(ds)}
    return city_rent_changes(ds, top)