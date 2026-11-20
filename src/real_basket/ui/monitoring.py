"""Monitoring: use-case paths of every interaction through the RealBasket Docker architecture (no Streamlit import).

Every interaction of the dashboard (load / reload data, reference-PDF download, report generation, Weaviate
search, chat question, new chat) is recorded as a `Trace`: an ordered list of `Step`s between the components of
the four Docker Compose services (realbasket-ui -> realbasket-agent -> realbasket-mcp -> weaviate) and the LLM
provider. `to_dot()` draws that architecture as Graphviz DOT and highlights the path of one trace with numbered
edges; the dashboard renders it with `st.graphviz_chart` (rendered in the browser, no Graphviz install).

The history lives in the Streamlit session only (one browser tab = one history, nothing is persisted).

Chat traces are derived from the compact Strands messages returned by the agent service (every assistant message =
one LLM call, `toolUse` / `toolResult` blocks = MCP tool calls), so they show what the agent really did, not a fixed
script. The number guardrail runs in the agent service; its result is part of the /chat response.
"""

from __future__ import annotations

import itertools
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Node:
    id: str
    label: str
    group: str


# one group per Docker Compose service (+ the external LLM provider)
GROUPS = {
    "ui": ("Container realbasket-ui · Streamlit :8501", "#e7f5ff"),
    "agent": ("Container realbasket-agent · FastAPI :8002 (nur intern)", "#fff4e6"),
    "mcp": ("Container realbasket-mcp · FastMCP :8001", "#ebfbee"),
    "weaviate": ("Container weaviate · :8080 / :50051", "#f3f0ff"),
    "llm": ("LLM-Provider (Azure OpenAI / OpenAI)", "#fff0f6"),
}

NODES: dict[str, Node] = {n.id: n for n in [
    Node("user", "👤 Nutzer", ""),
    Node("ui", "Streamlit-UI\nui/app.py", "ui"),
    Node("api_client", "HTTP-Client\nagent_service/client.py", "ui"),
    Node("agent_api", "Agent-API\n/chat · /tools/{name}", "agent"),
    Node("orchestrator", "Strands-Agent\nmcp_server/agent.py · ask()", "agent"),
    Node("guardrail", "Zahlen-Guardrail\nagents/guardrail.py", "agent"),
    Node("mcp_client", "MCP-Client\nStreamable HTTP", "agent"),
    Node("mcp_dashboard", "Dashboard & Berichte\nget_dashboard_snapshot · generate_reports\n"
                          "list_reference_pdfs · get_reference_pdf", "mcp"),
    Node("mcp_data", "Daten & Berechnung\nget_prices · get_cpi\ncalculate_index · get_city_rents", "mcp"),
    Node("mcp_storage", "SQLite-Tools\ningest_reference_pdfs\nget_observations", "mcp"),
    Node("mcp_vector", "Vektor-Tools\nsearch_documents\nindex_pdf_knowledge", "mcp"),
    Node("core", "core/\nindex.py · investigation.py", "mcp"),
    Node("data", "data/\nreal_data.py · basket.py", "mcp"),
    Node("reports", "reports/pdf_report.py", "mcp"),
    Node("sqlite", "SQLite\ndata_store/realbasket.sqlite3", "mcp"),
    Node("pdfs", "Referenz-PDFs\nreports/real-data (read-only)", "mcp"),
    Node("weaviate", "Weaviate\nRealBasketDocuments", "weaviate"),
    Node("llm", "Chat-Modell", "llm"),
    Node("embedding", "Embedding-Modell", "llm"),
]}

# static architecture (docker-compose.yml + docs/AGENT_SERVICE_V3.md)
ARCH_EDGES: list[tuple[str, str]] = [
    ("user", "ui"), ("ui", "api_client"), ("api_client", "agent_api"), ("agent_api", "orchestrator"),
    ("agent_api", "mcp_client"), ("agent_api", "guardrail"), ("orchestrator", "llm"), ("orchestrator", "mcp_client"),
    ("mcp_client", "mcp_dashboard"), ("mcp_client", "mcp_data"), ("mcp_client", "mcp_storage"),
    ("mcp_client", "mcp_vector"), ("mcp_dashboard", "core"), ("mcp_dashboard", "reports"), ("mcp_dashboard", "pdfs"),
    ("mcp_data", "core"), ("core", "data"), ("reports", "data"), ("data", "pdfs"), ("mcp_storage", "data"),
    ("mcp_storage", "sqlite"), ("mcp_vector", "embedding"), ("mcp_vector", "weaviate"), ("mcp_vector", "pdfs"),
]

