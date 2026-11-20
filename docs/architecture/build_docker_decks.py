"""Build the RealBasket Docker-Compose architecture decks (German + English, 4 slides each) on the NTT DATA template.

Run:  poetry run python docs/architecture/build_docker_decks.py
Needs the template docs/architecture/templates/agentic-ai-strands.pptx (NTT DATA template, versioned) and the diagram
docs/architecture/RealBasket-Architektur mit Docker Compose.png.
Output (next to this script): RealBasket_Docker_Compose_DE.pptx, RealBasket_Docker_Compose_EN.pptx

Logo, background, cover photo, footer and theme fonts (Georgia titles, Arial body) come from the template: the
cover is the template's own cover slide, the content slides use its layout "B_Title Only"; no font names are set
in this script. All other template slides are removed.
"""

from __future__ import annotations

import copy
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "templates" / "agentic-ai-strands.pptx"
DIAGRAM = HERE / "RealBasket-Architektur mit Docker Compose.png"

# template theme colours
NAVY = RGBColor(0x07, 0x0F, 0x26)      # accent1
BLUE = RGBColor(0x00, 0x72, 0xBC)      # accent2
DEEP = RGBColor(0x00, 0x5B, 0x96)      # accent3
CYAN = RGBColor(0x00, 0xDF, 0xED)      # accent4
GREEN = RGBColor(0x00, 0xCB, 0x5D)     # accent5
SLATE = RGBColor(0x2E, 0x40, 0x4D)     # dk2
SKY = RGBColor(0x19, 0xA3, 0xFC)       # lt2
GREY = RGBColor(0x94, 0x94, 0x94)      # accent6
PALE = RGBColor(0xEE, 0xF5, 0xFB)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

COVER_SLIDE = 0          # template cover (photo, innovation curve, logo)
FOOTER_SOURCE = 3        # template content slide with footer + slide number placeholders
CONTENT_LAYOUT = "B_Title Only"

