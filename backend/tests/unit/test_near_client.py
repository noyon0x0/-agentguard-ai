from app.foundation.config import Settings
from app.foundation.near_client import (
    NearInvalidInput,
    NearTestnetClient,
    READ_ONLY_METHODS,
    validate_account_id,
    validate_transaction_hash,
)


def test_near_rpc_settings_are_environment_configurable(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_NEAR_TESTNET_RPC_URL", "https://rpc.example.test")
    monkeypatch.setenv("AGENTGUARD_NEAR_RPC_TIMEOUT_SECONDS", "2.5")
    settings = Settings.from_environment()
    assert settings.near_testnet_rpc_url == "https://rpc.example.test"
    assert settings.near_rpc_timeout_seconds == 2.5


def test_client_rejects_non_https_public_rpc_urls():
    try:
        NearTestnetClient("http://rpc.example.test")
    except ValueError as exc:
        assert "HTTPS" in str(exc)
    else:
        raise AssertionError("non-HTTPS public RPC URL was accepted")


def test_rpc_client_refuses_broadcast_methods_without_network_access(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.foundation.near_client.requests.post",
        lambda *args, **kwargs: calls.append(kwargs),
    )
    client = NearTestnetClient("https://rpc.testnet.near.org")

    assert READ_ONLY_METHODS == frozenset({"status", "query", "tx"})
    try:
        client._rpc_call("broadcast_tx_commit", {"signed_tx_base64": "not-real"})
    except NearInvalidInput:
        pass
    else:
        raise AssertionError("broadcast method was accepted")
    assert calls == []


def test_read_only_client_requests_need_no_wallet_credentials(monkeypatch):
    seen = []

    def fake_post(url, **kwargs):
        seen.append(kwargs)
        method = kwargs["json"]["method"]
        result = {"chain_id": "testnet"} if method == "status" else {
            "amount": "0",
            "locked": "0",
            "storage_usage": 0,
            "code_hash": "11111111111111111111111111111111",
        }
        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"jsonrpc": "2.0", "id": "mock", "result": result}

        return Response()

    monkeypatch.setattr("app.foundation.near_client.requests.post", fake_post)
    client = NearTestnetClient("https://rpc.testnet.near.org")
    client.get_account("alice.testnet")

    assert [call["json"]["method"] for call in seen] == ["status", "query"]
    assert all("Authorization" not in call["headers"] for call in seen)
    assert all(not ({"private_key", "seed_phrase", "secret_key"} & call["json"].keys()) for call in seen)


def test_account_and_transaction_reference_validation():
    assert validate_account_id("alice.testnet") == "alice.testnet"
    assert validate_transaction_hash("HEgnVQZfs9uJzrqTob4g2Xmebqodq9waZvApSkrbcAhd")
    for invalid in ("Bad Account", "a", "alice..testnet"):
        try:
            validate_account_id(invalid)
        except NearInvalidInput:
            pass
        else:
            raise AssertionError(f"invalid account id was accepted: {invalid}")
    try:
        validate_transaction_hash("not-a-hash")
    except NearInvalidInput:
        pass
    else:
        raise AssertionError("invalid transaction hash was accepted")
