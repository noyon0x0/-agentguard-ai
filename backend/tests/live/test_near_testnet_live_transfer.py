"""Explicitly opt-in Testnet transfer smoke test; skipped by default."""

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.foundation.config import Settings
from app.foundation.main import create_app


pytestmark = pytest.mark.skipif(
    os.getenv("NEAR_HACKATHON_AGENTGUARD_RUN_LIVE_NEAR_TEST", "").casefold() != "true",
    reason="Set NEAR_HACKATHON_AGENTGUARD_RUN_LIVE_NEAR_TEST=true to submit one 0.01 NEAR Testnet transfer",
)


def test_explicit_live_testnet_transfer_has_verified_final_status():
    settings = Settings.from_environment()
    assert settings.near_transactions_enabled is True
    assert settings.near_testnet_private_key
    assert settings.near_sender_account and settings.near_authorized_recipient
    app = create_app(settings)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/near/experiment/transactions",
            headers={
                "Authorization": f"Bearer {settings.admin_token}",
                "Idempotency-Key": f"live-test-{uuid.uuid4().hex}",
            },
            json={"recipient": settings.near_authorized_recipient, "amount_near": "0.01", "prompt": "Explicit live Testnet integration test"},
        )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["decision"] == "ALLOW"
    assert result["signer_invoked"] is True
    assert result["execution"]["execution_succeeded"] is True
    assert result["execution"]["status"] == "SUCCESS"
    assert result["execution"]["transaction_hash"]
    assert result["execution"]["explorer_url"].startswith("https://explorer.testnet.near.org/transactions/")
