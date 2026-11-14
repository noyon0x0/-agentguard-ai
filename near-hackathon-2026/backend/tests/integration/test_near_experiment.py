from fastapi.testclient import TestClient
import base58
from sqlalchemy import select

from app.foundation.config import Settings
from app.foundation.main import create_app
from app.foundation.models import AuditEvent, PolicyConfiguration
from app.foundation.near_client import NearRpcUnavailable
from app.foundation.near_signer import NearCliKeychainTestnetSigner, derive_public_key
from app.foundation.near_signer import NearSignerError

TX_HASH = "HEgnVQZfs9uJzrqTob4g2Xmebqodq9waZvApSkrbcAhd"
TEST_PRIVATE_KEY = "ed25519:" + base58.b58encode(bytes(32)).decode("ascii")
TEST_PUBLIC_KEY = derive_public_key(TEST_PRIVATE_KEY)


class FakeNear:
    def __init__(self, *, fail=False, success=True, key_matches=True):
        self.fail = fail
        self.success = success
        self.key_matches = key_matches

    def verify_network(self):
        if self.fail:
            raise NearRpcUnavailable("sanitized")
        return {"network": "testnet"}

    def get_account(self, account_id):
        if self.fail:
            raise NearRpcUnavailable("sanitized")
        return {"account_id": account_id, "balance_near": "2.0"}

    def get_access_keys(self, account_id):
        public_key = TEST_PUBLIC_KEY if self.key_matches else "ed25519:not-the-configured-key"
        return {"keys": [{"public_key": public_key, "permission": "FullAccess"}]}

    def get_transaction(self, tx_hash, sender):
        return {
            "verified": True, "execution_succeeded": self.success, "network": "testnet",
            "transaction_hash": tx_hash, "sender_account_id": sender,
            "execution_status": {"SuccessValue": ""} if self.success else {"Failure": {"error_message": "failed"}},
            "explorer_url": f"https://explorer.testnet.near.org/transactions/{tx_hash}",
        }


class FakeSigner:
    calls = []

    def __init__(self, *args):
        pass

    def send_transfer(self, sender, recipient, amount_yocto):
        self.calls.append((sender, recipient, amount_yocto))
        return TX_HASH


def make_client(monkeypatch, *, rpc=None, success=True):
    FakeSigner.calls = []
    monkeypatch.setattr("app.foundation.near_experiment.PyNearTestnetSigner", FakeSigner)
    settings = Settings(
        database_url="sqlite://", log_level="CRITICAL", admin_token="near-experiment-admin",
        near_testnet_rpc_url="https://rpc.testnet.fastnear.com", near_sender_account="sender.testnet",
        near_authorized_recipient="treasury.testnet", near_unauthorized_recipient="attacker.testnet",
        near_testnet_private_key=TEST_PRIVATE_KEY, near_public_key="", near_transactions_enabled=True,
    )
    app = create_app(settings)
    app.state.near_client = rpc or FakeNear(success=success)
    return app, TestClient(app, raise_server_exceptions=False), {
        "Authorization": "Bearer near-experiment-admin",
        "X-Live-Testnet-Transfer-Confirmation": "CONFIRM TESTNET TRANSFER",
    }


def test_authorized_testnet_transfer_runs_policy_then_verifies_final_status(monkeypatch):
    app, client, headers = make_client(monkeypatch)
    with client:
        response = client.post("/api/v1/near/experiment/transactions", headers={**headers, "Idempotency-Key": "authorized-0001"}, json={
            "recipient": "treasury.testnet", "amount_near": "0.01", "prompt": "Approved demo payment",
        })
        waiting = response.json()
        assert waiting["signer_invoked"] is False
        response = client.post(f"/api/v1/near/experiment/transactions/{waiting['request_id']}/confirm", headers=headers)
        with client.app.state.session_factory() as db:
            audits = db.scalars(select(AuditEvent).where(AuditEvent.event_type == "NEAR_TESTNET_TRANSACTION")).all()
    body = response.json()
    assert response.status_code == 200
    assert body["decision"] == "ALLOW"
    assert body["signer_invoked"] is True
    assert body["execution"]["status"] == "SUCCESS"
    assert body["execution"]["execution_succeeded"] is True
    assert body["execution"]["transaction_hash"] == TX_HASH
    assert len(FakeSigner.calls) == 1
    assert FakeSigner.calls[0][2] == 10**22
    assert len(audits) == 2 and audits[-1].details["transaction_hash"] == TX_HASH


