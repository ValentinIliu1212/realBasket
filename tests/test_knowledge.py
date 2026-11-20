"""Tests of the method-notes retrieval (RAG) and the chat tool `search_methodology`."""

import re
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from real_basket.core.settings import get_settings
from real_basket.knowledge import KnowledgeBase
from real_basket.knowledge.ingest import page_chunks, strip_repeated_headers, table_text_cells

REAL_DOCS = Path(__file__).resolve().parents[1] / "reports" / "real-data"

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


@pytest.fixture
def docs(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    make_pdf(d / "Bericht_2025.pdf", [["Methodische Hinweise", *CAVEAT], [*TABLE, *LIMITS]])
    make_pdf(d / "Bericht_2026.pdf", [["Methodische Hinweise", *CAVEAT]])
    return d


@pytest.fixture
def settings(monkeypatch):
    def apply(**env):
        base = {"DESTATIS_GENESIS_TOKEN": "", "KNOWLEDGE_RETRIEVER": "bm25", "OPENAI_API_KEY": "",
                "OPENAI_API_TYPE": "", "AZURE_OPENAI_ENDPOINT": "", "AZURE_OPENAI_API_KEY": ""}
        for k, v in {**base, **env}.items():
            monkeypatch.setenv(k, str(v))
        get_settings.cache_clear()
        return get_settings()
    yield apply
    get_settings.cache_clear()


# --- ingestion --------------------------------------------------------------------------------
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


def test_index_dedups_and_never_contains_figures(docs, tmp_path, settings):
    kb = KnowledgeBase(doc_dir=docs, index_path=tmp_path / "idx.json", settings=settings())
    idx = kb.index()
    caveat = next(c for c in idx["chunks"] if "Nettokaltmiete" in c["text"])
    assert [loc["file"] for loc in caveat["locations"]] == ["Bericht_2025.pdf", "Bericht_2026.pdf"]
    assert caveat["years"] == [2025, 2026]
    assert not any(re.search(r"\d+,\d{2}", c["text"]) for c in idx["chunks"])
    assert any(c["kind"] == "table" and "Keine verifizierte Monatsreihe" in c["text"] for c in idx["chunks"])
    assert not any("Lebenshaltungskosten Bericht" in c["text"] for c in idx["chunks"])


def test_search_english_query_and_year_filter(docs, tmp_path, settings):
    kb = KnowledgeBase(doc_dir=docs, index_path=tmp_path / "idx.json", settings=settings())
    res = kb.search("is housing the net cold rent")
    assert res["retriever"] == "bm25" and "Nettokaltmiete" in res["passages"][0]["text"]
    assert res["passages"][0]["also_in"] == ["Bericht_2026.pdf p. 1"]
    assert all(2026 in p["years"] for p in kb.search("Grenzen Modell", year=2026)["passages"])
    assert kb.search("xyzzy")["passages"] == []


def test_index_is_rebuilt_when_documents_change(docs, tmp_path, settings):
    kb = KnowledgeBase(doc_dir=docs, index_path=tmp_path / "idx.json", settings=settings())
    assert len(kb.status()["documents"]) == 2
    make_pdf(docs / "Bericht_2027.pdf", [LIMITS])
    assert len(KnowledgeBase(doc_dir=docs, index_path=tmp_path / "idx.json",
                             settings=settings()).status()["documents"]) == 3


def test_missing_document_folder_returns_no_passages(tmp_path, settings):
    kb = KnowledgeBase(doc_dir=tmp_path / "none", index_path=tmp_path / "idx.json", settings=settings())
    res = kb.search("Miete")
    assert res["passages"] == [] and "No reference documents" in res["note"]


@pytest.mark.skipif(not REAL_DOCS.is_dir(), reason="reference PDFs not available")
def test_real_documents(tmp_path, settings):
    kb = KnowledgeBase(doc_dir=REAL_DOCS, index_path=tmp_path / "idx.json", settings=settings())
    top = kb.search("Ist Wohnen / Energie die Nettokaltmiete?")["passages"][0]
    assert "keine Nettokaltmiete" in top["text"]
    assert kb.search("Brandenburg Miete Bundesland")["passages"]


def test_chat_tool_cites_file_and_page(docs, tmp_path, settings):
    from real_basket.agents.tools import search_methodology

    settings(KNOWLEDGE_DIR=str(docs), DATA_DIR=str(tmp_path / "store"))
    res = search_methodology("Nettokaltmiete Wohnen")
    assert res["passages"][0]["cite"] == "Bericht_2025.pdf p. 1"
    assert "never take figures" in res["note"]
