from __future__ import annotations

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app import main, main_v2, main_v3
from app.foundation.config import Settings
from app.foundation.main import create_app


ADMIN_TOKEN = "legacy-v3-test-admin-token"


@pytest.fixture
def legacy_client(monkeypatch):
    monkeypatch.setattr(main_v3.app.state, "admin_token", ADMIN_TOKEN, raising=False)
    return TestClient(main_v3.app)


@pytest.fixture
def legacy_entrypoint_clients(monkeypatch):
    for legacy_app in (main.app, main_v2.app):
        monkeypatch.setattr(legacy_app.state, "admin_token", ADMIN_TOKEN, raising=False)
    return TestClient(main.app), TestClient(main_v2.app)


LEGACY_ENTRYPOINT_REQUESTS = [
    (0, "get", "/audit-logs", None),
    (0, "post", "/payment/check", {"recipient": "demo.near", "amount": 1}),
    (0, "post", "/payment/review/not-found", {"action": "REJECT"}),
    (0, "post", "/audit-logs/clear", None),
    (1, "get", "/api/state", None),
    (1, "post", "/api/evaluate", {"prompt": "safe", "recipient": "treasury.testnet", "amount_near": 1}),
    (1, "post", "/api/policy", {"max_single_tx_near": 10, "daily_spend_limit_near": 25, "hitl_threshold_near": 5, "block_prompt_injection": True, "strict_whitelist_mode": True}),
    (1, "post", "/api/hitl", {"tx_id": "not-found", "action": "REJECT"}),
]


@pytest.mark.parametrize("client_index,method,path,payload", LEGACY_ENTRYPOINT_REQUESTS)
@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid-token"}])
def test_v1_and_v2_sensitive_routes_reject_missing_or_invalid_tokens(
    legacy_entrypoint_clients, client_index, method, path, payload, headers
):
    client = legacy_entrypoint_clients[client_index]
    request = getattr(client, method)
    options = {"headers": headers}
    if payload is not None:
        options["json"] = payload
    response = request(path, **options)
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "UNAUTHORIZED"


def test_valid_token_can_read_v1_and_v2_sensitive_state(legacy_entrypoint_clients):
    headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    v1, v2 = legacy_entrypoint_clients
    assert v1.get("/audit-logs", headers=headers).status_code == 200
    assert v2.get("/api/state", headers=headers).status_code == 200


LEGACY_API_REQUESTS = [
    ("get", "/api/state", None),
    ("post", "/api/wallet/connect", {"wallet_id": "verified.testnet"}),
    ("post", "/api/policy", {
        "max_single_tx_near": 10,
        "hitl_threshold_near": 5,
        "block_prompt_injection": True,
        "strict_whitelist_mode": True,
        "velocity_guard_enabled": True,
        "telegram_alerts_enabled": False,
    }),
    ("post", "/api/wallets", {"list_type": "whitelist", "action": "add", "wallet": "safe.testnet"}),
    ("post", "/api/agent/freeze", {"agent_id": "External-Plugin-Agent", "frozen": False}),
    ("post", "/api/evaluate", {
        "agent_id": "DeFi-Trader-Bot",
        "prompt": "Evaluate authorized demo payment",
        "recipient": "treasury.testnet",
        "amount_near": 1,
    }),
    ("post", "/api/hitl", {"tx_id": "not-pending", "action": "REJECT"}),
]


@pytest.mark.parametrize("method,path,payload", LEGACY_API_REQUESTS)
@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid-token"}])
def test_every_legacy_v3_api_route_rejects_missing_or_invalid_token(
    legacy_client, method, path, payload, headers
):
    request = getattr(legacy_client, method)
    options = {"headers": headers}
    if payload is not None:
        options["json"] = payload
    response = request(path, **options)
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "UNAUTHORIZED"


def test_valid_admin_token_can_read_legacy_state_and_change_legacy_policy(legacy_client):
    headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

    state = legacy_client.get("/api/state", headers=headers)
    assert state.status_code == 200
    assert "pending_queue" in state.json()

    update = legacy_client.post("/api/policy", headers=headers, json=LEGACY_API_REQUESTS[2][2])
    assert update.status_code == 200
    assert update.json()["status"] == "ok"


def test_default_configuration_has_no_known_admin_credential(monkeypatch):
    monkeypatch.delenv("AGENTGUARD_ADMIN_TOKEN", raising=False)
    assert Settings().admin_token == ""
    assert Settings.from_environment().admin_token == ""

    monkeypatch.setattr(main_v3.app.state, "admin_token", "", raising=False)
    response = TestClient(main_v3.app).get("/api/state")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "ADMIN_AUTH_NOT_CONFIGURED"

    v4_response = TestClient(create_app(Settings(database_url="sqlite://", log_level="CRITICAL"))).get(
        "/api/v1/audit"
    )
    assert v4_response.status_code == 503


def test_legacy_v3_dashboard_sends_bearer_token_without_browser_storage():
    repository = Path(__file__).resolve().parents[3]
    markup = (repository / "frontend" / "dashboard_v3.html").read_text(encoding="utf-8")
    assert 'id="legacyAdminToken" type="password"' in markup
    assert "headers.set('Authorization', `Bearer ${adminToken}`)" in markup
    assert "localStorage" not in markup
    assert "sessionStorage" not in markup
    for path in ("/api/state", "/api/evaluate", "/api/hitl", "/api/policy"):
        assert f"apiFetch('{path}')" in markup or f"apiFetch('{path}'," in markup
