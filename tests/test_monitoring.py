"""Monitoring: use-case paths of the four Docker services (no Streamlit, no MCP runtime, no LLM)."""
import itertools

from real_basket.agents.trace import compact_messages
from real_basket.ui import monitoring as mon


def _turn(tool: str, result: dict | None = None, status: str = "success") -> list:
    import json
    msgs = [{"role": "user", "content": [{"text": "Frage"}]},
            {"role": "assistant", "content": [{"toolUse": {"toolUseId": "t1", "name": tool, "input": {"months": 24}}}]},
            {"role": "user", "content": [{"toolResult": {"toolUseId": "t1", "status": status,
                                                         "content": [{"text": json.dumps(result or {"x": 1})}]}}]},
            {"role": "assistant", "content": [{"text": "Antwort"}]}]
    return compact_messages(msgs)


def test_every_node_and_edge_is_known():
    for a, b in mon.ARCH_EDGES:
        assert a in mon.NODES and b in mon.NODES
    for node in mon.NODES.values():
        assert node.group == "" or node.group in mon.GROUPS
    for hops in mon.TOOL_HOPS.values():
        for a, b in hops:
            assert (a, b) in mon.ARCH_EDGES, (a, b)
    assert {"ui", "agent", "mcp", "weaviate"} <= set(mon.GROUPS)   # one group per Docker Compose service


def test_ui_tool_trace_passes_the_agent_api_allow_list():
    t = mon.ui_tool_trace("get_dashboard_snapshot", {}, 0.2, result_info="11 Prüfungen")
    path = [(s.source, s.target) for s in t.steps]
    assert path[:4] == [("user", "ui"), ("ui", "api_client"), ("api_client", "agent_api"), ("agent_api", "mcp_client")]
    assert ("mcp_dashboard", "core") in path and ("data", "sqlite") in path
    assert ("data", "pdfs") not in path                             # PDFs are only read by the import
    assert t.status == "ok" and "gecacht" in t.note
    assert not any(s.target == "llm" for s in t.steps)              # deterministic: no LLM involved


def test_ui_tool_trace_error_and_search_note():
    t = mon.ui_tool_trace("search_documents", {"query": "Miete"}, 1.0, error="Weaviate down")
    assert t.status == "error" and "Zahlen kommen nie" in t.note
    assert ("mcp_vector", "weaviate") in [(s.source, s.target) for s in t.steps]
    blocked = mon.ui_tool_trace("ingest_reference_pdfs", {}, 0.1, error="Tool not available through UI gateway")
    assert ("agent_api", "api_client") in [(s.source, s.target) for s in blocked.steps]
    assert not any(s.source == "mcp_client" for s in blocked.steps)


def test_chat_trace_follows_llm_and_tool_calls():
    t = mon.chat_trace("Wie hoch ist der ECLI?", _turn("calculate_index", {"essential_yoy_pct": 2.93}),
                       "Antwort", [], 1, 2.5)
    actions = [s.action for s in t.steps]
    assert actions.count("tools/call") == 1 and "LLM-Aufruf 2" in actions
    assert ("mcp_data", "core") in [(s.source, s.target) for s in t.steps]
    assert ("agent_api", "guardrail") in [(s.source, s.target) for s in t.steps]
    assert t.status == "ok" and "2 LLM-Aufrufe" in t.note


def test_chat_trace_flags_tool_errors_and_unverified_figures():
    t = mon.chat_trace("x", _turn("search_documents", {"error": "no embeddings"}), "Antwort", ["9,99"])
    assert t.status == "warn"
    assert any("9,99" in s.detail for s in t.steps)
    failed = mon.chat_trace("x", [], error="Agent/MCP failure")
    assert failed.status == "error"


def test_compact_messages_drop_large_payloads():
    msgs = _turn("get_dashboard_snapshot", {"prices": list(range(1000)), "passages": [1, 2, 3]})
    result = msgs[2]["content"][0]["toolResult"]
    assert result["content"] == [{"json": {"passages": 3}}]
    assert msgs[1]["content"][0]["toolUse"]["name"] == "get_dashboard_snapshot"


def test_fallback_without_trace_messages():
    t = mon.chat_trace("x", mon.messages_from_tools(["get_prices", "calculate_index"]), "Antwort")
    assert [s.detail.split("(")[0] for s in t.steps if s.action == "tools/call"] == ["get_prices", "calculate_index"]


def test_unknown_and_prefixed_tool_names():
    assert mon.tool_name("realbasket_get_cpi") == "get_cpi"
    t = mon.chat_trace("x", _turn("does_not_exist"), "Antwort")
    assert t.status == "warn"


def test_dot_highlights_the_numbered_path():
    t = mon.ui_tool_trace("generate_reports", {}, 0.5, result_info="5 PDFs")
    dot = mon.to_dot(t)
    assert dot.startswith("digraph") and dot.rstrip().endswith("}")
    assert 'label="1"' in dot and "cluster_weaviate" in dot
    assert mon.to_dot(None).count("->") == len(mon.ARCH_EDGES)


def test_trace_rows_and_ids():
    a, b = mon.new_chat_trace(4), mon.new_chat_trace(0)
    assert b.id > a.id and a.rows()[0]["Von"] == "👤 Nutzer"
    assert all(isinstance(r["#"], int) for r in itertools.chain(a.rows(), b.rows()))
