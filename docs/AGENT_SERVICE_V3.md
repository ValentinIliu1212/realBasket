# RealBasket v3 – separater Agent-Service

Vier Docker-Compose-Dienste: `realbasket-ui`, `realbasket-agent`, `realbasket-mcp`, `weaviate`.

## Daten- und Chat-Flüsse

- Dashboard und PDF-Downloads: **Streamlit** → HTTP `realbasket-agent:8002/tools/{tool_name}` → **MCPClient** → `realbasket-mcp:8001/mcp` → bestehende deterministische Tools.
- Chat: **Streamlit** → HTTP `realbasket-agent:8002/chat` → **Strands Orchestrator im Agent-Container** → **MCPClient** → MCP-Server → geprüfte Berechnung / RAG.
- Nur MCP-Container kann SQLite und Quellen-PDFs direkt lesen; Weaviate ist eine separate Vektordatenbank.
- `get_dashboard_snapshot` ist weiterhin eine deterministische Datenabfrage, **kein LLM-Aufruf**.

## Windows / Docker Desktop

Im Ordner `real-basket`:

```powershell
Copy-Item .env.example .env  # nur falls noch nicht vorhanden; Zugangsdaten ergänzen
# Weaviate-Embedding-Zugang konfigurieren, wenn RAG genutzt wird.
docker compose build --no-cache realbasket-ui realbasket-agent realbasket-mcp
docker compose up -d --force-recreate
docker compose ps
docker compose logs --tail=80 realbasket-agent realbasket-mcp realbasket-ui
```

UI: http://localhost:8501  |  MCP: http://localhost:8001/mcp (nur lokal am Host)

Agent API ist **nur intern im Compose-Netz** unter `http://realbasket-agent:8002` erreichbar; für lokale Debugging-Zugriffe optional `127.0.0.1:8002:8002` als Port-Mapping ergänzen. **Nicht ungeschützt im Internet veröffentlichen.**

Schnelltest Agent-Service (aus UI-Container):

```powershell
docker compose exec realbasket-ui python -c "import urllib.request; print(urllib.request.urlopen('http://realbasket-agent:8002/health').read().decode())"
```

Der Chat benötigt einen funktionierenden LLM-API-Zugang. Dashboard und PDF-Funktionen arbeiten auch ohne ihn, solange die MCP-Tools verfügbar sind. Für RAG `docker compose exec realbasket-mcp python -m real_basket.storage --mode vector` ausführen.

## Monitoring-Tab und Zahlen-Guardrail

- Tab **🛰️ Monitoring** im Dashboard: Jede Interaktion (Dashboard laden, Referenz-PDF, Auswertungsberichte,
  Weaviate-Suche, Chatfrage, neuer Chat) wird als Use-Case-Pfad durch die vier Dienste aufgezeichnet und als
  Graphviz-Diagramm mit nummerierten Kanten dargestellt (`src/real_basket/ui/monitoring.py`).
- Der Verlauf gilt **nur für die aktuelle Browser-Sitzung** (`st.session_state`, max. 30 Vorgänge) und wird
  nicht gespeichert.
- `/chat` liefert zusätzlich `unverified` (Zahlen der Antwort ohne Beleg in den Tool-Ergebnissen, geprüft im
  Agent-Service mit `agents/guardrail.py`), `figures_checked` und `trace_messages` (kompakte Strands-Nachrichten
  ohne große Tool-Payloads, `agents/trace.py`).

## Betriebshinweise

- `.env` enthält Zugangsdaten und gehört nicht ins Git-Repository. Beim Container-Build wird es durch `.dockerignore` ausgeschlossen.
- Die Agent-API ist in dieser Version nur über das interne Compose-Netz erreichbar, aber ohne HTTP-Authentifizierung. Vor externer Freigabe Authentifizierung, Limits und HTTPS ergänzen.
- Der Chat bleibt synchron und erzeugt pro Anfrage einen Strands-Agenten. Streaming, Session-Persistenz und LLM-Verbindungs-Resilienz sind spätere Erweiterungen.
- Ursprüngliche PDF-Daten können **modellierte Eurobeträge** enthalten und sind keine direkt gemessenen Supermarktpreise.
