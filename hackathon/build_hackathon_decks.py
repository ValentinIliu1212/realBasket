"""Build the RealBasket hackathon demo decks (German + English) with speaker notes.

Run (from the repo root):  poetry run python hackathon/build_hackathon_decks.py
Output (next to this script): RealBasket_Hackathon_Demo_DE.pptx, RealBasket_Hackathon_Demo_EN.pptx

Style: identical to docs/architecture/RealBasket_Docker_Compose_*.pptx - same NTT DATA template, cover, layout
"B_Title Only", footer, colours and drawing helpers (imported from docs/architecture/build_docker_decks.py).
Every slide carries speaker notes so the deck can be read while presenting the live app.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches

HERE = Path(__file__).resolve().parent
ARCH = HERE.parent / "docs" / "architecture" / "build_docker_decks.py"

_spec = importlib.util.spec_from_file_location("build_docker_decks", ARCH)
deck = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(deck)

BLUE, DEEP, NAVY, SKY, GREEN = deck.BLUE, deck.DEEP, deck.NAVY, deck.SKY, deck.GREEN
SLATE, PALE, WHITE = deck.SLATE, deck.PALE, deck.WHITE
box, para = deck.box, deck._para


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


def step(slide, s: dict) -> None:
    """Two columns (click path | what we show) + key-message bar; optional KPI row on top."""
    top = 1.4
    if s.get("kpis"):
        kpi_row(slide, s["kpis"])
        top = 2.6
    body_h = 5.75 - top - 0.5
    for col, (head_key, items_key, color, numbered) in enumerate(
            (("left_head", "left", BLUE, True), ("right_head", "right", GREEN, False))):
        x = 0.41 + col * 6.38
        head = box(slide, x, top, 6.14, 0.45, color)
        head.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        para(head.text_frame, s[head_key], 13, WHITE, True, first=True, space_after=0)
        body = box(slide, x, top + 0.5, 6.14, body_h, PALE)
        for j, item in enumerate(s[items_key]):
            prefix = f"{j + 1}. " if numbered else "• "
            para(body.text_frame, prefix + item, 12, SLATE, first=j == 0, space_after=7)
    bar = box(slide, 0.41, 5.95, 12.52, 0.9, NAVY)
    bar.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    para(bar.text_frame, s["bar"], 13.5, WHITE, True, first=True, align=PP_ALIGN.CENTER, space_after=0)


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
    bar = box(slide, 0.41, 5.95, 12.52, 0.9, NAVY)
    bar.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    para(bar.text_frame, s["bar"], 13.5, WHITE, True, first=True, align=PP_ALIGN.CENTER, space_after=0)


def notes(slide, text: str) -> None:
    slide.notes_slide.notes_text_frame.text = text.strip()


# --- content ------------------------------------------------------------------------------------------------
TEXT = {
    "de": {
        "file": "RealBasket_Hackathon_Demo_DE.pptx",
        "cover_title": "RealBasket",
        "cover_subtitle": "Hackathon-Demo – Was kostet das Leben wirklich?",
        "cover_notes": """
Begrüßung (ca. 30 Sekunden).
"Guten Tag zusammen. Wir sind das Team RealBasket. In den nächsten Minuten zeigen wir Ihnen live, wie ein agentisches KI-System die tatsächlichen Grundlebenshaltungskosten misst und mit dem offiziellen Verbraucherpreisindex vergleicht."
Vorab im Hintergrund: Alle fünf PowerShell-Fenster laufen, http://localhost:8501 ist im Browser geöffnet, die Seitenleiste zeigt "Agent-Service / MCP verbunden".
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
Kernbotschaft: Der VPI ist korrekt, misst aber einen anderen, breiteren Warenkorb.
"Viele Menschen haben das Gefühl, dass die Inflation höher ist als die offizielle Zahl. Das liegt oft daran, dass sie vor allem Ausgaben für Grundbedarf wahrnehmen: Lebensmittel, Miete, Energie, Mobilität."
"RealBasket baut genau dafür einen eigenen Index – den ECLI, Essential Living Cost Index – mit fünf Kategorien: Lebensmittel, Wohnen / Energie, Verkehr / Mobilität, Gesundheit und Kommunikation."
"Wichtig: Wir verwenden keine erfundenen Demo-Daten. Alle Werte stammen aus Referenz-PDFs auf Basis von Destatis-Daten und werden beim Einlesen 11-fach geprüft."
Übergang: "Schauen wir uns zuerst an, wie das System aufgebaut ist."
"""},
            {"kind": "arch", "title": "Architektur: vier Dienste mit Docker Compose",
             "s2_side_head": "Auf einen Blick", "s2_side": [
                 "UI (Streamlit :8501) spricht nur mit der Agent-API",
                 "Agent-API (FastAPI :8002): Strands-Agent + LLM, Zahlen-Guardrail",
                 "MCP-Server (:8001): Rechenkern, SQLite mit Quelle und Seite",
                 "Weaviate (:8080): Vektorsuche in den PDF-Texten",
                 "Zahlen nie aus RAG oder LLM – nur aus dem Rechenkern"],
             "notes": """
