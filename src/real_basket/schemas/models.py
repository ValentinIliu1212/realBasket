from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class Category(str, Enum):
    """Expenditure groups of the ECLI reference basket (reports/real-data)."""

    FOOD = "food"
    HOUSING_ENERGY = "housing_energy"     # "Wohnen / Energie" - more than the net cold rent
    MOBILITY = "mobility"
    HEALTH = "health"
    COMMUNICATION = "communication"


CATEGORY_LABEL_DE = {
    Category.FOOD: "Lebensmittel", Category.HOUSING_ENERGY: "Wohnen / Energie",
    Category.MOBILITY: "Verkehr / Mobilität", Category.HEALTH: "Gesundheit",
    Category.COMMUNICATION: "Kommunikation",
}


class RegionType(str, Enum):
    NATIONAL = "national"
    STATE = "bundesland"
    CITY = "stadt"


class PricePoint(BaseModel):
    category: Category
    item: str = Field(description="Concrete good/service, e.g. 'bread 1kg', 'rent per m2', 'electricity kWh'")
    period: date = Field(description="First day of the month the price refers to")
    price: float = Field(gt=0)
    unit: str = "EUR"
    source: str = Field(description="Origin of the value, e.g. 'Lebenshaltungskosten_2026_….pdf S. 1'")
    region: str = Field(default="Deutschland", description="Region the price refers to (state or city)")
    region_type: RegionType = RegionType.NATIONAL


class BasketWeights(BaseModel):
    """Weights of the essential basket. Must sum to 1.0 (default: expenditure shares of the reference basket,
    see `RealDataset.weights`)."""

    weights: dict[Category, float]

    @model_validator(mode="after")
    def _check_sum(self) -> "BasketWeights":
        total = sum(self.weights.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Basket weights must sum to 1.0, got {total:.4f}")
        return self


class CpiPoint(BaseModel):
    period: date
    index_value: float = Field(description="Official CPI index value (e.g. rebased Nov 2024 = 100)")
    source: str


class ComparisonPoint(BaseModel):
    period: date
    essential_index: float
    cpi_index: float
    essential_yoy_pct: float | None = None
    cpi_yoy_pct: float | None = None
    deviation_pp: float | None = Field(
        default=None, description="Essential YoY minus CPI YoY in percentage points"
    )
