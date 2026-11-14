from app.foundation.near_signer import NearCliKeychainTestnetSigner, NearSignerError, PyNearTestnetSigner, derive_public_key, near_to_yocto


def test_near_testnet_signer_uses_configured_testnet_and_returns_hash(monkeypatch):
    calls = []

    class FakeResult:
        class transaction:
            hash = "HEgnVQZfs9uJzrqTob4g2Xmebqodq9waZvApSkrbcAhd"

    class FakeAccount:
        def __init__(self, account_id, private_key, rpc_url):
            calls.append(("init", account_id, rpc_url))
            self.private_key = private_key

        async def startup(self):
            calls.append(("startup",))

        async def send_money(self, recipient, amount, nowait=False):
            calls.append(("send", recipient, amount, nowait))
            return FakeResult()

        async def shutdown(self):
            calls.append(("shutdown",))

    monkeypatch.setattr("py_near.account.Account", FakeAccount)
    signer = PyNearTestnetSigner("https://rpc.testnet.near.org", "ed25519:test-secret")
    tx_hash = signer.send_transfer("sender.testnet", "receiver.testnet", 10**22)
    assert tx_hash == FakeResult.transaction.hash
    assert calls == [
        ("init", "sender.testnet", "https://rpc.testnet.near.org"),
        ("startup",), ("send", "receiver.testnet", 10**22, True), ("shutdown",),
    ]
    assert "test-secret" not in repr(calls)


def test_near_signer_rejects_mainnet_and_bad_private_key():
    try:
        PyNearTestnetSigner("https://rpc.mainnet.near.org", "ed25519:any")
    except NearSignerError:
        pass
    else:
        raise AssertionError("Mainnet RPC must be rejected")
    try:
        PyNearTestnetSigner("https://rpc.testnet.near.org", "not-a-key")
    except NearSignerError:
        pass
    else:
        raise AssertionError("non-ed25519 key must be rejected")


def test_near_to_yocto_rejects_non_integral_amounts():
    from decimal import Decimal

    assert near_to_yocto(Decimal("0.01")) == 10**22
    try:
        near_to_yocto(Decimal("0.0000000000000000000000001"))
    except Exception:
        pass
    else:
        raise AssertionError("fractional yocto amount must be rejected")


def test_derived_signer_public_key_is_public_only_and_invalid_keys_fail():
    import base58

    private_key = "ed25519:" + base58.b58encode(bytes(32)).decode("ascii")
    public_key = derive_public_key(private_key)
    assert public_key.startswith("ed25519:")
    assert public_key != private_key
    try:
        derive_public_key("ed25519:not-valid")
    except NearSignerError:
        pass
    else:
        raise AssertionError("invalid key material was accepted")


def test_submission_timeout_preserves_only_a_valid_transaction_hash(monkeypatch):
    tx_hash = "HEgnVQZfs9uJzrqTob4g2Xmebqodq9waZvApSkrbcAhd"

    class FakeAccount:
        def __init__(self, *args):
            pass

        async def startup(self):
            pass

        async def send_money(self, *args, **kwargs):
            error = RuntimeError("private provider detail")
            error.trx_hash = tx_hash
            raise error

        async def shutdown(self):
            pass

    monkeypatch.setattr("py_near.account.Account", FakeAccount)
    signer = PyNearTestnetSigner("https://rpc.testnet.near.org", "ed25519:test-secret")
    try:
        signer.send_transfer("sender.testnet", "receiver.testnet", 10**22)
    except NearSignerError as exc:
        assert exc.transaction_hash == tx_hash
        assert "private provider detail" not in str(exc)
    else:
        raise AssertionError("failed submission unexpectedly returned")


def test_near_cli_signer_uses_os_keychain_and_only_returns_validated_hash(monkeypatch):
    calls = []

    class Result:
        returncode = 0
        stdout = "Transaction ID: HEgnVQZfs9uJzrqTob4g2Xmebqodq9waZvApSkrbcAhd"
        stderr = "diagnostic detail"

    monkeypatch.setattr("app.foundation.near_signer.shutil.which", lambda binary: "near.exe")
    monkeypatch.setattr("app.foundation.near_signer.subprocess.run", lambda args, **kwargs: calls.append((args, kwargs)) or Result())
    signer = NearCliKeychainTestnetSigner("https://rpc.testnet.near.org")
    assert signer.send_transfer("sender.testnet", "receiver.testnet", 10**22) == Result.stdout.split(": ")[1]
    args, kwargs = calls[0]
    assert args == ["near.exe", "--quiet", "tokens", "sender.testnet", "send-near", "receiver.testnet", "0.01 NEAR", "network-config", "agentguard-testnet", "sign-with-keychain", "send"]
    assert kwargs["stdin"] is __import__("subprocess").DEVNULL
    assert kwargs["capture_output"] is True


def test_near_cli_signer_fails_closed_for_bad_endpoint_or_submission(monkeypatch):
    monkeypatch.setattr("app.foundation.near_signer.shutil.which", lambda binary: "near.exe")
    try:
        NearCliKeychainTestnetSigner("https://rpc.mainnet.near.org")
    except NearSignerError:
        pass
    else:
        raise AssertionError("CLI signer must reject Mainnet")

    class Failure:
        returncode = 1
        stdout = "secret diagnostics must not escape"
        stderr = "faucet/keychain private details"

    monkeypatch.setattr("app.foundation.near_signer.subprocess.run", lambda *args, **kwargs: Failure())
    signer = NearCliKeychainTestnetSigner("https://rpc.testnet.near.org")
    try:
        signer.send_transfer("sender.testnet", "receiver.testnet", 10**22)
    except NearSignerError as exc:
        assert "private details" not in str(exc)
        assert exc.transaction_hash is None
    else:
        raise AssertionError("CLI failure must fail closed")


def test_near_cli_keychain_profile_must_be_the_official_testnet_rpc(monkeypatch):
    import io
    from pathlib import Path

    config_text = ['[network_connection.agentguard-testnet]\nnetwork_name = "testnet"\nrpc_url = "https://rpc.testnet.near.org/"\n']
    monkeypatch.setattr(Path, "open", lambda self, mode="r", *args, **kwargs: io.BytesIO(config_text[0].encode()))
    assert NearCliKeychainTestnetSigner.configured_for_official_testnet() is True
    config_text[0] = '[network_connection.agentguard-testnet]\nnetwork_name = "mainnet"\nrpc_url = "https://rpc.mainnet.near.org/"\n'
    assert NearCliKeychainTestnetSigner.configured_for_official_testnet() is False
