from __future__ import annotations

import time
from pathlib import Path
from tempfile import TemporaryDirectory

import base58
from fastapi.testclient import TestClient

from app.foundation.config import Settings
from app.foundation.main import create_app
import app.foundation.main as foundation_main
from app.foundation.near_signer import NearCliKeychainTestnetSigner, derive_public_key


def client_for_dashboard():
    app = create_app(Settings(database_url="sqlite://", log_level="CRITICAL", admin_token="test-admin"))
    return TestClient(app, raise_server_exceptions=False)


def test_settings_report_keychain_signer_readiness_without_exposing_credentials(monkeypatch):
    calls = []
    monkeypatch.setattr(
        NearCliKeychainTestnetSigner,
        "keychain_status",
        classmethod(lambda cls, account, key: calls.append((account, key)) or "verified"),
    )
    settings = Settings(
        database_url="sqlite://",
        log_level="CRITICAL",
        near_transactions_enabled=True,
        near_sender_account="sender.testnet",
        near_public_key="ed25519:public-test-key",
    )

    app = create_app(settings)
    app.state.near_keychain_verification = (
        settings.near_sender_account, settings.near_public_key, "verified", time.monotonic()
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/settings")

    assert response.status_code == 200
    assert response.json()["transaction_signing_enabled"] is True
    assert response.json()["transaction_submission_enabled"] is False
    assert response.json()["signer_verified"] is True
    assert response.json()["transaction_readiness_status"] == "requires live Testnet preflight"
    assert response.json()["transaction_signer_status"] == "verified"
    assert "public-test-key" not in response.text
    assert calls == []

    app = create_app(settings)
    app.state.near_keychain_verification = (
        settings.near_sender_account,
        settings.near_public_key,
        "configured but not verified",
        time.monotonic(),
    )
    with TestClient(app) as client:
        unconfigured_response = client.get("/api/v1/settings")
    assert unconfigured_response.json()["transaction_signing_enabled"] is False
    assert unconfigured_response.json()["transaction_submission_enabled"] is False
    assert unconfigured_response.json()["signer_verified"] is False
    assert unconfigured_response.json()["transaction_signer_status"] == "configured but not verified"


def test_public_settings_do_not_invoke_keychain_query_before_admin_verification(monkeypatch):
    calls = []
    monkeypatch.setattr("app.foundation.dashboard_routes.shutil.which", lambda _name: "near.exe")
    monkeypatch.setattr(
        NearCliKeychainTestnetSigner,
        "configured_for_official_testnet",
        classmethod(lambda cls: True),
    )
    monkeypatch.setattr(
        NearCliKeychainTestnetSigner,
        "keychain_status",
        classmethod(lambda cls, account, key: calls.append((account, key)) or "verified"),
    )
    settings = Settings(
        database_url="sqlite://",
        log_level="CRITICAL",
        near_transactions_enabled=True,
        near_sender_account="sender.testnet",
        near_public_key="ed25519:public-test-key",
    )

    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/settings")

    assert response.json()["transaction_signer_status"] == "configured but not verified"
    assert response.json()["transaction_signing_enabled"] is False
    assert response.json()["transaction_submission_enabled"] is False
    assert calls == []


def test_settings_report_private_key_signer_and_keep_disabled_gate(monkeypatch):
    private_key = "ed25519:" + base58.b58encode(bytes(32)).decode("ascii")
    configured = Settings(
        database_url="sqlite://",
        log_level="CRITICAL",
        near_transactions_enabled=True,
        near_testnet_private_key=private_key,
        near_public_key=derive_public_key(private_key),
    )
    disabled = Settings(
        database_url="sqlite://",
        log_level="CRITICAL",
        near_transactions_enabled=False,
        near_testnet_private_key=private_key,
        near_public_key=derive_public_key(private_key),
    )

    with TestClient(create_app(configured)) as client:
        enabled_response = client.get("/api/v1/settings")
    with TestClient(create_app(disabled)) as client:
        disabled_response = client.get("/api/v1/settings")

    assert enabled_response.json()["transaction_signing_enabled"] is True
    assert enabled_response.json()["transaction_submission_enabled"] is False
    assert enabled_response.json()["signer_verified"] is True
    assert private_key not in enabled_response.text
    assert disabled_response.json()["transaction_signing_enabled"] is False
    assert disabled_response.json()["transaction_submission_enabled"] is False


def test_keychain_signer_readiness_remains_disabled_when_transaction_gate_is_off(monkeypatch):
    calls = []
    monkeypatch.setattr(
        NearCliKeychainTestnetSigner,
        "keychain_status",
        classmethod(lambda cls, account, key: calls.append((account, key)) or "verified"),
    )
    settings = Settings(
        database_url="sqlite://",
        log_level="CRITICAL",
        near_transactions_enabled=False,
        near_sender_account="sender.testnet",
        near_public_key="ed25519:public-test-key",
    )

    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/settings")

    assert response.json()["transaction_signer_status"] == "disabled"
    assert response.json()["transaction_signing_enabled"] is False
    assert response.json()["transaction_submission_enabled"] is False
    assert calls == []


def test_settings_reject_nonofficial_rpc_for_private_key_readiness():
    settings = Settings(
        database_url="sqlite://",
        log_level="CRITICAL",
        near_transactions_enabled=True,
        near_testnet_private_key="ed25519:private-test-placeholder",
        near_testnet_rpc_url="https://rpc.testnet.fastnear.com:8443/proxy",
    )
    try:
        create_app(settings)
    except ValueError as exc:
        assert "exactly match" in str(exc)
    else:
        raise AssertionError("application accepted a noncanonical RPC URL")


def test_foundation_module_description_includes_gated_testnet_signer():
    assert "non-executing policy intake" in foundation_main.__doc__
    assert "separately gated NEAR Testnet signer" in foundation_main.__doc__


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


def test_sqlite_initialization_preserves_records_across_app_restarts():
    repository_root = Path(__file__).resolve().parents[3]
    with TemporaryDirectory(prefix="agentguard-persistence-", dir=repository_root) as temporary_directory:
        database_path = Path(temporary_directory) / "nested" / "agentguard.sqlite3"
        settings = Settings(database_url=f"sqlite:///{database_path.as_posix()}", log_level="CRITICAL")
        with TestClient(create_app(settings)) as first_client:
            response = first_client.post(
                "/api/v1/evaluations",
                headers={"Idempotency-Key": "restart-persist-001"},
                json={
                    "agent_id": "agent.testnet",
                    "sender": "agent.testnet",
                    "recipient": "attacker.testnet",
                    "amount_near": 1,
                    "prompt": "normal request",
                },
            )
            assert response.status_code == 202

        with TestClient(create_app(settings)) as second_client:
            overview = second_client.get("/api/v1/overview").json()

        assert overview["total_requests"] == 1
        assert overview["blocked_count"] == 1


def test_hackathon_dashboard_is_served_from_independent_app():
    with client_for_dashboard() as client:
        response = client.get("/dashboard")
        overview = client.get("/api/v1/overview")

    assert response.status_code == 200
    assert '<meta name="agentguard-api-base" content="">' in response.text
    assert overview.status_code == 200
    assert "AgentGuard AI | NEAR Hackathon 2026" in response.text
    assert "Transaction Security Center" in response.text
    assert "Telegram Monitoring" in response.text
    assert "innerHTML" not in response.text
    assert "onclick=" not in response.text
    for section in (
        "overview", "agents", "threats", "policy", "transactions", "approvals",
        "near", "simulation", "audit", "emergency", "telegram", "settings",
    ):
        assert f'id="{section}"' in response.text


def test_hackathon_dashboard_is_present_in_project_folder():
    repository = Path(__file__).resolve().parents[3]
    assert (repository / "frontend" / "dashboard.html").is_file()
