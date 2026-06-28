from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["database"] == "ok"


def test_research_endpoint_starts_run() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/research",
            json={
                "company_name": "Anthropic",
                "prompt": "Analyze Anthropic IPO readiness",
                "use_mock_data": True,
            },
        )
        assert response.status_code == 202
        payload = response.json()
        assert payload["run_id"] == payload["report_id"]


def test_agent_tool_policy_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/api/agents/tools")
        assert response.status_code == 200
        payload = response.json()
        assert "Identity Resolution Agent" in payload["agents"]
        identity_tools = payload["agents"]["Identity Resolution Agent"]
        assert any(tool["tool_name"] == "company_search" for tool in identity_tools)
        assert any(tool["provider"] == "sec_edgar" for tool in identity_tools)
        sec_tools = payload["agents"]["SEC Filing Agent"]
        assert any(tool["tool_name"] == "full_text_search" for tool in sec_tools)


def test_monitoring_alerts_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/api/monitoring-alerts")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


def test_streaming_events_endpoint_replays_history() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/research",
            json={
                "company_name": "Anthropic",
                "prompt": "Analyze Anthropic IPO readiness",
                "use_mock_data": True,
            },
        )
        run_id = response.json()["run_id"]
        with client.stream("GET", f"/api/research/{run_id}/events") as stream:
            body = "".join(stream.iter_text())
        assert "Report Writer Agent" in body
        assert "Research workflow completed" in body
