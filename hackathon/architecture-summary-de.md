# RealBasket – Architektur-Zusammenfassung

*MCP + Weaviate + Agent Service v3 – Kurzfassung von architecture-detailed.pdf – Stand 11/2026*

## 1. Was RealBasket leistet

RealBasket berechnet einen **Essential Living Cost Index (ECLI)** aus fünf Grundbedarfsgruppen – Lebensmittel, Wohnen / Energie, Mobilität, Gesundheit und Kommunikation – und vergleicht ihn mit dem offiziellen Verbraucherpreisindex (**VPI, Destatis**). Es erklärt Kategorie für Kategorie, *warum* sich beide unterscheiden.

Demo-Zahlen: ECLI **2,93 %** ggü. Vorjahr vs. VPI **2,83 %**, Abweichung **+0,11 PP**; größter Einflussfaktor ist **Mobilität**.

> **Grundsatz:** *nicht-deterministische Hülle, deterministischer Kern.* Das LLM wählt die Tools und formuliert die Antwort auf Deutsch. **Jede** Zahl berechnet Python. Ein Guardrail prüft jede Zahl der Antwort gegen die Tool-Ergebnisse.

## 2. Architektur im Überblick

```
 Browser :8501
    |
 realbasket-ui      Streamlit          - kein Datenzugriff, kein LLM-Key
    |  HTTP
 realbasket-agent   FastAPI v3 :8002   - Strands-Agent + Guardrail + Trace
    |  MCP (streamable-http /mcp)
 realbasket-mcp     FastMCP :8001      - 12 Tools, deterministischer Kern
    |                       |
 SQLite                  Weaviate 1.32.3 :8080
 alle Zahlen + Quelle    nur PDF-Textabschnitte
    ^ Import (11 Prüfungen) ^ Indexierung (nur Text)
    +--- reports/real-data/*.pdf (schreibgeschützt) ---+
```

**Kernregel:** Jede Interaktion läuft UI → Agent-API → MCP. Nur der MCP-Container greift auf SQLite, Weaviate und die PDFs zu. Zur Laufzeit stammen alle Zahlen aus **SQLite**; die PDFs liest nur der Import.

| Dienst | Rolle | Wichtig |
|---|---|---|
| `realbasket-ui` | Streamlit-Dashboard | Kennzahlenleiste, Tabs Index vs. VPI, Einflussfaktoren, Stadtmieten, PDF-Suche, MCP-Agent, Monitoring; importiert nur `agent_service.client` |
| `realbasket-agent` | FastAPI-Gateway v3 | `GET /health`, `POST /chat` (Agent + Guardrail + Trace), `POST /tools/{name}` mit Allow-List von 5 Lese-Tools (sonst → 404); nicht zum Host veröffentlicht |
| `realbasket-mcp` | FastMCP-Tool-Server | 12 Tools (z. B. `calculate_index`, `get_dashboard_snapshot`, `search_documents`, `get_prices`); führt beim Start den Import aus |
| `weaviate` | Vektordatenbank | Collection `RealBasketDocuments`; Vektoren werden clientseitig mit Azure-OpenAI-Embeddings berechnet |

## 3. Daten und Speicherung

- **Quellen:** ausschließlich die Referenz-PDFs in `reports/real-data` (Destatis-EVS-2023-Grundbeträge, modellierte Monatskosten 11/2024–10/2026, VPI umbasiert auf 11/2024 = 100, immowelt-Angebotsmieten der 15 größten Städte). **Keine synthetischen oder Demo-Daten.**
- **Import mit 11 Prüfungen:** Summen, erster Monat = Basiswarenkorb, keine Lücken, Zeilensummen, nachgerechneter vs. gedruckter ECLI und Jahresraten, Konsistenz zwischen den Berichten, VPI je Monat, Stadtmieten, Länderabdeckung. Schlägt eine Prüfung fehl, wird nichts geschrieben und der bisherige Datenbestand bleibt erhalten.
- **SQLite – einzige Lesequelle:** geprüfter Datenbestand plus Herkunft (Datei + Seite) in einer Transaktion; zur Laufzeit schreibgeschützt geöffnet und je Import-ID gecacht. Ein Test verbietet PDF-Zugriffe zur Laufzeit.
- **Weaviate – nur Kontext:** Fließtext und nicht-numerische Tabellenzellen, in Abschnitte von ≤ 800 Zeichen zerlegt. **Numerische Zellen werden verworfen**, Zahlen können also nie aus RAG stammen.
- **Nicht vorhanden, daher nie geschätzt:** Mieten je Bundesland, Nettogehälter, Live-Daten nach 10/2026.

## 4. Deterministischer Kern und Guardrail

- **Indexberechnung (`core/index.py`):** Index mit festen Gewichten nach Laspeyres-Art (Gewicht = Grundbetrag ÷ Summe); Vorjahresvergleich nach Datum; immer auf der vollen Reihe berechnet, daher unabhängig vom gewählten Zeitfenster.
- **Einflussfaktoren (`core/investigation.py`):** Die Beiträge je Kategorie ergeben in Summe exakt die Gesamtabweichung:

