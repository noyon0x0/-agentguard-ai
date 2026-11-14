from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.foundation.config import Settings
from app.foundation.main import create_app
from app.foundation.models import AuditEvent, SimulationRun


def test_run_all_executes_real_engine_scenarios_and_records_scorecard():
    app = create_app(Settings(database_url="sqlite://", log_level="CRITICAL", admin_token="simulation-admin-token"))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/simulation/run-all",
            headers={"Authorization": "Bearer simulation-admin-token"},
        )
        scorecard = client.get(
            "/api/v1/simulation/scorecard",
            headers={"Authorization": "Bearer simulation-admin-token"},
        ).json()
        with client.app.state.session_factory() as session:
            simulation_audits = session.scalar(
                select(func.count(AuditEvent.id)).where(AuditEvent.event_type == "SIMULATION_TEST")
            )
            simulation_rows = session.scalars(select(SimulationRun)).all()

    assert response.status_code == 200, response.text
    body = response.json()
    results = body["results"]
    expected_names = {
        "safe-payment",
        "prompt-injection",
        "wallet-drainer",
        "blacklisted-recipient",
        "unknown-recipient",
        "large-payout",
        "duplicate-transaction",
        "rapid-transaction-burst",
        "frozen-agent",
        "unauthorized-tool-call",
        "invalid-contract",
        "expired-human-approval",
        "unauthorized-recipient-payment",
        "prompt-injection-payment-override",
        "spending-limit-bypass",
        "duplicate-payment-replay",
        "unauthorized-contract-method",
    }
    assert {item["scenario"] for item in results} == expected_names
    assert len({item["test_id"] for item in results}) == 17
    assert all(item["expected_decision"] == item["actual_decision"] for item in results)
    assert all(item["passed"] for item in results)
    assert all(item["execution_ms"] >= 0 for item in results)
    assert body["transaction_execution"] == "disabled"
    assert body["scorecard"]["total"] == 17
    assert body["scorecard"]["passed"] == 17
    assert body["scorecard"]["failed"] == 0
    assert scorecard["total"] == 17
    assert simulation_audits == 17
    assert len(simulation_rows) == 17


def test_attack_scenarios_return_blocked_signer_and_persist_evidence():
    app = create_app(Settings(database_url="sqlite://", log_level="CRITICAL", admin_token="simulation-admin-token"))
    scenarios = (
        "unauthorized-recipient-payment", "prompt-injection-payment-override",
        "spending-limit-bypass", "duplicate-payment-replay", "unauthorized-contract-method",
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        results = [client.post(f"/api/v1/simulation/run/{name}", headers={"Authorization": "Bearer simulation-admin-token"}).json() for name in scenarios]
        with client.app.state.session_factory() as session:
            evidence = session.scalars(select(AuditEvent).where(AuditEvent.event_type == "ATTACK_EXECUTION_EVIDENCE")).all()
    assert all(result["actual_decision"] == "BLOCK" and result["passed"] for result in results)
    assert all(result["execution_evidence"]["signer_invoked"] is False for result in results)
    assert all(result["execution_evidence"]["broadcast"] is False for result in results)
    assert len(evidence) == 5
    assert all(row.details["signer_invoked"] is False and row.details["broadcast"] is False for row in evidence)


def test_simulation_lab_rejects_unauthorized_run_and_unknown_scenario():
    app = create_app(Settings(database_url="sqlite://", log_level="CRITICAL", admin_token="simulation-admin-token"))
    with TestClient(app, raise_server_exceptions=False) as client:
        unauthorized = client.post("/api/v1/simulation/run-all")
        unknown = client.post(
            "/api/v1/simulation/run/not-a-scenario",
            headers={"Authorization": "Bearer simulation-admin-token"},
        )

    assert unauthorized.status_code == 401
    assert unknown.status_code == 404