Zeit: ca. 1 Minute. Auf das Diagramm zeigen, von links nach rechts.
"Die App besteht aus vier Diensten. Ganz links die Streamlit-Oberfläche. Sie greift nie direkt auf Daten zu, sondern ruft ausschließlich die Agent-API auf."
"Die Agent-API enthält einen Strands-Agenten mit Azure OpenAI. Für feste Dashboard-Abfragen leitet sie Anfragen über eine Allow-List direkt an den MCP-Server weiter – ohne LLM."
"Der MCP-Server ist das Herzstück: Er stellt die Tools bereit – Index-Berechnung, VPI-Vergleich, Einflussfaktoren – und liest die Werte aus einer SQLite-Datenbank, in der zu jedem Wert Datei und Seite gespeichert sind."
"Weaviate ist unsere Vektordatenbank. Dort liegen nur die Texte der PDFs, also Methodenhinweise. Zahlen kommen nie aus der Textsuche."
"Grundsatz: Der Agent wählt die Tools und formuliert die Antwort, die Zahlen entstehen nur im deterministischen Code."
"""},
            {"kind": "startup", "title": "Start der Demo: fünf PowerShell-Fenster",
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
Diese Folie nur kurz zeigen oder überspringen, wenn die Zeit knapp ist – alles läuft bereits.
"Für die Demo laufen die vier Dienste lokal: Weaviate in Podman, die drei Python-Dienste mit Poetry. In Produktion startet dasselbe mit einem einzigen docker compose up."
Falls etwas hakt:
- "Agent API not reachable": Fenster 3 läuft nicht.
- "machine not in running state": wsl --shutdown, Fenster 1 neu starten.
- PDF-Suche schlägt fehl: Weaviate prüfen, storage --mode vector erneut ausführen.
Übergang: "Gehen wir jetzt in die App."
"""},
            {"kind": "step", "title": "Schritt 1 · Kopfzeile: ECLI gegenüber VPI",
             "kpis": [("2,93 %", "ECLI ggü. Vorjahr (10/2026)"), ("2,83 %", "VPI ggü. Vorjahr"),
                      ("+0,11 PP", "Abweichung"), ("Mobilität", "Größter Einflussfaktor")],
             "left_head": "So geht's in der App", "left": [
                 "Browser: http://localhost:8501",
                 "Seitenleiste: \"Agent-Service / MCP verbunden\" zeigen",
                 "Auf die vier Kennzahlen in der Kopfzeile zeigen",
                 "Info-Kasten \"Datenbasis\" vorlesen"],
             "right_head": "Was wir zeigen", "right": [
                 "Alle vier Werte kommen per MCP aus dem Rechenkern",
                 "Echte Daten 11/2024 – 10/2026, keine Demo-Daten",
                 "Ohne Referenz-PDFs zeigt die App einen Fehler statt Zahlen"],
             "bar": "Auf einen Blick: Grundbedarf steigt um 0,11 Prozentpunkte stärker als der VPI.",
             "notes": """
Zeit: ca. 1 Minute.
"Das ist die Startseite. Oben sehen Sie die vier wichtigsten Kennzahlen."
"Der ECLI – unser Grundbedarfsindex – ist im Oktober 2026 gegenüber dem Vorjahr um 2,93 Prozent gestiegen. Der offizielle VPI um 2,83 Prozent."
"Die Abweichung beträgt also plus 0,11 Prozentpunkte. Der größte Einflussfaktor ist Verkehr / Mobilität."
Auf die Seitenleiste zeigen: "Links sehen Sie, dass die Oberfläche mit dem Agent-Service und dem MCP-Server verbunden ist, und welche Datenbasis verwendet wird."
"Diese Zahlen hat kein Sprachmodell erzeugt. Sie kommen aus dem deterministischen Rechenkern auf dem MCP-Server."
"""},
            {"kind": "step", "title": "Schritt 2 · Tab \"Index vs. VPI\"",
             "left_head": "So geht's in der App", "left": [
                 "Tab \"Index vs. VPI\" öffnen",
                 "Linkes Diagramm: Indexverlauf, Basis 11/2024 = 100",
                 "Rechtes Diagramm: jährliche Veränderung in %",
                 "Nach unten scrollen: Grundbedarfskosten in Euro"],
             "right_head": "Was wir zeigen", "right": [
                 "ECLI und VPI im direkten Zeitvergleich",
                 "Monatliche Ausgaben des Referenzwarenkorbs je Kategorie (€/Monat)",
                 "Tabelle mit allen Monatswerten zum Nachprüfen"],
             "bar": "Transparenz: jeder Punkt im Diagramm ist ein belegter Wert aus den Referenz-PDFs.",
             "notes": """
Zeit: ca. 1 Minute.
"Im ersten Tab sehen wir den Verlauf. Links beide Indizes mit gemeinsamer Basis November 2024 gleich 100."
"Rechts die Jahresveränderung – also die Inflationsrate – von ECLI und VPI im Vergleich."
Nach unten scrollen: "Hier sehen Sie die modellierten Grundbedarfskosten in Euro pro Monat, aufgeteilt nach Kategorien. Wohnen / Energie ist erwartungsgemäß der größte Block."
"Die Tabelle darunter enthält alle Werte – nichts ist versteckt."
"""},
            {"kind": "step", "title": "Schritt 3 · Tab \"Einflussfaktoren\"",
             "left_head": "So geht's in der App", "left": [
                 "Tab \"Einflussfaktoren\" öffnen",
                 "Balkendiagramm: Beitrag jeder Kategorie in Prozentpunkten",
                 "Expander \"Quelle und Datenprüfungen\" aufklappen",
                 "Die 11 Prüfungen und die PDF-Quellen zeigen"],
             "right_head": "Was wir zeigen", "right": [
                 "Warum weicht der ECLI vom VPI ab? – exakte Beiträge je Kategorie",
                 "Die Beiträge ergeben in Summe genau die Abweichung",
                 "11 Datenprüfungen: Summen, Lücken, Jahresraten nachgerechnet"],
             "bar": "Erklärbarkeit: Die Abweichung wird vollständig auf Kategorien zurückgeführt.",
             "notes": """
Zeit: ca. 1 Minute.
"Die spannende Frage ist: Warum weichen die beiden Indizes voneinander ab?"
"Dieses Diagramm zeigt den Beitrag jeder Kategorie zur Abweichung in Prozentpunkten. Die Beiträge addieren sich exakt zur Gesamtabweichung – das ist reine Mathematik im Rechenkern, kein LLM."
Expander aufklappen: "Hier sehen Sie die elf Prüfungen, die beim Einlesen der PDFs laufen: Summen, Lücken, und die im PDF gedruckten Jahresraten werden von unserem Rechenkern nachgerechnet. Nur wenn alles passt, zeigen wir Zahlen an."
"""},
            {"kind": "step", "title": "Schritt 4 · Tab \"Stadtmieten\"",
             "left_head": "So geht's in der App", "left": [
                 "Tab \"Stadtmieten\" öffnen",
                 "Tabelle der 15 größten Städte zeigen",
                 "Balkendiagramm \"Miete Oktober 2026 in €/m²\"",
                 "Nach unten: \"Bundesländer – Datenabdeckung\""],
             "right_head": "Was wir zeigen", "right": [
                 "Echte Angebotskaltmieten Januar vs. Oktober 2026",
                 "Inklusive Beispiel: 75-m²-Wohnung",
                 "Keine Landesmieten in den Quellen – wir schätzen nicht",
                 "Stattdessen: welche Städte je Bundesland belegt sind"],
             "bar": "Ehrlich mit Datenlücken: \"nicht in den Referenzdaten\" statt geschätzter Zahlen.",
             "notes": """
Zeit: ca. 1 Minute.
"Wohnen ist für viele der größte Kostenblock. Hier sehen Sie die Angebotskaltmieten der 15 größten Städte Deutschlands, Januar gegenüber Oktober 2026, auch umgerechnet auf eine 75-Quadratmeter-Wohnung."
"Wichtig ist uns die Ehrlichkeit bei Datenlücken: Die Quellen enthalten keine Mieten pro Bundesland. Statt etwas zu schätzen, zeigen wir, welche Städte je Bundesland belegt sind – und sagen klar, wo keine Daten vorliegen."
"""},
            {"kind": "step", "title": "Schritt 5 · Tab \"PDF-Suche (Weaviate)\"",
             "left_head": "So geht's in der App", "left": [
                 "Tab \"PDF-Suche (Weaviate)\" öffnen",
                 "Eingeben: \"Ist Wohnen / Energie die Nettokaltmiete?\"",
                 "Button \"Weaviate durchsuchen\" klicken",
                 "Treffer mit Datei und Seite zeigen"],
             "right_head": "Was wir zeigen", "right": [
                 "Semantische Suche (RAG) über Methodenhinweise der PDFs",
                 "Embeddings über Azure OpenAI, gespeichert in Weaviate",
                 "Jede Textstelle mit Quelle: Datei · Seite",
                 "Nur Kontext – Kennzahlen kommen nie aus der Textsuche"],
             "bar": "RAG liefert Erklärungen mit Quellenangabe – die Zahlen bleiben im Rechenkern.",
             "notes": """
Zeit: ca. 1 Minute.
"Zahlen allein reichen nicht – man muss auch verstehen, wie sie berechnet werden. Dafür haben wir eine semantische Suche über die Methodenhinweise der Referenz-PDFs."
Frage eintippen: "Ist Wohnen / Energie die Nettokaltmiete?" und auf "Weaviate durchsuchen" klicken.
"Die Suche läuft über den MCP-Server: Die Frage wird mit Azure OpenAI in einen Vektor umgewandelt, Weaviate findet die ähnlichsten Textstellen. Jede Fundstelle zeigt Datei und Seite – man kann es im Original nachlesen."
Alternative Frage: "Wie wird Wohnen / Energie berechnet?"
"""},
            {"kind": "step", "title": "Schritt 6 · Tab \"MCP-Agent\": Chat mit RealBasket",
             "left_head": "So geht's in der App", "left": [
                 "Tab \"MCP-Agent\" öffnen",
                 "Fragen: \"Wie hat sich der ECLI gegenüber dem VPI entwickelt?\"",
                 "Unter der Antwort: verwendete MCP-Tools zeigen",
                 "Nachfrage: \"Warum weicht der ECLI vom VPI ab?\""],
             "right_head": "Was wir zeigen", "right": [
                 "Strands-Agent wählt selbst die passenden MCP-Tools",
                 "Antwort immer auf Deutsch, Zahlen aus Tool-Ergebnissen",
                 "Zahlen-Guardrail: jede Zahl wird gegen die Tools geprüft",
                 "Unbelegte Zahlen werden sichtbar markiert"],
             "bar": "Der Agent entscheidet, welche Tools nötig sind – der Code entscheidet die Zahlen.",
             "notes": """
Zeit: ca. 1,5 Minuten. Antwort dauert einige Sekunden – währenddessen erklären.
"Jetzt der agentische Teil. Ich stelle eine Frage in natürlicher Sprache."
Fragen: "Wie hat sich der ECLI gegenüber dem VPI entwickelt?"
"Der Agent entscheidet selbst, welche Tools er braucht. Er hat keinen direkten Datenzugriff – alles läuft über den MCP-Server."
Antwort zeigen (erwartet: ECLI 2,93 %, VPI 2,83 %, Abweichung +0,11 PP): "Unter der Antwort sehen Sie, welche MCP-Tools aufgerufen wurden."
"Und hier kommt unser Guardrail ins Spiel: Der Agent-Service prüft jede Zahl in der Antwort gegen die Tool-Ergebnisse. Erfindet das Modell eine Zahl, wird sie als nicht belegt markiert."
Nachfrage: "Warum weicht der ECLI vom VPI ab?" – der Agent bohrt in die Einflussfaktoren.
"""},
            {"kind": "step", "title": "Schritt 7 · Tab \"Monitoring\": den Weg jeder Anfrage sehen",
             "left_head": "So geht's in der App", "left": [
                 "Tab \"Monitoring\" öffnen",
                 "Kennzahlen: Vorgänge, Chatfragen, MCP-Aufrufe, Warnungen",
                 "Im Auswahlfeld die letzte Chatfrage wählen",
                 "Graph mit nummerierten Schritten erklären",
                 "Expander \"Verlauf\" aufklappen"],
             "right_head": "Was wir zeigen", "right": [
                 "Pfad durch UI → Agent → MCP → Weaviate / LLM",
                 "Nummerierte Kanten = Reihenfolge der Schritte",
                 "Dauer und Status jedes Vorgangs",
                 "Nur für diese Browser-Sitzung, nichts wird gespeichert"],
             "bar": "Nachvollziehbarkeit: Jede Interaktion wird als Pfad durch die Architektur sichtbar.",
             "notes": """
Zeit: ca. 1 Minute.
"Agentische Systeme sind oft eine Blackbox. Unser Monitoring-Tab macht sichtbar, was passiert."
"Oben sehen Sie, wie viele Vorgänge, Chatfragen und MCP-Tool-Aufrufe es in dieser Sitzung gab."
Letzte Chatfrage auswählen: "Der Graph zeigt den genauen Weg der Anfrage: von der Oberfläche zur Agent-API, zum LLM, dann die Tool-Aufrufe über den MCP-Server. Die nummerierten Kanten zeigen die Reihenfolge."
"Die Tabelle darunter listet jeden Schritt mit Dauer und Status. Der Verlauf gilt nur für diese Browser-Sitzung und wird nicht gespeichert."
"""},
            {"kind": "step", "title": "Schritt 8 · Seitenleiste: PDF-Berichte",
             "left_head": "So geht's in der App", "left": [
                 "Seitenleiste: Bereich \"Referenzberichte\"",
                 "\"Laden: Lebenshaltungskosten_2026 …\" klicken und herunterladen",
                 "\"Auswertungsberichte generieren\" klicken",
                 "Einen erzeugten Bericht herunterladen und kurz öffnen"],
             "right_head": "Was wir zeigen", "right": [
                 "Die Original-Referenz-PDFs (Quelle aller Zahlen)",
                 "Generierte Berichte: je Jahr, Stadtmieten, VPI-Bericht",
                 "Auf Deutsch, in Euro, aus denselben geprüften Daten"],
             "bar": "Vom Dashboard zum teilbaren Bericht – mit einem Klick.",
             "notes": """
Zeit: ca. 45 Sekunden.
"Zum Abschluss der Live-Demo: Über die Seitenleiste kann man die Original-Referenz-PDFs herunterladen – das ist die Quelle aller Zahlen."
"Und mit einem Klick auf 'Auswertungsberichte generieren' erstellt RealBasket eigene PDF-Berichte: einen pro Jahr, einen zu den Stadtmieten und einen VPI-Bericht – alles auf Deutsch, in Euro und aus denselben geprüften Daten."
Einen Bericht öffnen und kurz zeigen.
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
Zeit: ca. 1 Minute, dann Fragen.
"Zusammengefasst: RealBasket misst die Inflation der Grundbedarfskosten auf echten Daten und erklärt die Abweichung zum VPI nach Kategorien."
"Der Agent wählt die Tools selbst, rechnet aber nie selbst. Der Guardrail prüft jede Zahl, RAG liefert Erklärungen mit Quelle, und das Monitoring macht jeden Schritt sichtbar."
"130 automatisierte Tests sichern das ab."
"Als nächste Schritte wollen wir weitere Datenquellen anbinden, den Chat-Kontext verbessern und die Dienste für den Produktivbetrieb absichern."
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
Welcome (about 30 seconds).
"Hello everyone. We are team RealBasket. In the next few minutes we will show you live how an agentic AI system measures real essential living costs and compares them with the official Consumer Price Index."
Beforehand: all five PowerShell windows are running, http://localhost:8501 is open in the browser, and the sidebar shows "Agent-Service / MCP verbunden" (connected).
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
Key message: the CPI is correct, but it measures a different, broader basket.
"Many people feel that inflation is higher than the official figure. Often that is because they mainly notice essential spending: food, rent, energy, mobility."
"RealBasket builds its own index for exactly that – the ECLI, Essential Living Cost Index – with five categories: food, housing / energy, transport / mobility, health and communication."
"Important: we use no made-up demo data. All values come from reference PDFs based on Destatis data and are checked 11 times on import."
Transition: "Let's first look at how the system is built."
"""},
            {"kind": "arch", "title": "Architecture: four services with Docker Compose",
             "s2_side_head": "At a glance", "s2_side": [
                 "UI (Streamlit :8501) talks only to the agent API",
                 "Agent API (FastAPI :8002): Strands agent + LLM, number guardrail",
                 "MCP server (:8001): calculation core, SQLite with source and page",
                 "Weaviate (:8080): vector search over the PDF text",
                 "Figures never from RAG or the LLM – only from the core"],
             "notes": """
Time: about 1 minute. Point at the diagram, left to right.
"The app consists of four services. On the left, the Streamlit UI. It never reads data directly; it only calls the agent API."
"The agent API contains a Strands agent with Azure OpenAI. For fixed dashboard queries it forwards requests through an allow-list straight to the MCP server – no LLM involved."
"The MCP server is the heart of the system: it provides the tools – index calculation, CPI comparison, deviation drivers – and reads values from a SQLite database that stores file and page for every value."
"Weaviate is our vector database. It only holds the text of the PDFs, i.e. method notes. Figures never come from text search."
"Principle: the agent picks the tools and writes the answer; the figures are produced by deterministic code only."
"""},
            {"kind": "startup", "title": "Starting the demo: five PowerShell windows",
             "windows": [
                 ("Window 1", "Weaviate :8080", ["wsl --shutdown", "podman run in the WSL VM", "image from mirror.gcr.io", "keep window open"]),
                 ("Window 2", "MCP server :8001", ["load .env", "storage --mode sql", "storage --mode vector", "real-basket-mcp"]),
                 ("Window 3", "Agent API :8002", ["load .env", "uvicorn agent_service.api:app", "port 8002"]),
                 ("Window 4", "UI :8501", ["streamlit run src/real_basket/ui/app.py"]),
                 ("Window 5", "Check", ["/health → status ok", "search_documents → 200", "open localhost:8501"]),
             ],
             "tip": "All commands are in the README, section \"Start for the presentation\".",
             "bar": "Keep the order: Weaviate → MCP → agent API → UI → check.",
             "notes": """
Show this slide briefly or skip it if time is short – everything is already running.
"For the demo the four services run locally: Weaviate in Podman, the three Python services with Poetry. In production the same stack starts with a single docker compose up."
If something goes wrong:
- "Agent API not reachable": window 3 is not running.
- "machine not in running state": wsl --shutdown, restart window 1.
- PDF search fails: check Weaviate, rerun storage --mode vector.
Transition: "Now let's go into the app."
"""},
            {"kind": "step", "title": "Step 1 · Header: ECLI vs. CPI",
             "kpis": [("2.93 %", "ECLI year on year (10/2026)"), ("2.83 %", "CPI (VPI) year on year"),
                      ("+0.11 PP", "Deviation"), ("Mobility", "Biggest driver")],
             "left_head": "Click path in the app", "left": [
                 "Browser: http://localhost:8501",
                 "Sidebar: show \"Agent-Service / MCP verbunden\"",
                 "Point at the four KPIs in the header",
                 "Read the \"Datenbasis\" (data basis) info box"],
             "right_head": "What we show", "right": [
                 "All four values come from the calculation core via MCP",
                 "Real data 11/2024 – 10/2026, no demo data",
                 "Without the reference PDFs the app shows an error, not numbers",
                 "The UI is in German – labels are translated on the slides"],
             "bar": "At a glance: essential costs rise 0.11 percentage points faster than the CPI.",
             "notes": """
Time: about 1 minute.
"This is the start page. At the top you see the four key figures."
"The ECLI – our essential living cost index – rose 2.93 percent year on year in October 2026. The official CPI rose 2.83 percent."
"So the deviation is plus 0.11 percentage points. The biggest driver is transport / mobility."
Point at the sidebar: "On the left you can see that the UI is connected to the agent service and the MCP server, and which data basis is used."
"No language model produced these numbers. They come from the deterministic calculation core on the MCP server."
Note: the UI is in German (target audience: German households). "VPI" is the German CPI.
"""},
            {"kind": "step", "title": "Step 2 · Tab \"Index vs. VPI\"",
             "left_head": "Click path in the app", "left": [
                 "Open the tab \"Index vs. VPI\"",
                 "Left chart: index over time, base 11/2024 = 100",
                 "Right chart: yearly change in %",
                 "Scroll down: essential costs in euros"],
             "right_head": "What we show", "right": [
                 "ECLI and CPI side by side over time",
                 "Monthly spending of the reference basket per category (€/month)",
                 "Table with every monthly value for checking"],
             "bar": "Transparency: every point in the chart is a sourced value from the reference PDFs.",
             "notes": """
Time: about 1 minute.
"The first tab shows the development over time. On the left, both indices with a common base: November 2024 equals 100."
"On the right, the year-on-year change – the inflation rate – of ECLI and CPI compared."
Scroll down: "Here you see the modelled essential living costs in euros per month, split by category. Housing / energy is, as expected, the biggest block."
"The table below contains all values – nothing is hidden."
"""},
            {"kind": "step", "title": "Step 3 · Tab \"Einflussfaktoren\" (deviation drivers)",
             "left_head": "Click path in the app", "left": [
                 "Open the tab \"Einflussfaktoren\"",
                 "Bar chart: contribution of each category in percentage points",
                 "Expand \"Quelle und Datenprüfungen\" (source and data checks)",
                 "Show the 11 checks and the PDF sources"],
             "right_head": "What we show", "right": [
                 "Why does the ECLI differ from the CPI? – exact contribution per category",
                 "The contributions add up exactly to the deviation",
                 "11 data checks: sums, gaps, yearly rates recomputed"],
             "bar": "Explainability: the deviation is fully attributed to categories.",
             "notes": """
Time: about 1 minute.
"The interesting question is: why do the two indices differ?"
"This chart shows each category's contribution to the deviation in percentage points. The contributions add up exactly to the total deviation – that is plain maths in the calculation core, no LLM."
Expand the section: "Here you see the eleven checks that run when the PDFs are imported: sums, gaps, and the yearly rates printed in the PDFs are recomputed by our core. We only show numbers if everything matches."
"""},
            {"kind": "step", "title": "Step 4 · Tab \"Stadtmieten\" (city rents)",
             "left_head": "Click path in the app", "left": [
                 "Open the tab \"Stadtmieten\"",
                 "Show the table of the 15 largest cities",
                 "Bar chart \"Miete Oktober 2026 in €/m²\"",
                 "Scroll down: \"Bundesländer – Datenabdeckung\" (state coverage)"],
             "right_head": "What we show", "right": [
                 "Real asking rents January vs. October 2026",
                 "Including an example: 75 m² flat",
                 "No state-level rents in the sources – we do not estimate",
                 "Instead: which cities are covered per federal state"],
             "bar": "Honest about data gaps: \"not in the reference data\" instead of estimated numbers.",
             "notes": """
Time: about 1 minute.
"Housing is the biggest cost block for many people. Here you see the asking rents of Germany's 15 largest cities, January versus October 2026, also converted to a 75 square metre flat."
"We care about honesty with data gaps: the sources contain no rents per federal state. Instead of estimating, we show which cities are covered per state – and clearly say where there is no data."
"""},
            {"kind": "step", "title": "Step 5 · Tab \"PDF-Suche (Weaviate)\"",
             "left_head": "Click path in the app", "left": [
                 "Open the tab \"PDF-Suche (Weaviate)\"",
                 "Type: \"Ist Wohnen / Energie die Nettokaltmiete?\"",
                 "Click \"Weaviate durchsuchen\" (search)",
                 "Show the hits with file and page"],
             "right_head": "What we show", "right": [
                 "Semantic search (RAG) over the method notes of the PDFs",
                 "Embeddings via Azure OpenAI, stored in Weaviate",
                 "Every passage with its source: file · page",
                 "Context only – figures never come from text search"],
             "bar": "RAG delivers explanations with sources – the figures stay in the calculation core.",
             "notes": """
Time: about 1 minute.
"Numbers alone are not enough – you also need to understand how they are calculated. For that we have a semantic search over the method notes of the reference PDFs."
Type the question "Ist Wohnen / Energie die Nettokaltmiete?" (Is housing / energy the net cold rent?) and click "Weaviate durchsuchen".
"The search runs through the MCP server: the question is turned into a vector with Azure OpenAI, and Weaviate finds the most similar passages. Every hit shows file and page – you can check it in the original."
Alternative question: "Wie wird Wohnen / Energie berechnet?" (How is housing / energy calculated?)
"""},
            {"kind": "step", "title": "Step 6 · Tab \"MCP-Agent\": chat with RealBasket",
             "left_head": "Click path in the app", "left": [
                 "Open the tab \"MCP-Agent\"",
                 "Ask: \"Wie hat sich der ECLI gegenüber dem VPI entwickelt?\"",
                 "Below the answer: show the MCP tools used",
                 "Follow-up: \"Warum weicht der ECLI vom VPI ab?\""],
             "right_head": "What we show", "right": [
                 "Strands agent picks the right MCP tools itself",
                 "Answer always in German, figures from tool results",
                 "Number guardrail: every figure is checked against the tools",
                 "Unbacked figures are flagged visibly"],
             "bar": "The agent decides which tools are needed – the code decides the figures.",
             "notes": """
Time: about 1.5 minutes. The answer takes a few seconds – explain while waiting.
"Now the agentic part. I ask a question in natural language."
Ask: "Wie hat sich der ECLI gegenüber dem VPI entwickelt?" (How has the ECLI developed compared with the CPI?)
"The agent decides by itself which tools it needs. It has no direct data access – everything goes through the MCP server."
Show the answer (expected: ECLI 2.93 %, CPI 2.83 %, deviation +0.11 PP): "Below the answer you see which MCP tools were called."
"And here our guardrail comes in: the agent service checks every number in the answer against the tool results. If the model invents a number, it is flagged as not backed."
Follow-up: "Warum weicht der ECLI vom VPI ab?" (Why does the ECLI differ from the CPI?) – the agent drills down into the drivers.
"""},
            {"kind": "step", "title": "Step 7 · Tab \"Monitoring\": see the path of every request",
             "left_head": "Click path in the app", "left": [
                 "Open the tab \"Monitoring\"",
                 "KPIs: interactions, chat questions, MCP calls, warnings",
                 "Select the latest chat question in the dropdown",
                 "Explain the graph with numbered steps",
                 "Expand \"Verlauf\" (history)"],
             "right_head": "What we show", "right": [
                 "Path through UI → agent → MCP → Weaviate / LLM",
                 "Numbered edges = order of the steps",
                 "Duration and status of every interaction",
                 "Only for this browser session, nothing is stored"],
             "bar": "Traceability: every interaction becomes visible as a path through the architecture.",
             "notes": """
Time: about 1 minute.
"Agentic systems are often a black box. Our Monitoring tab shows what happens."
"At the top you see how many interactions, chat questions and MCP tool calls there were in this session."
Select the latest chat question: "The graph shows the exact path of the request: from the UI to the agent API, to the LLM, then the tool calls through the MCP server. The numbered edges show the order."
"The table below lists every step with duration and status. The history is kept only for this browser session and is not stored."
"""},
            {"kind": "step", "title": "Step 8 · Sidebar: PDF reports",
             "left_head": "Click path in the app", "left": [
                 "Sidebar: section \"Referenzberichte\" (reference reports)",
                 "Click \"Laden: Lebenshaltungskosten_2026 …\" and download",
                 "Click \"Auswertungsberichte generieren\" (generate reports)",
                 "Download one generated report and open it briefly"],
             "right_head": "What we show", "right": [
                 "The original reference PDFs (source of all figures)",
                 "Generated reports: per year, city rents, CPI report",
                 "In German, in euros, from the same checked data"],
             "bar": "From dashboard to shareable report – in one click.",
             "notes": """
Time: about 45 seconds.
"To finish the live demo: in the sidebar you can download the original reference PDFs – the source of all figures."
"And with one click on 'Auswertungsberichte generieren' RealBasket creates its own PDF reports: one per year, one on city rents and one CPI report – all in German, in euros and from the same checked data."
Open one report and show it briefly.
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
Time: about 1 minute, then questions.
"In summary: RealBasket measures essential-cost inflation on real data and explains the deviation from the CPI by category."
"The agent picks the tools itself but never calculates itself. The guardrail checks every figure, RAG provides explanations with sources, and monitoring makes every step visible."
"130 automated tests back this up."
"As next steps we want to connect more data sources, improve the chat context and secure the services for production."
"Thank you – we look forward to your questions."
Possible questions:
- Why not let the LLM calculate? → Traceability and correctness; LLMs hallucinate numbers.
- Where does the data come from? → Reference PDFs based on Destatis EVS 2023 + CPI, 11/2024 – 10/2026.
- Why MCP? → Standardised tool interface; agent and data are decoupled and deployable separately.
"""},
        ],
    },
}


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
        if s["kind"] == "arch":
            deck.architecture(slide, s)
        elif s["kind"] == "startup":
            startup(slide, s)
        elif s["kind"] == "results":
            deck.results(slide, s)
        else:
            step(slide, s)
        notes(slide, s["notes"])
    prs.core_properties.title = f"{t['cover_title']} – {t['cover_subtitle']}"
    prs.core_properties.language = "de-DE" if lang == "de" else "en-US"
    out = HERE / t["file"]
    prs.save(str(out))
    return out


if __name__ == "__main__":
    for language in TEXT:
        print("written", build(language))
