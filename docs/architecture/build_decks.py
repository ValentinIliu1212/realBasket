"""Build the architecture slide decks: current state and the MCP/A2A target proposal.

Run:  poetry run python docs/architecture/build_decks.py
Output (next to this script):
  - RealBasket_Architektur_Ist.pptx
  - RealBasket_Architektur_Vorschlag_MCP_A2A.pptx
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

OUT = Path(__file__).resolve().parent

NAVY = RGBColor(0x1F, 0x3A, 0x5F)
TEAL = RGBColor(0x2A, 0x9D, 0x8F)
PURPLE = RGBColor(0x6D, 0x4C, 0x9F)
ORANGE = RGBColor(0xE7, 0x6F, 0x51)
SAND = RGBColor(0xF4, 0xD3, 0x8C)
LIGHT = RGBColor(0xEE, 0xF2, 0xF7)
GREY = RGBColor(0x6B, 0x72, 0x80)
DARK = RGBColor(0x1F, 0x29, 0x37)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

FOOTER = "RealBasket · Architektur · Stand November 2026"


# --- helpers ---------------------------------------------------------------------------------------
def new_deck() -> Presentation:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    return prs


def _runs(paragraph, text: str, size: float, color: RGBColor, bold: bool = False, font: str | None = None):
    run = paragraph.add_run()
    run.text = text
    run.font.size, run.font.bold, run.font.color.rgb = Pt(size), bold, color
    if font:
        run.font.name = font
    return run


def textbox(s, x, y, w, h, lines, size=16, color=DARK, bold=False, align=PP_ALIGN.LEFT, font=None):
    tf = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)).text_frame
    tf.word_wrap = True
    for i, line in enumerate([lines] if isinstance(lines, str) else lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        _runs(p, line, size, color, bold, font)
    return tf


def bullets(s, x, y, w, h, items, size=18):
    """items: str (level 0) or (str, 1) for a sub-bullet."""
    tf = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)).text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        text, level = item if isinstance(item, tuple) else (item, 0)
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(6)
        _runs(p, ("      – " if level else "• ") + text, size - 3 * level, GREY if level else DARK)
    return tf


def title_slide(prs, title, subtitle):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    bg.fill.solid()
    bg.fill.fore_color.rgb = NAVY
    bg.line.fill.background()
    textbox(s, 0.8, 2.5, 11.7, 1.3, title, 40, WHITE, True)
    textbox(s, 0.8, 3.8, 11.7, 1.2, subtitle, 20, SAND)
    textbox(s, 0.8, 6.6, 11.7, 0.5, FOOTER, 12, LIGHT)
    return s


def slide(prs, title, subtitle=None):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.9))
    bar.fill.solid()
    bar.fill.fore_color.rgb = NAVY
    bar.line.fill.background()
    textbox(s, 0.5, 0.14, 12.3, 0.65, title, 26, WHITE, True)
    if subtitle:
        textbox(s, 0.5, 0.92, 12.3, 0.35, subtitle, 13, GREY)
    textbox(s, 0.5, 7.08, 9, 0.35, FOOTER, 10, GREY)
    textbox(s, 11.8, 7.08, 1.0, 0.35, str(len(prs.slides)), 10, GREY, align=PP_ALIGN.RIGHT)
    return s


def box(s, x, y, w, h, title, body=(), fill=LIGHT, fg=None, size=13, border=None, dashed=False,
        align=PP_ALIGN.CENTER, font=None):
    sh = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.adjustments[0] = 0.08
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill
    sh.shadow.inherit = False
    if border is not None:
        sh.line.color.rgb = border
        sh.line.width = Pt(1.25)
        if dashed:
            sh.line.dash_style = MSO_LINE.DASH
    else:
        sh.line.fill.background()
    fg = fg or (WHITE if fill in (NAVY, TEAL, PURPLE, ORANGE) else DARK)
    tf = sh.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    for side in ("margin_left", "margin_right"):
        setattr(tf, side, Inches(0.08))
    tf.margin_top = tf.margin_bottom = Inches(0.04)
    p = tf.paragraphs[0]
    p.alignment = align
    if title:
        _runs(p, title, size, fg, True, font)
    for line in body:
        p = tf.add_paragraph()
        p.alignment = align
        _runs(p, line, size - 2, fg, False, font)
    return sh


def arrow(s, x1, y1, x2, y2, color=GREY, dashed=False, label=None, both=False, lx=None, ly=None):
    c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color
    c.line.width = Pt(1.75)
    if dashed:
        c.line.dash_style = MSO_LINE.DASH
    ln = c.line._get_or_add_ln()
    if both:
        ln.append(ln.makeelement(qn("a:headEnd"), {"type": "triangle"}))
    ln.append(ln.makeelement(qn("a:tailEnd"), {"type": "triangle"}))
    if label:
        textbox(s, lx if lx is not None else (x1 + x2) / 2 + 0.05, ly if ly is not None else (y1 + y2) / 2 - 0.15,
                2.2, 0.3, label, 10, color)
    return c


def table(s, x, y, w, rows, col_w, size=12, row_h=0.42):
    shape = s.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w),
                               Inches(row_h * len(rows)))
    tbl = shape.table
    for j, cw in enumerate(col_w):
        tbl.columns[j].width = Inches(cw)
    for i, row in enumerate(rows):
        for j, value in enumerate(row):
            cell = tbl.cell(i, j)
            cell.text = ""
            cell.fill.solid()
            cell.fill.fore_color.rgb = NAVY if i == 0 else (LIGHT if i % 2 else WHITE)
            cell.margin_left = cell.margin_right = Inches(0.08)
            _runs(cell.text_frame.paragraphs[0], value, size, WHITE if i == 0 else DARK, i == 0)
    return tbl


def flow(s, steps, y=1.6, h=2.2, fills=None, size=13):
    """Numbered process steps left to right with arrows."""
    n, gap, x0, total = len(steps), 0.35, 0.5, 12.3
    w = (total - gap * (n - 1)) / n
    for i, (title, body) in enumerate(steps):
        x = x0 + i * (w + gap)
        fill = (fills or [TEAL])[i % len(fills or [TEAL])]
        box(s, x, y, w, h, f"{i + 1}  {title}", body, fill, size=size)
        if i < n - 1:
            arrow(s, x + w + 0.03, y + h / 2, x + w + gap - 0.03, y + h / 2, NAVY)


def legend(s, items, y=6.62):
    x = 0.5
    for label, fill in items:
        box(s, x, y, 0.3, 0.3, "", (), fill, border=GREY if fill == LIGHT else None)
        textbox(s, x + 0.35, y - 0.03, 2.4, 0.35, label, 11, GREY)
        x += 2.55


# --- deck 1: current architecture ----------------------------------------------------------------
def current_deck() -> Presentation:
    prs = new_deck()
    title_slide(prs, "RealBasket – Ist-Architektur",
                "Agentischer Index der Grundlebenshaltungskosten im Vergleich zum amtlichen VPI\n"
                "Streamlit · Strands Agents · Azure OpenAI · deterministische Rechenkerne")

    s = slide(prs, "Was RealBasket heute leistet")
    bullets(s, 0.5, 1.3, 8.0, 5.6, [
        "Index der Grundlebenshaltungskosten (ECLI-Warenkorb, 5 Ausgabengruppen) vs. amtlicher VPI",
        "Echte Daten: deterministisch aus den PDF-Tabellen in reports/real-data geparst",
        ("11 Nachrechen-Prüfungen (Summen, Lücken, ECLI, Jahresraten, VPI, Stadtmieten, Länder)", 1),
        ("Keine Demo-Daten, kein Fallback: ohne PDFs Fehlermeldung statt Zahlen", 1),
        "Einflussfaktoren: Beitrag jeder Ausgabengruppe zur Abweichung in Prozentpunkten",
        "Mieten der 15 größten Städte (Jan vs. Okt 2026); je Bundesland nur Abdeckung",
        "Methodenhinweise per RAG (BM25 + Embeddings), Zitate mit Datei und Seite",
        "Chat mit RealBasket: Strands-Agent auf Azure OpenAI (gpt-4o), Antworten auf Deutsch",
        "Grundsatz: Zahlen nur aus deterministischen Tools – das LLM rechnet nie selbst",
    ], 16)
    box(s, 8.9, 1.5, 3.9, 3.6, "Ergebnis 10/2026 (echte Daten)",
        ["", "Grundbedarf: +2,93 %", "VPI: +2,83 %", "Abweichung: +0,11 PP", "",
         "Größter Einflussfaktor:", "Verkehr / Mobilität (+0,94 PP)"], TEAL, size=17)
    textbox(s, 8.9, 5.25, 3.9, 0.8, "Quelle: ECLI-Modellrechnung 2024–2026, Basis Nov 2024 = 100", 11, GREY)

    s = slide(prs, "Komponenten", "Ein Python-Prozess: Streamlit hostet Dashboard und Agenten; nur das LLM ist extern")
    box(s, 0.5, 1.35, 12.3, 0.7, "Streamlit-UI  (ui/app.py)",
        ["Index vs. VPI · Einflussfaktoren · Miete Städte · Methodenhinweise · "
         "Chat mit RealBasket · Sidebar: Gewichte & PDF-Berichte"], NAVY, size=14)
    box(s, 0.5, 2.4, 4.0, 1.0, "Orchestrator-Agent (Strands)",
        ["REALBASKET-ORCHESTRATOR · agents/orchestrator.py"], TEAL)
    box(s, 5.0, 2.4, 3.6, 1.0, "Price-Collector-Sub-Agent",
        ["„Agents as Tools“ · collect_category_prices"], TEAL)
    box(s, 9.4, 2.4, 3.4, 1.0, "Azure OpenAI",
        ["gpt-4o (Completion)", "text-embedding-3-large"], ORANGE)
    box(s, 0.5, 3.75, 4.0, 1.0, "Agent-Tools  (agents/tools.py)",
        ["fetch_prices · fetch_official_cpi · calculate_essential_vs_cpi · investigate_deviation · "
         "fetch_regional_rents · search_methodology"], SAND, size=12)
    box(s, 5.0, 3.75, 3.6, 1.0, "Prompts  (agents/prompts.py)",
        ["Deutsch · Disclaimer · nur echte Daten, keine Schätzungen"], LIGHT, border=GREY, size=12)
    box(s, 9.4, 3.75, 3.4, 1.0, "PDF-Berichte",
        ["reports/pdf_report.py (reportlab)"], LIGHT, border=GREY, size=12)
    box(s, 0.5, 5.05, 2.55, 1.05, "Rechenkern  core/",
        ["index.py", "investigation.py"], LIGHT, border=NAVY, size=12)
    box(s, 3.25, 5.05, 2.6, 1.05, "Daten  data/",
        ["real_data.py (Parser + Prüfungen)", "basket.py (nur echte Daten)"], LIGHT, border=NAVY, size=12)
    box(s, 6.05, 5.05, 2.55, 1.05, "Wissensbasis  knowledge/",
        ["ingest · BM25 + Embedding", "(RRF) · index.json"], LIGHT, border=NAVY, size=12)
    box(s, 9.4, 5.05, 3.4, 1.05, "Konfiguration",
        ["core/settings.py · core/llm.py", ".env im Projektordner"], LIGHT, border=GREY, size=12)
    box(s, 3.25, 6.3, 5.35, 0.45, "reports/real-data/*.pdf  –  ECLI-Modellrechnung 2024 · 2025 · 2026",
        (), LIGHT, border=GREY, dashed=True, size=11)
    arrow(s, 2.5, 2.05, 2.5, 2.4, NAVY, label="Chat", lx=2.6, ly=2.05)
    arrow(s, 4.75, 2.05, 4.75, 5.05, NAVY, label="Dashboard (ohne LLM)", lx=4.8, ly=4.75)
    arrow(s, 8.95, 2.05, 9.4, 4.0, NAVY, label="PDF", lx=8.7, ly=3.35)
    arrow(s, 4.5, 2.9, 5.0, 2.9, TEAL)
    arrow(s, 8.6, 2.9, 9.4, 2.9, ORANGE, both=True)
    arrow(s, 2.5, 3.4, 2.5, 3.75, TEAL)
    arrow(s, 5.6, 3.4, 4.3, 3.75, TEAL)
    arrow(s, 1.5, 4.75, 1.5, 5.05, GREY)
    arrow(s, 3.6, 4.75, 3.9, 5.05, GREY)
    arrow(s, 4.3, 4.75, 6.6, 5.05, GREY)
    arrow(s, 3.25, 5.55, 3.05, 5.55, GREY)
    arrow(s, 4.5, 6.1, 4.5, 6.3, GREY)
    arrow(s, 7.3, 6.1, 7.3, 6.3, GREY)

    s = slide(prs, "Ablauf einer Chat-Frage",
              "Beispiel: „Steigen die Grundlebenshaltungskosten stärker als der VPI?“")
    flow(s, [
        ("Frage", ["Nutzer fragt im Tab", "„Chat mit RealBasket“"]),
        ("Orchestrator", ["Streamlit ruft den Agenten", "in-process auf (eine", "Sitzung, Folgefragen)"]),
        ("Planung", ["gpt-4o wählt die Tools", "(Function Calling)"]),
        ("Rechnen", ["Tools rechnen deterministisch", "(core/, data/) bzw. suchen", "Hinweise (knowledge/)"]),
        ("Sub-Agent", ["Price-Collector fasst", "Preise je Ausgabengruppe", "zusammen"]),
        ("Antwort", ["Deutsch, Zahlen aus Tools,", "Quellen „Datei S. N“,", "Disclaimer"]),
    ], y=1.7, h=2.3, fills=[NAVY, TEAL, ORANGE, PURPLE, TEAL, NAVY], size=13)
    bullets(s, 0.5, 4.5, 12.3, 2.4, [
        "Dashboard-Tabs (Index vs. VPI, Einflussfaktoren) rufen core/ und data/ direkt auf – ohne LLM, "
        "deshalb identische Zahlen in Dashboard und Chat",
        "Nur echte Daten: Mieten je Bundesland und Nettogehälter sind nicht in den Quellen – der Agent sagt das, "
        "statt zu schätzen",
        "Unveränderte Gewichts-Regler → exakte Warenkorbgewichte aus den PDFs",
    ], 16)

    s = slide(prs, "Datenpipeline", "Zwei getrennte Pfade: Zahlen (deterministisch) und Methodenhinweise (RAG)")
    box(s, 0.5, 2.9, 2.0, 1.3, "Referenz-PDFs", ["reports/real-data", "2024 · 2025 · 2026"], NAVY)
    textbox(s, 2.7, 1.35, 10, 0.4, "Zahlenpfad", 15, TEAL, True)
    textbox(s, 2.7, 4.55, 10, 0.4, "Hinweispfad (RAG)", 15, PURPLE, True)
    num = [("Text extrahieren", ["ingest.extract_pages", "(pypdf)"]),
           ("Tabellen parsen", ["Basiswarenkorb · Monats-", "kosten · ECLI/VPI · Mieten"]),
           ("11 Prüfungen", ["Summen · Lücken · ECLI", "VPI · Mieten · Länder"]),
           ("Warenkorb", ["load_basket()", "nur echte Daten"]),
           ("Rechenkern", ["Index · Abweichung", "Einflussfaktoren"])]
    rag = [("Passagen", ["Hinweise + Text-", "Tabellenzellen"]),
           ("Bereinigen", ["Zahlen verworfen,", "Duplikate zusammengeführt"]),
           ("Index", ["index.json", "+ Embeddings"]),
           ("Suche", ["BM25 + Embedding", "(Reciprocal Rank Fusion)"]),
           ("Zitat", ["Datei + Seite", "„auch in …“"])]
    for row, (y, items, fill) in enumerate([(1.8, num, TEAL), (5.0, rag, PURPLE)]):
        for i, (t, b) in enumerate(items):
            x = 3.0 + i * 2.0
            box(s, x, y, 1.75, 1.3, t, b, fill, size=12)
            if i:
                arrow(s, x - 0.25, y + 0.65, x, y + 0.65, NAVY)
        arrow(s, 2.5, 3.55, 3.0, y + 0.65, NAVY)
    textbox(s, 3.0, 3.2, 9.8, 0.6, "Kein Fallback: PDFs fehlen oder nicht lesbar → RealDataError; Dashboard "
            "zeigt den Fehler, Tools liefern {\"error\": …} – es gibt keine Demo-Daten", 12, GREY)
    textbox(s, 3.0, 6.4, 9.8, 0.6, "Ohne LLM-Zugang: reine BM25-Suche (offline) mit deutscher Stammformbildung "
            "und Glossar Englisch → Deutsch", 12, GREY)

    s = slide(prs, "Technologie-Stack")
    table(s, 0.5, 1.4, 12.3, [
        ["Schicht", "Technologie", "Rolle"],
        ["UI", "Streamlit, Plotly", "Dashboard, Chat, PDF-Download"],
        ["Agenten", "Strands Agents SDK (OpenAIModel / AzureOpenAIModel)", "Orchestrator + Collector-Sub-Agent"],
        ["LLM", "Azure OpenAI: gpt-4o, text-embedding-3-large", "Planung, Formulierung, Embeddings"],
        ["Daten", "pypdf, pandas, pydantic", "PDF-Parsing, Prüfungen, Modelle"],
        ["Wissen", "eigener BM25 + Embedding-Retriever, index.json", "Methodenhinweise mit Zitaten"],
        ["Berichte", "reportlab", "PDF-Berichte"],
        ["Konfiguration", "pydantic-settings, .env (Projektordner)", "Azure-Einstellungen, KNOWLEDGE_DIR"],
        ["Qualität / Build", "pytest (31 Tests), ruff, Poetry", "Tests, Lint, Abhängigkeiten"],
    ], [2.3, 5.6, 4.4], size=14, row_h=0.55)

    s = slide(prs, "Stärken und Grenzen")
    box(s, 0.5, 1.35, 6.0, 0.55, "Stärken", (), TEAL, size=16)
    bullets(s, 0.5, 2.0, 6.0, 4.9, [
        "Einfach: ein Prozess, ein Deployment – ideal für die Demo",
        "Deterministische, nachgeprüfte Zahlen; LLM nur für Sprache",
        "Dashboard und Chat nutzen denselben Rechenkern",
        "Nur echte, nachgerechnete Daten – keine synthetischen Werte",
        "Offline nutzbar ohne LLM (Dashboard, BM25-Suche, PDFs)",
        "31 automatische Tests, Lint sauber",
    ], 16)
    box(s, 6.8, 1.35, 6.0, 0.55, "Grenzen", (), ORANGE, size=16)
    bullets(s, 6.8, 2.0, 6.0, 4.9, [
        "Tools nur im eigenen Prozess nutzbar – keine Wiederverwendung durch Copilot, Claude & Co.",
        "Agent läuft im Streamlit-Prozess: skaliert nur mit der UI",
        "Sub-Agent eng gekoppelt, nicht separat versionier- oder deploybar",
        "Datenstand fix (PDFs bis 10/2026), keine Live-Anbindung (Destatis)",
        "Keine Mieten je Bundesland, keine Nettogehälter in den Quellen",
        "Kein Auth-/Mandantenkonzept, Schlüssel in .env",
    ], 16)
    return prs


# --- deck 2: MCP / A2A proposal ------------------------------------------------------------------
def proposal_deck() -> Presentation:
    prs = new_deck()
    title_slide(prs, "RealBasket – Zielarchitektur mit MCP und A2A",
                "Vorschlag: Werkzeuge und Daten als MCP-Server, Agenten als A2A-Dienste\n"
                "Gleicher deterministischer Rechenkern – offen für weitere Clients und Agenten")

    s = slide(prs, "Warum MCP und A2A?")
    bullets(s, 0.5, 1.3, 6.3, 5.6, [
        "Wiederverwendung: RealBasket-Daten und -Rechnungen in Copilot, Claude Desktop oder VS Code nutzbar",
        "Interoperabilität: andere Agenten (z. B. von Partnern) fragen RealBasket per A2A",
        "Entkopplung: Agenten und Werkzeuge einzeln versionieren, deployen und skalieren",
        "Klare Verträge: Tool-Schemas (MCP) und Agent Cards (A2A) statt Python-Importen",
        "Determinismus bleibt: Zahlen kommen weiterhin nur aus den Rechen-Tools",
    ], 17)
    box(s, 7.2, 1.4, 5.6, 2.4, "MCP – Model Context Protocol",
        ["Agent ↔ Werkzeuge & Daten", "", "Tools (Funktionen) · Resources (Dokumente, Daten)",
         "Prompts (Vorlagen)", "Transport: stdio (lokal) · Streamable HTTP"], PURPLE, size=16)
    box(s, 7.2, 4.1, 5.6, 2.4, "A2A – Agent2Agent-Protokoll",
        ["Agent ↔ Agent", "", "Agent Card (Fähigkeiten, Endpunkt, Auth)",
         "Tasks · Nachrichten · Artefakte", "JSON-RPC über HTTPS · SSE-Streaming"], TEAL, size=16)

    s = slide(prs, "Zielarchitektur", "Clients → Orchestrator (A2A) → Fach-Agenten (A2A) → MCP-Server → Datenquellen")
    for x, (t, b) in zip((0.5, 3.6, 6.7, 9.8), [("Streamlit-UI", ["Dashboard + Chat · A2A-Client"]),
                                                ("Microsoft Teams / Copilot", ["A2A-Client"]),
                                                ("Partner-Agenten", ["z. B. Verbraucherberatung · A2A"]),
                                                ("Claude Desktop / VS Code", ["MCP-Host"])]):
        box(s, x, 1.35, 2.9, 0.65, t, b, NAVY, size=12)
    box(s, 0.5, 2.3, 1.8, 0.8, "Azure OpenAI", ["gpt-4o · Embeddings"], ORANGE, size=12)
    box(s, 2.6, 2.3, 6.2, 0.8, "Orchestrator-Agent (Strands)",
        ["A2A-Server + A2A-Client · Antwort auf Deutsch mit Disclaimer"], TEAL, size=13)
    textbox(s, 0.5, 3.12, 9.5, 0.3, "A2A  ·  JSON-RPC über HTTPS  ·  Agent Cards  ·  Tasks  ·  SSE-Streaming",
            11, TEAL, True)
    agents = [("Price-Collector", ["Preise je Gruppe"]), ("Abweichungs-Analyst", ["Einflussfaktoren, Mieten"]),
              ("Methodik-Agent", ["RAG, Zitate"]), ("Report-Agent", ["PDF-Berichte"])]
    for i, (t, b) in enumerate(agents):
        box(s, 0.5 + i * 2.4, 3.45, 2.2, 0.75, t, b, TEAL, size=12)
    textbox(s, 0.5, 4.22, 12.3, 0.3, "MCP  ·  Streamable HTTP (lokal: stdio)  ·  Tools  ·  Resources  ·  Prompts",
            11, PURPLE, True)
    servers = [("realbasket-data", ["get_prices · get_cpi", "calculate_index · data_checks"]),
               ("realbasket-analysis", ["deviation_breakdown", "city_rents · state_coverage"]),
               ("realbasket-knowledge", ["search_methodology", "Resource doc://…/seite"]),
               ("realbasket-report", ["render_pdf", "Resource report://…"]),
               ("destatis-genesis (neu)", ["get_vpi_table", "Live-VPI"])]
    for i, (t, b) in enumerate(servers):
        box(s, 0.5 + i * 2.5, 4.55, 2.3, 1.0, t, b, PURPLE, size=12)
    sources = [("reports/real-data/*.pdf", ["ECLI 2024–2026 · VPI"]), ("Stadtmieten (in den PDFs)",
                                                                       ["15 Städte, immowelt"]),
               ("Vektorindex", ["index.json / Vector Store"]), ("Externe APIs", ["Destatis GENESIS · Mietportale"])]
    for x, (t, b) in zip((0.5, 3.6, 6.7, 9.8), sources):
        box(s, x, 5.85, 2.9, 0.65, t, b, LIGHT, border=GREY, size=12)
    # clients -> orchestrator
    arrow(s, 1.95, 2.0, 3.3, 2.3, NAVY)
    arrow(s, 5.05, 2.0, 5.05, 2.3, NAVY)
    arrow(s, 8.15, 2.0, 7.9, 2.3, NAVY)
    arrow(s, 11.5, 2.0, 11.5, 4.55, PURPLE, dashed=True, label="MCP direkt", lx=11.55, ly=3.2)
    arrow(s, 2.6, 2.7, 2.3, 2.7, ORANGE, both=True)
    # orchestrator -> agents
    for x_from, x_to in ((3.0, 1.6), (4.5, 4.0), (6.4, 6.4), (8.5, 8.8)):
        arrow(s, x_from, 3.1, x_to, 3.45, TEAL)
    # agents -> MCP servers
    for x_from, x_to in ((1.6, 1.65), (3.6, 1.9), (4.4, 4.15), (6.4, 6.65), (8.8, 9.15)):
        arrow(s, x_from, 4.2, x_to, 4.55, PURPLE)
    # MCP servers -> sources
    for x_from, x_to in ((1.3, 1.6), (2.2, 3.9), (4.15, 4.6), (6.65, 8.15), (11.65, 11.25)):
        arrow(s, x_from, 5.55, x_to, 5.85, GREY)
    legend(s, [("Clients", NAVY), ("A2A-Agenten", TEAL), ("MCP-Server", PURPLE), ("LLM", ORANGE),
               ("Datenquellen", LIGHT)])

    s = slide(prs, "MCP-Server im Detail", "Bestehender Code bleibt – die Server sind dünne Hüllen um core/, data/, "
              "knowledge/ und reports/")
    table(s, 0.5, 1.45, 12.3, [
        ["MCP-Server", "Tools", "Resources / Prompts", "Implementierung"],
        ["realbasket-data", "get_basket() · get_prices(category, months) · get_cpi(months) · "
         "calculate_index(weights, months) · data_checks()", "basket://weights · basket://checks",
         "data/basket.py, data/real_data.py, core/index.py"],
        ["realbasket-analysis", "deviation_breakdown(months) · item_changes(category) · city_rents(top) · "
         "state_coverage()", "–", "core/investigation.py"],
        ["realbasket-knowledge", "search_methodology(query, year)",
         "doc://{datei}/seite/{n} · Prompt „Hinweis zitieren“", "knowledge/ingest.py, search.py"],
        ["realbasket-report", "render_pdf(kind, year)", "report://{name}.pdf", "reports/pdf_report.py"],
        ["destatis-genesis (neu)", "get_vpi_table(code, from, to)", "–", "GENESIS-API, DESTATIS_GENESIS_TOKEN"],
    ], [2.4, 4.6, 2.8, 2.5], size=12, row_h=0.75)
    textbox(s, 0.5, 6.25, 12.3, 0.7, "Nur echte Daten: jedes Tool liefert Datenbasis, Quell-PDFs (Datei, Seite) und "
            "Prüfergebnisse mit; fehlen die PDFs, kommt ein Fehler statt Zahlen.", 13, GREY)

    s = slide(prs, "A2A-Agenten im Detail", "Jeder Agent veröffentlicht eine Agent Card unter "
              "/.well-known/agent-card.json")
    table(s, 0.5, 1.45, 12.3, [
        ["Agent", "Skills (Agent Card)", "nutzt MCP-Server", "Ergebnis (Artefakt)"],
        ["Orchestrator", "Lebenshaltung vs. VPI erklären · Fragen an Fach-Agenten verteilen",
         "– (delegiert)", "Antwort auf Deutsch + Disclaimer"],
        ["Price-Collector", "Preise je Ausgabengruppe sammeln und zusammenfassen", "realbasket-data",
         "Preisübersicht je Gruppe"],
        ["Abweichungs-Analyst", "Einflussfaktoren · Stadtmieten · Abdeckung je Bundesland",
         "realbasket-data, realbasket-analysis", "Beiträge in PP, Tabellen"],
        ["Methodik-Agent", "Methodenhinweise und Grenzen mit Zitat erklären", "realbasket-knowledge",
         "Zitate (Datei, Seite)"],
        ["Report-Agent", "PDF-Berichte erstellen", "realbasket-report, realbasket-data", "PDF als Artefakt"],
    ], [2.4, 4.6, 2.8, 2.5], size=13, row_h=0.72)
    textbox(s, 0.5, 6.0, 12.3, 0.9, "Lang laufende Aufgaben (z. B. Berichte) als A2A-Task mit Status-Updates "
            "per SSE; Ergebnisse als Artefakte statt Freitext.", 13, GREY)

    s = slide(prs, "Ablauf einer Frage in der Zielarchitektur",
              "Beispiel: „Warum liegt der Grundbedarf über dem VPI und was sagt die Methodik dazu?“")
    flow(s, [
        ("Client", ["Streamlit / Teams sendet", "A2A-Nachricht an den", "Orchestrator"]),
        ("Planung", ["Orchestrator liest Agent", "Cards und verteilt", "Teilaufgaben"]),
        ("Analyse", ["Abweichungs-Analyst ruft", "calculate_index und", "deviation_breakdown (MCP)"]),
        ("Methodik", ["Methodik-Agent ruft", "search_methodology (MCP),", "parallel zur Analyse"]),
        ("Zusammenführen", ["Orchestrator kombiniert", "Artefakte, prüft", "Quellen + Prüfungen"]),
        ("Antwort", ["Deutsch, Zahlen + Zitate,", "Disclaimer, gestreamt", "per SSE"]),
    ], y=1.7, h=2.3, fills=[NAVY, TEAL, PURPLE, PURPLE, TEAL, NAVY], size=13)
    bullets(s, 0.5, 4.5, 12.3, 2.4, [
        "Die Zahlen stammen ausschließlich aus MCP-Tools – kein Agent rechnet selbst",
        "Unabhängige Teilaufgaben laufen parallel (Analyse und Methodik)",
        "Durchgängiges Tracing über A2A- und MCP-Grenzen (OpenTelemetry, in Strands integriert)",
    ], 16)

    s = slide(prs, "Abbildung Ist → Ziel")
    table(s, 0.5, 1.4, 12.3, [
        ["Heute", "Ziel", "Protokoll"],
        ["agents/tools.py: fetch_prices, fetch_official_cpi, calculate_essential_vs_cpi",
         "MCP-Server realbasket-data", "MCP"],
        ["agents/tools.py: investigate_deviation, fetch_regional_rents",
         "MCP-Server realbasket-analysis", "MCP"],
        ["agents/tools.py: search_methodology + knowledge/", "MCP-Server realbasket-knowledge (Tools + Resources)",
         "MCP"],
        ["ui/app.py: PDF-Download über reports/pdf_report.py", "MCP-Server realbasket-report + Report-Agent",
         "MCP / A2A"],
        ["collect_category_prices (Sub-Agent im selben Prozess)", "Price-Collector als eigener Dienst mit Agent Card",
         "A2A"],
        ["Orchestrator im Streamlit-Prozess", "Orchestrator-Dienst (A2A-Server)", "A2A"],
        ["Streamlit ruft den Agenten direkt auf", "Streamlit als A2A-Client; Dashboard nutzt realbasket-data",
         "A2A / MCP"],
        ["core/, data/, Tests", "unverändert – gemeinsamer Rechenkern aller MCP-Server", "–"],
    ], [5.6, 5.0, 1.7], size=13, row_h=0.58)

    s = slide(prs, "Umsetzung mit Strands und dem MCP-SDK", "Skizze – alle Bausteine sind als Python-Pakete verfügbar")
    code = [
        ("MCP-Server (mcp-SDK, FastMCP)", [
            "mcp = FastMCP(\"realbasket-data\")",
            "",
            "@mcp.tool()",
            "def calculate_index(weights: dict | None = None,",
            "                    months: int = 12) -> dict:",
            "    basket = load_basket()",
            "    return compute(basket, weights, months)",
            "",
            "mcp.run(transport=\"streamable-http\")"]),
        ("Fach-Agent als A2A-Dienst mit MCP-Tools", [
            "data = MCPClient(lambda: streamablehttp_client(",
            "    \"http://data-mcp:8001/mcp\"))",
            "with data:",
            "    collector = Agent(",
            "        name=\"price-collector\",",
            "        model=create_model(),",
            "        tools=data.list_tools_sync())",
            "    A2AServer(agent=collector,",
            "              port=9001).serve()"]),
        ("Orchestrator ruft A2A-Agenten", [
            "agents = A2AClientToolProvider(",
            "    known_agent_urls=[",
            "        \"http://collector:9001\",",
            "        \"http://analyst:9002\",",
            "        \"http://methodik:9003\"])",
            "",
            "orchestrator = Agent(",
            "    system_prompt=ORCHESTRATOR_PROMPT,",
            "    tools=agents.tools)"]),
    ]
    for i, (t, lines) in enumerate(code):
        x = 0.5 + i * 4.15
        box(s, x, 1.45, 4.0, 0.5, t, (), PURPLE if i == 0 else TEAL, size=13)
        box(s, x, 2.0, 4.0, 3.9, "", lines, LIGHT, border=GREY, size=13, align=PP_ALIGN.LEFT, font="Consolas")
    textbox(s, 0.5, 6.1, 12.3, 0.8, "Pakete: mcp (FastMCP, Streamable HTTP) · strands-agents[a2a] (A2AServer) · "
            "strands-agents-tools (A2AClientToolProvider) · strands.tools.mcp.MCPClient", 12, GREY)

    s = slide(prs, "Querschnittsthemen")
    for i, (t, items, fill) in enumerate([
        ("Sicherheit", ["Entra ID / OAuth 2.1 für MCP-HTTP und A2A", "Auth-Schemata in der Agent Card",
                        "Schlüssel in Azure Key Vault statt .env", "Least Privilege je MCP-Server"], NAVY),
        ("Determinismus & Qualität", ["Zahlen nur aus MCP-Tools", "Prüfergebnisse als Resource",
                                      "Contract-Tests je Tool-Schema", "31 bestehende Tests gegen core/"], TEAL),
        ("Betrieb", ["Je Dienst ein Container (Azure Container Apps)", "Health-Checks, unabhängige Skalierung",
                     "OpenTelemetry-Tracing über alle Hops", "Versionierte Agent Cards und Tools"], PURPLE),
    ]):
        x = 0.5 + i * 4.15
        box(s, x, 1.4, 4.0, 0.6, t, (), fill, size=17)
        bullets(s, x, 2.15, 4.0, 4.7, items, 16)

    s = slide(prs, "Roadmap und Empfehlung")
    for i, (t, b, fill) in enumerate([
        ("Phase 1 · sofort (1–2 Tage)", ["MCP-Server realbasket-data und", "realbasket-knowledge extrahieren",
                                        "Agent nutzt MCPClient (stdio)", "Tests unverändert grün",
                                        "Bonus: Nutzung in Claude Desktop / VS Code"], PURPLE),
        ("Phase 2 · nach dem Hackathon", ["Collector, Analyst, Methodik als", "A2A-Dienste mit Agent Cards",
                                          "Orchestrator als A2A-Server", "Streamlit als A2A-Client"], TEAL),
        ("Phase 3 · Produktion", ["destatis-genesis-MCP (Live-VPI)", "Neue Quellen: Ländermieten, Gehälter",
                                  "Entra ID, Key Vault, Container Apps", "OpenTelemetry, Monitoring"], NAVY),
    ]):
        x = 0.5 + i * 4.15
        box(s, x, 1.4, 4.0, 2.9, t, ["", *b], fill, size=16)
        if i < 2:
            arrow(s, x + 4.0, 2.85, x + 4.15, 2.85, NAVY)
    box(s, 0.5, 4.6, 6.0, 0.5, "Vorteile", (), TEAL, size=15)
    bullets(s, 0.5, 5.15, 6.0, 1.9, ["Wiederverwendbar und interoperabel", "Einzeln skalier- und deploybar",
                                    "Klare Schnittstellen, gleicher Rechenkern"], 14)
    box(s, 6.8, 4.6, 6.0, 0.5, "Aufwand / Risiken", (), ORANGE, size=15)
    bullets(s, 6.8, 5.15, 6.0, 1.9, ["Mehr Dienste, mehr Betrieb", "Zusätzliche Latenz je Netzwerk-Hop",
                                    "Auth und Versionierung nötig – für den Hackathon genügt Phase 1"], 14)
    return prs


def main() -> None:
    current_deck().save(OUT / "RealBasket_Architektur_Ist.pptx")
    proposal_deck().save(OUT / "RealBasket_Architektur_Vorschlag_MCP_A2A.pptx")
    print(f"Decks written to {OUT}")


if __name__ == "__main__":
    main()
