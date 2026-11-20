"""Import of the real data in the reference PDFs (reports/real-data, "ECLI Modellrechnung").

The numbers are parsed DETERMINISTICALLY from the PDF tables (no LLM, no text search) and re-checked in code:

- Referenzwarenkorb: fixed monthly base amount (EUR) per expenditure group, basis November 2024
- Monatliche modellierte Kosten: EUR per group and month (-> PricePoint, one item per group)
- ECLI vs. VPI: official CPI rebased to November 2024 = 100 (-> CpiPoint)
- 15 Großstädte: published asking rents (immowelt), January vs. October 2026
- Bundesland-Abdeckung: per federal state, which cities have published rents ("Nur ausgewählte Städte: …") or
  "Keine verifizierte Monatsreihe" - the reports deliberately give NO rent per federal state

Rechecks (see `RealDataset.checks`): base amounts add up to the printed total, row sums, the ECLI recomputed by the
RealBasket engine equals the printed ECLI, the printed ECLI annual rate, the two ECLI tables agree, the monthly
series has no gaps, months repeated in several reports carry identical values, the city rent changes and 75 m²
rents are recomputed, and the federal-state coverage lists exactly the cities of the rent table.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

import pandas as pd

from real_basket.core.index import essential_index
from real_basket.core.settings import get_settings, resolve_path
from real_basket.schemas.models import BasketWeights, Category, CpiPoint, PricePoint

MONTHS_DE = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
GROUPS: dict[str, Category] = {
    "Lebensmittel": Category.FOOD,
    "Wohnen / Energie": Category.HOUSING_ENERGY,
    "Verkehr": Category.MOBILITY,
    "Gesundheit": Category.HEALTH,
    "Kommunikation": Category.COMMUNICATION,
}
GROUP_NAME = {cat: name for name, cat in GROUPS.items()}
STATES = ["Baden-Württemberg", "Bayern", "Berlin", "Brandenburg", "Bremen", "Hamburg", "Hessen",
          "Mecklenburg-Vorpommern", "Niedersachsen", "Nordrhein-Westfalen", "Rheinland-Pfalz", "Saarland", "Sachsen",
          "Sachsen-Anhalt", "Schleswig-Holstein", "Thüringen"]
NO_STATE_SERIES = "Keine verifizierte Monatsreihe"
CITIES_ONLY = "Nur ausgewählte Städte:"
CITY_FLAT_M2 = 75

_MONTH = re.compile(r"^(" + "|".join(MONTHS_DE) + r") (\d{4})$")
_EUR = re.compile(r"^-?\d{1,3}(?:\.\d{3})*,\d{2} €$")
_INDEX = re.compile(r"^\d+,\d$")
_RATE = re.compile(r"^-?\d+,\d %$")
_CITY = re.compile(r"^(.+?) / (.+)$")


class RealDataError(RuntimeError):
    """The reference PDFs are missing or their tables could not be read."""


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


@dataclass
class RealDataset:
    prices: list[PricePoint]
    cpi: list[CpiPoint]
    base_amounts: dict[Category, float]
    base_total: float
    printed_ecli: dict[date, float]
    printed_ecli_yoy: dict[date, float]
    city_rents: list[dict]
    documents: list[str]
    state_coverage: list[dict] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)

    @property
    def weights(self) -> BasketWeights:
        """Expenditure shares of the reference basket (fixed EUR base amounts / total)."""
        total = sum(self.base_amounts.values())
        return BasketWeights(weights={c: v / total for c, v in self.base_amounts.items()})

    @property
    def periods(self) -> list[date]:
        return sorted({p.period for p in self.prices})

    @property
    def all_checks_ok(self) -> bool:
        return all(c.ok for c in self.checks)


def parse_number(text: str) -> float:
    """'1.137,00 €' -> 1137.0, '1,9 %' -> 1.9, '100,3' -> 100.3"""
    return float(text.replace("€", "").replace("%", "").strip().replace(".", "").replace(",", "."))


def _month(match: re.Match) -> date:
    return date(int(match.group(2)), MONTHS_DE.index(match.group(1)) + 1, 1)


def _column_order(header_lines: list[str]) -> list[str]:
    """Group names in the order of the monthly table header ('Wohnen /' + 'Energie', 'Kommunikatio' + 'n')."""
    joined = "".join(header_lines).replace(" ", "")
    found = [(joined.find(name.replace(" ", "")), name) for name in GROUPS]
    if any(pos < 0 for pos, _ in found):
        raise RealDataError(f"Unknown header of the monthly cost table: {' '.join(header_lines)!r}")
    return [name for _, name in sorted(found)]


def parse_document(path: Path) -> dict:
    """All tables of one ECLI report: base amounts, monthly costs, ECLI/VPI rows, city rents."""
    from real_basket.knowledge.ingest import extract_pages

    lines = [(page, ln) for page, page_lines in enumerate(extract_pages(path), 1) for ln in page_lines]
    text = [ln for _, ln in lines]
    out: dict = {"file": path.name, "base": {}, "base_total": None, "costs": {}, "vpi": {}, "cities": [],
                 "states": {}}
    order: list[str] | None = None
    for i, (page, line) in enumerate(lines):
        nxt = text[i + 1:i + 8]
        if line in GROUPS and nxt and _EUR.match(nxt[0]) and line not in out["base"]:
            out["base"][line] = parse_number(nxt[0])
        elif line == "SUMME" and nxt and _EUR.match(nxt[0]):
            out["base_total"] = parse_number(nxt[0])
        elif line == "Monat" and order is None:
            header = []
            for ln in text[i + 1:]:
                if ln == "ECLI":
                    break
                header.append(ln)
            if any(h.startswith("Summe") for h in header):
                order = _column_order(header)
        elif m := _MONTH.match(line):
            period, source = _month(m), f"{path.name} S. {page}"
            if len(nxt) >= 7 and all(_EUR.match(x) for x in nxt[:6]) and _INDEX.match(nxt[6]):
                if order is None:
                    raise RealDataError(f"{path.name}: monthly cost row before the table header")
                values = [parse_number(x) for x in nxt[:6]]
                out["costs"][period] = {"groups": dict(zip(order, values[:5])), "sum": values[5],
                                        "ecli": parse_number(nxt[6]), "source": source}
            elif (len(nxt) >= 3 and _INDEX.match(nxt[0]) and _INDEX.match(nxt[1])
                  and (_RATE.match(nxt[2]) or nxt[2] == "nicht berechenbar")):
                out["vpi"][period] = {"ecli": parse_number(nxt[0]), "vpi": parse_number(nxt[1]),
                                      "ecli_yoy": parse_number(nxt[2]) if _RATE.match(nxt[2]) else None,
                                      "source": source}
        elif (c := _CITY.match(line)) and len(nxt) >= 5 and all(_EUR.match(x) for x in nxt[:4]) \
                and _RATE.match(nxt[4]):
            jan, okt = parse_number(nxt[0]), parse_number(nxt[1])
            out["cities"].append({"city": c.group(1), "state": c.group(2), "rent_jan_eur_m2": jan,
                                  "rent_oct_eur_m2": okt, "rent_jan_flat_eur": parse_number(nxt[2]),
                                  "rent_oct_flat_eur": parse_number(nxt[3]), "change_pct": parse_number(nxt[4]),
                                  "source": f"{path.name} S. {page} (immowelt Mietkompass)"})
        elif line in STATES and nxt and (nxt[0] == NO_STATE_SERIES or nxt[0].startswith(CITIES_ONLY)):
            cities = [x.strip() for x in nxt[0][len(CITIES_ONLY):].split(",")] if nxt[0] != NO_STATE_SERIES else []
            out["states"][line] = {"state": line, "cities": cities, "verified_state_series": False,
                                   "status": nxt[0], "source": f"{path.name} S. {page}"}
    return out


def _shift(d: date, months: int) -> date:
    idx = d.year * 12 + d.month - 1 + months
    return date(idx // 12, idx % 12 + 1, 1)


def build_dataset(docs: list[dict]) -> RealDataset:
    checks: list[Check] = []
    base: dict[str, float] = {}
    base_total = None
    costs: dict[date, dict] = {}
    vpi: dict[date, dict] = {}
    conflicts: list[str] = []
    for doc in docs:
        for name, value in doc["base"].items():
            if name in base and base[name] != value:
                conflicts.append(f"Basis {name}")
            base.setdefault(name, value)
        base_total = base_total or doc["base_total"]
        for target, rows in ((costs, doc["costs"]), (vpi, doc["vpi"])):
            for period, row in rows.items():
                if period in target and {k: v for k, v in target[period].items() if k != "source"} != \
                        {k: v for k, v in row.items() if k != "source"}:
                    conflicts.append(f"{period:%m/%Y}")
                target.setdefault(period, row)
    if not costs or len(base) != len(GROUPS):
        raise RealDataError("No ECLI cost table found in the reference PDFs")

    periods = sorted(costs)
    base_cat = {GROUPS[n]: v for n, v in base.items()}
    total = sum(base.values())
    checks.append(Check("Basisbeträge ergeben die SUMME", base_total is not None and abs(total - base_total) < 0.01,
                        f"Σ {total:.2f} € vs. SUMME {base_total} €"))
    first = costs[periods[0]]["groups"]
    checks.append(Check("Erster Monat = Basiswarenkorb", all(abs(first[n] - base[n]) < 0.01 for n in base),
                        f"{periods[0]:%m/%Y}"))
    expected = [_shift(periods[0], i) for i in range(len(periods))]
    checks.append(Check("Lückenlose Monatsreihe", periods == expected,
                        f"{periods[0]:%m/%Y}–{periods[-1]:%m/%Y}, {len(periods)} Monate"))
    sum_diff = max(abs(sum(r["groups"].values()) - r["sum"]) for r in costs.values())
    checks.append(Check("Zeilensummen nachgerechnet", sum_diff <= 0.05,
                        f"max. Abweichung {sum_diff:.3f} € (Summen aus ungerundeten Werten)"))

    prices = [PricePoint(category=GROUPS[name], item=name, period=p, price=value, unit="EUR/Monat",
                         source=costs[p]["source"])
              for p in periods for name, value in costs[p]["groups"].items()]
    cpi = [CpiPoint(period=p, index_value=vpi[p]["vpi"], source=vpi[p]["source"]) for p in sorted(vpi)]
    printed_ecli = {p: costs[p]["ecli"] for p in periods}
    printed_yoy = {p: v["ecli_yoy"] for p, v in vpi.items() if v["ecli_yoy"] is not None}

    weights = BasketWeights(weights={c: v / total for c, v in base_cat.items()})
    ecli = essential_index(prices, weights)
    ecli_diff = max(abs(float(ecli[pd.Timestamp(p)]) - v) for p, v in printed_ecli.items())
    checks.append(Check("ECLI mit RealBasket-Engine nachgerechnet", ecli_diff <= 0.051,
                        f"max. Abweichung {ecli_diff:.3f} Indexpunkte (gedruckt mit 1 Nachkommastelle)"))
    both = [p for p in periods if p in vpi]
    tables_ok = bool(both) and all(abs(vpi[p]["ecli"] - printed_ecli[p]) < 0.01 for p in both)
    checks.append(Check("ECLI-Tabellen stimmen überein", tables_ok, f"{len(both)} Monate verglichen"))
    sums = {p: sum(costs[p]["groups"].values()) for p in periods}
    yoy_diff = max((abs((sums[p] / sums[_shift(p, -12)] - 1) * 100 - v)
                    for p, v in printed_yoy.items() if _shift(p, -12) in sums), default=0.0)
    checks.append(Check("ECLI-Vorjahresraten nachgerechnet", yoy_diff <= 0.06,
                        f"{len(printed_yoy)} Raten, max. Abweichung {yoy_diff:.3f} Prozentpunkte"))
    checks.append(Check("Mehrfach berichtete Werte identisch", not conflicts,
                        ", ".join(sorted(set(conflicts))) or "keine Widersprüche"))
    checks.append(Check("VPI für alle Monate vorhanden", set(periods) <= set(vpi),
                        f"{len(vpi)} von {len(periods)} Monaten"))

    cities = next((d["cities"] for d in reversed(docs) if d["cities"]), [])
    change_diff = max((abs((c["rent_oct_eur_m2"] / c["rent_jan_eur_m2"] - 1) * 100 - c["change_pct"])
                       for c in cities), default=0.0)
    flat_diff = max((max(abs(c["rent_jan_eur_m2"] * CITY_FLAT_M2 - c["rent_jan_flat_eur"]),
                         abs(c["rent_oct_eur_m2"] * CITY_FLAT_M2 - c["rent_oct_flat_eur"])) for c in cities),
                    default=0.0)
    checks.append(Check("Stadtmieten nachgerechnet (Änderung, 75 m²)",
                        bool(cities) and change_diff <= 0.1 and flat_diff <= 0.01,
                        f"{len(cities)} Städte, max. Abweichung {change_diff:.3f} PP bzw. {flat_diff:.3f} €"
                        if cities else "keine Stadtmieten gefunden"))
    # latest report that lists the coverage per federal state (the 2026 report names the cities with rents)
    states = next((d["states"] for d in reversed(docs) if any(s["cities"] for s in d["states"].values())),
                  next((d["states"] for d in reversed(docs) if d["states"]), {}))
    covered = {(c, s["state"]) for s in states.values() for c in s["cities"]}
    coverage_ok = set(states) == set(STATES) and covered == {(c["city"], c["state"]) for c in cities}
    checks.append(Check("Bundesland-Abdeckung passt zur Städtetabelle", coverage_ok,
                        f"{len(states)} Bundesländer, {sum(bool(s['cities']) for s in states.values())} mit "
                        f"Städtewerten, {sum(not s['cities'] for s in states.values())} ohne verifizierte Reihe"))
    return RealDataset(prices=prices, cpi=cpi, base_amounts=base_cat, base_total=total, printed_ecli=printed_ecli,
                       printed_ecli_yoy=printed_yoy, city_rents=cities, documents=[d["file"] for d in docs],
                       state_coverage=[states[s] for s in STATES if s in states], checks=checks)


def real_data_dir() -> Path:
    return resolve_path(get_settings().KNOWLEDGE_DIR)


def available(doc_dir: str | Path | None = None) -> bool:
    d = Path(doc_dir) if doc_dir else real_data_dir()
    return d.is_dir() and any(d.glob("*.pdf"))


@lru_cache(maxsize=4)
def _load(doc_dir: str, fingerprint: tuple) -> RealDataset:
    docs = [parse_document(p) for p in sorted(Path(doc_dir).glob("*.pdf"))]
    return build_dataset([d for d in docs if d["costs"] or d["base"]])


def load_real_data(doc_dir: str | Path | None = None) -> RealDataset:
    """Parsed + re-checked dataset; cached until a PDF changes. Raises RealDataError if not available."""
    d = Path(doc_dir) if doc_dir else real_data_dir()
    if not available(d):
        raise RealDataError(f"No reference PDFs in '{d}'")
    fingerprint = tuple((p.name, p.stat().st_size, p.stat().st_mtime) for p in sorted(d.glob("*.pdf")))
    return _load(str(d), fingerprint)
