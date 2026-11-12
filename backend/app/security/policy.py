"""Deterministic, in-memory payment security policy."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

APPROVAL_LIMIT_NEAR = 5.0
MAX_AMOUNT_NEAR = 10.0
APPROVED_RECIPIENTS = frozenset({"demo.near", "treasury.testnet", "merchant.testnet"})
SUSPICIOUS_TERMS = ("ignore previous", "urgent", "seed", "private key", "drain")
DUPLICATE_WINDOW_SECONDS = 60.0


@dataclass(frozen=True)
class PolicyResult:
    decision: str
    reason: str
    risk_score: int


class SecurityPolicy:
    """Evaluate payments deterministically and remember recent request tuples."""

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._recent: dict[tuple[str, str, float], float] = {}
        self._lock = threading.Lock()

    def evaluate(self, sender: str, recipient: str, amount: float, memo: str | None = None) -> PolicyResult:
        memo_text = (memo or "").casefold()
        if any(term in memo_text for term in SUSPICIOUS_TERMS):
            return PolicyResult("BLOCK", "Suspicious memo content detected", 100)
        if amount > MAX_AMOUNT_NEAR:
            return PolicyResult("BLOCK", "Spending limit exceeded (maximum 10.0 NEAR)", 80)
        if recipient not in APPROVED_RECIPIENTS:
            return PolicyResult("BLOCK", "Unknown recipient", 90)

        now = self._clock()
        key = (sender, recipient, float(amount))
        with self._lock:
            self._recent = {k: seen for k, seen in self._recent.items() if now - seen < DUPLICATE_WINDOW_SECONDS}
            if key in self._recent:
                return PolicyResult("BLOCK", "Duplicate payment request within 60 seconds", 85)
            self._recent[key] = now

        if amount <= APPROVAL_LIMIT_NEAR:
            return PolicyResult("APPROVE", "Payment passed security policy", 0)
        return PolicyResult("PENDING_APPROVAL", "Medium-risk payment paused for human approval", 35)

    def clear(self) -> None:
        with self._lock:
            self._recent.clear()


policy_engine = SecurityPolicy()
