"""Deterministic server-side transaction policy evaluation."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import AgentState, PolicyConfiguration, PolicyRevision, SecurityEvaluation
from .schemas import EvaluationIntake

PROMPT_ATTACK_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"bypass\s+(security|guard|policy|limit)",
        r"system\s+override",
        r"drain\s+(wallet|funds|all)",
        r"transfer\s+everything",
        r"act\s+as\s+admin",
        r"sudo\s+mode",
        r"forget\s+rules",
        r"private\s+key|seed\s+phrase",
    )
)


@dataclass(frozen=True)
class PolicyResult:
    decision: str
    risk_score: int
    explanation: str
    checks: dict[str, str]


def payload_fingerprint(payload: EvaluationIntake) -> str:
    serialized = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def policy_snapshot(policy: PolicyConfiguration) -> dict:
    return {
        "version": policy.policy_version,
        "max_transaction_near": policy.max_transaction_near,
        "daily_limit_near": policy.daily_limit_near,
        "review_threshold_near": policy.review_threshold_near,
        "allowlist": policy.allowlist,
        "blocklist": policy.blocklist,
        "prompt_detection_enabled": policy.prompt_detection_enabled,
        "velocity_enabled": policy.velocity_enabled,
        "velocity_max_requests": policy.velocity_max_requests,
        "velocity_window_seconds": policy.velocity_window_seconds,
        "duplicate_window_seconds": policy.duplicate_window_seconds,
        "allowed_tools": policy.allowed_tools,
        "allowed_contracts": policy.allowed_contracts,
        "global_kill_switch": policy.global_kill_switch,
    }


def ensure_default_policy(session: Session) -> None:
    if session.get(PolicyConfiguration, 1) is None:
        session.add(
            PolicyConfiguration(
                id=1,
                max_transaction_near=10.0,
                daily_limit_near=25.0,
                review_threshold_near=5.0,
                allowlist=["demo.near", "treasury.testnet", "merchant.testnet"],
                blocklist=["attacker.testnet", "drainer.evil.testnet"],
                prompt_detection_enabled=True,
                velocity_enabled=True,
                velocity_max_requests=3,
                velocity_window_seconds=15,
                duplicate_window_seconds=60,
                allowed_tools=["view_account", "view_contract", "evaluate_policy"],
                allowed_contracts=[],
            )
        )
    for agent_id in ("agent.testnet", "DeFi-Trader-Bot", "Auto-Payroll-Agent", "Marketing-Grant-Bot", "External-Plugin-Agent"):
        if session.get(AgentState, agent_id) is None:
            session.add(AgentState(agent_id=agent_id, frozen=False))
    session.commit()
    policy = session.get(PolicyConfiguration, 1)
    if session.scalar(select(PolicyRevision.id).where(PolicyRevision.version == policy.policy_version)) is None:
        session.add(PolicyRevision(version=policy.policy_version, snapshot=policy_snapshot(policy)))
        session.commit()


def evaluate_policy(
    session: Session,
    payload: EvaluationIntake,
    *,
    exclude_request_id: str | None = None,
    now: datetime | None = None,
) -> PolicyResult:
    """Compute a decision from persisted policy and server-owned history only."""
    policy = session.get(PolicyConfiguration, 1)
    if policy is None:
        return PolicyResult("BLOCK", 100, "Required policy configuration is unavailable.", {"policy": "FAIL"})

    now = now or datetime.now(timezone.utc)
    now_db = now.replace(tzinfo=None)
    checks: dict[str, str] = {}
    reasons: list[str] = []
    block_reasons: list[str] = []

    if policy.global_kill_switch:
        checks["global_kill_switch"] = "ENABLED"
        block_reasons.append("Global kill switch is enabled.")
    else:
        checks["global_kill_switch"] = "DISABLED"

    agent = session.get(AgentState, payload.agent_id)
    if agent is None:
        checks["agent"] = "FAIL"
        block_reasons.append("Agent is not registered.")
    elif agent.frozen:
        checks["agent"] = "FROZEN"
        block_reasons.append("Agent is frozen.")
    else:
        checks["agent"] = "PASS"

    prompt_text = " ".join(part for part in (payload.prompt, payload.memo) if part)
    injection_found = policy.prompt_detection_enabled and any(p.search(prompt_text) for p in PROMPT_ATTACK_PATTERNS)
    checks["prompt_injection"] = "FAIL" if injection_found else "PASS"
    if injection_found:
        block_reasons.append("Prompt injection pattern detected.")

    if payload.tool_name is None:
        checks["tool_authorization"] = "NOT_REQUESTED"
    elif payload.tool_name in policy.allowed_tools:
        checks["tool_authorization"] = "PASS"
    else:
        checks["tool_authorization"] = "FAIL"
        block_reasons.append("Requested tool is not authorized by policy.")

    if payload.contract_account is None:
        checks["contract_validation"] = "NOT_REQUESTED"
    else:
        from .near_client import NearInvalidInput, validate_account_id

        try:
            contract_account = validate_account_id(payload.contract_account)
        except NearInvalidInput:
            checks["contract_validation"] = "FAIL"
            block_reasons.append("Contract account ID is invalid.")
        else:
            if contract_account not in policy.allowed_contracts:
                checks["contract_validation"] = "FAIL"
                block_reasons.append("Contract account is not in the approved contract list.")
            else:
                checks["contract_validation"] = "PASS"

    recipient = payload.recipient
    if recipient in policy.blocklist:
        checks["wallet_blocklist"] = "FAIL"
        block_reasons.append("Recipient is on the blocklist.")
    else:
        checks["wallet_blocklist"] = "PASS"
    if recipient not in policy.allowlist:
        checks["wallet_allowlist"] = "FAIL"
        block_reasons.append("Recipient is not on the allowlist.")
    else:
        checks["wallet_allowlist"] = "PASS"

    if payload.amount_near > policy.max_transaction_near:
        checks["transaction_limit"] = "FAIL"
        block_reasons.append("Amount exceeds the maximum transaction limit.")
    else:
        checks["transaction_limit"] = "PASS"

    day_start = now_db.replace(hour=0, minute=0, second=0, microsecond=0)
    spent_query = select(func.coalesce(func.sum(SecurityEvaluation.amount_near), 0.0)).where(
        SecurityEvaluation.agent_id == payload.agent_id,
        SecurityEvaluation.status == "APPROVE",
        SecurityEvaluation.created_at >= day_start,
    )
    spent_today = float(session.scalar(spent_query) or 0.0)
    if spent_today + payload.amount_near > policy.daily_limit_near:
        checks["daily_limit"] = "FAIL"
        block_reasons.append("Request would exceed the agent daily spending limit.")
    else:
        checks["daily_limit"] = "PASS"

    duplicate_query = select(SecurityEvaluation.request_id).where(
        SecurityEvaluation.sender == payload.sender,
        SecurityEvaluation.agent_id == payload.agent_id,
        SecurityEvaluation.recipient == recipient,
        SecurityEvaluation.amount_near == payload.amount_near,
        SecurityEvaluation.created_at >= now_db - timedelta(seconds=policy.duplicate_window_seconds),
    )
    if exclude_request_id:
        duplicate_query = duplicate_query.where(SecurityEvaluation.request_id != exclude_request_id)
    is_duplicate = session.scalar(duplicate_query) is not None
    checks["duplicate"] = "FAIL" if is_duplicate else "PASS"
    if is_duplicate:
        block_reasons.append("Duplicate request detected within the protection window.")

    velocity_query = select(func.count(SecurityEvaluation.id)).where(
        SecurityEvaluation.agent_id == payload.agent_id,
        SecurityEvaluation.created_at >= now_db - timedelta(seconds=policy.velocity_window_seconds),
    )
    if exclude_request_id:
        velocity_query = velocity_query.where(SecurityEvaluation.request_id != exclude_request_id)
    recent_count = int(session.scalar(velocity_query) or 0)
    velocity_failed = policy.velocity_enabled and recent_count >= policy.velocity_max_requests
    checks["velocity"] = "FAIL" if velocity_failed else ("PASS" if policy.velocity_enabled else "DISABLED")
    if velocity_failed:
        block_reasons.append("Velocity threshold exceeded.")

    if block_reasons:
        return PolicyResult("BLOCK", min(100, 75 + 5 * len(block_reasons)), " ".join(block_reasons), checks)
    if payload.amount_near > policy.review_threshold_near:
        reasons.append("Amount exceeds the automatic approval threshold and requires human review.")
        checks["human_approval"] = "REQUIRED"
        return PolicyResult("REVIEW", 40, " ".join(reasons), checks)

    checks["human_approval"] = "NOT_REQUIRED"
    return PolicyResult("APPROVE", 0, "All server-side security checks passed.", checks)
