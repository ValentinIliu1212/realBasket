"""Build the RealBasket hackathon demo decks (German + English) for a 6-minute slot, with speaker notes.

Run (from the repo root):  poetry run python hackathon/build_hackathon_decks.py
Output (next to this script): RealBasket_Hackathon_Demo_DE.pptx, RealBasket_Hackathon_Demo_EN.pptx

Style: identical to docs/architecture/RealBasket_Docker_Compose_*.pptx - same NTT DATA template, cover, layout
"B_Title Only", footer, colours and drawing helpers (imported from docs/architecture/build_docker_decks.py).

Time plan (6:00): cover 0:15 · problem 0:30 · architecture 1:00 · demo dashboard 1:15 · demo search + chat 1:30 ·
demo monitoring 0:30 · source code 0:30 · summary 0:30.
The German deck additionally contains the start-up slide as a HIDDEN slide (not shown in the slide show);
the English deck has none - start-up instructions live in the README.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent
ARCH = HERE.parent / "docs" / "architecture" / "build_docker_decks.py"

_spec = importlib.util.spec_from_file_location("build_docker_decks", ARCH)
deck = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(deck)

BLUE, DEEP, NAVY, SKY, GREEN = deck.BLUE, deck.DEEP, deck.NAVY, deck.SKY, deck.GREEN
SLATE, PALE, WHITE = deck.SLATE, deck.PALE, deck.WHITE
CODE_TEXT = RGBColor(0xE6, 0xF1, 0xFA)
CODE_COMMENT = RGBColor(0x7F, 0xD8, 0xA6)
box, para = deck.box, deck._para


# --- source code shown on the code slide (excerpts of the real files) ------------------------------------------
CODE = [
    ("src/real_basket/mcp_server/server.py", [
        "@mcp.tool()",
        "def calculate_index(months: int = 24) -> dict:",
        '    """Calculate inflation vs CPI using the existing deterministic engine and validated PDFs."""',
        "    from real_basket.agents.tools import calculate_essential_vs_cpi",
        "    return calculate_essential_vs_cpi(months=months)",
    ]),
    ("src/real_basket/agent_service/api.py", [
        '@app.post("/chat")',
        "async def chat(payload: ChatRequest) -> dict:",
        "    answer, invoked, messages = await run_in_threadpool(ask, payload.question, ...)",
        "    # guardrail runs here: only the agent service sees the full tool results of the turn",
        '    return {"answer": answer, "tools": invoked,',
        '            "unverified": unverified_figures(answer, messages, payload.question), ...}',
    ]),
    ("src/real_basket/agents/guardrail.py", [
        'def unverified_figures(answer: str, messages: list, question: str = "") -> list[str]:',
        "    sources = tool_values(messages) | {v for _, v, _ in answer_figures(question)}",
        "    return list(dict.fromkeys(tok for tok, value, dec in answer_figures(answer)",
        "                              if not _backed(value, dec, sources)))",
    ]),
]


# --- slide renderers ----------------------------------------------------------------------------------------
def kpi_row(slide, kpis, y=1.4, h=1.0):
    n = len(kpis)
    gap = 0.24
    w = (12.52 - gap * (n - 1)) / n
    for i, (value, label) in enumerate(kpis):
        tile = box(slide, 0.41 + i * (w + gap), y, w, h, PALE, line=SKY)
        tf = tile.text_frame
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        para(tf, value, 20, BLUE, True, first=True, space_after=0)
        para(tf, label, 10, SLATE, space_after=0)


def key_bar(slide, text: str) -> None:
    bar = box(slide, 0.41, 5.95, 12.52, 0.9, NAVY)
    bar.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    para(bar.text_frame, text, 13.5, WHITE, True, first=True, align=PP_ALIGN.CENTER, space_after=0)


def step(slide, s: dict) -> None:
    """Two columns (click path | what we show) + key-message bar; optional KPI row on top."""
    top = 1.4
    if s.get("kpis"):
        kpi_row(slide, s["kpis"])
        top = 2.6
    body_h = 5.75 - top - 0.5
    size = s.get("size", 12)
    for col, (head_key, items_key, color, numbered) in enumerate(
            (("left_head", "left", BLUE, True), ("right_head", "right", GREEN, False))):
        x = 0.41 + col * 6.38
        head = box(slide, x, top, 6.14, 0.45, color)
        head.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        para(head.text_frame, s[head_key], 13, WHITE, True, first=True, space_after=0)
        body = box(slide, x, top + 0.5, 6.14, body_h, PALE)
        for j, item in enumerate(s[items_key]):
            prefix = f"{j + 1}. " if numbered else "• "
            para(body.text_frame, prefix + item, size, SLATE, first=j == 0, space_after=5)
    key_bar(slide, s["bar"])


def startup(slide, s: dict) -> None:
    """Five PowerShell windows side by side."""
    colors = [SKY, NAVY, DEEP, BLUE, GREEN]
    w, gap, y = 2.33, 0.217, 1.45
    for i, (name, port, items) in enumerate(s["windows"]):
        x = 0.41 + i * (w + gap)
        head = box(slide, x, y, w, 0.8, colors[i])
        tf = head.text_frame
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        para(tf, name, 13, WHITE, True, first=True, align=PP_ALIGN.CENTER, space_after=0)
        para(tf, port, 10, WHITE, align=PP_ALIGN.CENTER, space_after=0)
        body = box(slide, x, y + 0.85, w, 2.95, PALE)
        for j, item in enumerate(items):
            para(body.text_frame, "• " + item, 10.5, SLATE, first=j == 0, space_after=5)
        if i < 4:
            arrow = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x + w + 0.01), Inches(y + 0.28),
                                           Inches(gap - 0.02), Inches(0.24))
            arrow.fill.solid()
            arrow.fill.fore_color.rgb = GREEN
            arrow.line.fill.background()
    tip = box(slide, 0.41, 5.35, 12.52, 0.5, PALE, line=SKY)
    tip.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    para(tip.text_frame, s["tip"], 11, SLATE, first=True, align=PP_ALIGN.CENTER, space_after=0)
    key_bar(slide, s["bar"])


def code(slide, s: dict) -> None:
    """Three real code excerpts (left) + why they matter (right)."""
    y, x, w = 1.4, 0.41, 8.55
    for (path, lines), caption in zip(CODE, s["captions"]):
        tag = box(slide, x, y, w, 0.3, BLUE, radius=0.15)
        tag.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        tag.text_frame.margin_top = tag.text_frame.margin_bottom = Inches(0.01)
        para(tag.text_frame, f"{caption}  ·  {path}", 10, WHITE, True, first=True, space_after=0)
        h = 0.12 + len(lines) * 0.165
        panel = box(slide, x, y + 0.33, w, h, NAVY, radius=0.03)
        tf = panel.text_frame
        tf.margin_top = tf.margin_bottom = Inches(0.05)
        for j, line in enumerate(lines):
            color = CODE_COMMENT if line.strip().startswith(("#", '"""', "@")) else CODE_TEXT
            p = para(tf, line, 8.5, color, first=j == 0, space_after=0)
            p.runs[0].font.name = "Consolas"
            p.line_spacing = 1.0
        y += 0.33 + h + 0.15
    side = box(slide, 9.2, 1.4, 3.73, 4.4, PALE)
    para(side.text_frame, s["side_head"], 14, BLUE, True, first=True, space_after=8)
    for item in s["side"]:
        para(side.text_frame, "• " + item, 11.5, SLATE, space_after=8)
    key_bar(slide, s["bar"])


