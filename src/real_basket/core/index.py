"""Index calculation: fixed-weight essential living cost index and CPI comparison.

Method
- Category index: unweighted mean of the item price relatives vs. the base period (= 100). With one item per
  category - as in the reference data - this is simply the price relative of the category's monthly cost.
- Essential index: fixed-weight sum of the category indices. With the default weights (expenditure shares of the
  reference basket in the base period) this equals a Laspeyres index of the modelled monthly costs:
  sum_c w_c * P_c(t) / P_c(b) = sum_c P_c(t) / sum_c P_c(b).
- The base period matters: rebasing the category indices changes their effective weights and therefore the YoY
  rate of the essential index. Always index the FULL series (base = first month, 11/2024) and slice the result
  afterwards - never slice the prices first (see `real_basket.agents.tools._last_months`).
- YoY rates compare a month with the same month of the previous year by DATE (gaps give NaN, never a wrong month).
"""

from __future__ import annotations

import pandas as pd

from real_basket.schemas.models import BasketWeights, CpiPoint, PricePoint


def prices_to_frame(prices: list[PricePoint]) -> pd.DataFrame:
    return pd.DataFrame([p.model_dump() for p in prices])


def yoy_pct(data: pd.Series | pd.DataFrame) -> pd.Series | pd.DataFrame:
    """Change vs. the same month one year earlier in percent, matched by date (not by position)."""
    prev = data.reindex(data.index - pd.DateOffset(months=12))
    prev.index = data.index
    return (data / prev - 1) * 100


def category_indices(prices: list[PricePoint], base_period: str | None = None) -> pd.DataFrame:
    """Return a DataFrame (period x category) of category indices (base period = 100).

    Each item is indexed to its base price; items within a category are equally weighted. The base period
    defaults to the first month of `prices` - pass the full series, not a slice.
    """
    df = prices_to_frame(prices)
    df["category"] = df["category"].map(lambda c: getattr(c, "value", c))
    df["period"] = pd.to_datetime(df["period"])
    base = pd.Timestamp(base_period) if base_period else df["period"].min()

    base_prices = df[df["period"] == base].set_index(["category", "item"])["price"]
    if base_prices.empty:
        raise ValueError(f"No prices in the base period {base:%Y-%m}")
    df = df.join(base_prices.rename("base_price"), on=["category", "item"])
    df["relative"] = df["price"] / df["base_price"] * 100
    return df.pivot_table(index="period", columns="category", values="relative", aggfunc="mean").sort_index()


def normalised_weights(weights: BasketWeights, available: list[str] | pd.Index) -> pd.Series:
    """Positive weights as a Series (category value -> weight) summing to 1.

    Raises ValueError if a category with a positive weight has no prices (instead of silently dropping it).
    """
    w = pd.Series({getattr(k, "value", k): float(v) for k, v in weights.weights.items() if v > 0})
    missing = sorted(set(w.index) - set(available))
    if missing:
        raise ValueError(f"No prices for weighted categories {missing}")
    if w.empty or w.sum() <= 0:
        raise ValueError("At least one weight must be > 0")
    return w / w.sum()


def essential_index(prices: list[PricePoint], weights: BasketWeights, base_period: str | None = None) -> pd.Series:
    """Weighted essential living cost index (base period = 100)."""
    cat = category_indices(prices, base_period)
    w = normalised_weights(weights, cat.columns)
    return (cat[list(w.index)] * w).sum(axis=1)


def compare_with_cpi(essential: pd.Series, cpi: list[CpiPoint]) -> pd.DataFrame:
    """Rebase CPI to the essential base period and compute YoY rates and deviation (pp)."""
    cpi_s = pd.Series({pd.Timestamp(c.period): c.index_value for c in cpi}).sort_index()
    df = pd.DataFrame({"essential_index": essential, "cpi_raw": cpi_s}).dropna()
    df["cpi_index"] = df["cpi_raw"] / df["cpi_raw"].iloc[0] * 100
    df = df.drop(columns="cpi_raw")
    df["essential_yoy_pct"] = yoy_pct(df["essential_index"])
    df["cpi_yoy_pct"] = yoy_pct(df["cpi_index"])
    df["deviation_pp"] = df["essential_yoy_pct"] - df["cpi_yoy_pct"]
    return df