TEXT = {
    "de": {
        "file": "RealBasket_Docker_Compose_DE.pptx",
        "cover_title": "RealBasket",
        "cover_subtitle": "Architektur mit Docker Compose",
        "s2_title": "RealBasket-Architektur mit Docker Compose",
        "s2_side_head": "Auf einen Blick",
        "s2_side": [
            "Vier Dienste in einem Compose-Netz; Ports nur an 127.0.0.1",
            "UI greift nie direkt auf Daten zu – alles über Agent-API und MCP",
            "Zahlen aus dem deterministischen Rechenkern, nie aus RAG",
            "Weaviate liefert nur Methodik-Kontext mit Quelle und Seite",
        ],
        "s3_title": "Vier Dienste – Zuständigkeiten und Datenflüsse",
        "services": [
            ("realbasket-ui", "Streamlit :8501",
             ["Dashboard, PDF-Downloads, Chat", "Tab Monitoring (Pfade je Sitzung)", "nur HTTP-Client zur Agent-API"]),
            ("realbasket-agent", "FastAPI :8002 (intern)",
             ["/chat: Strands-Agent + LLM", "/tools/{name}: Allow-List", "Zahlen-Guardrail je Antwort"]),
            ("realbasket-mcp", "FastMCP :8001",
             ["Rechenkern: Index, VPI, Treiber", "SQLite: Werte mit Quelle + Seite", "Original-PDFs read-only"]),
            ("weaviate", ":8080 / :50051",
             ["Vektorindex der PDF-Texte", "Embeddings via Azure OpenAI", "keine Zahlentabellen"]),
        ],
        "flows_head": "Datenflüsse",
        "flows": [
            ("Dashboard", "UI → /tools/{name} → MCP → Rechenkern / SQLite → validierte Werte (kein LLM)"),
            ("Chat", "UI → /chat → Strands-Agent → LLM wählt MCP-Tools → Antwort → Guardrail prüft jede Zahl"),
            ("PDF-Suche", "UI → /tools/search_documents → MCP → Embedding → Weaviate → Textstellen mit Seite"),
        ],
        "rules": "Grundsatz: Der Agent wählt Tools und formuliert – Kennzahlen entstehen nur im deterministischen Code.",
        "s4_title": "Branch feature/monitoring-fixes – Ergebnisse und nächste Schritte",
        "kpis": [("2,93 %", "ECLI ggü. Vorjahr – Chat-Tools = Dashboard (vorher 2,91 % bei 13 Monaten)"),
                 ("130", "Tests grün (vorher 99, davon einer auf Windows rot)"),
                 ("4 Dienste", "im Monitoring-Tab als nummerierter Use-Case-Pfad")],
        "done_head": "Umgesetzt",
        "done": [
            "Umlaute: Ursache war die Eclipse-Kodierung cp1252 – Projekt auf UTF-8, .editorconfig, Encoding-Test",
            "Rechenfehler: Index immer auf voller Reihe (Basis 11/2024), Vorjahresvergleich nach Datum",
            "Einflussfaktoren wurden in investigate_deviation überschrieben – behoben",
            "Monitoring-Tab: jede Interaktion als Pfad durch UI, Agent, MCP, Weaviate, LLM – nur je Browser-Sitzung",
            "Zahlen-Guardrail im Agent-Service: unbelegte Zahlen werden im Chat markiert",
        ],
        "next_head": "Nächste Schritte",
        "next": [
            "Weaviate-Store über core.llm konfigurieren; Jahresfilter direkt in Weaviate",
            "Chat-Kontext: Tool-Ergebnisse früherer Fragen erhalten",
            "Agent-API und MCP absichern (Authentisierung, TLS), Weaviate ohne anonymen Zugriff",
            "Docker-Build mit poetry.lock, Nicht-Root-User; CI mit ruff + pytest",
            "PDF-Upload über die Oberfläche ist nicht geplant",
        ],
        "footer_note": "RealBasket · Architektur · Stand November 2026",
    },
    "en": {
        "file": "RealBasket_Docker_Compose_EN.pptx",
        "cover_title": "RealBasket",
        "cover_subtitle": "Architecture with Docker Compose",
        "s2_title": "RealBasket architecture with Docker Compose",
        "s2_side_head": "At a glance",
        "s2_side": [
            "Four services in one Compose network; ports bound to 127.0.0.1 only",
            "The UI never reads data directly – everything goes through the agent API and MCP",
            "Figures come from the deterministic calculation core, never from RAG",
            "Weaviate only provides methodology context with file and page",
        ],
        "s3_title": "Four services – responsibilities and data flows",
        "services": [
            ("realbasket-ui", "Streamlit :8501",
             ["Dashboard, PDF downloads, chat", "Monitoring tab (paths per session)", "HTTP client to the agent API only"]),
            ("realbasket-agent", "FastAPI :8002 (internal)",
             ["/chat: Strands agent + LLM", "/tools/{name}: allow-list", "Number guardrail per answer"]),
            ("realbasket-mcp", "FastMCP :8001",
             ["Core: index, CPI, drivers", "SQLite: values with source + page", "Original PDFs read-only"]),
            ("weaviate", ":8080 / :50051",
             ["Vector index of PDF text", "Embeddings via Azure OpenAI", "No numeric tables"]),
        ],
        "flows_head": "Data flows",
        "flows": [
            ("Dashboard", "UI → /tools/{name} → MCP → core / SQLite → validated values (no LLM)"),
            ("Chat", "UI → /chat → Strands agent → LLM picks MCP tools → answer → guardrail checks every figure"),
            ("PDF search", "UI → /tools/search_documents → MCP → embedding → Weaviate → passages with page"),
        ],
        "rules": "Principle: the agent picks tools and writes the answer – figures are produced by deterministic code only.",
        "s4_title": "Branch feature/monitoring-fixes – results and next steps",
        "kpis": [("2.93 %", "ECLI year on year – chat tools = dashboard (before: 2.91 % with 13 months)"),
                 ("130", "tests passing (before: 99, one failing on Windows)"),
                 ("4 services", "shown as numbered use-case path in the Monitoring tab")],
        "done_head": "Delivered",
        "done": [
            "Umlauts: root cause was the cp1252 Eclipse encoding – project set to UTF-8, .editorconfig, encoding test",
            "Calculation bug: index always on the full series (base 11/2024), year-on-year matched by date",
            "Deviation drivers were overwritten in investigate_deviation – fixed",
            "Monitoring tab: every interaction as a path through UI, agent, MCP, Weaviate, LLM – per browser session",
            "Number guardrail in the agent service: unbacked figures are flagged in the chat",
        ],
        "next_head": "Next steps",
        "next": [
            "Configure the Weaviate store via core.llm; year filter inside Weaviate",
            "Chat context: keep tool results of earlier questions",
            "Secure agent API and MCP (authentication, TLS), Weaviate without anonymous access",
            "Docker build from poetry.lock, non-root user; CI with ruff + pytest",
            "PDF upload through the UI is not planned",
        ],
        "footer_note": "RealBasket · Architecture · November 2026",
    },
}


