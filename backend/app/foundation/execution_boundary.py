"""Fail-closed boundary used by the non-broadcasting attack lab signer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Any


@dataclass
class SimulatedSigner:
    """Records authorized demo calls; it never creates or submits a transaction."""

    calls: list[dict[str, Any]] = field(default_factory=list)

    def sign(self, request: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"request": request, "mode": "simulation_only"})
        return {"simulated": True, "broadcast": False}


def enforce_before_signing(
    decision: str,
    request: dict[str, Any],
    signer: Callable[[dict[str, Any]], Any],
    *,
    human_approved: bool = False,
) -> dict[str, Any]:
    """Never calls signer for BLOCK, ERROR, or an unapproved REVIEW/WARN."""
    if decision == "BLOCK":
        return {"outcome": "BLOCK", "signer_invoked": False}
    if decision == "ERROR":
        return {"outcome": "ERROR", "signer_invoked": False}
    if decision in {"REVIEW", "WARN"} and not human_approved:
        return {"outcome": "WARN", "signer_invoked": False, "approval_required": True}
    if decision not in {"APPROVE", "REVIEW", "WARN"}:
        return {"outcome": "ERROR", "signer_invoked": False}
    try:
        result = signer(request)
    except Exception:
        return {"outcome": "ERROR", "signer_invoked": True}
    return {"outcome": "ALLOW", "signer_invoked": True, "signer_result": result}
