"""Human approval lifecycle shared by API actions and the simulation lab."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .models import AuditEvent, SecurityEvaluation
from .schemas import EvaluationIntake
from .security_engine import evaluate_policy


def resolve_human_decision(
    db: Session,
    record: SecurityEvaluation,
    action: str,
    *,
    now: datetime | None = None,
) -> SecurityEvaluation:
    now = now or datetime.now(timezone.utc)
    if record.status != "REVIEW":
        raise ValueError("request is not awaiting human review")

    expires_at = record.review_expires_at
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= now:
            record.status = "BLOCK"
            record.explanation = "Human approval window expired; the request was blocked."
            db.add(
                AuditEvent(
                    request_id=record.request_id,
                    event_type="HUMAN_APPROVAL_EXPIRED",
                    decision="BLOCK",
                    details={"expired_at": expires_at.isoformat()},
                )
            )
            db.commit()
            db.refresh(record)
            return record

    if action == "REJECT":
        record.status = "BLOCK"
        record.explanation = "Human operator rejected the request."
        event_type = "HUMAN_REJECTED"
    elif action == "APPROVE":
        payload = EvaluationIntake(
            sender=record.sender,
            agent_id=record.agent_id,
            recipient=record.recipient,
            amount_near=record.amount_near,
            prompt=record.prompt,
            memo=record.memo,
            tool_name=record.tool_name,
            contract_account=record.contract_account,
        )
        result = evaluate_policy(db, payload, exclude_request_id=record.request_id, now=now)
        record.checks = result.checks
        if result.decision == "BLOCK":
            record.status = "BLOCK"
            record.risk_score = result.risk_score
            record.explanation = "Human approval denied because current policy blocks the request. " + result.explanation
            event_type = "HUMAN_APPROVAL_DENIED_BY_POLICY"
        else:
            record.status = "APPROVE"
            record.explanation = "Human operator approved the request after current blocking checks passed."
            event_type = "HUMAN_APPROVED"
    else:
        raise ValueError("action must be APPROVE or REJECT")

    db.add(
        AuditEvent(
            request_id=record.request_id,
            event_type=event_type,
            decision=record.status,
            details={"operator": "authenticated_admin"},
        )
    )
    db.commit()
    db.refresh(record)
    return record