def notes(slide, text: str) -> None:
    slide.notes_slide.notes_text_frame.text = text.strip()


def hide(slide) -> None:
    slide._element.set("show", "0")


# --- content ------------------------------------------------------------------------------------------------
TEXT = {
    "de": {
        "file": "RealBasket_Hackathon_Demo_DE.pptx",
        "cover_title": "RealBasket",
        "cover_subtitle": "Hackathon-Demo – Was kostet das Leben wirklich?",
        "cover_notes": """
Zeit: 0:15 (Gesamt 6:00 – Zeitplan: Titel 0:15 · Problem 0:30 · Architektur 1:00 · Demo Dashboard 1:15 · Demo Suche + Chat 1:30 · Monitoring 0:30 · Code 0:30 · Fazit 0:30).
"Guten Tag zusammen. Wir sind das Team RealBasket. Wir zeigen Ihnen live, wie ein agentisches KI-System die tatsächlichen Grundlebenshaltungskosten misst und mit dem offiziellen Verbraucherpreisindex vergleicht."
Vorab im Hintergrund: Alle Dienste laufen, http://localhost:8501 ist im Browser geöffnet, die Seitenleiste zeigt "Agent-Service / MCP verbunden".
""",
        "slides": [
            {"kind": "step", "title": "Problem und Idee",
             "left_head": "Die Frage", "left": [
                 "Der VPI misst einen breiten Warenkorb – auch Reisen, Elektronik, Freizeit",
                 "Haushalte spüren vor allem Lebensmittel, Wohnen / Energie und Mobilität",
                 "Wie stark steigen genau diese Grundbedarfskosten?"],
             "right_head": "Unsere Antwort: RealBasket", "right": [
                 "Grundbedarfsindex ECLI aus 5 Kategorien, Basis 11/2024 = 100",
                 "Vergleich mit dem offiziellen VPI und Erklärung der Abweichung",
                 "Nur echte Daten aus Referenz-PDFs (Destatis EVS 2023 + VPI)",
                 "KI-Agent beantwortet Fragen – Zahlen kommen nur aus deterministischem Code"],
             "bar": "Eine Abweichung zum VPI heißt nicht, dass der VPI falsch ist – die Warenkörbe sind verschieden.",
             "notes": """
Zeit: 0:30.
Kernbotschaft: Der VPI ist korrekt, misst aber einen anderen, breiteren Warenkorb.
"Viele Menschen haben das Gefühl, dass die Inflation höher ist als die offizielle Zahl – weil sie vor allem Grundbedarf wahrnehmen: Lebensmittel, Miete, Energie, Mobilität."
"RealBasket baut genau dafür einen eigenen Index – den ECLI, Essential Living Cost Index – mit fünf Kategorien."
"Wichtig: keine erfundenen Demo-Daten. Alle Werte stammen aus Referenz-PDFs auf Basis von Destatis-Daten und werden beim Einlesen 11-fach geprüft."
"""},
            {"kind": "arch", "title": "Architektur: vier Dienste mit Docker Compose",
             "s2_side_head": "Auf einen Blick", "s2_side": [
                 "UI (Streamlit :8501) spricht nur mit der Agent-API",
                 "Agent-API (FastAPI :8002): Strands-Agent + LLM, Zahlen-Guardrail",
                 "MCP-Server (:8001): Rechenkern, SQLite mit Quelle und Seite",
                 "Weaviate (:8080): Vektorsuche in den PDF-Texten",
                 "Zahlen nie aus RAG oder LLM – nur aus dem Rechenkern"],
             "notes": """
Zeit: 1:00. Auf das Diagramm zeigen, von links nach rechts.
"Die App besteht aus vier Diensten. Ganz links die Streamlit-Oberfläche. Sie greift nie direkt auf Daten zu, sondern ruft ausschließlich die Agent-API auf."
"Die Agent-API enthält einen Strands-Agenten mit Azure OpenAI. Für feste Dashboard-Abfragen leitet sie Anfragen über eine Allow-List direkt an den MCP-Server weiter – ohne LLM."
"Der MCP-Server ist das Herzstück: Er stellt die Tools bereit – Index-Berechnung, VPI-Vergleich, Einflussfaktoren – und liest die Werte aus einer SQLite-Datenbank, in der zu jedem Wert Datei und Seite gespeichert sind."
"Weaviate ist unsere Vektordatenbank. Dort liegen nur die Texte der PDFs, also Methodenhinweise. Zahlen kommen nie aus der Textsuche."
"Grundsatz: Der Agent wählt die Tools und formuliert die Antwort, die Zahlen entstehen nur im deterministischen Code."
"""},
            {"kind": "startup", "hidden": True, "title": "Start der Demo: fünf PowerShell-Fenster",
             "windows": [
                 ("Fenster 1", "Weaviate :8080", ["wsl --shutdown", "podman run im WSL-VM", "Image von mirror.gcr.io", "Fenster offen lassen"]),
                 ("Fenster 2", "MCP-Server :8001", [".env laden", "storage --mode sql", "storage --mode vector", "real-basket-mcp"]),
                 ("Fenster 3", "Agent-API :8002", [".env laden", "uvicorn agent_service.api:app", "Port 8002"]),
                 ("Fenster 4", "UI :8501", ["streamlit run src/real_basket/ui/app.py"]),
                 ("Fenster 5", "Prüfung", ["/health → status ok", "search_documents → 200", "localhost:8501 öffnen"]),
             ],
             "tip": "Alle Befehle stehen im README, Abschnitt \"Start for the presentation\".",
             "bar": "Reihenfolge einhalten: Weaviate → MCP → Agent-API → UI → Prüfung.",
             "notes": """
AUSGEBLENDETE FOLIE – wird in der Bildschirmpräsentation nicht gezeigt (nur als Spickzettel für den Start vor dem Vortrag).
Falls etwas hakt:
- "Agent API not reachable": Fenster 3 läuft nicht.
- "machine not in running state": wsl --shutdown, Fenster 1 neu starten.
- PDF-Suche schlägt fehl: Weaviate prüfen, storage --mode vector erneut ausführen.
"""},
            {"kind": "step", "title": "Live-Demo 1 · Dashboard: ECLI gegenüber VPI und Einflussfaktoren",
             "kpis": [("2,93 %", "ECLI ggü. Vorjahr (10/2026)"), ("2,83 %", "VPI ggü. Vorjahr"),
                      ("+0,11 PP", "Abweichung"), ("Mobilität", "Größter Einflussfaktor")],
             "left_head": "So geht's in der App", "left": [
                 "localhost:8501 – auf die vier Kennzahlen der Kopfzeile zeigen",
                 "Tab \"Index vs. VPI\": beide Verläufe, Basis 11/2024 = 100",
                 "Tab \"Einflussfaktoren\": Beitrag je Kategorie in PP",
                 "Expander \"Quelle und Datenprüfungen\": 11 Prüfungen"],
             "right_head": "Was wir zeigen", "right": [
                 "Alle Werte per MCP aus dem Rechenkern – kein LLM",
                 "Echte Daten 11/2024 – 10/2026, keine Demo-Daten",
                 "Beiträge ergeben in Summe genau die Abweichung",
                 "Datenprüfungen: Summen, Lücken, Jahresraten nachgerechnet"],
             "bar": "Grundbedarf steigt um 0,11 Prozentpunkte stärker als der VPI – vollständig erklärt nach Kategorien.",
             "notes": """
Zeit: 1:15.
"Das ist die Startseite. Oben die vier wichtigsten Kennzahlen: Der ECLI ist im Oktober 2026 gegenüber dem Vorjahr um 2,93 Prozent gestiegen, der offizielle VPI um 2,83 Prozent. Die Abweichung beträgt plus 0,11 Prozentpunkte, größter Einflussfaktor ist Verkehr / Mobilität."
"Diese Zahlen hat kein Sprachmodell erzeugt. Sie kommen aus dem deterministischen Rechenkern auf dem MCP-Server."
Tab "Index vs. VPI" kurz zeigen: "Beide Indizes mit gemeinsamer Basis November 2024 gleich 100, rechts die Jahresveränderung."
Tab "Einflussfaktoren": "Warum weichen die Indizes ab? Dieses Diagramm zeigt den Beitrag jeder Kategorie in Prozentpunkten. Die Beiträge addieren sich exakt zur Gesamtabweichung – reine Mathematik, kein LLM."
Expander aufklappen: "Hier die elf Prüfungen beim Einlesen der PDFs: Summen, Lücken, und die gedruckten Jahresraten werden nachgerechnet. Nur wenn alles passt, zeigen wir Zahlen an."
"""},
            {"kind": "step", "title": "Live-Demo 2 · PDF-Suche (Weaviate) und Chat mit dem MCP-Agenten",
             "left_head": "So geht's in der App", "left": [
                 "Tab \"PDF-Suche (Weaviate)\": \"Ist Wohnen / Energie die Nettokaltmiete?\"",
                 "\"Weaviate durchsuchen\" – Treffer mit Datei und Seite zeigen",
                 "Tab \"MCP-Agent\": \"Wie hat sich der ECLI gegenüber dem VPI entwickelt?\"",
                 "Unter der Antwort: verwendete MCP-Tools zeigen"],
             "right_head": "Was wir zeigen", "right": [
                 "RAG über Methodenhinweise – Embeddings via Azure OpenAI in Weaviate",
                 "Jede Textstelle mit Quelle; Kennzahlen nie aus der Textsuche",
                 "Strands-Agent wählt selbst die passenden MCP-Tools",
                 "Zahlen-Guardrail: unbelegte Zahlen werden sichtbar markiert"],
             "bar": "Der Agent entscheidet, welche Tools nötig sind – der Code entscheidet die Zahlen.",
             "notes": """
Zeit: 1:30. Erst die Chatfrage abschicken, dann während der Wartezeit die PDF-Suche erklären, wenn es knapp wird.
PDF-Suche: "Zahlen allein reichen nicht – man muss verstehen, wie sie berechnet werden." Frage eintippen: "Ist Wohnen / Energie die Nettokaltmiete?" und "Weaviate durchsuchen" klicken.
"Die Frage wird mit Azure OpenAI in einen Vektor umgewandelt, Weaviate findet die ähnlichsten Textstellen. Jede Fundstelle zeigt Datei und Seite – man kann es im Original nachlesen."
Chat: Fragen "Wie hat sich der ECLI gegenüber dem VPI entwickelt?"
"Der Agent entscheidet selbst, welche Tools er braucht. Er hat keinen direkten Datenzugriff – alles läuft über den MCP-Server."
Antwort zeigen (erwartet: ECLI 2,93 %, VPI 2,83 %, Abweichung +0,11 PP): "Unter der Antwort sehen Sie, welche MCP-Tools aufgerufen wurden."
"Unser Guardrail prüft jede Zahl in der Antwort gegen die Tool-Ergebnisse. Erfindet das Modell eine Zahl, wird sie als nicht belegt markiert."
"""},
            {"kind": "step", "title": "Live-Demo 3 · Monitoring: den Weg jeder Anfrage sehen",
             "left_head": "So geht's in der App", "left": [
                 "Tab \"Monitoring\" öffnen",
                 "Im Auswahlfeld die letzte Chatfrage wählen",
                 "Graph mit nummerierten Schritten erklären"],
             "right_head": "Was wir zeigen", "right": [
                 "Pfad durch UI → Agent → MCP → Weaviate / LLM",
                 "Nummerierte Kanten = Reihenfolge, mit Dauer und Status",
                 "Nur für diese Browser-Sitzung, nichts wird gespeichert"],
             "bar": "Nachvollziehbarkeit: Jede Interaktion wird als Pfad durch die Architektur sichtbar.",
             "notes": """
Zeit: 0:30.
"Agentische Systeme sind oft eine Blackbox. Unser Monitoring-Tab macht sichtbar, was passiert."
Letzte Chatfrage auswählen: "Der Graph zeigt den genauen Weg der Anfrage: von der Oberfläche zur Agent-API, zum LLM, dann die Tool-Aufrufe über den MCP-Server. Die nummerierten Kanten zeigen die Reihenfolge, die Tabelle darunter Dauer und Status jedes Schritts."
Optional, nur wenn Zeit bleibt: Seitenleiste "Auswertungsberichte generieren" – PDF-Berichte mit einem Klick.
"""},
            {"kind": "code", "title": "Aus dem Quellcode: Tools, Agent-API und Zahlen-Guardrail",
             "captions": ["MCP-Tool", "Agent-API /chat (gekürzt)", "Zahlen-Guardrail"],
             "side_head": "Warum das wichtig ist", "side": [
                 "Ein MCP-Tool ist eine Python-Funktion mit @mcp.tool() – der Agent sieht Name und Docstring",
                 "Die Berechnung bleibt im deterministischen Rechenkern",
                 "Nach jeder Chat-Antwort prüft die Agent-API alle Zahlen gegen die Tool-Ergebnisse",
                 "Unbelegte Zahlen gehen als \"unverified\" an die UI und werden markiert"],
             "bar": "Wenige Zeilen Code trennen sauber: LLM formuliert, Code rechnet, Guardrail prüft.",
             "notes": """
Zeit: 0:30.
"Ein kurzer Blick in den Code. Oben ein MCP-Tool: eine normale Python-Funktion mit dem Dekorator @mcp.tool(). Der Agent sieht nur Name und Beschreibung und entscheidet, wann er sie aufruft – die Berechnung selbst passiert im deterministischen Rechenkern."
"In der Mitte der Chat-Endpunkt der Agent-API: Nach der Antwort des Agenten läuft der Guardrail – nur hier sind alle Tool-Ergebnisse der Runde bekannt."
"Unten der Guardrail selbst: Jede Zahl der Antwort muss in einem Tool-Ergebnis oder in der Frage vorkommen. Sonst wird sie als unbelegt gemeldet."
"""},
            {"kind": "results", "title": "Zusammenfassung und nächste Schritte",
             "kpis": [("2,93 % vs. 2,83 %", "ECLI vs. VPI – Abweichung +0,11 PP"),
                      ("130", "automatisierte Tests grün"),
                      ("0", "Kennzahlen vom LLM – alle aus dem Rechenkern")],
             "done_head": "Was RealBasket zeigt", "done": [
                 "Grundbedarfsinflation auf echten Daten, erklärt nach Kategorien",
                 "Agent mit MCP-Tools: wählt selbst, rechnet nie selbst",
                 "Zahlen-Guardrail gegen erfundene Werte",
                 "RAG mit Weaviate: Erklärungen mit Datei und Seite",
                 "Monitoring: jede Anfrage als Pfad durch die Architektur"],
             "next_head": "Nächste Schritte", "next": [
                 "Weitere Datenquellen anbinden (z. B. Destatis GENESIS)",
                 "Chat-Kontext: Tool-Ergebnisse früherer Fragen behalten",
                 "Agent-API und MCP absichern (Authentisierung, TLS)",
                 "CI mit ruff + pytest, Docker-Build mit poetry.lock",
                 "Vielen Dank – Fragen?"],
             "notes": """
Zeit: 0:30.
"Zusammengefasst: RealBasket misst die Inflation der Grundbedarfskosten auf echten Daten und erklärt die Abweichung zum VPI nach Kategorien. Der Agent wählt die Tools selbst, rechnet aber nie selbst. Der Guardrail prüft jede Zahl, RAG liefert Erklärungen mit Quelle, und das Monitoring macht jeden Schritt sichtbar – abgesichert durch 130 automatisierte Tests."
"Vielen Dank – wir freuen uns auf Ihre Fragen."
Mögliche Fragen:
- Warum nicht das LLM rechnen lassen? → Nachvollziehbarkeit und Korrektheit; LLMs halluzinieren Zahlen.
- Woher kommen die Daten? → Referenz-PDFs auf Basis Destatis EVS 2023 + VPI, 11/2024 – 10/2026.
- Warum MCP? → Standardisierte Tool-Schnittstelle; Agent und Daten sind entkoppelt und einzeln deploybar.
"""},
        ],
    },
    "en": {
        "file": "RealBasket_Hackathon_Demo_EN.pptx",
        "cover_title": "RealBasket",
        "cover_subtitle": "Hackathon demo – What does living really cost?",
        "cover_notes": """
Time: 0:15 (total 6:00 – plan: title 0:15 · problem 0:30 · architecture 1:00 · demo dashboard 1:15 · demo search + chat 1:30 · monitoring 0:30 · code 0:30 · summary 0:30).
"Hello everyone. We are team RealBasket. We will show you live how an agentic AI system measures real essential living costs and compares them with the official Consumer Price Index."
Beforehand: all services are running, http://localhost:8501 is open in the browser, and the sidebar shows "Agent-Service / MCP verbunden" (connected).
""",
        "slides": [
            {"kind": "step", "title": "Problem and idea",
             "left_head": "The question", "left": [
                 "The CPI measures a broad basket – including travel, electronics, leisure",
                 "Households mostly feel food, housing / energy and mobility",
                 "How fast do exactly these essential costs rise?"],
             "right_head": "Our answer: RealBasket", "right": [
                 "Essential index ECLI from 5 categories, base 11/2024 = 100",
                 "Comparison with the official CPI and explanation of the gap",
                 "Real data only, from reference PDFs (Destatis EVS 2023 + CPI)",
                 "AI agent answers questions – figures only from deterministic code"],
             "bar": "A gap to the CPI does not mean the CPI is wrong – the baskets are different.",
             "notes": """
Time: 0:30.
Key message: the CPI is correct, but it measures a different, broader basket.
"Many people feel that inflation is higher than the official figure – because they mainly notice essential spending: food, rent, energy, mobility."
"RealBasket builds its own index for exactly that – the ECLI, Essential Living Cost Index – with five categories."
"Important: no made-up demo data. All values come from reference PDFs based on Destatis data and are checked 11 times on import."
"""},
            {"kind": "arch", "title": "Architecture: four services with Docker Compose",
             "s2_side_head": "At a glance", "s2_side": [
                 "UI (Streamlit :8501) talks only to the agent API",
                 "Agent API (FastAPI :8002): Strands agent + LLM, number guardrail",
                 "MCP server (:8001): calculation core, SQLite with source and page",
                 "Weaviate (:8080): vector search over the PDF text",
                 "Figures never from RAG or the LLM – only from the core"],
             "notes": """
Time: 1:00. Point at the diagram, left to right.
"The app consists of four services. On the left, the Streamlit UI. It never reads data directly; it only calls the agent API."
"The agent API contains a Strands agent with Azure OpenAI. For fixed dashboard queries it forwards requests through an allow-list straight to the MCP server – no LLM involved."
"The MCP server is the heart of the system: it provides the tools – index calculation, CPI comparison, deviation drivers – and reads values from a SQLite database that stores file and page for every value."
"Weaviate is our vector database. It only holds the text of the PDFs, i.e. method notes. Figures never come from text search."
"Principle: the agent picks the tools and writes the answer; the figures are produced by deterministic code only."
"""},
            {"kind": "step", "title": "Live demo 1 · Dashboard: ECLI vs. CPI and deviation drivers",
             "kpis": [("2.93 %", "ECLI year on year (10/2026)"), ("2.83 %", "CPI (VPI) year on year"),
                      ("+0.11 PP", "Deviation"), ("Mobility", "Biggest driver")],
             "left_head": "Click path in the app", "left": [
                 "localhost:8501 – point at the four KPIs in the header",
                 "Tab \"Index vs. VPI\": both series, base 11/2024 = 100",
                 "Tab \"Einflussfaktoren\" (drivers): contribution per category in PP",
                 "Expand \"Quelle und Datenprüfungen\": the 11 data checks"],
             "right_head": "What we show", "right": [
                 "All values come from the calculation core via MCP – no LLM",
                 "Real data 11/2024 – 10/2026, no demo data",
                 "Contributions add up exactly to the deviation",
                 "Data checks: sums, gaps, yearly rates recomputed"],
             "bar": "Essential costs rise 0.11 percentage points faster than the CPI – fully explained by category.",
             "notes": """
Time: 1:15. The UI is in German – translate labels as you go.
"This is the start page. At the top, the four key figures: the ECLI rose 2.93 percent year on year in October 2026, the official CPI 2.83 percent. The deviation is plus 0.11 percentage points; the biggest driver is transport / mobility."
"No language model produced these numbers. They come from the deterministic calculation core on the MCP server."
Tab "Index vs. VPI" briefly: "Both indices with a common base, November 2024 equals 100; on the right the year-on-year change."
Tab "Einflussfaktoren": "Why do the indices differ? This chart shows each category's contribution in percentage points. The contributions add up exactly to the total deviation – plain maths, no LLM."
Expand the section: "Here are the eleven checks that run when the PDFs are imported: sums, gaps, and the printed yearly rates are recomputed. We only show numbers if everything matches."
"""},
            {"kind": "step", "title": "Live demo 2 · PDF search (Weaviate) and chat with the MCP agent",
             "left_head": "Click path in the app", "left": [
                 "Tab \"PDF-Suche (Weaviate)\": \"Ist Wohnen / Energie die Nettokaltmiete?\"",
                 "Click \"Weaviate durchsuchen\" – show hits with file and page",
                 "Tab \"MCP-Agent\": \"Wie hat sich der ECLI gegenüber dem VPI entwickelt?\"",
                 "Below the answer: show the MCP tools used"],
             "right_head": "What we show", "right": [
                 "RAG over method notes – Azure OpenAI embeddings in Weaviate",
                 "Every passage with its source; figures never from text search",
                 "Strands agent picks the right MCP tools itself",
                 "Number guardrail: unbacked figures are flagged visibly"],
             "bar": "The agent decides which tools are needed – the code decides the figures.",
             "notes": """
Time: 1:30. If time is short, send the chat question first and explain the PDF search while the agent is working.
PDF search: "Numbers alone are not enough – you also need to understand how they are calculated." Type "Ist Wohnen / Energie die Nettokaltmiete?" (Is housing / energy the net cold rent?) and click "Weaviate durchsuchen".
"The question is turned into a vector with Azure OpenAI, and Weaviate finds the most similar passages. Every hit shows file and page – you can check it in the original."
Chat: ask "Wie hat sich der ECLI gegenüber dem VPI entwickelt?" (How has the ECLI developed compared with the CPI?)
"The agent decides by itself which tools it needs. It has no direct data access – everything goes through the MCP server."
Show the answer (expected: ECLI 2.93 %, CPI 2.83 %, deviation +0.11 PP): "Below the answer you see which MCP tools were called."
"Our guardrail checks every number in the answer against the tool results. If the model invents a number, it is flagged as not backed."
"""},
            {"kind": "step", "title": "Live demo 3 · Monitoring: see the path of every request",
             "left_head": "Click path in the app", "left": [
                 "Open the tab \"Monitoring\"",
                 "Select the latest chat question in the dropdown",
                 "Explain the graph with numbered steps"],
             "right_head": "What we show", "right": [
                 "Path through UI → agent → MCP → Weaviate / LLM",
                 "Numbered edges = order of the steps, with duration and status",
                 "Only for this browser session, nothing is stored"],
             "bar": "Traceability: every interaction becomes visible as a path through the architecture.",
             "notes": """
Time: 0:30.
"Agentic systems are often a black box. Our Monitoring tab shows what happens."
Select the latest chat question: "The graph shows the exact path of the request: from the UI to the agent API, to the LLM, then the tool calls through the MCP server. The numbered edges show the order; the table below shows duration and status of every step."
Optional, only if time is left: sidebar "Auswertungsberichte generieren" – PDF reports in one click.
"""},
            {"kind": "code", "title": "From the source code: tools, agent API and number guardrail",
             "captions": ["MCP tool", "Agent API /chat (shortened)", "Number guardrail"],
             "side_head": "Why it matters", "side": [
                 "An MCP tool is a Python function with @mcp.tool() – the agent sees its name and docstring",
                 "The calculation stays in the deterministic core",
                 "After every chat answer the agent API checks all figures against the tool results",
                 "Unbacked figures go to the UI as \"unverified\" and are flagged"],
             "bar": "A few lines of code keep it clean: the LLM writes, the code calculates, the guardrail checks.",
             "notes": """
Time: 0:30.
"A quick look at the code. At the top, an MCP tool: a plain Python function with the @mcp.tool() decorator. The agent only sees the name and description and decides when to call it – the calculation itself happens in the deterministic core."
"In the middle, the chat endpoint of the agent API: after the agent answers, the guardrail runs – only here are all tool results of the turn known."
"At the bottom, the guardrail itself: every number in the answer must appear in a tool result or in the question. Otherwise it is reported as unverified."
"""},
            {"kind": "results", "title": "Summary and next steps",
             "kpis": [("2.93 % vs. 2.83 %", "ECLI vs. CPI – deviation +0.11 PP"),
                      ("130", "automated tests passing"),
                      ("0", "figures from the LLM – all from the calculation core")],
             "done_head": "What RealBasket shows", "done": [
                 "Essential-cost inflation on real data, explained by category",
                 "Agent with MCP tools: picks tools itself, never calculates itself",
                 "Number guardrail against invented values",
                 "RAG with Weaviate: explanations with file and page",
                 "Monitoring: every request as a path through the architecture"],
             "next_head": "Next steps", "next": [
                 "Connect more data sources (e.g. Destatis GENESIS)",
                 "Chat context: keep tool results of earlier questions",
                 "Secure agent API and MCP (authentication, TLS)",
                 "CI with ruff + pytest, Docker build from poetry.lock",
                 "Thank you – questions?"],
             "notes": """
Time: 0:30.
"In summary: RealBasket measures essential-cost inflation on real data and explains the deviation from the CPI by category. The agent picks the tools itself but never calculates itself. The guardrail checks every figure, RAG provides explanations with sources, and monitoring makes every step visible – backed by 130 automated tests."
"Thank you – we look forward to your questions."
Possible questions:
- Why not let the LLM calculate? → Traceability and correctness; LLMs hallucinate numbers.
- Where does the data come from? → Reference PDFs based on Destatis EVS 2023 + CPI, 11/2024 – 10/2026.
- Why MCP? → Standardised tool interface; agent and data are decoupled and deployable separately.
"""},
        ],
    },
}

RENDER = {"arch": deck.architecture, "startup": startup, "results": deck.results, "code": code, "step": step}


def build(lang: str) -> Path:
    t = TEXT[lang]
    prs = Presentation(str(deck.TEMPLATE))
    footer = deck._footer_elements(prs.slides[deck.FOOTER_SOURCE])
    for i in reversed(range(len(prs.slides))):
        if i != deck.COVER_SLIDE:
            deck._drop_slide(prs, i)
    deck.cover(prs.slides[0], t)
    notes(prs.slides[0], t["cover_notes"])
    for s in t["slides"]:
        slide = deck.content_slide(prs, s["title"], footer)
        RENDER[s["kind"]](slide, s)
        notes(slide, s["notes"])
        if s.get("hidden"):
            hide(slide)
    prs.core_properties.title = f"{t['cover_title']} – {t['cover_subtitle']}"
    prs.core_properties.language = "de-DE" if lang == "de" else "en-US"
    out = HERE / t["file"]
    prs.save(str(out))
    return out


if __name__ == "__main__":
    for language in TEXT:
        print("written", build(language))
