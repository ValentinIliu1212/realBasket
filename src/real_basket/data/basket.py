"""The essential basket: real data from the reference PDFs (reports/real-data, ECLI model calculation).

There is no synthetic fallback. If the PDFs are missing or cannot be parsed, `load_basket()` raises
`RealDataError` and the dashboard / agent tools show that error instead of numbers.
"""

from __future__ import annotations

from dataclasses import dataclass

from real_basket.data.real_data import RealDataError, RealDataset, load_real_data
from real_basket.schemas.models import BasketWeights, Category, CpiPoint, PricePoint

__all__ = ["Basket", "RealDataError", "load_basket"]


@dataclass
class Basket:
    label: str                       # German description for UI / agent
    real: RealDataset

    @property
    def prices(self) -> list[PricePoint]:
        return self.real.prices

    @property
    def cpi(self) -> list[CpiPoint]:
        return self.real.cpi

    @property
    def weights(self) -> BasketWeights:
        """Default weights: exact expenditure shares of the reference basket."""
        return self.real.weights

    @property
    def categories(self) -> list[Category]:
        return [c for c in Category if c in self.weights.weights]


def load_basket() -> Basket:
    """Parsed and re-checked reference basket (cached until a PDF changes). Raises RealDataError."""
    ds = load_real_data()
    return Basket(real=ds, label="ECLI-Referenzwarenkorb (Destatis EVS 2023 + VPI), "
                                 f"{ds.periods[0]:%m/%Y}–{ds.periods[-1]:%m/%Y}")
