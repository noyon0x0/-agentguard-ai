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
    signer = PyNearTestnetSigner("https://rpc.testnet.fastnear.com", "ed25519:test-secret")
    tx_hash = signer.send_transfer("sender.testnet", "receiver.testnet", 10**22)
    assert tx_hash == FakeResult.transaction.hash
    assert calls == [
        ("init", "sender.testnet", "https://rpc.testnet.fastnear.com"),
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
        PyNearTestnetSigner("https://rpc.testnet.fastnear.com", "not-a-key")
    except NearSignerError:
        pass
    else:
        raise AssertionError("non-ed25519 key must be rejected")
    try:
        PyNearTestnetSigner("https://rpc.testnet.near.org", "ed25519:any")
    except NearSignerError:
        pass
    else:
        raise AssertionError("noncanonical Testnet RPC endpoint must be rejected")


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
    signer = PyNearTestnetSigner("https://rpc.testnet.fastnear.com", "ed25519:test-secret")
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

    monkeypatch.setenv("PATH", "C:/safe/path")
    monkeypatch.setenv("APPDATA", "C:/Users/test/AppData/Roaming")
    monkeypatch.setenv("NEAR_HACKATHON_AGENTGUARD_ADMIN_TOKEN", "must-not-reach-cli")
    monkeypatch.setenv("NEAR_HACKATHON_AGENTGUARD_NEAR_TESTNET_PRIVATE_KEY", "must-not-reach-cli")
    monkeypatch.setattr("app.foundation.near_signer.shutil.which", lambda binary: "near.exe")
    monkeypatch.setattr("app.foundation.near_signer.subprocess.run", lambda args, **kwargs: calls.append((args, kwargs)) or Result())
    signer = NearCliKeychainTestnetSigner("https://rpc.testnet.fastnear.com")
    assert signer.send_transfer("sender.testnet", "receiver.testnet", 10**22) == Result.stdout.split(": ")[1]
    args, kwargs = calls[0]
    assert args == ["near.exe", "--quiet", "tokens", "sender.testnet", "send-near", "receiver.testnet", "0.01 NEAR", "network-config", "testnet", "sign-with-keychain", "send"]
    assert kwargs["stdin"] is __import__("subprocess").DEVNULL
    assert kwargs["capture_output"] is True
    assert kwargs["env"]["PATH"] == "C:/safe/path"
    assert kwargs["env"]["APPDATA"] == "C:/Users/test/AppData/Roaming"
    assert "NEAR_HACKATHON_AGENTGUARD_ADMIN_TOKEN" not in kwargs["env"]
    assert "NEAR_HACKATHON_AGENTGUARD_NEAR_TESTNET_PRIVATE_KEY" not in kwargs["env"]


def test_near_cli_signer_fails_closed_for_bad_endpoint_or_submission(monkeypatch):
    monkeypatch.setattr("app.foundation.near_signer.shutil.which", lambda binary: "near.exe")
    try:
        NearCliKeychainTestnetSigner("https://rpc.mainnet.near.org")
    except NearSignerError:
        pass
    else:
        raise AssertionError("CLI signer must reject Mainnet")
    try:
        NearCliKeychainTestnetSigner("https://rpc.testnet.near.org")
    except NearSignerError:
        pass
    else:
        raise AssertionError("noncanonical Testnet RPC endpoint must be rejected")

    class Failure:
        returncode = 1
        stdout = "secret diagnostics must not escape"
        stderr = "faucet/keychain private details"

    monkeypatch.setattr("app.foundation.near_signer.subprocess.run", lambda *args, **kwargs: Failure())
    signer = NearCliKeychainTestnetSigner("https://rpc.testnet.fastnear.com")
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

    config_text = ['[network_connection.testnet]\nnetwork_name = "testnet"\nrpc_url = "https://rpc.testnet.fastnear.com"\n']
    monkeypatch.setattr(Path, "open", lambda self, mode="r", *args, **kwargs: io.BytesIO(config_text[0].encode()))
    assert NearCliKeychainTestnetSigner.configured_for_official_testnet() is True
    config_text[0] = '[network_connection.testnet]\nnetwork_name = "mainnet"\nrpc_url = "https://rpc.mainnet.near.org/"\n'
    assert NearCliKeychainTestnetSigner.configured_for_official_testnet() is False


def _configure_near_cli_test_profile(monkeypatch, rpc_url="https://rpc.testnet.fastnear.com", network_name="testnet"):
    import io
    from pathlib import Path

    content = (
        "[network_connection.testnet]\n"
        f'network_name = "{network_name}"\n'
        f'rpc_url = "{rpc_url}"\n'
    )
    monkeypatch.setattr(Path, "open", lambda self, mode="r", *args, **kwargs: io.BytesIO(content.encode()))
    monkeypatch.setattr(
        "app.foundation.near_signer.shutil.which",
        lambda binary: "near.exe" if binary == "near" else None,
    )


def test_keychain_status_requires_cli_and_configured_public_key(monkeypatch):
    _configure_near_cli_test_profile(monkeypatch)
    calls = []
    monkeypatch.setattr("app.foundation.near_signer.shutil.which", lambda _binary: None)
    monkeypatch.setattr(
        "app.foundation.near_signer.subprocess.run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    assert NearCliKeychainTestnetSigner.keychain_status("sender.testnet", "ed25519:expected") == "not configured"
    monkeypatch.setattr(
        "app.foundation.near_signer.shutil.which",
        lambda binary: "near.exe" if binary == "near" else None,
    )
    assert NearCliKeychainTestnetSigner.keychain_status("sender.testnet", "") == "not configured"
    assert calls == []


def test_keychain_status_reports_missing_key_as_configured_but_not_verified(monkeypatch):
    _configure_near_cli_test_profile(monkeypatch)

    class MissingKey:
        returncode = 1
        stdout = ""
        stderr = "key unavailable"

    monkeypatch.setattr("app.foundation.near_signer.subprocess.run", lambda *args, **kwargs: MissingKey())

    status = NearCliKeychainTestnetSigner.keychain_status("sender.testnet", "ed25519:expected")

    assert status == "configured but not verified"


def test_keychain_status_rejects_public_key_mismatch(monkeypatch):
    _configure_near_cli_test_profile(monkeypatch)

    class DifferentKey:
        returncode = 0
        stdout = "Public key (printed to stdout):\ned25519:another-public-key"
        stderr = ""

    monkeypatch.setattr("app.foundation.near_signer.subprocess.run", lambda *args, **kwargs: DifferentKey())

    assert NearCliKeychainTestnetSigner.keychain_status(
        "sender.testnet", "ed25519:expected-public-key"
    ) == "configured but not verified"


def test_keychain_profile_rejects_noncanonical_rpc_urls(monkeypatch):
    _configure_near_cli_test_profile(monkeypatch)
    from pathlib import Path

    for rpc_url in (
        "https://rpc.testnet.near.org",
        "https://rpc.testnet.fastnear.com/",
        "https://rpc.testnet.fastnear.com:8443",
        "https://rpc.testnet.fastnear.com/proxy",
        "http://rpc.testnet.fastnear.com",
        "https://rpc.testnet.fastnear.com.evil.example",
        "https://user@rpc.testnet.fastnear.com",
        "https://rpc.testnet.fastnear.com?query=1",
        "https://rpc.testnet.fastnear.com#fragment",
        "https://archival-rpc.testnet.fastnear.com",
        "https://archival-rpc.testnet.near.org/",
    ):
        content = (
            "[network_connection.testnet]\n"
            'network_name = "testnet"\n'
            f'rpc_url = "{rpc_url}"\n'
        )
        monkeypatch.setattr(
            Path,
            "open",
            lambda self, mode="r", _content=content, *args, **kwargs: __import__("io").BytesIO(_content.encode()),
        )
        assert NearCliKeychainTestnetSigner.configured_for_official_testnet() is False


def test_keychain_status_verifies_public_key_with_read_only_cli_command(monkeypatch):
    import subprocess

    _configure_near_cli_test_profile(monkeypatch)
    monkeypatch.setenv("NEAR_HACKATHON_AGENTGUARD_ADMIN_TOKEN", "must-not-reach-cli")
    monkeypatch.setenv("NEAR_HACKATHON_AGENTGUARD_NEAR_TESTNET_PRIVATE_KEY", "must-not-reach-cli")
    calls = []

    class PublicKeyResult:
        returncode = 0
        stdout = "Public key (printed to stdout):\ned25519:expected-public-key\n"
        stderr = ""

    monkeypatch.setattr(
        "app.foundation.near_signer.subprocess.run",
        lambda args, **kwargs: calls.append((args, kwargs)) or PublicKeyResult(),
    )

    status = NearCliKeychainTestnetSigner.keychain_status(
        "sender.testnet", "ed25519:expected-public-key"
    )

    assert status == "verified"
    args, kwargs = calls[0]
    assert args == [
        "near.exe", "--quiet", "account", "get-public-key", "from-keychain",
        "sender.testnet", "network-config", "testnet",
    ]
    assert kwargs["stdin"] is subprocess.DEVNULL
    assert kwargs["capture_output"] is True
    assert kwargs["timeout"] == 15
    assert "NEAR_HACKATHON_AGENTGUARD_ADMIN_TOKEN" not in kwargs["env"]
    assert "NEAR_HACKATHON_AGENTGUARD_NEAR_TESTNET_PRIVATE_KEY" not in kwargs["env"]


def test_keychain_status_timeout_fails_closed_without_exposing_cli_output(monkeypatch):
    import subprocess

    _configure_near_cli_test_profile(monkeypatch)
    monkeypatch.setattr(
        "app.foundation.near_signer.subprocess.run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            subprocess.TimeoutExpired(args[0], kwargs["timeout"], stderr="sensitive diagnostic")
        ),
    )

    assert NearCliKeychainTestnetSigner.keychain_status(
        "sender.testnet", "ed25519:expected-public-key"
    ) == "configured but not verified"