def test_unauthorized_recipient_and_limit_never_invoke_signer(monkeypatch):
    app, client, headers = make_client(monkeypatch)
    with client:
        unauthorized = client.post("/api/v1/near/experiment/transactions", headers={**headers, "Idempotency-Key": "unauth-0001"}, json={
            "recipient": "attacker.testnet", "amount_near": "0.005",
        })
        oversized = client.post("/api/v1/near/experiment/transactions", headers={**headers, "Idempotency-Key": "oversize-0001"}, json={
            "recipient": "treasury.testnet", "amount_near": "0.01000001",
        })
    assert unauthorized.json()["decision"] == "BLOCK"
    assert oversized.json()["decision"] == "BLOCK"
    assert unauthorized.json()["signer_invoked"] is False
    assert oversized.json()["signer_invoked"] is False
    assert FakeSigner.calls == []


def test_warn_requires_approval_and_rpc_failure_fails_before_signer(monkeypatch):
    app, client, headers = make_client(monkeypatch)
    with client:
        with client.app.state.session_factory() as db:
            policy = db.get(PolicyConfiguration, 1)
            policy.review_threshold_near = 0.005
            db.commit()
        warned = client.post("/api/v1/near/experiment/transactions", headers={**headers, "Idempotency-Key": "warned-0001"}, json={
            "recipient": "treasury.testnet", "amount_near": "0.01",
        }).json()
        assert warned["decision"] == "WARN"
        assert warned["signer_invoked"] is False
        approved = client.post(f"/api/v1/near/experiment/transactions/{warned['request_id']}/approve", headers=headers).json()
        assert approved["execution"]["status"] == "AWAITING_EXPLICIT_CONFIRMATION"
        assert FakeSigner.calls == []
        approved = client.post(f"/api/v1/near/experiment/transactions/{warned['request_id']}/confirm", headers=headers).json()
        assert approved["execution"]["status"] == "SUCCESS"
        assert len(FakeSigner.calls) == 1

    app, client, headers = make_client(monkeypatch, rpc=FakeNear(fail=True))
    with client:
        waiting = client.post("/api/v1/near/experiment/transactions", headers={**headers, "Idempotency-Key": "rpc-failed-01"}, json={
            "recipient": "treasury.testnet", "amount_near": "0.01",
        }).json()
        failed = client.post(f"/api/v1/near/experiment/transactions/{waiting['request_id']}/confirm", headers=headers).json()
    assert failed["execution"]["status"] == "ERROR"
    assert failed["signer_invoked"] is False
    assert FakeSigner.calls == []


def test_failed_final_execution_status_is_not_reported_as_success(monkeypatch):
    app, client, headers = make_client(monkeypatch, success=False)
    with client:
        waiting = client.post("/api/v1/near/experiment/transactions", headers={**headers, "Idempotency-Key": "chain-fail-01"}, json={
            "recipient": "treasury.testnet", "amount_near": "0.01",
        }).json()
        response = client.post(f"/api/v1/near/experiment/transactions/{waiting['request_id']}/confirm", headers=headers)
    assert response.json()["execution"]["status"] == "FAILED"
    assert response.json()["execution"]["execution_succeeded"] is False


