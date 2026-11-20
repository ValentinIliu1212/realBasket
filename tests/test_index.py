from datetime import date

import pytest

from real_basket.core.index import compare_with_cpi, essential_index
from real_basket.schemas.models import BasketWeights, Category, CpiPoint, PricePoint


def _months(n: int) -> list[date]:
    return [date(2024 + (10 + i) // 12, (10 + i) % 12 + 1, 1) for i in range(n)]


def _prices(n: int = 24) -> list[PricePoint]:
    """Tiny in-test series (never used by the app): food +0.5 %/month, mobility flat."""
    return [PricePoint(item=cat.value, category=cat, period=m, price=price * (1 + rate) ** i, unit="EUR/Monat",
                       source="test")
            for i, m in enumerate(_months(n))
            for cat, price, rate in ((Category.FOOD, 300.0, 0.005), (Category.MOBILITY, 200.0, 0.0))]


def _cpi(n: int = 24) -> list[CpiPoint]:
    return [CpiPoint(period=m, index_value=100 * 1.002 ** i, source="test") for i, m in enumerate(_months(n))]


WEIGHTS = BasketWeights(weights={Category.FOOD: 0.6, Category.MOBILITY: 0.4})


def test_essential_index_starts_at_100():
    assert essential_index(_prices(), WEIGHTS).iloc[0] == pytest.approx(100.0)


def test_comparison_has_deviation():
    df = compare_with_cpi(essential_index(_prices(), WEIGHTS), _cpi())
    assert "deviation_pp" in df.columns
    assert df["deviation_pp"].dropna().shape[0] == 12


def test_weights_must_sum_to_one():
    with pytest.raises(ValueError):
        BasketWeights(weights={Category.FOOD: 0.5, Category.HOUSING_ENERGY: 0.2})