```
gap_pp(c) = w_c * (I_c(t) - I_c(t-12)) / E(t-12) * 100  -  w_c * CPI_YoY(t)
Summe über c von gap_pp(c) = ECLI_YoY(t) - CPI_YoY(t)
```

- **Prompt-Vertrag:** Antwort auf Deutsch, Zahlen **nur** aus MCP-Tools, `search_documents` nur für Methodenkontext, immer mit dem Hinweis, dass eine Abweichung nicht bedeutet, dass der VPI falsch ist.
- **Zahlen-Guardrail (`agents/guardrail.py`):** extrahiert Zahlen mit Nachkommastellen oder Einheit aus der Antwort und prüft sie gegen alle `toolResult`-Werte (oder die Frage). Unbelegte Zahlen werden als `unverified` zurückgegeben und **markiert, nie umgeschrieben**.
- **Monitoring:** kompakte Traces aus den Agent-Nachrichten; die UI zeichnet je Anfrage einen Graphviz-Pfad mit nummerierten Kanten (max. 30 je Sitzung, nichts wird gespeichert).

## 5. Zentrale Abläufe

| Ablauf | Weg | LLM |
|---|---|---|
| Dashboard | UI → `/tools/get_dashboard_snapshot` → MCP → SQLite → Kern → Diagramme + Kennzahlen | nein |
| Chat | UI → `/chat` → neuer Strands-Agent (Azure OpenAI) → MCP-Tools → Guardrail + Trace → UI | ja – nur Tool-Auswahl und Text |
| Import | `mcp-entrypoint.sh`: PDFs → 11 Prüfungen → SQLite; optional Abschnitte → Embeddings → Weaviate | nein |

## 6. Betrieb, Qualität und Sicherheit

- **Docker Compose:** vier Dienste, gestartet in Healthcheck-Reihenfolge weaviate → mcp → agent → ui; Host-Ports nur auf **127.0.0.1**; Image `python:3.11-slim`; Secrets werden zur Laufzeit aus `.env` geladen und sind nicht im Image.
- **Konfiguration:** Azure OpenAI (`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_COMPLETION_MODEL`, `AZURE_EMBEDDING_MODEL`), Dienst-URLs (`REALBASKET_MCP_URL`, `REALBASKET_AGENT_URL`), `REALBASKET_SQLITE_PATH`, Weaviate-Host und -Ports.
- **Tests (pytest + ruff):** UI nutzt nur den HTTP-Client, Allow-List 404, Guardrail, verlustfreier SQLite-Roundtrip, keine PDF-Zugriffe zur Laufzeit, Raten mit fester Basis, Indexberechnung, Einflussfaktoren, Chunking ohne Zahlen, Encoding.
- **Umgesetzt:** Ports nur auf localhost, Agent-API nicht veröffentlicht, Lese-Allow-List für `/tools`, Schutz gegen Path Traversal, Größenlimits für Anfragen, Zahlen-Guardrail.
- **Offen vor externem Einsatz:** Container laufen als root, keine Authentisierung / kein TLS für Agent-API und MCP, anonymer Weaviate-Zugriff, der Chat-Agent sieht alle 12 Tools (auch Schreib-Tools), HTTP-502-Antworten geben Fehlertexte zurück, der Guardrail prüft Zahlen, nicht Aussagen.

## 7. Roadmap

| Phase | Inhalt |
|---|---|
| Jetzt | 4 Container: UI → Agent-API v3 → MCP → SQLite / Weaviate |
| Als Nächstes | Härtung: Non-root-User, Authentisierung (Entra ID / OAuth 2.1), TLS, eigene Tool-Allow-List für den Chat-Agenten, Key Vault |
| A2A | Spezialisierte Agenten (Preissammler, Abweichungsanalyse, Methodik, Berichte) als A2A-Dienste |
| Skalierung | MCP-Server `destatis-genesis` (Live-VPI), neue Quellen, OpenTelemetry, Azure Container Apps |

## 8. Kernaussagen

1. **Das LLM rechnet nie** – Zahlen kommen aus getestetem Python-Code und werden vom Guardrail geprüft.
2. **MCP ist die einzige Datengrenze** – die UI hat keinen Datenzugriff und keinen Key.
3. **Zwei Speicher, zwei Aufgaben** – SQLite hält alle Zahlen mit Datei + Seite; Weaviate hält nur Text als Kontext.
4. **Nur echte Daten, beim Import 11-fach geprüft** – Lücken in den Quellen werden benannt, nicht geschätzt.
5. **Nachvollziehbar by Design** – jede Anfrage ist im Monitoring-Tab als Pfad sichtbar.
6. **Ehrlich bei Lücken** – root-Container, fehlende Authentisierung / TLS und breiter Tool-Zugriff des Chats sind die nächsten Punkte.
