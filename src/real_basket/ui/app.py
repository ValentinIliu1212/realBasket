"""RealBasket dashboard. All source data and calculations are fetched from MCP (no local data access).

Every interaction is recorded for the Monitoring tab (history per browser session only, see ui/monitoring.py).
"""
from __future__ import annotations

import base64
import time

import pandas as pd
import plotly.express as px
import streamlit as st

from real_basket.agent_service.client import call_tool, chat, url
from real_basket.ui import monitoring as mon

st.set_page_config(page_title="RealBasket – MCP", page_icon="🧺", layout="wide")

MAX_TRACES = 30


def de(value, digits=2):
    return f"{float(value):,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def record(trace: mon.Trace) -> None:
    """Store the use-case path of an interaction for the Monitoring tab (latest first, this session only)."""
    traces = st.session_state.setdefault("traces", [])
    traces.insert(0, trace)
    del traces[MAX_TRACES:]


def traced_call(tool: str, info=None, **arguments):
    """call_tool via the agent API, recorded with duration and outcome; `info(result)` -> short result text."""
    t0 = time.perf_counter()
    try:
        result = call_tool(tool, **arguments)
    except Exception as exc:
        record(mon.ui_tool_trace(tool, arguments, time.perf_counter() - t0, error=str(exc)))
        raise
    record(mon.ui_tool_trace(tool, arguments, time.perf_counter() - t0, result_info=info(result) if info else ""))
    return result


@st.cache_data(ttl=90, show_spinner="Lade validierte Werte über MCP …")
def snapshot():
    return call_tool("get_dashboard_snapshot")


st.title("🧺 RealBasket")
st.caption("Streamlit → Agent-Service (FastAPI / Strands) → MCP → Rechenkern / SQLite / Weaviate")
st.sidebar.header("🔌 Agent-Service")
st.sidebar.code(url(), language="text")
t0 = time.perf_counter()
try:
    data = snapshot()
    if "error" in data:
        raise RuntimeError(data["error"])
except Exception as exc:
    record(mon.ui_tool_trace("get_dashboard_snapshot", {}, time.perf_counter() - t0, error=str(exc)))
    st.error(f"MCP-Server oder Quelldaten nicht erreichbar: {exc}")
    st.info("Starte die Dienste mit `docker compose up --build -d` und prüfe `docker compose logs realbasket-mcp`.")
    if st.button("Erneut verbinden"):
        snapshot.clear()
        st.rerun()
    st.stop()
if not st.session_state.get("snapshot_traced"):        # first load of the session or after "Daten neu laden"
    record(mon.ui_tool_trace("get_dashboard_snapshot", {}, time.perf_counter() - t0,
                             result_info=f"{len(data['checks'])} Prüfungen, {len(data['comparison'])} Monate"))
    st.session_state.snapshot_traced = True

st.sidebar.success("Agent-Service / MCP verbunden")
st.sidebar.caption(str(data["data_basis"]))
if st.sidebar.button("Daten neu laden"):
    snapshot.clear()
    st.session_state.snapshot_traced = False
    st.rerun()

st.sidebar.header("📄 Referenzberichte")
try:
    if "ref_files" not in st.session_state:             # once per session (not on every rerun)
        st.session_state.ref_files = traced_call("list_reference_pdfs",
                                                 lambda r: f"{len(r['files'])} PDFs")["files"]
    for ref in st.session_state.ref_files:
        if st.sidebar.button("Laden: " + ref["filename"], key="ref_" + ref["filename"]):
            payload = traced_call("get_reference_pdf", lambda r: f"{len(r['content_base64']) * 3 // 4:,} Bytes",
                                  filename=ref["filename"])
            st.session_state["download_pdf"] = (payload["filename"], base64.b64decode(payload["content_base64"]))
    if "download_pdf" in st.session_state:
        name, raw = st.session_state["download_pdf"]
        st.sidebar.download_button("⬇️ " + name, data=raw, file_name=name, mime="application/pdf")
    if st.sidebar.button("Auswertungsberichte generieren"):
        st.session_state["reports"] = traced_call("generate_reports", lambda r: f"{len(r)} PDFs")
    for filename, pdf64 in st.session_state.get("reports", {}).items():
        st.sidebar.download_button(filename, data=base64.b64decode(pdf64), file_name=filename,
                                   mime="application/pdf", key="generated_" + filename)
except Exception as exc:
    st.sidebar.warning(f"PDF-Funktionen nicht verfügbar: {exc}")

