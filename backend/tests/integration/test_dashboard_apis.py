from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.foundation.config import Settings
from app.foundation.main import create_app


def client_for_dashboard():
    app = create_app(Settings(database_url="sqlite://", log_level="CRITICAL", admin_token="test-admin"))
    return TestClient(app, raise_server_exceptions=False)


def test_dashboard_read_apis_return_persisted_and_runtime_state():
    with client_for_dashboard() as client:
        overview = client.get("/api/v1/overview").json()
        agents = client.get("/api/v1/agents").json()
        threats = client.get("/api/v1/threats").json()
        telegram = client.get("/api/v1/telegram/status").json()
        settings = client.get("/api/v1/settings").json()
        audit = client.get("/api/v1/audit/summary").json()

    assert overview == {
        "total_requests": 0,
        "approved_count": 0,
        "review_count": 0,
        "blocked_count": 0,
        "evaluated_amount_near": 0.0,
        "last_evaluation_at": None,
        "execution_enabled": False,
        "policy_version": 1,
        "global_kill_switch": False,
    }
    assert any(agent["agent_id"] == "agent.testnet" for agent in agents)
    assert threats["source"] == "local_policy_engine"
    assert threats["external_feed_configured"] is False
    assert telegram["status"] == "not_configured"
    assert settings["database_backend"] == "sqlite"
    assert settings["transaction_submission_enabled"] is False
    assert audit["event_count"] == 0


def test_dashboard_aggregates_update_from_real_evaluations():
    with client_for_dashboard() as client:
        evaluated = client.post(
            "/api/v1/evaluations",
            headers={"Idempotency-Key": "dashboard-test-001"},
            json={
                "agent_id": "agent.testnet",
                "sender": "agent.testnet",
                "recipient": "attacker.testnet",
                "amount_near": 1,
                "prompt": "normal request",
            },
        )
        overview = client.get("/api/v1/overview").json()
        threats = client.get("/api/v1/threats").json()
        agent = next(item for item in client.get("/api/v1/agents").json() if item["agent_id"] == "agent.testnet")

    assert evaluated.json()["decision"] == "BLOCK"
    assert overview["total_requests"] == 1
    assert overview["blocked_count"] == 1
    assert agent["evaluation_count"] == 1
    assert len(threats["recent_blocks"]) == 1


def test_v4_dashboard_is_served_without_replacing_legacy_page():
    with client_for_dashboard() as client:
        response = client.get("/dashboard-v4")

    assert response.status_code == 200
    assert "AgentGuard AI v4" in response.text
    assert "Transaction Security Center" in response.text
    assert "Telegram Monitoring" in response.text
    assert "innerHTML" not in response.text
    assert "onclick=" not in response.text
    for section in (
        "overview", "agents", "threats", "policy", "transactions", "approvals",
        "near", "simulation", "audit", "emergency", "telegram", "settings",
    ):
        assert f'id="{section}"' in response.text


def test_v4_dashboard_exists_as_additive_file():
    repository = Path(__file__).resolve().parents[3]
    assert (repository / "frontend" / "dashboard_v4.html").is_file()
    assert (repository / "frontend" / "dashboard_v3.html").is_file()
