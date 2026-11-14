"""SHA-256 linked audit events (integrity evidence, not immutable storage)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AuditEvent

GENESIS_HASH = "0" * 64


def event_payload(event: AuditEvent) -> dict:
    created = event.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return {
        "request_id": event.request_id,
        "event_type": event.event_type,
        "decision": event.decision,
        "agent_id": event.agent_id,
        "policy_version": event.policy_version,
        "details": event.details or {},
        "created_at": created.astimezone(timezone.utc).isoformat(),
    }


def calculate_event_hash(previous_hash: str, event: AuditEvent) -> str:
    canonical = json.dumps(
        {"previous_hash": previous_hash, "event": event_payload(event)},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def append_audit_event(
    db: Session,
    *,
    request_id: str,
    event_type: str,
    decision: str,
    details: dict,
    agent_id: str | None = None,
    policy_version: int = 1,
) -> AuditEvent:
    previous = db.scalar(select(AuditEvent.event_hash).order_by(AuditEvent.id.desc()).limit(1))
    previous_hash = previous or GENESIS_HASH
    event = AuditEvent(
        request_id=request_id,
        event_type=event_type,
        decision=decision,
        agent_id=agent_id,
        policy_version=policy_version,
        details=details,
        created_at=datetime.now(timezone.utc),
        previous_hash=previous_hash,
    )
    event.event_hash = calculate_event_hash(previous_hash, event)
    db.add(event)
    return event


def verify_audit_chain(db: Session) -> dict:
    rows = db.scalars(select(AuditEvent).order_by(AuditEvent.id)).all()
    previous_hash = GENESIS_HASH
    for index, event in enumerate(rows, start=1):
        expected = calculate_event_hash(previous_hash, event)
        if event.previous_hash != previous_hash or event.event_hash != expected:
            return {"valid": False, "event_count": len(rows), "invalid_event_id": event.id, "verified_count": index - 1}
        previous_hash = event.event_hash
    return {"valid": True, "event_count": len(rows), "invalid_event_id": None, "verified_count": len(rows)}