def test_submission_error_hash_is_still_finally_verified(monkeypatch):
    class HashReturningErrorSigner:
        def __init__(self, *args):
            pass

        def send_transfer(self, *args):
            raise NearSignerError("sanitized submission outcome", transaction_hash=TX_HASH)

    monkeypatch.setattr("app.foundation.near_experiment.PyNearTestnetSigner", HashReturningErrorSigner)
    _, client, headers = make_client(monkeypatch)
    with client:
        waiting = client.post("/api/v1/near/experiment/transactions", headers={**headers, "Idempotency-Key": "submit-timeout-01"}, json={
            "recipient": "treasury.testnet", "amount_near": "0.01",
        }).json()
        result = client.post(f"/api/v1/near/experiment/transactions/{waiting['request_id']}/confirm", headers=headers).json()
    assert result["execution"]["transaction_hash"] == TX_HASH
    assert result["execution"]["status"] == "SUCCESS"
    assert result["execution"]["execution_succeeded"] is True


def test_experiment_status_never_returns_server_key(monkeypatch):
    _, client, headers = make_client(monkeypatch)
    with client:
        response = client.get("/api/v1/near/experiment/status", headers=headers)
    assert response.status_code == 200
    assert response.json()["signer_configured"] is True
    assert response.json()["account_verified"] is True
    assert response.json()["faucet_funding_status"] == "balance_confirmed_by_testnet_rpc"
    assert response.json()["public_key"] == TEST_PUBLIC_KEY
    assert response.json()["public_wallet_address"] == "sender.testnet"
    assert "private" not in response.text.casefold()
    assert TEST_PRIVATE_KEY not in response.text


def test_nonmatching_signer_access_key_fails_before_signer(monkeypatch):
    _, client, headers = make_client(monkeypatch, rpc=FakeNear(key_matches=False))
    with client:
        waiting = client.post("/api/v1/near/experiment/transactions", headers={**headers, "Idempotency-Key": "key-mismatch-01"}, json={
            "recipient": "treasury.testnet", "amount_near": "0.01",
        }).json()
        response = client.post(f"/api/v1/near/experiment/transactions/{waiting['request_id']}/confirm", headers=headers)
    assert response.json()["execution"]["status"] == "ERROR"
    assert response.json()["execution"]["error_code"] == "NEAR_PREFLIGHT_REJECTED"
    assert response.json()["signer_invoked"] is False
    assert FakeSigner.calls == []


def test_live_transfer_feature_defaults_to_disabled(monkeypatch):
    from app.foundation.near_experiment import _live_configuration

    settings = Settings(near_transactions_enabled=False)
    try:
        _live_configuration(settings)
    except Exception as exc:
        assert getattr(exc, "detail", {}).get("code") == "NEAR_TESTNET_TRANSACTIONS_DISABLED"
    else:
        raise AssertionError("Testnet transaction endpoint must default to disabled")


def test_keychain_signing_requires_an_exact_official_testnet_key_match(monkeypatch):
    import app.foundation.near_experiment as experiment

    monkeypatch.setattr(
        NearCliKeychainTestnetSigner,
        "keychain_status",
        classmethod(lambda cls, account, key: "verified"),
    )
    settings = Settings(
        near_sender_account="sender.testnet", near_authorized_recipient="treasury.testnet",
        near_unauthorized_recipient="attacker.testnet", near_public_key=TEST_PUBLIC_KEY,
        near_transactions_enabled=True,
    )
    sender, recipient = experiment._live_configuration(settings)
    assert sender == "sender.testnet" and recipient == "treasury.testnet"


def test_keychain_public_key_not_verified_blocks_live_configuration(monkeypatch):
    import app.foundation.near_experiment as experiment

    monkeypatch.setattr(
        NearCliKeychainTestnetSigner,
        "keychain_status",
        classmethod(lambda cls, account, key: "configured but not verified"),
    )
    settings = Settings(
        near_sender_account="sender.testnet",
        near_authorized_recipient="treasury.testnet",
        near_unauthorized_recipient="attacker.testnet",
        near_public_key=TEST_PUBLIC_KEY,
        near_transactions_enabled=True,
    )

    try:
        experiment._live_configuration(settings)
    except Exception as exc:
        assert getattr(exc, "detail", {}).get("code") == "NEAR_TESTNET_KEYCHAIN_SIGNER_NOT_READY"
    else:
        raise AssertionError("Unverified keychain signer must not enable transactions")


