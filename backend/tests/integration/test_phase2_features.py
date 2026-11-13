from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.foundation.config import Settings
from app.foundation.main import create_app
from app.foundation.models import AuditEvent


TOKEN = "phase-two-admin-token"


def client_for_phase2():
    app = create_app(Settings(database_url="sqlite://", log_level="CRITICAL", admin_token=TOKEN))
    return app, TestClient(app, raise_server_exceptions=False)


def payload(**overrides):
    return {
        "agent_id": "agent.testnet",
        "sender": "agent.testnet",
        "recipient": "treasury.testnet",
        "amount_near": 1.25,
        **overrides,
    }


def admin():
    return {"Authorization": f"Bearer {TOKEN}"}


def test_evaluation_response_has_network_policy_version_timestamp_and_request_id():
    _, client = client_for_phase2()
    with client:
        response = client.post(
            "/api/v1/evaluations",
            headers={"Idempotency-Key": "phase-two-evaluation-01", "X-Request-ID": "audit-check-01"},
            json=payload(),
        )
    assert response.status_code == 202
    assert response.headers["X-Request-ID"] == "audit-check-01"
    body = response.json()
    assert body["network"] == "testnet"
    assert body["policy_version"] == 1
    assert body["request_timestamp"]


def test_global_kill_switch_blocks_intake_and_audits_state_change():
    _, client = client_for_phase2()
    with client:
        enabled = client.put("/api/v1/kill-switch", headers=admin(), json={"enabled": True})
        decision = client.post(
            "/api/v1/evaluations",
            headers={"Idempotency-Key": "phase-two-kill-switch"},
            json=payload(),
        )
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is True
    assert decision.json()["decision"] == "BLOCK"
    assert decision.json()["checks"]["global_kill_switch"] == "ENABLED"


def test_activity_is_available_without_admin_token_and_audit_chain_exports():
    _, client = client_for_phase2()
    with client:
        client.post(
            "/api/v1/evaluations",
            headers={"Idempotency-Key": "phase-two-activity"},
            json=payload(),
        )
        activity = client.get("/api/v1/activity")
        verified = client.get("/api/v1/audit/verify", headers=admin())
        json_export = client.get("/api/v1/audit/export?format=json", headers=admin())
        csv_export = client.get("/api/v1/audit/export?format=csv", headers=admin())
    assert activity.status_code == 200
    assert activity.json()[0]["event_type"] == "POLICY_DECISION"
    assert verified.json()["valid"] is True
    assert json_export.json()["integrity"]["valid"] is True
    assert "event_hash" in json_export.json()["events"][0]
    assert csv_export.status_code == 200
    assert "previous_hash,event_hash" in csv_export.text


def test_audit_integrity_detects_database_record_edit():
    app, client = client_for_phase2()
    with client:
        client.post(
            "/api/v1/evaluations",
            headers={"Idempotency-Key": "phase-two-tamper"},
            json=payload(),
        )
        with app.state.session_factory() as session:
            event = session.scalar(select(AuditEvent))
            event.details = {"edited": True}
            session.commit()
        verified = client.get("/api/v1/audit/verify", headers=admin())
    assert verified.json()["valid"] is False


def test_telegram_status_is_disabled_without_credentials_and_test_is_rejected():
    _, client = client_for_phase2()
    with client:
        status = client.get("/api/v1/telegram/status")
        test = client.post("/api/v1/telegram/test", headers=admin())
    assert status.json()["configured"] is False
    assert status.json()["status"] == "not_configured"
    assert test.status_code == 409
    assert test.json()["error"]["code"] == "TELEGRAM_NOT_CONFIGURED"


def test_policy_updates_create_immutable_revisions_and_reject_stale_versions():
    _, client = client_for_phase2()
    with client:
        policy = client.get("/api/v1/policy").json()
        updated = dict(policy, daily_limit_near=policy["daily_limit_near"] + 1)
        response = client.put("/api/v1/policy", headers=admin(), json=updated)
        history = client.get("/api/v1/policy/history").json()
        stale = client.put("/api/v1/policy", headers=admin(), json=updated)
    assert response.status_code == 200
    assert response.json()["policy"]["policy_version"] == policy["policy_version"] + 1
    assert [row["version"] for row in history] == [1, 2]
    assert history[1]["snapshot"]["daily_limit_near"] == updated["daily_limit_near"]
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "POLICY_VERSION_CONFLICT"
