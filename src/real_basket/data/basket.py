"""The essential basket: the validated real dataset, read from SQLite.

The reference PDFs (reports/real-data, ECLI model calculation) are read ONLY by the import
(`python -m real_basket.storage --mode sql` -> `storage.sqlite_store.persist_reference_pdfs`, 11 checks).
`load_basket()` reads the imported dataset from SQLite (`REALBASKET_SQLITE_PATH`). There is no synthetic
fallback and no implicit import: if the database or the dataset is missing, `load_basket()` raises
`RealDataError` and the dashboard / agent tools show that error instead of numbers.
"""

from __future__ import annotations

from dataclasses import dataclass

from real_basket.data.real_data import RealDataError, RealDataset
from real_basket.schemas.models import BasketWeights, Category, CpiPoint, PricePoint
from real_basket.storage.sqlite_store import load_dataset

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
    """Validated reference basket from SQLite (cached per import). Raises RealDataError."""
    ds = load_dataset()
    return Basket(real=ds, label="ECLI-Referenzwarenkorb (Destatis EVS 2023 + VPI), "
                                 f"{ds.periods[0]:%m/%Y}–{ds.periods[-1]:%m/%Y}")