# --- template handling ------------------------------------------------------------------------------
def _drop_slide(prs, index: int) -> None:
    sld_ids = prs.slides._sldIdLst
    sld_id = list(sld_ids)[index]
    prs.part.drop_rel(sld_id.get(qn("r:id")))
    sld_ids.remove(sld_id)


def _layout(prs, name: str, master: int = 0):
    return next(lay for lay in prs.slide_masters[master].slide_layouts if lay.name == name)


def _footer_elements(slide) -> list:
    """Footer and slide-number placeholders (with their field codes) of a template slide."""
    return [copy.deepcopy(sh._element) for sh in slide.shapes if sh.is_placeholder
            and sh.placeholder_format.type is not None and sh.placeholder_format.idx in (3, 4)]


# --- drawing helpers --------------------------------------------------------------------------------
def _para(tf, text: str, size: float, color: RGBColor, bold: bool = False, first: bool = False,
          align=PP_ALIGN.LEFT, space_after: float = 4):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.space_after = Pt(space_after)
    run = p.add_run()
    run.text = text
    run.font.size, run.font.bold, run.font.color.rgb = Pt(size), bold, color
    return p


def textbox(slide, x, y, w, h, lines, size=12, color=SLATE, bold=False, align=PP_ALIGN.LEFT, bullet=False):
    tf = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)).text_frame
    tf.word_wrap = True
    for i, line in enumerate([lines] if isinstance(lines, str) else lines):
        _para(tf, ("• " if bullet else "") + line, size, color, bold, first=i == 0, align=align)
    return tf


def box(slide, x, y, w, h, fill, line=None, radius=0.06):
    sh = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.adjustments[0] = radius
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill
    sh.shadow.inherit = False
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line
        sh.line.width = Pt(1)
    tf = sh.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP
    tf.margin_left = tf.margin_right = Inches(0.12)
    tf.margin_top = tf.margin_bottom = Inches(0.08)
    return sh


def content_slide(prs, title: str, footer: list):
    slide = prs.slides.add_slide(_layout(prs, CONTENT_LAYOUT))
    slide.shapes.title.text = title
    for el in footer:
        slide.shapes._spTree.append(copy.deepcopy(el))
    return slide


# --- slides -----------------------------------------------------------------------------------------
def cover(slide, t: dict) -> None:
    for sh in list(slide.shapes):           # remove the training badge / Strands logo of the template cover
        if not sh.is_placeholder:
            sh._element.getparent().remove(sh._element)
    for sh in slide.placeholders:
        idx = sh.placeholder_format.idx
        if idx == 0:
            sh.text = t["cover_title"]
        elif idx == 1:
            sh.text = t["cover_subtitle"]


def architecture(slide, t: dict) -> None:
    with Image.open(DIAGRAM) as im:
        ratio = im.width / im.height
    h = 5.45
    w = h * ratio
    slide.shapes.add_picture(str(DIAGRAM), Inches(0.41), Inches(1.4), Inches(w), Inches(h))
    x = 0.41 + w + 0.3
    side = box(slide, x, 1.4, 12.93 - x, h, PALE)
    tf = side.text_frame
    _para(tf, t["s2_side_head"], 14, BLUE, True, first=True, space_after=8)
    for line in t["s2_side"]:
        _para(tf, "• " + line, 11.5, SLATE, space_after=8)


