from __future__ import annotations

from fastapi.testclient import TestClient

from app.foundation.config import Settings
from app.foundation.main import create_app

TX_HASH = "HEgnVQZfs9uJzrqTob4g2Xmebqodq9waZvApSkrbcAhd"


class MockResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def rpc_result(result):
    return MockResponse({"jsonrpc": "2.0", "id": "mock", "result": result})


def make_client():
    app = create_app(
        Settings(database_url="sqlite://", log_level="CRITICAL", near_testnet_rpc_url="https://rpc.testnet.near.org")
    )
    return app, TestClient(app, raise_server_exceptions=False)


def test_rpc_health_verifies_network_and_records_monitoring(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return rpc_result({"chain_id": "testnet", "latest_block_height": 123})

    monkeypatch.setattr("app.foundation.near_client.requests.post", fake_post)
    app, client = make_client()
    with client:
        response = client.get("/api/v1/near/health")

    assert response.status_code == 200
    assert response.json()["network"] == "testnet"
    assert response.json()["status"] == "healthy"
    assert calls[0][1]["json"]["method"] == "status"
    assert calls[0][1]["timeout"] == 5.0
    assert app.state.near_client.last_health.status == "healthy"


def test_wrong_network_fails_closed(monkeypatch):
    monkeypatch.setattr(
        "app.foundation.near_client.requests.post",
        lambda *args, **kwargs: rpc_result({"chain_id": "mainnet"}),
    )
    app, client = make_client()
    with client:
        response = client.get("/api/v1/near/health")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "NEAR_WRONG_NETWORK"
    assert app.state.near_client.last_health.status == "unhealthy"


def test_account_balance_lookup_uses_verified_testnet_response(monkeypatch):
    responses = iter(
        [
            rpc_result({"chain_id": "testnet"}),
            rpc_result(
                {
                    "amount": "1234500000000000000000000",
                    "locked": "0",
                    "storage_usage": 182,
                    "code_hash": "11111111111111111111111111111111",
                }
            ),
        ]
    )
    monkeypatch.setattr("app.foundation.near_client.requests.post", lambda *args, **kwargs: next(responses))
    _, client = make_client()
    with client:
        response = client.get("/api/v1/near/accounts/alice.testnet")

    assert response.status_code == 200
    assert response.json()["network"] == "testnet"
    assert response.json()["balance_near"] == "1.2345"
    assert response.json()["is_contract"] is False


def test_account_not_found_is_returned_as_not_found(monkeypatch):
    responses = iter(
        [
            rpc_result({"chain_id": "testnet"}),
            MockResponse(
                {
                    "jsonrpc": "2.0",
                    "id": "mock",
                    "error": {"code": -32000, "message": "Account does not exist"},
                }
            ),
        ]
    )
    monkeypatch.setattr("app.foundation.near_client.requests.post", lambda *args, **kwargs: next(responses))
    _, client = make_client()
    with client:
        response = client.get("/api/v1/near/accounts/missing.testnet")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NEAR_ACCOUNT_NOT_FOUND"


def test_query_rpc_unavailability_is_reported_without_leaking_provider_error(monkeypatch):
    calls = []

    def unavailable(url, **kwargs):
        calls.append(kwargs["json"]["method"])
        if kwargs["json"]["method"] == "status":
            return rpc_result({"chain_id": "testnet"})
        raise __import__("requests").Timeout("private upstream diagnostics")

    monkeypatch.setattr("app.foundation.near_client.requests.post", unavailable)
    _, client = make_client()
    with client:
        response = client.get("/api/v1/near/accounts/alice.testnet")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "NEAR_RPC_UNAVAILABLE"
    assert "private upstream diagnostics" not in response.text
    assert calls == ["status", "query"]


def test_invalid_account_ids_are_rejected_without_rpc_call(monkeypatch):
    calls = []
    monkeypatch.setattr("app.foundation.near_client.requests.post", lambda *args, **kwargs: calls.append(args))
    _, client = make_client()
    with client:
        response = client.get("/api/v1/near/accounts/Bad%20Account")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_NEAR_ACCOUNT_ID"
    assert calls == []


def test_invalid_transaction_hash_is_rejected_without_rpc_call(monkeypatch):
    calls = []
    monkeypatch.setattr("app.foundation.near_client.requests.post", lambda *args, **kwargs: calls.append(args))
    _, client = make_client()
    with client:
        response = client.get("/api/v1/near/transactions/not-a-hash?sender_account_id=alice.testnet")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_NEAR_TRANSACTION_REFERENCE"
    assert calls == []


def test_contract_validation_uses_deployed_code_hash(monkeypatch):
    responses = iter(
        [
            rpc_result({"chain_id": "testnet"}),
            rpc_result(
                {
                    "amount": "0",
                    "locked": "0",
                    "storage_usage": 8,
                    "code_hash": "8xvRrQContractCodeHashMocked",
                }
            ),
        ]
    )
    monkeypatch.setattr("app.foundation.near_client.requests.post", lambda *args, **kwargs: next(responses))
    _, client = make_client()
    with client:
        response = client.get("/api/v1/near/contracts/example.testnet")

    assert response.status_code == 200
    assert response.json()["is_contract"] is True
    assert response.json()["network"] == "testnet"


def test_verified_transaction_gets_testnet_explorer_link(monkeypatch):
    responses = iter(
        [
            rpc_result({"chain_id": "testnet"}),
            rpc_result(
                {
                    "transaction": {"hash": TX_HASH, "signer_id": "alice.testnet"},
                    "status": {"SuccessValue": ""},
                }
            ),
        ]
    )
    calls = []

    def fake_post(url, **kwargs):
        calls.append(kwargs["json"])
        return next(responses)

    monkeypatch.setattr("app.foundation.near_client.requests.post", fake_post)
    _, client = make_client()
    with client:
        response = client.get(
            f"/api/v1/near/transactions/{TX_HASH}?sender_account_id=alice.testnet"
        )

    assert response.status_code == 200
    assert response.json()["verified"] is True
    assert response.json()["explorer_url"] == f"https://explorer.testnet.near.org/transactions/{TX_HASH}"
    assert calls[1]["method"] == "tx"
    assert calls[1]["params"]["wait_until"] == "FINAL"


def test_missing_transaction_maps_to_not_found(monkeypatch):
    responses = iter(
        [
            rpc_result({"chain_id": "testnet"}),
            MockResponse(
                {
                    "jsonrpc": "2.0",
                    "id": "mock",
                    "error": {"code": -32000, "message": "Unknown transaction"},
                }
            ),
        ]
    )
    monkeypatch.setattr("app.foundation.near_client.requests.post", lambda *args, **kwargs: next(responses))
    _, client = make_client()
    with client:
        response = client.get(
            f"/api/v1/near/transactions/{TX_HASH}?sender_account_id=alice.testnet"
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NEAR_TRANSACTION_NOT_FOUND"


def test_transaction_identity_mismatch_never_returns_explorer_link(monkeypatch):
    responses = iter(
        [
            rpc_result({"chain_id": "testnet"}),
            rpc_result(
                {
                    "transaction": {"hash": "different", "signer_id": "alice.testnet"},
                    "status": {"SuccessValue": ""},
                }
            ),
        ]
    )
    monkeypatch.setattr("app.foundation.near_client.requests.post", lambda *args, **kwargs: next(responses))
    _, client = make_client()
    with client:
        response = client.get(
            f"/api/v1/near/transactions/{TX_HASH}?sender_account_id=alice.testnet"
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "NEAR_RPC_UNAVAILABLE"
    assert "explorer_url" not in response.text


def test_rpc_timeouts_are_reported_as_unavailable(monkeypatch):
    def timeout(*args, **kwargs):
        raise __import__("requests").Timeout("sensitive endpoint details")

    monkeypatch.setattr("app.foundation.near_client.requests.post", timeout)
    _, client = make_client()
    with client:
        response = client.get("/api/v1/near/health")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "NEAR_RPC_UNAVAILABLE"
    assert "sensitive endpoint details" not in response.text
