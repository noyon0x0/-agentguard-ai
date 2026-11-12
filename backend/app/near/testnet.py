"""Keyless, read-only NEAR Testnet account verification and simulation."""

from __future__ import annotations

import hashlib
import uuid

import requests

TESTNET_RPC_URL = "https://rpc.testnet.near.org"
RPC_TIMEOUT_SECONDS = 5.0


def is_valid_account_id(account_id: str) -> bool:
    """Check common NEAR account ID rules (lowercase, 2-64 chars, valid separators)."""
    if not isinstance(account_id, str) or not 2 <= len(account_id) <= 64:
        return False
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789._-")
    return (
        all(char in allowed for char in account_id)
        and account_id[0] in "abcdefghijklmnopqrstuvwxyz0123456789"
        and account_id[-1] in "abcdefghijklmnopqrstuvwxyz0123456789"
        and not any(a in "._-" and b in "._-" for a, b in zip(account_id, account_id[1:]))
    )


def verify_testnet_account(account_id: str) -> tuple[bool | None, str]:
    """Return (exists, status); `None` means verification could not be completed.

    Uses only the public query RPC method. No wallet, signing, or private key is involved.
    """
    if not is_valid_account_id(account_id):
        return False, "invalid_account_format"
    if not account_id.endswith(".testnet"):
        return None, "not_testnet_account"
    try:
        response = requests.post(
            TESTNET_RPC_URL,
            json={"jsonrpc": "2.0", "id": "agentguard-readonly", "method": "query",
                  "params": {"request_type": "view_account", "finality": "final", "account_id": account_id}},
            timeout=RPC_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("error"):
            error = data["error"]
            message = str(error.get("message", "")) if isinstance(error, dict) else str(error)
            if "does not exist" in message.casefold() or "unknown account" in message.casefold():
                return False, "account_not_found"
            return None, "rpc_error"
        if isinstance(data.get("result"), dict) and "amount" in data["result"]:
            return True, "verified_on_testnet"
        return None, "unexpected_rpc_response"
    except (requests.RequestException, ValueError):
        return None, "rpc_unavailable"


def create_authorization_receipt(sender: str, recipient: str, amount: float) -> str:
    """Create a clearly simulated receipt ID; this does not submit a transaction."""
    material = f"{sender}|{recipient}|{amount:.8f}|{uuid.uuid4()}".encode()
    return "sim_" + hashlib.sha256(material).hexdigest()[:24]