def services(slide, t: dict) -> None:
    colors = [BLUE, DEEP, NAVY, SKY]
    w, gap, y = 2.95, 0.24, 1.45
    for i, (name, port, items) in enumerate(t["services"]):
        x = 0.41 + i * (w + gap)
        head = box(slide, x, y, w, 0.75, colors[i])
        tf = head.text_frame
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        _para(tf, name, 14, WHITE, True, first=True, align=PP_ALIGN.CENTER, space_after=0)
        _para(tf, port, 10.5, WHITE, align=PP_ALIGN.CENTER, space_after=0)
        body = box(slide, x, y + 0.8, w, 1.65, PALE)
        for j, item in enumerate(items):
            _para(body.text_frame, "• " + item, 11, SLATE, first=j == 0, space_after=3)
        if i < 3:                           # arrow to the next service
            arrow = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x + w + 0.01), Inches(y + 0.25),
                                           Inches(gap - 0.02), Inches(0.25))
            arrow.fill.solid()
            arrow.fill.fore_color.rgb = GREEN
            arrow.line.fill.background()
    textbox(slide, 0.41, 4.05, 12.52, 0.35, t["flows_head"], 14, BLUE, True)
    for k, (label, flow) in enumerate(t["flows"]):
        yy = 4.45 + k * 0.5
        tag = box(slide, 0.41, yy, 1.6, 0.42, GREEN)
        tag.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        _para(tag.text_frame, label, 11, WHITE, True, first=True, align=PP_ALIGN.CENTER, space_after=0)
        line = box(slide, 2.1, yy, 10.83, 0.42, PALE)
        line.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        _para(line.text_frame, flow, 11, SLATE, first=True, space_after=0)
    rule = box(slide, 0.41, 6.05, 12.52, 0.85, NAVY)
    rule.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    _para(rule.text_frame, t["rules"], 13, WHITE, True, first=True, align=PP_ALIGN.CENTER, space_after=0)


def results(slide, t: dict) -> None:
    w, gap = 4.0, 0.26
    for i, (value, label) in enumerate(t["kpis"]):
        x = 0.41 + i * (w + gap)
        tile = box(slide, x, 1.4, w, 1.0, PALE, line=SKY)
        tf = tile.text_frame
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        _para(tf, value, 20, BLUE, True, first=True, space_after=0)
        _para(tf, label, 10, SLATE, space_after=0)
    for col, (head_key, items_key, color) in enumerate((("done_head", "done", GREEN), ("next_head", "next", BLUE))):
        x = 0.41 + col * 6.38
        head = box(slide, x, 2.6, 6.14, 0.45, color)
        head.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        _para(head.text_frame, t[head_key], 13, WHITE, True, first=True, space_after=0)
        body = box(slide, x, 3.1, 6.14, 3.8, PALE)
        for j, item in enumerate(t[items_key]):
            _para(body.text_frame, "• " + item, 11.5, SLATE, first=j == 0, space_after=6)


def build(lang: str) -> Path:
    t = TEXT[lang]
    prs = Presentation(str(TEMPLATE))
    footer = _footer_elements(prs.slides[FOOTER_SOURCE])
    for i in reversed(range(len(prs.slides))):
        if i != COVER_SLIDE:
            _drop_slide(prs, i)
    cover(prs.slides[0], t)
    architecture(content_slide(prs, t["s2_title"], footer), t)
    services(content_slide(prs, t["s3_title"], footer), t)
    results(content_slide(prs, t["s4_title"], footer), t)
    prs.core_properties.title = f"{t['cover_title']} – {t['cover_subtitle']}"
    prs.core_properties.language = "de-DE" if lang == "de" else "en-US"
    out = HERE / t["file"]
    prs.save(str(out))
    return out


if __name__ == "__main__":
    for language in TEXT:
        print("written", build(language))
