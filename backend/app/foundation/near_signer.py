"""Isolated signer for an explicitly configured, dedicated Testnet account."""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import tomllib
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from .near_client import NearInvalidInput, validate_transaction_hash


class NearSignerError(Exception):
    """Sanitized transaction signing or submission failure."""

    def __init__(self, message: str, *, transaction_hash: str | None = None):
        super().__init__(message)
        self.transaction_hash = transaction_hash


class TransferSigner(Protocol):
    def send_transfer(self, sender: str, recipient: str, amount_yocto: int) -> str: ...


class PyNearTestnetSigner:
    """Private key is injected from backend configuration and never serialized."""

    def __init__(self, rpc_url: str, private_key: str):
        if rpc_url != "https://rpc.testnet.near.org":
            raise NearSignerError("Live signing is restricted to the official NEAR Testnet RPC")
        if not private_key.startswith("ed25519:"):
            raise NearSignerError("A valid Testnet ed25519 signing key is not configured")
        self.rpc_url = rpc_url
        self.__private_key = private_key

    def send_transfer(self, sender: str, recipient: str, amount_yocto: int) -> str:
        async def submit() -> str:
            try:
                from py_near.account import Account
            except ImportError as exc:
                raise NearSignerError("NEAR signing dependency is not installed") from exc
            account = Account(sender, self.__private_key, self.rpc_url)
            try:
                await account.startup()
                result = await account.send_money(recipient, amount_yocto, nowait=True)
                if isinstance(result, str):
                    tx_hash = result
                else:
                    transaction = getattr(result, "transaction", None)
                    tx_hash = getattr(transaction, "hash", None) or getattr(result, "hash", None)
                if not isinstance(tx_hash, str):
                    raise NearSignerError("NEAR signer returned no transaction hash")
                return validate_transaction_hash(tx_hash)
            except NearSignerError:
                raise
            except Exception as exc:
                # Do not include provider errors, the key, or SDK diagnostics.
                possible_hash = getattr(exc, "trx_hash", None)
                try:
                    tx_hash = validate_transaction_hash(possible_hash) if isinstance(possible_hash, str) else None
                except NearInvalidInput:
                    tx_hash = None
                raise NearSignerError("NEAR Testnet transaction submission failed", transaction_hash=tx_hash) from exc
            finally:
                shutdown = getattr(account, "shutdown", None)
                if shutdown is not None:
                    try:
                        await shutdown()
                    except Exception:
                        pass

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(submit())
        raise NearSignerError("Synchronous signer cannot run inside an active event loop")


class NearCliKeychainTestnetSigner:
    """Use near-cli-rs to sign from its OS keychain without exporting key data."""

    NETWORK_CONNECTION = "agentguard-testnet"

    def __init__(self, rpc_url: str, *, cli_path: str | None = None):
        if rpc_url != "https://rpc.testnet.near.org":
            raise NearSignerError("Live signing is restricted to the official NEAR Testnet RPC")
        resolved = cli_path or shutil.which("near")
        if not resolved:
            raise NearSignerError("near-cli-rs is not installed")
        self.rpc_url = rpc_url
        self.__cli_path = resolved

    @classmethod
    def configured_for_official_testnet(cls) -> bool:
        if os.name == "nt":
            root = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming"))
            config_path = root / "near-cli" / "config.toml"
        elif os.uname().sysname == "Darwin":
            config_path = Path.home() / "Library" / "Application Support" / "near-cli" / "config.toml"
        else:
            config_path = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")) / "near-cli" / "config.toml"
        try:
            with config_path.open("rb") as config_file:
                config = tomllib.load(config_file)
            connection = config.get("network_connection", {}).get(cls.NETWORK_CONNECTION, {})
            from urllib.parse import urlparse

            parsed = urlparse(connection.get("rpc_url", ""))
            return (
                connection.get("network_name") == "testnet"
                and parsed.scheme == "https"
                and parsed.hostname == "rpc.testnet.near.org"
            )
        except (OSError, tomllib.TOMLDecodeError, AttributeError):
            return False

    def send_transfer(self, sender: str, recipient: str, amount_yocto: int) -> str:
        if not isinstance(amount_yocto, int) or amount_yocto <= 0:
            raise NearSignerError("Invalid NEAR Testnet transfer amount")
        amount = Decimal(amount_yocto) / Decimal(10**24)
        amount_arg = f"{amount:f} NEAR"
        command = [
            self.__cli_path, "--quiet", "tokens", sender, "send-near", recipient,
            amount_arg, "network-config", self.NETWORK_CONNECTION,
            "sign-with-keychain", "send",
        ]
        try:
            result = subprocess.run(
                command, check=False, capture_output=True, text=True,
                timeout=90, stdin=subprocess.DEVNULL,
                env=os.environ.copy(),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise NearSignerError("NEAR keychain signer could not complete the Testnet request") from exc
        # Capture is deliberately never logged or propagated: the CLI owns key
        # retrieval and may include signing diagnostics in its output.
        combined = f"{result.stdout or ''}\n{result.stderr or ''}"
        tx_hash = None
        patterns = (
            r"Transaction ID:\s*([1-9A-HJ-NP-Za-km-z]{32,50})",
            r"explorer\.testnet\.near\.org/transactions/?([1-9A-HJ-NP-Za-km-z]{32,50})",
        )
        for pattern in patterns:
            match = re.search(pattern, combined)
            if match:
                try:
                    tx_hash = validate_transaction_hash(match.group(1))
                except NearInvalidInput:
                    tx_hash = None
                if tx_hash:
                    break
        if result.returncode != 0:
            raise NearSignerError(
                "NEAR keychain signing or submission failed", transaction_hash=tx_hash
            )
        if tx_hash is None:
            raise NearSignerError("NEAR keychain signer returned no transaction hash")
        return tx_hash


def derive_public_key(private_key: str) -> str:
    """Derive the corresponding public access-key id without returning the secret."""
    try:
        import base58
        from nacl.signing import SigningKey

        if not isinstance(private_key, str) or not private_key.startswith("ed25519:"):
            raise ValueError
        raw = base58.b58decode(private_key.removeprefix("ed25519:"))
        if len(raw) not in (32, 64):
            raise ValueError
        public_key = SigningKey(raw[:32]).verify_key.encode()
        return "ed25519:" + base58.b58encode(public_key).decode("ascii")
    except Exception as exc:
        raise NearSignerError("Configured NEAR Testnet key is invalid") from exc


def near_to_yocto(amount_near: Decimal) -> int:
    yocto = amount_near * Decimal(10**24)
    if amount_near <= 0 or yocto != yocto.to_integral_value():
        raise NearInvalidInput("NEAR amount must be a positive whole yoctoNEAR value")
    return int(yocto)
