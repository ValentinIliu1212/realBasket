"""v3 architecture and API tests; do not require a running MCP server or LLM."""
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from real_basket.agent_service import api

ROOT = Path(__file__).resolve().parents[1]


def test_compose_has_four_services_and_separate_agent():
    services = yaml.safe_load((ROOT / 'docker-compose.yml').read_text(encoding='utf-8'))['services']
    assert set(services) == {'realbasket-ui', 'realbasket-agent', 'realbasket-mcp', 'weaviate'}
    assert services['realbasket-agent']['environment']['REALBASKET_MCP_URL'] == 'http://realbasket-mcp:8001/mcp'
    assert services['realbasket-ui']['environment']['REALBASKET_AGENT_URL'] == 'http://realbasket-agent:8002'
    assert 'REALBASKET_MCP_URL' not in services['realbasket-ui']['environment']
    assert services['realbasket-ui']['depends_on']['realbasket-agent']['condition'] == 'service_healthy'
    assert 'ports' not in services['realbasket-agent']


def test_ui_uses_only_agent_http_client():
    source = (ROOT / 'src/real_basket/ui/app.py').read_text(encoding='utf-8')
    assert 'from real_basket.agent_service.client import call_tool, chat, url' in source
    assert 'mcp_server.agent import ask' not in source
    assert 'mcp_server.client import call_tool' not in source


def test_api_health_and_tool_allowlist(monkeypatch):
    import sys
    from types import ModuleType
    stub = ModuleType('real_basket.mcp_server.client')
    stub.call_tool = lambda name, **kw: {'name': name, 'args': kw}
    monkeypatch.setitem(sys.modules, 'real_basket.mcp_server.client', stub)
    with TestClient(api.app) as c:
        assert c.get('/health').json()['status'] == 'ok'
        res = c.post('/tools/get_dashboard_snapshot', json={'arguments': {}})
        assert res.status_code == 200
        assert res.json()['result']['name'] == 'get_dashboard_snapshot'
        assert c.post('/tools/ingest_reference_pdfs', json={'arguments': {}}).status_code == 404


def test_api_chat_delegates_to_agent_and_runs_guardrail(monkeypatch):
    # Avoid importing Strands/LLM by patching the lazily loaded module below.
    import json
    import sys
    from types import ModuleType
    big = {'essential_yoy_pct': 2.93, 'prices': list(range(500))}
    messages = [
        {'role': 'user', 'content': [{'text': 'Test'}]},
        {'role': 'assistant', 'content': [{'toolUse': {'toolUseId': 't1', 'name': 'calculate_index',
                                                       'input': {'months': 24}}}]},
        {'role': 'user', 'content': [{'toolResult': {'toolUseId': 't1', 'status': 'success',
                                                     'content': [{'text': json.dumps(big)}]}}]},
        {'role': 'assistant', 'content': [{'text': 'ECLI 2,93 %, VPI 9,99 %'}]},
    ]
    stub = ModuleType('real_basket.mcp_server.agent')
    stub.ask = lambda question, history: ('ECLI 2,93 %, VPI 9,99 %', ['calculate_index'], messages)
    monkeypatch.setitem(sys.modules, 'real_basket.mcp_server.agent', stub)
    with TestClient(api.app) as c:
        r = c.post('/chat', json={'question': 'Test', 'history': []})
        assert r.status_code == 200
        body = r.json()
        assert body['answer'] == 'ECLI 2,93 %, VPI 9,99 %' and body['tools'] == ['calculate_index']
        assert body['unverified'] == ['9,99'] and body['figures_checked'] == 2
        result = body['trace_messages'][2]['content'][0]['toolResult']
        assert result['status'] == 'success' and result['content'] == [{'json': {}}]   # payload not forwarded
