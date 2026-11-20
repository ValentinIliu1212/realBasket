"""Regression tests: chat tools and dashboard must report the same rates, independent of `months`.

Before the fix, the tools sliced the prices to the last `months` before indexing. That moved the base period and
changed the effective weights, so `calculate_essential_vs_cpi(months=13)` reported 2,91 % while the dashboard
showed 2,93 %.
"""
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from real_basket.core.index import compare_with_cpi, essential_index, yoy_pct
from real_basket.schemas.models import BasketWeights, Category, PricePoint

REAL_DOCS = Path(__file__).resolve().parents[1] / "reports" / "real-data"
needs_docs = pytest.mark.skipif(not REAL_DOCS.is_dir(), reason="reference PDFs not available")


@needs_docs
@pytest.mark.parametrize("months", [13, 18, 24])
def test_index_tool_matches_dashboard_for_every_window(months):
    from real_basket.agents.tools import calculate_essential_vs_cpi
    from real_basket.data.basket import load_basket

    b = load_basket()
    full = compare_with_cpi(essential_index(b.prices, b.weights), b.cpi).dropna().iloc[-1]
    res = calculate_essential_vs_cpi(months=months)
    assert res["essential_yoy_pct"] == round(float(full["essential_yoy_pct"]), 2)
    assert res["cpi_yoy_pct"] == round(float(full["cpi_yoy_pct"]), 2)
    assert res["deviation_pp"] == round(float(full["deviation_pp"]), 2)
    assert len(res["history"]) == min(months, len(compare_with_cpi(essential_index(b.prices, b.weights),
                                                                   b.cpi).dropna()))
    assert res["base_period"].startswith("2024-11")


@needs_docs
def test_prices_tool_returns_deterministic_summary():
    from real_basket.agents.tools import fetch_prices

    res = fetch_prices("food", months=24)
    summary = res["summary"][0]
    assert {"first_value", "last_value", "change_pct", "yoy_pct_latest"} <= set(summary)
    assert summary["change_pct"] == round((summary["last_value"] / summary["first_value"] - 1) * 100, 2)


def test_yoy_matches_by_date_not_by_position():
    idx = pd.to_datetime(["2024-01-01", "2024-02-01", "2025-01-01", "2025-03-01"])
    s = pd.Series([100.0, 200.0, 110.0, 999.0], index=idx)
    res = yoy_pct(s)
    assert res.loc["2025-01-01"] == pytest.approx(10.0)
    assert pd.isna(res.loc["2025-03-01"])           # no March 2024 -> NaN, never a wrong month


def test_weighted_category_without_prices_raises():
    p = [PricePoint(item="food", category=Category.FOOD, period=date(2024, 11, 1), price=1.0, unit="EUR",
                    source="test")]
    with pytest.raises(ValueError):
        essential_index(p, BasketWeights(weights={Category.FOOD: 0.5, Category.MOBILITY: 0.5}))
