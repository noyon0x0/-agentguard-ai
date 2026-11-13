"""Strictly read-only client for the NEAR Testnet JSON-RPC API."""

from __future__ import annotations

import re
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

import requests


class NearIntegrationError(Exception):
    """Base class for sanitized NEAR integration errors."""


class NearRpcUnavailable(NearIntegrationError):
    pass


class NearWrongNetwork(NearIntegrationError):
    pass


class NearAccountNotFound(NearIntegrationError):
    pass


class NearTransactionNotFound(NearIntegrationError):
    pass


class NearInvalidInput(NearIntegrationError):
    pass


@dataclass(frozen=True)
class RpcHealth:
    status: str
    network: str | None
    latency_ms: int
    checked_at: str


ACCOUNT_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
EMPTY_CODE_HASH = "11111111111111111111111111111111"
READ_ONLY_METHODS = frozenset({"status", "query", "tx"})


def validate_account_id(account_id: str) -> str:
    if not isinstance(account_id, str) or not 2 <= len(account_id) <= 64:
        raise NearInvalidInput("Invalid NEAR account ID")
    if not ACCOUNT_ID_PATTERN.fullmatch(account_id):
        raise NearInvalidInput("Invalid NEAR account ID")
    return account_id


def validate_transaction_hash(tx_hash: str) -> str:
    if not isinstance(tx_hash, str) or not 32 <= len(tx_hash) <= 50:
        raise NearInvalidInput("Invalid NEAR transaction hash")
    if any(char not in BASE58_ALPHABET for char in tx_hash):
        raise NearInvalidInput("Invalid NEAR transaction hash")
    value = 0
    for char in tx_hash:
        value = value * 58 + BASE58_ALPHABET.index(char)
    decoded = value.to_bytes((value.bit_length() + 7) // 8, "big") if value else b""
    leading_zeroes = len(tx_hash) - len(tx_hash.lstrip("1"))
    if len(decoded) + leading_zeroes != 32:
        raise NearInvalidInput("Invalid NEAR transaction hash")
    return tx_hash


class NearTestnetClient:
    """Permit only status and state/status queries; never accepts signing data."""

    def __init__(self, rpc_url: str, timeout_seconds: float = 5.0):
        parsed = urlparse(rpc_url)
        local_http = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
        if not parsed.hostname or (parsed.scheme != "https" and not local_http):
            raise ValueError("NEAR RPC URL must use HTTPS (HTTP is allowed only for localhost)")
        if not 0.1 <= timeout_seconds <= 60:
            raise ValueError("NEAR RPC timeout must be between 0.1 and 60 seconds")
        self.rpc_url = rpc_url
        self.timeout_seconds = timeout_seconds
        self._health_lock = threading.Lock()
        self._last_health: RpcHealth | None = None

    @property
    def last_health(self) -> RpcHealth | None:
        with self._health_lock:
            return self._last_health

    def _rpc_call(self, method: str, params: object = None) -> dict:
        if method not in READ_ONLY_METHODS:
            raise NearInvalidInput("RPC method is not allowed by the read-only client")
        payload = {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": method}
        if params is not None:
            payload["params"] = params
        data = None
        for attempt in range(2):
            try:
                response = requests.post(
                    self.rpc_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                data = response.json()
                break
            except (requests.RequestException, ValueError):
                if attempt == 1:
                    raise NearRpcUnavailable("NEAR Testnet RPC request failed") from None
                time.sleep(0.1)
        if data is None:
            raise NearRpcUnavailable("NEAR Testnet RPC request failed")
        if not isinstance(data, dict) or data.get("jsonrpc") != "2.0":
            raise NearRpcUnavailable("NEAR Testnet RPC returned an invalid response")
        error = data.get("error")
        if error is not None:
            message = str(error.get("message", "")) if isinstance(error, dict) else ""
            code = error.get("code") if isinstance(error, dict) else None
            if code in {-32000, -32001} and any(term in message.casefold() for term in ("unknown account", "does not exist", "unknown transaction")):
                if "transaction" in message.casefold():
                    raise NearTransactionNotFound("Transaction was not found on NEAR Testnet")
                raise NearAccountNotFound("Account was not found on NEAR Testnet")
            raise NearRpcUnavailable("NEAR Testnet RPC returned an error")
        result = data.get("result")
        if not isinstance(result, dict):
            raise NearRpcUnavailable("NEAR Testnet RPC returned an invalid result")
        return result

    def verify_network(self) -> dict:
        started = time.monotonic()
        checked_at = datetime.now(timezone.utc).isoformat()
        try:
            result = self._rpc_call("status")
            chain_id = result.get("chain_id")
            if chain_id != "testnet":
                raise NearWrongNetwork("Configured RPC is not connected to NEAR Testnet")
            health = RpcHealth(
                status="healthy",
                network="testnet",
                latency_ms=round((time.monotonic() - started) * 1000),
                checked_at=checked_at,
            )
            with self._health_lock:
                self._last_health = health
            return {
                "status": health.status,
                "network": health.network,
                "latency_ms": health.latency_ms,
                "checked_at": health.checked_at,
            }
        except NearIntegrationError:
            health = RpcHealth(
                status="unhealthy",
                network=None,
                latency_ms=round((time.monotonic() - started) * 1000),
                checked_at=checked_at,
            )
            with self._health_lock:
                self._last_health = health
            raise

    def _verify_network_before_query(self) -> None:
        self.verify_network()

    @staticmethod
    def _balance_near(raw_value: object) -> str:
        if not isinstance(raw_value, str) or not raw_value.isdigit():
            raise NearRpcUnavailable("NEAR account response contained an invalid balance")
        try:
            amount = Decimal(raw_value) / Decimal(10**24)
        except InvalidOperation:
            raise NearRpcUnavailable("NEAR account response contained an invalid balance") from None
        return format(amount, "f")

    def get_account(self, account_id: str) -> dict:
        account_id = validate_account_id(account_id)
        self._verify_network_before_query()
        account = self._rpc_call(
            "query",
            {"request_type": "view_account", "finality": "final", "account_id": account_id},
        )
        code_hash = account.get("code_hash")
        if not isinstance(code_hash, str):
            raise NearRpcUnavailable("NEAR account response was incomplete")
        return {
            "account_id": account_id,
            "network": "testnet",
            "balance_near": self._balance_near(account.get("amount")),
            "locked_near": self._balance_near(account.get("locked", "0")),
            "storage_usage": account.get("storage_usage"),
            "code_hash": code_hash,
            "is_contract": code_hash != EMPTY_CODE_HASH,
        }

    def get_transaction(self, tx_hash: str, sender_account_id: str) -> dict:
        tx_hash = validate_transaction_hash(tx_hash)
        sender_account_id = validate_account_id(sender_account_id)
        self._verify_network_before_query()
        result = self._rpc_call(
            "tx",
            {"tx_hash": tx_hash, "sender_account_id": sender_account_id, "wait_until": "FINAL"},
        )
        transaction = result.get("transaction")
        if not isinstance(transaction, dict):
            raise NearTransactionNotFound("Transaction was not found on NEAR Testnet")
        if transaction.get("hash") != tx_hash or transaction.get("signer_id") != sender_account_id:
            raise NearRpcUnavailable("NEAR RPC transaction identity did not match the request")
        if not isinstance(result.get("status"), dict):
            raise NearRpcUnavailable("NEAR RPC transaction result was incomplete")
        return {
            "verified": True,
            "network": "testnet",
            "transaction_hash": tx_hash,
            "sender_account_id": sender_account_id,
            "execution_status": result["status"],
            "explorer_url": f"https://explorer.testnet.near.org/transactions/{tx_hash}",
        }
