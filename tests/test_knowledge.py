"""Chunking of the reference PDFs for the Weaviate index (`knowledge/ingest.py`): text only, never figures."""

import re
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from real_basket.knowledge.ingest import ingest_documents, page_chunks, strip_repeated_headers, table_text_cells

CAVEAT = [
    "Wichtig: Die Modellposition Wohnen / Energie ist keine Nettokaltmiete und enthält",
    "auch Nebenkosten sowie die Instandhaltung der Wohnung durch die Haushalte.",
]
TABLE = ["Bundesland-Abdeckung", "Bundesland", "Monatliche Miete", "Bayern", "Keine verifizierte Monatsreihe",
         "Hamburg", "Keine verifizierte Monatsreihe", "Berlin", "12,50 €", "13,10 €"]
LIMITS = ["Grenzen: Modellierte Eurobeträge können konkrete Preisbeobachtungen im Laden nicht ersetzen."]


def make_pdf(path: Path, pages: list[list[str]]) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    for n, lines in enumerate(pages, 1):
        y = 800
        for line in ["Lebenshaltungskosten Bericht", *lines, str(n)]:
            c.drawString(40, y, line)
            y -= 16
        c.showPage()
    c.save()


def test_table_keeps_descriptive_cells_and_drops_numbers():
    # 'Berlin' sits between rent values: a label of a numeric row -> dropped together with the numbers
    cells = ["Bayern", "Keine verifizierte Monatsreihe", "11,80 €", "Berlin", "12,50 €", "Hamburg",
             "Keine verifizierte Monatsreihe"]
    assert table_text_cells(cells) == ["Bayern", "Keine verifizierte Monatsreihe", "Hamburg",
                                       "Keine verifizierte Monatsreihe"]


def test_page_chunks_join_wrapped_prose():
    chunks = page_chunks(["Methodische Hinweise", *CAVEAT])
    notes = [c for c in chunks if c["kind"] == "note"]
    assert len(notes) == 1 and notes[0]["text"] == " ".join(CAVEAT)


def test_repeated_headers_and_page_numbers_are_removed():
    pages = strip_repeated_headers([["Kopfzeile", "1", "Text A"], ["Kopfzeile", "2", "Text B"]])
    assert pages == [["Text A"], ["Text B"]]


def test_chunks_are_deduplicated_and_never_contain_figures(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    make_pdf(docs / "Bericht_2025.pdf", [["Methodische Hinweise", *CAVEAT], [*TABLE, *LIMITS]])
    make_pdf(docs / "Bericht_2026.pdf", [["Methodische Hinweise", *CAVEAT]])
    documents, chunks = ingest_documents(docs)
    assert len(documents) == 2
    caveat = next(c for c in chunks if "Nettokaltmiete" in c["text"])
    assert [loc["file"] for loc in caveat["locations"]] == ["Bericht_2025.pdf", "Bericht_2026.pdf"]
    assert caveat["years"] == [2025, 2026]
    assert not any(re.search(r"\d+,\d{2}", c["text"]) for c in chunks)
    assert any(c["kind"] == "table" and "Keine verifizierte Monatsreihe" in c["text"] for c in chunks)
    assert not any("Lebenshaltungskosten Bericht" in c["text"] for c in chunks)
