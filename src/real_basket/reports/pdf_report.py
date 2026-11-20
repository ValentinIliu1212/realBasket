"""PDF-Berichte aus den echten Daten der Referenz-PDFs (reports/real-data, ECLI-Modellrechnung).

- realbasket_preise_<Jahr>.pdf: modellierte Monatskosten je Ausgabengruppe (EUR/Monat), Summe, ECLI und VPI
- realbasket_miete_staedte.pdf: Angebotsmieten der 15 größten Städte + Abdeckung je Bundesland
- realbasket_verbraucherpreisindex.pdf: VPI vs. Grundlebenshaltungskosten-Index, Vorjahresraten, Datenprüfung

Es gibt keine synthetischen Daten: fehlen die Referenz-PDFs, bricht die Erzeugung mit `RealDataError` ab.

Aufruf: poetry run real-basket-pdf [--out reports]
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from real_basket.agents.prompts import DISCLAIMER
from real_basket.core.index import compare_with_cpi, essential_index
from real_basket.core.investigation import STATE_NOTE, state_rent_coverage
from real_basket.data.basket import Basket, RealDataError, load_basket
from real_basket.data.real_data import CITY_FLAT_M2, MONTHS_DE
from real_basket.schemas.models import CATEGORY_LABEL_DE

__all__ = ["RealDataError", "format_eur", "generate_all", "generate_cpi_report", "generate_rent_report",
           "generate_yearly_price_reports"]

BLUE, GREY = colors.HexColor("#0072BC"), colors.HexColor("#5A6772")
PAGE_W = landscape(A4)[0] - 2 * cm


def format_eur(value: float) -> str:
    """Deutsches Format: 1.234,56 € (Werte < 1 € mit 3 Nachkommastellen)."""
    decimals = 3 if abs(value) < 1 else 2
    s = f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} €"


def _num(value: float, digits: int = 1) -> str:
    return f"{value:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(value: float | None, sign: bool = False) -> str:
    if value is None or pd.isna(value):
        return "–"
    return f"{'+' if sign and value >= 0 else ''}{_num(value)} %"


def _table(rows: list[list[str]], widths: list[float], header: colors.Color = BLUE,
           bold_last: bool = False, font_size: float = 8, align_left: bool = False) -> Table:
    t = Table(rows, colWidths=widths, repeatRows=1)
    style = [
        ("FONT", (0, 0), (-1, -1), "Helvetica", font_size),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", font_size),
        ("BACKGROUND", (0, 0), (-1, 0), header),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (1, 0), (-1, -1), "LEFT" if align_left else "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F6FA")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B0B7BF")),
    ]
    if bold_last:
        style += [("FONT", (0, -1), (-1, -1), "Helvetica-Bold", font_size),
                  ("LINEABOVE", (0, -1), (-1, -1), 1, header)]
    t.setStyle(TableStyle(style))
    return t


def _header(title: str, basket: Basket, styles) -> list:
    return [
        Paragraph(title, styles["Title"]),
        Paragraph(f"Datenbasis: {basket.label} · echte Daten aus den Referenz-PDFs · Erstellt am "
                  f"{date.today():%d.%m.%Y}", styles["Normal"]),
        Paragraph("Quellen: " + ", ".join(basket.real.documents), styles["Normal"]),
        Spacer(1, 0.4 * cm),
    ]


def _build(out_file: Path, title: str, story: list) -> Path:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(str(out_file), pagesize=landscape(A4), leftMargin=1 * cm, rightMargin=1 * cm,
                      topMargin=1 * cm, bottomMargin=1 * cm, title=title, author="RealBasket").build(story)
    return out_file


def generate_yearly_price_reports(output_dir: str | Path = "reports", basket: Basket | None = None) -> list[Path]:
    """Ein PDF pro Kalenderjahr der Referenzdaten: Monatskosten je Ausgabengruppe, Summe, ECLI und VPI."""
    basket = basket or load_basket()
    ds, styles = basket.real, getSampleStyleSheet()
    ecli = essential_index(basket.prices, basket.weights)
    cpi = {c.period: c.index_value for c in basket.cpi}
    cost = {(p.category, p.period): p.price for p in basket.prices}
    files = []
    for year in sorted({p.year for p in ds.periods}):
        months = [p for p in ds.periods if p.year == year]
        first_w = 4.2 * cm
        widths = [first_w] + [(PAGE_W - first_w) / len(months)] * len(months)
        head = ["Ausgabengruppe"] + [MONTHS_DE[m.month - 1] for m in months]
        rows = [head] + [[CATEGORY_LABEL_DE[c]] + [format_eur(cost[(c, m)]) for m in months]
                         for c in basket.categories]
        rows.append(["Summe €/Monat"] + [format_eur(sum(cost[(c, m)] for c in basket.categories)) for m in months])
        idx_rows = [["Index (11/2024 = 100)"] + head[1:],
                    ["ECLI (nachgerechnet)"] + [_num(float(ecli[pd.Timestamp(m)])) for m in months],
                    ["ECLI (Referenzbericht)"] + [_num(ds.printed_ecli[m]) for m in months],
                    ["VPI (Destatis)"] + [_num(cpi[m]) if m in cpi else "–" for m in months]]
        story = _header(f"RealBasket – Modellierte Lebenshaltungskosten {year}", basket, styles) + [
            Paragraph(f"Referenzwarenkorb (Basis 11/2024) in EUR pro Monat, {MONTHS_DE[months[0].month - 1]} – "
                      f"{MONTHS_DE[months[-1].month - 1]} {year}", styles["Heading2"]),
            _table(rows, widths, bold_last=True, font_size=7.5),
            Spacer(1, 0.5 * cm),
            Paragraph("Indizes", styles["Heading2"]),
            _table(idx_rows, widths, header=GREY, font_size=7.5),
            Spacer(1, 0.5 * cm),
            Paragraph("„Wohnen / Energie“ umfasst mehr als die Nettokaltmiete. Die Werte sind modelliert "
                      "(Destatis-Ausgaben EVS 2023, fortgeschrieben mit amtlichen Preisindizes).", styles["Italic"]),
            Paragraph(DISCLAIMER, styles["Italic"]),
        ]
        files.append(_build(Path(output_dir) / f"realbasket_preise_{year}.pdf", f"RealBasket Preise {year}", story))
    return files


def generate_rent_report(output_dir: str | Path = "reports", basket: Basket | None = None) -> Path:
    """PDF: Angebotsmieten der 15 größten Städte (Jan vs. Okt 2026) und Abdeckung je Bundesland."""
    basket = basket or load_basket()
    ds, styles = basket.real, getSampleStyleSheet()
    if not ds.city_rents:
        raise RealDataError("Keine Stadtmieten in den Referenz-PDFs gefunden")
    cities = sorted(ds.city_rents, key=lambda c: -c["rent_oct_eur_m2"])
    rows = [["Stadt", "Bundesland", "Jan 2026 €/m²", "Okt 2026 €/m²", f"Jan 2026 {CITY_FLAT_M2} m²",
             f"Okt 2026 {CITY_FLAT_M2} m²", "Veränderung"]]
    rows += [[c["city"], c["state"], format_eur(c["rent_jan_eur_m2"]), format_eur(c["rent_oct_eur_m2"]),
              format_eur(c["rent_jan_flat_eur"]), format_eur(c["rent_oct_flat_eur"]), _pct(c["change_pct"], True)]
             for c in cities]
    n = len(cities)
    rows.append(["Ø alle Städte (ungewichtet)", "",
                 *(format_eur(sum(c[k] for c in cities) / n) for k in
                   ("rent_jan_eur_m2", "rent_oct_eur_m2", "rent_jan_flat_eur", "rent_oct_flat_eur")),
                 _pct(sum(c["change_pct"] for c in cities) / n, True)])
    widths = [4.6 * cm, 4.6 * cm] + [(PAGE_W - 9.2 * cm) / 5] * 5

    cov_rows = [["Bundesland", "Verifizierte Landesreihe", "Städte mit veröffentlichter Miete (Okt 2026)"]]
    cov_rows += [[s["bundesland"], "nein",
                  ", ".join(f"{c['city']} {format_eur(c['rent_eur_per_m2'])}/m²" for c in s["cities"]) or "–"]
                 for s in state_rent_coverage(ds)]

    story = _header("RealBasket – Mieten der größten Städte", basket, styles) + [
        Paragraph(f"Angebotskaltmiete (nettokalt) pro m² und für eine {CITY_FLAT_M2}-m²-Wohnung",
                  styles["Heading2"]),
        Paragraph(f"Quelle: {cities[0]['source']}", styles["Normal"]),
        Spacer(1, 0.2 * cm),
        _table(rows, widths, bold_last=True),
        PageBreak(),
        Paragraph("Abdeckung je Bundesland", styles["Heading2"]),
        Paragraph(STATE_NOTE, styles["Normal"]),
        Spacer(1, 0.2 * cm),
        _table(cov_rows, [5 * cm, 4 * cm, PAGE_W - 9 * cm], align_left=True),
    ]
    return _build(Path(output_dir) / "realbasket_miete_staedte.pdf", "RealBasket Mieten Städte", story)


def generate_cpi_report(output_dir: str | Path = "reports", basket: Basket | None = None) -> Path:
    """PDF: VPI vs. Grundlebenshaltungskosten-Index je Monat inkl. Vorjahresraten und Datenprüfung."""
    basket = basket or load_basket()
    ds, styles = basket.real, getSampleStyleSheet()
    cmp = compare_with_cpi(essential_index(basket.prices, basket.weights), basket.cpi)
    rows = [["Monat", "ECLI", "VPI", "ECLI ggü. Vorjahr", "VPI ggü. Vorjahr", "Abweichung"]]
    for ts, r in cmp.iterrows():
        dev = r["deviation_pp"]
        rows.append([f"{MONTHS_DE[ts.month - 1]} {ts.year}", _num(r["essential_index"]), _num(r["cpi_index"]),
                     _pct(r["essential_yoy_pct"]), _pct(r["cpi_yoy_pct"]),
                     "–" if pd.isna(dev) else f"{'+' if dev >= 0 else ''}{_num(dev, 2)} PP"])
    weights = ", ".join(f"{CATEGORY_LABEL_DE[c]} {_num(w * 100)} %" for c, w in basket.weights.weights.items())
    check_rows = [["", "Prüfung", "Details"]] + [["OK" if c.ok else "FEHLER", c.name, c.detail] for c in ds.checks]

    story = _header("RealBasket – Verbraucherpreisindex vs. Grundlebenshaltungskosten", basket, styles) + [
        Paragraph("Index (11/2024 = 100) und Veränderung ggü. Vorjahresmonat", styles["Heading2"]),
        Paragraph(f"Gewichte = Ausgabenanteile des Referenzwarenkorbs: {weights}. Vorjahresraten erst ab dem "
                  "13. Monat der Reihe berechenbar.", styles["Normal"]),
        Spacer(1, 0.2 * cm),
        _table(rows, [3 * cm] + [(PAGE_W - 3 * cm) / 5] * 5),
        Spacer(1, 0.4 * cm),
        Paragraph(DISCLAIMER, styles["Italic"]),
        PageBreak(),
        Paragraph(f"Datenprüfung: {sum(c.ok for c in ds.checks)} von {len(ds.checks)} Prüfungen bestanden",
                  styles["Heading2"]),
        Paragraph("Die Zahlen werden deterministisch aus den Tabellen der Referenz-PDFs gelesen (kein LLM) und im "
                  "Code nachgerechnet.", styles["Normal"]),
        Spacer(1, 0.2 * cm),
        _table(check_rows, [2 * cm, 8 * cm, PAGE_W - 10 * cm], align_left=True),
    ]
    return _build(Path(output_dir) / "realbasket_verbraucherpreisindex.pdf", "RealBasket Verbraucherpreisindex",
                  story)


def generate_all(output_dir: str | Path = "reports", basket: Basket | None = None) -> list[Path]:
    """All reports: yearly price PDFs, city rents, VPI comparison."""
    basket = basket or load_basket()
    return [*generate_yearly_price_reports(output_dir, basket), generate_rent_report(output_dir, basket),
            generate_cpi_report(output_dir, basket)]


def main() -> None:
    parser = argparse.ArgumentParser(description="PDF-Berichte aus den echten Daten der Referenz-PDFs.")
    parser.add_argument("--out", default="reports")
    args = parser.parse_args()
    try:
        basket = load_basket()
    except RealDataError as exc:
        raise SystemExit(f"Echte Daten nicht verfügbar: {exc}") from exc
    jobs = [("Jahres-PDFs", lambda: generate_yearly_price_reports(args.out, basket)),
            ("Mieten Städte", lambda: [generate_rent_report(args.out, basket)]),
            ("Verbraucherpreisindex", lambda: [generate_cpi_report(args.out, basket)])]
    for name, job in jobs:
        try:
            for f in job():
                print(f"PDF erstellt: {f.resolve()}")
        except PermissionError as exc:
            print(f"ÜBERSPRUNGEN ({name}): Datei ist gesperrt – bitte im PDF-Viewer schließen. ({exc.filename})")


if __name__ == "__main__":
    main()
