"""Import of the real data from the reference PDFs (reports/real-data). There is no demo fallback."""

from pathlib import Path

import pytest

from real_basket.core.index import compare_with_cpi, essential_index
from real_basket.core.investigation import deviation_breakdown
from real_basket.data.basket import load_basket
from real_basket.data.real_data import CITY_FLAT_M2, STATES, RealDataError, load_real_data, parse_number
from real_basket.schemas.models import Category

REAL_DOCS = Path(__file__).resolve().parents[1] / "reports" / "real-data"
needs_docs = pytest.mark.skipif(not REAL_DOCS.is_dir(), reason="reference PDFs not available")


def test_parse_number():
    assert parse_number("1.137,00 €") == 1137.0
    assert parse_number("-0,4 %") == -0.4
    assert parse_number("100,3") == 100.3


def test_missing_documents_raise_instead_of_demo_data(tmp_path):
    with pytest.raises(RealDataError):
        load_real_data(tmp_path)


def test_no_demo_module_left():
    with pytest.raises(ImportError):
        import real_basket.data.demo_data  # noqa: F401
    assert {c.value for c in Category} == {"food", "housing_energy", "mobility", "health", "communication"}


@needs_docs
def test_real_dataset_is_complete_and_rechecked():
    ds = load_real_data(REAL_DOCS)
    assert ds.all_checks_ok, [c for c in ds.checks if not c.ok]
    assert len(ds.periods) >= 24 and len(ds.cpi) == len(ds.periods)
    assert set(ds.base_amounts) == set(Category)
    assert sum(ds.weights.weights.values()) == pytest.approx(1.0)
    assert len(ds.city_rents) == 15
    assert all(p.source.endswith(tuple(f"S. {n}" for n in range(1, 20))) for p in ds.prices)
    for c in ds.city_rents:
        assert c["rent_oct_flat_eur"] == pytest.approx(c["rent_oct_eur_m2"] * CITY_FLAT_M2, abs=1)


@needs_docs
def test_state_coverage_lists_cities_but_no_state_rents():
    ds = load_real_data(REAL_DOCS)
    assert [s["state"] for s in ds.state_coverage] == list(STATES)
    assert all(s["verified_state_series"] is False for s in ds.state_coverage)
    covered = sorted(name for s in ds.state_coverage for name in s["cities"])
    assert covered == sorted(c["city"] for c in ds.city_rents)


@needs_docs
def test_engine_reproduces_printed_ecli():
    ds = load_real_data(REAL_DOCS)
    ecli = essential_index(ds.prices, ds.weights)
    for period, printed in ds.printed_ecli.items():
        assert float(ecli[str(period)]) == pytest.approx(printed, abs=0.051)
    res = deviation_breakdown(ds.prices, ds.cpi, ds.weights)
    assert sum(c["gap_pp"] for c in res["categories"]) == pytest.approx(res["deviation_pp"], abs=0.05)
    latest = compare_with_cpi(ecli, ds.cpi).dropna().iloc[-1]
    assert res["essential_yoy_pct"] == pytest.approx(latest["essential_yoy_pct"], abs=0.01)


@needs_docs
def test_basket_is_real():
    b = load_basket()
    assert b.categories == list(Category) and "ECLI" in b.label


@needs_docs
def test_default_weights_are_exact_expenditure_shares():
    from real_basket.agents.tools import calculate_essential_vs_cpi

    ds = load_real_data(REAL_DOCS)
    res = calculate_essential_vs_cpi()
    for cat, amount in ds.base_amounts.items():
        assert res["weights"][cat.value] == round(amount / ds.base_total, 4)
    printed_yoy = ds.printed_ecli_yoy[max(ds.printed_ecli_yoy)]
    assert res["essential_yoy_pct"] == pytest.approx(printed_yoy, abs=0.06)


@needs_docs
def test_tools_use_real_data_only():
    from real_basket.agents import tools

    res = tools.calculate_essential_vs_cpi()
    assert "housing_energy" in res["weights"] and res["documents"]
    custom = tools.calculate_essential_vs_cpi(weights={"food": 1, "mobility": 1})
    assert custom["weights"] == {"food": 0.5, "mobility": 0.5}
    assert "error" in tools.fetch_prices("rent")
    assert tools.fetch_prices("health")["prices"]
    rents = tools.fetch_regional_rents(region_type="all")
    assert len(rents["cities"]) == 15 and len(rents["states"]) == 16
    assert all("rent_eur_per_m2" not in s for s in rents["states"])
    assert not hasattr(tools, "fetch_net_salaries")
