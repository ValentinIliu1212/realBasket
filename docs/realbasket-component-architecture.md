# REALBASKET – Komponentenarchitektur

> Grundlage: `process-redesign.md` (November 2026). Architekturansicht des beschriebenen Hackathon-Demosystems, **kein** geplanter Monitoring-Workflow. Die Aufteilung in Layer ist eine Visualisierung der beschriebenen Zuständigkeiten; sie definiert keine zusätzlichen Services oder APIs.

## 1. Gesamtarchitektur nach Komponenten

```mermaid
flowchart TB
    subgraph UI["1 · Presentation Layer"]
        DASH["Dashboard · Sidebar · Chat"]
        CLI["real-basket-cli"]
        KCLI["real-basket-knowledge · Method-notes-Tab"]
    end

    subgraph AGENTS["2 · Agent Layer – nichtdeterministische Orchestrierung"]
        ORCH["REALBASKET-ORCHESTRATOR<br/>LLM-Agent · Tool-Auswahl · deutsche Antwort"]
        COLAG["REALBASKET-COLLECTOR<br/>Agent für Preisabfragen"]
    end

    subgraph TOOLS["3 · Tool Layer"]
        CALC["calculate_essential_vs_cpi"]
        INV["investigate_deviation"]
        RATES["fetch_regional_rents<br/>fetch_net_salaries<br/>fetch_official_cpi"]
        COLLECT["collect_category_prices"]
        PRICES["fetch_prices"]
        SEARCH["search_methodology"]
    end

    subgraph CORE["4 · Deterministic Core"]
        INDEX["core/index.py<br/>Index · YoY · Abweichung"]
        INVEST["core/investigation.py<br/>Kategorie · Artikel · Region · Treiber"]
        FETCHCODE["Deterministische Fetch-Tools<br/>Renten · Einkommen · CPI · Preise"]
    end

    subgraph DATA["5 · Data Layer"]
        SOURCE["data.basket.set_data_source<br/>real | demo · auto als Standard"]
        BASKET["load_basket()<br/>einheitlicher Warenkorb je Session"]
        PARSER["data/real_data.py<br/>PDF-Tabellenparser · 9 Prüfungen"]
        DEMO[("Demo-Daten")]
        PDF[("reports/real-data/*.pdf")]
    end

    subgraph KNOW["6 · Knowledge / RAG – Methodik, keine Zahlen"]
        INGEST["pypdf · Textpassagen<br/>numerische Tabellenzellen ausgeschlossen"]
        RETRIEVAL["BM25 offline · optional Embeddings<br/>Rank Fusion · BM25-Fallback"]
        KINDEX[("data_store/knowledge/index.json")]
    end

    DASH --> ORCH
    CLI --> ORCH
    DASH --> SOURCE
    SOURCE --> BASKET
    ORCH --> CALC & INV & RATES & COLLECT & SEARCH
    COLLECT --> COLAG --> PRICES
    CALC --> INDEX
    INV --> INVEST
    RATES --> FETCHCODE
    PRICES --> FETCHCODE
    INDEX & INVEST & FETCHCODE --> BASKET
    BASKET --> PARSER & DEMO
    PARSER --> PDF
    SEARCH --> RETRIEVAL
    KCLI --> RETRIEVAL
    RETRIEVAL --> KINDEX
    PDF --> INGEST --> KINDEX
    ORCH --> DASH
    ORCH --> CLI

    classDef agent fill:#e5edff,stroke:#4776bd,color:#152744
    classDef deterministic fill:#e5f4ec,stroke:#398161,color:#153f2c
    classDef data fill:#fff0da,stroke:#b47f36,color:#533910
    class ORCH,COLAG agent
    class INDEX,INVEST,FETCHCODE,PARSER deterministic
    class BASKET,PDF,DEMO,KINDEX data
```

**Regeln:** Der Agent wählt Tools und formuliert die Antwort, berechnet aber keine Kennzahlen. Zahlen entstehen ausschließlich im deterministischen Code. PDF-Tabellen dienen als numerische Datenbasis; PDF-Fließtext wird ausschließlich für Methodik und Einschränkungen durchsucht.

## 2. Komponente: Presentation und Session

```mermaid
flowchart LR
    USER([Nutzer]) --> DASH["Dashboard mit Chat"]
    USER --> CLI["real-basket-cli"]
    DASH --> SIDE["Sidebar: real | demo<br/>Standard: DATA_SOURCE=auto"]
    SIDE --> SET["data.basket.set_data_source"]
    SET --> BASKET["load_basket()"]
    SET --> RESET["Datenquellenwechsel:<br/>neuer Chat"]
    DASH --> ORCH["REALBASKET-ORCHESTRATOR"]
    CLI --> ORCH
    BASKET --> VIS["Dashboardwerte und Gewichte"]
    BASKET --> TOOLS["Agent-Tools"]
    ORCH --> TOOLS
    ORCH --> RESPONSE["Deutsche Antwort<br/>Datengrundlage · Belege · Disclaimer"]
    RESPONSE --> DASH
    RESPONSE --> CLI
```

Unveränderte Gewichtsregler verwenden die exakten, ungerundeten Warenkorbgewichte. Dashboard, Tools und veröffentlichter ECLI sollen übereinstimmen.

## 3. Komponente: Agenten und Tool-Orchestrierung