# MCP tool -> hops behind the MCP client (tool group first)
TOOL_HOPS: dict[str, list[tuple[str, str]]] = {
    "get_dashboard_snapshot": [("mcp_dashboard", "core"), ("core", "data"), ("data", "pdfs")],
    "generate_reports": [("mcp_dashboard", "reports"), ("reports", "data"), ("data", "pdfs")],
    "list_reference_pdfs": [("mcp_dashboard", "pdfs")],
    "get_reference_pdf": [("mcp_dashboard", "pdfs")],
    "get_prices": [("mcp_data", "core"), ("core", "data")],
    "get_cpi": [("mcp_data", "core"), ("core", "data")],
    "calculate_index": [("mcp_data", "core"), ("core", "data")],
    "get_city_rents": [("mcp_data", "core"), ("core", "data")],
    "ingest_reference_pdfs": [("mcp_storage", "data"), ("data", "pdfs"), ("mcp_storage", "sqlite")],
    "get_observations": [("mcp_storage", "sqlite")],
    "search_documents": [("mcp_vector", "embedding"), ("mcp_vector", "weaviate")],
    "index_pdf_knowledge": [("mcp_vector", "pdfs"), ("mcp_vector", "embedding"), ("mcp_vector", "weaviate")],
}
HOP_ACTION = {
    ("mcp_dashboard", "core"): "Index, VPI-Vergleich, Einflussfaktoren berechnen",
    ("mcp_data", "core"): "deterministische Berechnung",
    ("core", "data"): "load_basket() – echte Daten (im Serverprozess gecacht)",
    ("data", "pdfs"): "Tabellen deterministisch lesen + prüfen",
    ("mcp_dashboard", "reports"): "generate_all()",
    ("reports", "data"): "Monatskosten, VPI, Stadtmieten",
    ("mcp_dashboard", "pdfs"): "Originaldatei lesen",
    ("mcp_storage", "data"): "validierter PDF-Parser",
    ("mcp_storage", "sqlite"): "SQL-Abfrage / Schreiben (Quelle + Seite)",
    ("mcp_vector", "embedding"): "Suchanfrage / Textstellen einbetten",
    ("mcp_vector", "weaviate"): "Ähnlichkeitssuche (WeaviateVectorStore)",
    ("mcp_vector", "pdfs"): "Textstellen ohne Zahlentabellen",
}
TOOL_GROUP = {tool: hops[0][0] for tool, hops in TOOL_HOPS.items()}

STATUS_ICON = {"ok": "✅", "warn": "⚠️", "error": "❌"}
_SEVERITY = {"ok": 0, "warn": 1, "error": 2}
_EDGE_COLOR = {"ok": "#d9480f", "warn": "#f08c00", "error": "#e03131"}
_counter = itertools.count(1)


@dataclass
class Step:
    source: str
    target: str
    action: str
    detail: str = ""
    status: str = "ok"


@dataclass
class Trace:
    kind: str
    title: str
    steps: list[Step]
    duration_s: float | None = None
    note: str = ""
    started: datetime = field(default_factory=datetime.now)
    id: int = field(default_factory=lambda: next(_counter))

    @property
    def status(self) -> str:
        return max((s.status for s in self.steps), key=_SEVERITY.__getitem__, default="ok")

    @property
    def label(self) -> str:
        took = f" · {self.duration_s:.2f} s" if self.duration_s is not None else ""
        return f"{STATUS_ICON[self.status]} {self.started:%H:%M:%S} · {self.kind}: {self.title}{took}"

    def rows(self) -> list[dict]:
        """Steps as table rows (German column names)."""
        return [{"#": i, "Von": _first_line(s.source), "Nach": _first_line(s.target), "Aktion": s.action,
                 "Details": s.detail, "Status": STATUS_ICON[s.status]} for i, s in enumerate(self.steps, 1)]