breakdown = data["breakdown"]
comparison = pd.DataFrame(data["comparison"])
prices = pd.DataFrame(data["prices"])
cities = pd.DataFrame(data["cities"])
category_names = {"food": "Lebensmittel", "housing_energy": "Wohnen / Energie",
                  "mobility": "Mobilität", "health": "Gesundheit", "communication": "Kommunikation"}

c1, c2, c3, c4 = st.columns(4)
c1.metric("ECLI ggü. Vorjahr", f"{de(breakdown['essential_yoy_pct'])} %")
c2.metric("VPI ggü. Vorjahr", f"{de(breakdown['cpi_yoy_pct'])} %")
c3.metric("Abweichung", f"{de(breakdown['deviation_pp'])} PP")
driver = breakdown["categories"][0]
c4.metric("Größter Einflussfaktor", category_names.get(driver["category"], driver["category"]),
          f"{de(driver['gap_pp'])} PP")
st.info("**Datenbasis:** " + data["note"] + " Eine Abweichung zum VPI bedeutet nicht, dass der VPI falsch ist.")

view_index, view_drivers, view_rent, view_rag, view_agent, view_monitor = st.tabs(
    ["📈 Index vs. VPI", "🧩 Einflussfaktoren", "🏠 Stadtmieten", "📄 PDF-Suche (Weaviate)", "🤖 MCP-Agent",
     "🛰️ Monitoring"])

with view_index:
    left, right = st.columns(2)
    with left:
        st.plotly_chart(px.line(comparison, x="period", y=["essential_index", "cpi_index"],
                                title="Index (Basis: November 2024 = 100)", labels={"value": "Index"}),
                        use_container_width=True)
    with right:
        st.plotly_chart(px.line(comparison, x="period", y=["essential_yoy_pct", "cpi_yoy_pct"],
                                title="Jährliche Veränderung", labels={"value": "%"}),
                        use_container_width=True)
    st.subheader("Modellierte Grundbedarfskosten in Euro")
    if not prices.empty:
        monthly = prices.pivot_table(index="period", columns="category", values="eur", aggfunc="sum")
        monthly = monthly.rename(columns=category_names)
        st.plotly_chart(px.area(monthly, title="Monatliche Ausgaben des Referenzwarenkorbs (€/Monat)"),
                        use_container_width=True)
        st.dataframe(monthly, use_container_width=True)

with view_drivers:
    st.caption("Deterministische Kategorienbeiträge aus dem MCP-Rechenkern.")
    drivers = pd.DataFrame(breakdown["categories"])
    drivers["Kategorie"] = drivers["category"].map(category_names)
    st.plotly_chart(px.bar(drivers, x="Kategorie", y="gap_pp", color="gap_pp",
                           title="Beiträge zur ECLI-VPI-Abweichung in Prozentpunkten"),
                    use_container_width=True)
    st.dataframe(drivers, use_container_width=True)
    with st.expander("Quelle und Datenprüfungen"):
        st.dataframe(pd.DataFrame(data["checks"]), use_container_width=True)
        st.dataframe(pd.DataFrame(data["base_amounts"]), use_container_width=True)
        st.write("PDF-Quellen:", ", ".join(data["documents"]))

with view_rent:
    st.caption("Veröffentlichte Angebotskaltmieten, keine repräsentativen Bestandsmieten oder Landesmieten.")
    if cities.empty:
        st.warning("Keine belegten Stadtmieten verfügbar.")
    else:
        st.dataframe(cities, use_container_width=True)
        st.plotly_chart(px.bar(cities.sort_values("rent_oct_eur_m2", ascending=False),
                               x="city", y="rent_oct_eur_m2", title="Miete Oktober 2026 in €/m²"),
                        use_container_width=True)
    st.subheader("Bundesländer – Datenabdeckung")
    st.info(data["state_note"])
    st.dataframe(pd.DataFrame(data["states"]), use_container_width=True)

with view_rag:
    st.caption("Semantische Suche ausschließlich via WeaviateVectorStore hinter dem MCP-Server. "
               "Für die Indizes werden keine Zahlen aus RAG übernommen.")
    query = st.text_input("PDF-Methodik durchsuchen", placeholder="Wie wird Wohnen / Energie berechnet?")
    if st.button("Weaviate durchsuchen") and query:
        try:
            found = traced_call("search_documents", lambda r: f"{len(r.get('passages', []))} Textstellen",
                                query=query, top_k=5)
            if not found.get("passages"):
                st.info("Keine Treffer. Wurde die Weaviate-Ingestion bereits ausgeführt?")
            for passage in found.get("passages", []):
                st.markdown(f"**{passage.get('source_file', '?')} · S. {passage.get('page', '?')}**")
                st.write(passage.get("text", ""))
        except Exception as exc:
            st.error(f"Weaviate-Suche nicht verfügbar: {exc}. Bitte Embeddings konfigurieren und indexieren.")