def test_status_keeps_transaction_readiness_false_when_keychain_verification_times_out(monkeypatch):
    monkeypatch.setattr(
        NearCliKeychainTestnetSigner,
        "keychain_status",
        classmethod(lambda cls, account, key: "configured but not verified"),
    )
    settings = Settings(
        database_url="sqlite://", log_level="CRITICAL", admin_token="near-experiment-admin",
        near_testnet_rpc_url="https://rpc.testnet.fastnear.com", near_sender_account="sender.testnet",
        near_authorized_recipient="treasury.testnet", near_unauthorized_recipient="attacker.testnet",
        near_testnet_private_key="", near_public_key=TEST_PUBLIC_KEY, near_transactions_enabled=True,
    )
    app = create_app(settings)
    app.state.near_client = FakeNear()
    client = TestClient(app, raise_server_exceptions=False)
    headers = {"Authorization": "Bearer near-experiment-admin"}

    with client:
        response = client.get("/api/v1/near/experiment/status", headers=headers)

    assert response.status_code == 200
    assert response.json()["signer_verified"] is False
    assert response.json()["transaction_ready"] is False


def test_allow_decision_waits_for_explicit_confirmation_and_confirmation_is_idempotent(monkeypatch):
    app, client, headers = make_client(monkeypatch)
    with client:
        request_result = client.post("/api/v1/near/experiment/transactions", headers={
            "Authorization": headers["Authorization"], "Idempotency-Key": "confirm-first-0001",
        }, json={"recipient": "treasury.testnet", "amount_near": "0.01"}).json()
        assert request_result["decision"] == "ALLOW"
        assert request_result["execution"]["status"] == "AWAITING_EXPLICIT_CONFIRMATION"
        assert request_result["signer_invoked"] is False
        assert FakeSigner.calls == []
        request_id = request_result["request_id"]
        missing_confirmation = client.post(f"/api/v1/near/experiment/transactions/{request_id}/confirm", headers={"Authorization": headers["Authorization"]})
        assert missing_confirmation.status_code == 428
        assert FakeSigner.calls == []
        confirmed = client.post(f"/api/v1/near/experiment/transactions/{request_id}/confirm", headers=headers).json()
        repeated = client.post(f"/api/v1/near/experiment/transactions/{request_id}/confirm", headers=headers).json()
    assert confirmed["execution"]["status"] == "SUCCESS"
    assert repeated["execution"]["transaction_hash"] == TX_HASH
    assert len(FakeSigner.calls) == 1


def test_four_testnet_attack_demonstrations_are_policy_blocked_without_signing(monkeypatch):
    app, client, headers = make_client(monkeypatch)
    with client:
        cases = ("unauthorized-recipient", "prompt-injection", "spending-limit", "duplicate-replay")
        results = {case: client.post(f"/api/v1/near/experiment/attacks/{case}", headers=headers).json() for case in cases}
        with client.app.state.session_factory() as db:
            evidence = db.scalars(select(AuditEvent).where(AuditEvent.event_type == "NEAR_ATTACK_SIMULATION")).all()
    assert results["unauthorized-recipient"]["decision"] == "BLOCK"
    assert results["prompt-injection"]["decision"] == "BLOCK"
    assert results["spending-limit"]["decision"] == "BLOCK"
    assert results["duplicate-replay"]["decision"] == "BLOCK"
    assert all(result["signer_invoked"] is False for result in results.values())
    assert all(result["transaction_hash"] is None for result in results.values())
    assert len(evidence) == 5  # replay scenario records both the original and replay attempt