def _first_line(node_id: str) -> str:
    node = NODES.get(node_id)
    return node.label.split("\n")[0] if node else node_id


def _short(text: Any, limit: int = 90) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def tool_name(name: str) -> str:
    """Canonical MCP tool name; tolerates prefixed names such as `realbasket_get_cpi`."""
    if name in TOOL_HOPS:
        return name
    return next((tool for tool in TOOL_HOPS if name.endswith(tool)), name)


def _hop_steps(name: str, args: str, status: str, outcome: str) -> list[Step]:
    """mcp_client -> tool group -> core / storage ... -> back to mcp_client."""
    tool = tool_name(name)
    hops = TOOL_HOPS.get(tool)
    if not hops:
        return [Step("mcp_client", "mcp_client", name, "unbekanntes Tool (keine Zuordnung)", "warn")]
    group = TOOL_GROUP[tool]
    steps = [Step("mcp_client", group, name, args)]
    steps += [Step(a, b, HOP_ACTION.get((a, b), "aufrufen")) for a, b in hops]
    steps.append(Step(group, "mcp_client", "Ergebnis", outcome, status))
    return steps


# --- Trace builders -------------------------------------------------------------------------------
UI_ACTION = {
    "get_dashboard_snapshot": ("Dashboard", "Dashboard öffnen / Daten neu laden"),
    "list_reference_pdfs": ("Referenz-PDFs", "Sidebar laden"),
    "get_reference_pdf": ("Referenz-PDF", "PDF laden"),
    "generate_reports": ("PDF-Berichte", "Auswertungsberichte generieren"),
    "search_documents": ("Weaviate-Suche", "PDF-Methodik durchsuchen"),
}


def ui_tool_trace(tool: str, arguments: dict | None = None, duration_s: float | None = None, error: str = "",
                  result_info: str = "") -> Trace:
    """Direct (deterministic, no LLM) tool call of the UI: UI -> agent API /tools/{name} -> MCP -> core/storage."""
    kind, action = UI_ACTION.get(tool, ("MCP-Tool", tool))
    args = _short(json.dumps(arguments or {}, ensure_ascii=False), 70)
    status = "error" if error else "ok"
    outcome = _short(error, 70) if error else (result_info or "Ergebnis (JSON)")
    steps = [Step("user", "ui", action, args if arguments else ""),
             Step("ui", "api_client", f"call_tool({tool!r})"),
             Step("api_client", "agent_api", f"POST /tools/{tool}", "HTTP im Compose-Netz"),
             Step("agent_api", "mcp_client", "Allow-List prüfen", "UI_TOOLS")]
    if error and "not available through UI gateway" in error:
        steps.append(Step("agent_api", "api_client", "HTTP 404", "Tool nicht freigegeben", "error"))
    else:
        steps += _hop_steps(tool, args, status, outcome)
        steps.append(Step("mcp_client", "agent_api", "Tool-Ergebnis", outcome, status))
        steps.append(Step("agent_api", "api_client", "HTTP 502" if error else "HTTP 200 JSON", status=status))
    steps.append(Step("ui", "user", "Fehler anzeigen" if error else "Ergebnis anzeigen", outcome, status))
    note = "Kein LLM: deterministische MCP-Tools über die Allow-List der Agent-API."
    if tool == "get_dashboard_snapshot":
        note += " Ergebnis 90 s im UI gecacht (st.cache_data)."
    if tool == "search_documents":
        note += " Nur Kontext – Zahlen kommen nie aus der Vektorsuche."
    title = str((arguments or {}).get("query", "")) if tool == "search_documents" else action
    return Trace(kind, _short(title or action, 60), steps, duration_s, note)


def new_chat_trace(turns: int) -> Trace:
    return Trace("Neuer Chat", "Verlauf gelöscht", [Step("user", "ui", "Neuer Chat", f"{turns} Nachrichten gelöscht")],
                 note="Kein Serverzustand: der Agent-Service erzeugt pro Frage einen neuen Strands-Agenten.")


def _content(msg: Any) -> list:
    return msg.get("content", []) if isinstance(msg, dict) else []


