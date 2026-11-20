from pathlib import Path

import pytest

from real_basket.core.index import compare_with_cpi, essential_index
from real_basket.core.investigation import deviation_breakdown, item_changes, regional_rent_changes
from real_basket.data.basket import load_basket
from real_basket.schemas.models import BasketWeights, Category

REAL_DOCS = Path(__file__).resolve().parents[1] / "reports" / "real-data"
pytestmark = pytest.mark.skipif(not REAL_DOCS.is_dir(), reason="reference PDFs not available")

ALL = {"food", "housing_energy", "mobility", "health", "communication"}


def test_breakdown_gaps_add_up_to_the_deviation():
    b = load_basket()
    res = deviation_breakdown(b.prices, b.cpi, b.weights)
    cats = res["categories"]
    assert {c["category"] for c in cats} == ALL
    assert sum(c["contribution_pp"] for c in cats) == pytest.approx(res["essential_yoy_pct"], abs=0.05)
    assert sum(c["gap_pp"] for c in cats) == pytest.approx(res["deviation_pp"], abs=0.05)
    assert abs(cats[0]["gap_pp"]) == max(abs(c["gap_pp"]) for c in cats)     # biggest driver first


def test_breakdown_matches_index_for_custom_weights():
    b = load_basket()
    w = BasketWeights(weights={Category.FOOD: 0.5, Category.HOUSING_ENERGY: 0.5, Category.MOBILITY: 0})
    res = deviation_breakdown(b.prices, b.cpi, w)
    latest = compare_with_cpi(essential_index(b.prices, w), b.cpi).dropna().iloc[-1]
    assert res["deviation_pp"] == pytest.approx(latest["deviation_pp"], abs=0.01)
    assert {c["category"] for c in res["categories"]} == {"food", "housing_energy"}


def test_item_and_region_drill_down():
    b = load_basket()
    items = item_changes(b.prices, "housing_energy")
    assert items and all("yoy_pct" in i for i in items)
    cities = regional_rent_changes(b.real, "stadt")
    assert cities["strongest"][0]["change_pct"] >= cities["weakest"][-1]["change_pct"]
    states = regional_rent_changes(b.real, "bundesland")
    assert states["verified_state_series"] is False and len(states["coverage"]) == 16
    assert "strongest" not in states                     # no state rents are invented


def test_investigate_tool_levels():
    from real_basket.agents.tools import investigate_deviation

    basket = load_basket()
    res = investigate_deviation._tool_func("category")
    assert res["categories"] and res["data_basis"] == basket.label
    assert investigate_deviation._tool_func("item", basket.categories[0].value)["items"]
    assert "error" in investigate_deviation._tool_func("item", "x")
    assert "error" in investigate_deviation._tool_func("item", "rent")