with view_agent:
    st.caption("Der Strands-Agent lädt seine Tools über FastMCP. Er hat keine direkten lokalen Datentools. "
               "Jede Zahl der Antwort wird im Agent-Service gegen die Tool-Ergebnisse geprüft (Guardrail).")
    st.session_state.setdefault("chat_history", [])
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("tools"):
                st.caption("MCP: " + " → ".join(msg["tools"]))
            if msg.get("check"):
                st.warning(msg["check"])
    question = st.chat_input("Wie hat sich der ECLI gegenüber dem VPI entwickelt?")
    if question:
        previous = [{"role": m["role"], "content": m["content"]} for m in st.session_state.chat_history]
        st.session_state.chat_history.append({"role": "user", "content": question})
        st.chat_message("user").write(question)
        check = ""
        with st.chat_message("assistant"), st.spinner("MCP-Tools werden aufgerufen …"):
            t0 = time.perf_counter()
            try:
                res = chat(question, previous)
                answer, invoked = res["answer"], res.get("tools", [])
                unverified = res.get("unverified", [])
                if unverified:
                    check = "⚠️ Nicht durch Tool-Ergebnisse belegt (bitte prüfen): " + ", ".join(unverified)
                record(mon.chat_trace(question, res.get("trace_messages") or mon.messages_from_tools(invoked),
                                      answer, unverified, res.get("figures_checked"), time.perf_counter() - t0))
            except Exception as exc:
                answer, invoked = f"Agenten- oder MCP-Fehler: {exc}", []
                record(mon.chat_trace(question, [], duration_s=time.perf_counter() - t0, error=str(exc)))
            st.write(answer)
            if invoked:
                st.caption("MCP: " + " → ".join(invoked))
            if check:
                st.warning(check)
        st.session_state.chat_history.append({"role": "assistant", "content": answer, "tools": invoked,
                                              "check": check})
    if st.button("Neuer Chat"):
        record(mon.new_chat_trace(len(st.session_state.chat_history)))
        st.session_state.chat_history = []
        st.rerun()

# --- Monitoring: rendered last -> includes the interactions of this run --------------------------------------
with view_monitor:
    st.caption("Use-Case-Pfade durch die vier Docker-Compose-Dienste (realbasket-ui → realbasket-agent → "
               "realbasket-mcp → weaviate) und den LLM-Provider. Nummerierte Kanten = Reihenfolge der Schritte. "
               "Der Verlauf gilt nur für diese Browser-Sitzung und wird nicht gespeichert.")
    traces: list[mon.Trace] = st.session_state.get("traces", [])
    if traces:
        h1, h2, h3, h4 = st.columns(4)
        h1.metric("Aufgezeichnete Vorgänge", len(traces))
        h2.metric("Chatfragen", sum(t.kind == "Chat" for t in traces))
        h3.metric("MCP-Tool-Aufrufe", sum(s.source == "mcp_client" and s.target in mon.TOOL_GROUP.values()
                                          for t in traces for s in t.steps))
        h4.metric("Mit Warnung / Fehler", sum(t.status != "ok" for t in traces))
    by_id = {t.id: t for t in traces}
    overview = "🗺️ Gesamtarchitektur (ohne Pfad)"
    chosen = st.selectbox("Vorgang", [0, *by_id], index=1 if traces else 0,
                          format_func=lambda i: by_id[i].label if i in by_id else overview)
    selected = by_id.get(chosen)
    if selected is not None and selected.note:
        st.info(selected.note)
    st.graphviz_chart(mon.to_dot(selected), use_container_width=True)
    if selected is not None:
        st.dataframe(pd.DataFrame(selected.rows()), hide_index=True, use_container_width=True)
    if traces:
        with st.expander(f"Verlauf ({len(traces)} Vorgänge, neueste zuerst)"):
            st.dataframe(pd.DataFrame([{"Zeit": f"{t.started:%H:%M:%S}", "Status": mon.STATUS_ICON[t.status],
                                        "Vorgang": t.kind, "Titel": t.title, "Schritte": len(t.steps),
                                        "Dauer s": None if t.duration_s is None else round(t.duration_s, 2),
                                        "Info": t.note} for t in traces]), hide_index=True,
                         use_container_width=True)
        if st.button("🧹 Verlauf leeren"):
            st.session_state.traces = []
            st.rerun()