def _result_payload(result: dict | None) -> dict | None:
    """JSON payload of a Strands `toolResult` (first JSON block or JSON text block), if any."""
    for block in (result or {}).get("content", []) or []:
        if isinstance(block, dict) and isinstance(block.get("json"), dict):
            return block["json"]
        if isinstance(block, dict) and isinstance(block.get("text"), str):
            try:
                data = json.loads(block["text"])
            except ValueError:
                continue
            if isinstance(data, dict):
                return data
    return None


def _tool_steps(use: dict, result: dict | None) -> list[Step]:
    name = str(use.get("name", "?"))
    args = _short(json.dumps(use.get("input") or {}, ensure_ascii=False), 70)
    payload = _result_payload(result)
    if result is None:
        status, outcome = "warn", "kein Ergebnis"
    elif result.get("status") == "error":
        status, outcome = "error", "Fehler"
    elif payload and "error" in payload:
        status, outcome = "warn", f"Tool meldet: {_short(payload['error'], 60)}"
    elif payload and "passages" in payload:
        status, outcome = "ok", f"{payload['passages']} Textstellen"
    else:
        status, outcome = "ok", "Ergebnis (JSON)"
    steps = [Step("orchestrator", "mcp_client", "tools/call", f"{name}({args})")]
    steps += _hop_steps(name, args, status, outcome)
    steps.append(Step("mcp_client", "orchestrator", "Tool-Ergebnis", f"{name}: {outcome}", status))
    return steps


def messages_from_tools(tools: list[str]) -> list[dict]:
    """Fallback if the agent service returns no `trace_messages`: one assistant message with all tool uses."""
    uses = [{"toolUse": {"toolUseId": f"t{i}", "name": t, "input": {}}} for i, t in enumerate(tools)]
    results = [{"toolResult": {"toolUseId": f"t{i}", "status": "success", "content": []}} for i in range(len(tools))]
    return ([{"role": "assistant", "content": uses}, {"role": "user", "content": results}] if tools else []) + \
        [{"role": "assistant", "content": [{"text": ""}]}]


def chat_trace(question: str, messages: list, answer: str = "", unverified: list[str] | None = None,
               figures_checked: int | None = None, duration_s: float | None = None, error: str = "") -> Trace:
    """Use-case path of one chat turn. `messages` = the (compact) Strands messages of this turn."""
    steps = [Step("user", "ui", "Frage", _short(question)),
             Step("ui", "api_client", "chat(frage, verlauf)"),
             Step("api_client", "agent_api", "POST /chat", "Frage + letzte 8 Nachrichten als Text"),
             Step("agent_api", "orchestrator", "ask()", "neuer Strands-Agent pro Frage"),
             Step("orchestrator", "mcp_client", "MCP-Sitzung öffnen", "list_tools")]
    results = {b["toolResult"].get("toolUseId"): b["toolResult"] for m in messages for b in _content(m)
               if isinstance(b, dict) and isinstance(b.get("toolResult"), dict)}
    calls = 0
    for msg in messages:
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        calls += 1
        uses = [b["toolUse"] for b in _content(msg) if isinstance(b, dict) and isinstance(b.get("toolUse"), dict)]
        steps.append(Step("orchestrator", "llm", f"LLM-Aufruf {calls}", "Systemprompt + Verlauf + Tool-Schemas"))
        if uses:
            steps.append(Step("llm", "orchestrator", "Tool-Wahl", ", ".join(str(u.get("name")) for u in uses)))
        else:
            text = "".join(b.get("text", "") for b in _content(msg) if isinstance(b, dict))
            steps.append(Step("llm", "orchestrator", "Antworttext", f"{len(text)} Zeichen"))
        for use in uses:
            steps += _tool_steps(use, results.get(use.get("toolUseId")))
    if error:
        steps.append(Step("agent_api", "api_client", "HTTP 502", _short(error), "error"))
        steps.append(Step("ui", "user", "Fehlermeldung anzeigen", status="error"))
    else:
        unverified = unverified or []
        checked = "" if figures_checked is None else f"{figures_checked} Zahlen "
        steps.append(Step("orchestrator", "agent_api", "Antwort", f"{len(answer)} Zeichen"))
        steps.append(Step("agent_api", "guardrail", "unverified_figures()", f"{checked}gegen Tool-Ergebnisse prüfen"))
        steps.append(Step("guardrail", "agent_api", "Prüfergebnis",
                          ("Nicht belegt: " + ", ".join(unverified)) if unverified else "alle Zahlen belegt",
                          "warn" if unverified else "ok"))
        steps.append(Step("agent_api", "api_client", "HTTP 200 JSON", "Antwort, Tools, Guardrail, Trace"))
        steps.append(Step("ui", "user", "Antwort anzeigen", "inkl. genutzter Tools und Guardrail-Hinweis"))
    tools = sum(1 for s in steps if s.action == "tools/call")
    return Trace("Chat", _short(question, 60), steps, duration_s, f"{calls} LLM-Aufrufe · {tools} Tool-Aufrufe")