```mermaid
flowchart TD
    Q([Frage]) --> ORCH["REALBASKET-ORCHESTRATOR"]
    ORCH --> C["calculate_essential_vs_cpi"]
    ORCH --> I["investigate_deviation"]
    ORCH --> R["fetch_regional_rents / fetch_net_salaries / fetch_official_cpi"]
    ORCH --> COL["collect_category_prices"]
    ORCH --> K["search_methodology"]
    COL --> CA["REALBASKET-COLLECTOR"]
    CA --> FP["fetch_prices"]
    C & I & R & FP --> NUM["Deterministischer Code + Warenkorb"]
    K --> METHOD["Methodik-Passagen (RAG)"]
    NUM --> ORCH
    METHOD --> ORCH
    ORCH --> A(["Antwort auf Deutsch<br/>Headline + max. 5 Bulletpoints<br/>real/demo · Quellen · Disclaimer"])
```

Beispiel für eine Warum-Frage: `investigate_deviation(level='category')` → Kategorie mit dem größten absoluten `gap_pp` → `level='item'` (bzw. `region` für Mieten) → optional `search_methodology` für methodische Einschränkungen.

## 4. Komponente: Deterministic Core und Kennzahlen

```mermaid
flowchart LR
    C["calculate_essential_vs_cpi"] --> IDX["core/index.py"]
    I["investigate_deviation"] --> INVEST["core/investigation.py"]
    IDX --> LOAD["load_basket()"]
    INVEST --> LOAD
    LOAD --> ENGINE["Deterministische Berechnung"]
    ENGINE --> OUT["Index · YoY · CPI-Vergleich<br/>Treiberbeitrag · Abweichung"]
    OUT --> DASH["Dashboard: größter |gap_pp|-Treiber"]
    OUT --> AGENT["Agent erhält berechnete Werte"]
```

Für Monat `t` gegenüber `t−12`:

- `contribution_pp(c) = w_c × (I_c(t) − I_c(t−12)) / E(t−12) × 100`
- `gap_pp(c) = contribution_pp(c) − w_c × CPI_YoY`

Die Summe der Beiträge ergibt die essentielle YoY-Rate; die Summe der `gap_pp` entspricht der Differenz zwischen essentieller YoY-Rate und CPI-YoY.

## 5. Komponente: Datenbasis und Validierung

```mermaid
flowchart TD
    CHOICE["Datenquellenwahl pro Session"] --> BASKET["load_basket()"]
    BASKET --> REAL["Real-Modus"]
    BASKET --> DEMO["Demo-Modus"]
    REAL --> PARSE["data/real_data.py<br/>deterministische Tabellenextraktion"]
    PDF[("reports/real-data/*.pdf")] --> PARSE
    PARSE --> CHECK["9 deterministische Prüfungen:<br/>Summen · Abweichungen · gedruckter ECLI<br/>Jahresraten · Berichts-Konsistenz"]
    CHECK --> VALID["Validierte Realdaten"]
    DEMO --> DDATA[("Demo-Daten")]
    VALID --> OUTPUT["Einheitliche Datenbasis"]
    DDATA --> OUTPUT
    OUTPUT --> DASH["Dashboard"]
    OUTPUT --> TOOLS["Berechnungstools"]
    CHECK -. "Bei unlesbaren PDFs: auto-Fallback" .-> DEMO
```

Jedes Tool kennzeichnet die Datenquelle (`real` oder `demo`). Die Quelle wird pro Session einheitlich gehalten, damit keine realen und simulierten Zahlen vermischt werden.

## 6. Komponente: Knowledge / RAG

```mermaid
flowchart TD
    PDF[("reports/real-data/*.pdf")] --> PYPDF["pypdf: Text pro Seite"]
    PYPDF --> FILTER["Header entfernen · Duplikate bereinigen<br/>Fließtext und nichtnumerische Tabellenpassagen"]
    FILTER --> DROP["Numerische Tabellenzellen ausschließen"]
    DROP --> INDEX[("data_store/knowledge/index.json")]
    INDEX --> BM25["BM25 offline"]
    INDEX --> EMB["OpenAI-Embeddings optional"]
    BM25 --> FUSE["Retrieval · ggf. Reciprocal Rank Fusion"]
    EMB --> FUSE
    EMB -. "kein API-Key / Fehler" .-> BM25
    Q["search_methodology<br/>Method-notes-Tab · real-basket-knowledge"] --> FUSE
    FUSE --> NOTES["Methodik · Einschränkungen · Seitenbelege"]
    NOTES --> AGENT["Agent: Kontext, niemals Zahlenquelle"]
```

Der Index wird bei Änderungen von PDF-Dateigröße oder Änderungszeitpunkt neu aufgebaut. Ohne Embedding-Zugang funktioniert BM25 offline.

## 7. Architekturgrenzen

Nicht Bestandteil dieser Version sind geplante Hintergrundausführungen, Monitoring mit Retry- und Validierungsloops, Human Approval, Audit Trail, Source Memory, Live-Destatis-GENESIS-Collector sowie reale Bundesland-Mieten und Nettogehälter. Der frühere Monitoring-Workflow ist laut Quelldokument in der Git-Historie bis `f9344ef` enthalten.

## 8. Mermaid in VS Code anzeigen

Die Datei als `.md` öffnen und mit `Ctrl + Shift + V` die Markdown-Vorschau aufrufen. Jedes der sechs Diagramme steht in einem eigenen `mermaid`-Codeblock.

---

*Quellbasis: `process-redesign.md`, Stand November 2026. Die Pfeile sind Architektur-/Datenabhängigkeiten; sie sind keine Behauptung über Netzwerk-Deployments oder physische Microservices.*