# --- Graphviz --------------------------------------------------------------------------------------
def _q(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def to_dot(trace: Trace | None = None) -> str:
    """Architecture diagram as DOT; with a trace, its path is highlighted with numbered edges."""
    active: dict[tuple[str, str], list[int]] = {}
    edge_status: dict[tuple[str, str], str] = {}
    node_status: dict[str, str] = {}
    for i, s in enumerate(trace.steps if trace else [], 1):
        key = (s.source, s.target)
        active.setdefault(key, []).append(i)
        edge_status[key] = max(edge_status.get(key, "ok"), s.status, key=_SEVERITY.__getitem__)
        for n in (s.source, s.target):
            node_status.setdefault(n, "ok")
        if s.status != "ok":
            node_status[s.target] = max(node_status[s.target], s.status, key=_SEVERITY.__getitem__)

    def node_line(node: Node) -> str:
        fill = GROUPS[node.group][1] if node.group else "#ffffff"
        attrs = {"fillcolor": fill, "color": "#495057", "fontcolor": "#212529", "penwidth": "1"}
        if trace and node.id in node_status:
            st = node_status[node.id]
            attrs.update(fillcolor={"ok": "#ffe8cc", "warn": "#fff3bf", "error": "#ffe3e3"}[st],
                         color=_EDGE_COLOR[st], penwidth="2.4")
        elif trace:
            attrs.update(fillcolor="#f8f9fa", color="#dee2e6", fontcolor="#adb5bd")
        shape = ', shape="ellipse"' if node.id == "user" else ""
        return (f"  {_q(node.id)} [label={_q(node.label)}{shape}, "
                + ", ".join(f'{k}="{v}"' for k, v in attrs.items()) + "];")

    lines = ["digraph realbasket {",
             ('  graph [rankdir="LR", fontname="Helvetica", fontsize="11", nodesep="0.3", ranksep="0.55", '
              'bgcolor="transparent", compound="true"];'),
             '  node [shape="box", style="rounded,filled", fontname="Helvetica", fontsize="10"];',
             '  edge [fontname="Helvetica", fontsize="9", arrowsize="0.7"];']
    for node in NODES.values():
        if not node.group:
            lines.append(node_line(node))
    for group, (label, _) in GROUPS.items():
        lines.append(f"  subgraph cluster_{group} {{")
        lines.append(f'    label={_q(label)}; style="rounded,dashed"; color="#adb5bd"; fontcolor="#495057";')
        lines += ["  " + node_line(n) for n in NODES.values() if n.group == group]
        lines.append("  }")
    arch = set(ARCH_EDGES)
    for a, b in ARCH_EDGES:
        if (a, b) in active:
            continue
        style = 'color="#dee2e6", style="dashed"' if trace else 'color="#868e96"'
        lines.append(f"  {_q(a)} -> {_q(b)} [{style}];")
    for (a, b), nums in active.items():
        color = _EDGE_COLOR[edge_status[(a, b)]]
        extra = "" if (a, b) in arch else ', style="dashed", constraint="false"'
        label = ", ".join(map(str, nums))
        lines.append(f'  {_q(a)} -> {_q(b)} [color="{color}", fontcolor="{color}", penwidth="2.2", '
                     f"label={_q(label)}{extra}];")
    lines.append("}")
    return "\n".join(lines)
