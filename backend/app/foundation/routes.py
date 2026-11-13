"""HTTP routes for policy evaluation, approvals, and protected administration."""

from __future__ import annotations

import hmac
import csv
import io
import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Request, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .approval_workflow import resolve_human_decision
from .audit_chain import append_audit_event, verify_audit_chain
from .models import AgentState, AuditEvent, PolicyConfiguration, PolicyRevision, SecurityEvaluation
from .schemas import (
    AgentUpdate,
    EvaluationAccepted,
    EvaluationIntake,
    HealthResponse,
    HumanDecision,
    KillSwitchUpdate,
    PolicyUpdate,
)
from .security_engine import ensure_default_policy, evaluate_policy, payload_fingerprint, policy_snapshot
from .telegram import send_telegram, telegram_configured

router = APIRouter(prefix="/api/v1")
bearer_scheme = HTTPBearer(auto_error=False)


def database_session(request: Request):
    session_factory = request.app.state.session_factory
    with session_factory() as session:
        yield session


def require_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    expected = request.app.state.settings.admin_token
    if not expected:
        raise HTTPException(status_code=503, detail={"code": "ADMIN_AUTH_NOT_CONFIGURED"})
    supplied = credentials.credentials if credentials else ""
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED"})
    return "admin"


def evaluation_response(record: SecurityEvaluation) -> EvaluationAccepted:
    return EvaluationAccepted(
        request_id=record.request_id,
        decision=record.status,
        status=record.status,
        risk_score=record.risk_score,
        network=record.network,
        policy_version=record.policy_version,
        request_timestamp=(
            record.created_at.replace(tzinfo=timezone.utc).isoformat()
            if record.created_at.tzinfo is None else record.created_at.isoformat()
        ),
        explanation=record.explanation,
        checks=record.checks,
        review_expires_at=(
            record.review_expires_at.replace(tzinfo=timezone.utc).isoformat()
            if record.review_expires_at is not None and record.review_expires_at.tzinfo is None
            else record.review_expires_at.isoformat() if record.review_expires_at is not None else None
        ),
    )


def write_audit(
    db: Session,
    *,
    request_id: str,
    event_type: str,
    decision: str,
    details: dict,
    agent_id: str | None = None,
) -> None:
    policy = db.get(PolicyConfiguration, 1)
    append_audit_event(
        db, request_id=request_id, event_type=event_type, decision=decision, details=details,
        agent_id=agent_id, policy_version=policy.policy_version if policy else 1,
    )


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health_check(db: Session = Depends(database_session)) -> HealthResponse:
    db.execute(text("SELECT 1"))
    return HealthResponse(status="ok", database="ok")


@router.post(
    "/evaluations",
    response_model=EvaluationAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["security evaluations"],
    summary="Evaluate a request with server-side security policy; never execute it",
)
def accept_evaluation(
    payload: EvaluationIntake,
    request: Request,
    idempotency_key: str = Header(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"),
    db: Session = Depends(database_session),
) -> EvaluationAccepted:
    # Serialize policy read/check/write within this process so velocity, duplicate,
    # daily-limit, and idempotency checks observe the preceding decision. SQLite's
    # write reservation also serializes independent app workers sharing the DB.
    with request.app.state.security_lock:
        ensure_default_policy(db)
        db.execute(text("BEGIN IMMEDIATE"))
        fingerprint = payload_fingerprint(payload)
        prior = db.scalar(select(SecurityEvaluation).where(SecurityEvaluation.idempotency_key == idempotency_key))
        if prior is not None:
            if prior.payload_fingerprint != fingerprint:
                raise HTTPException(status_code=409, detail={"code": "IDEMPOTENCY_KEY_REUSED"})
            return evaluation_response(prior)

        policy = db.get(PolicyConfiguration, 1)
        result = evaluate_policy(db, payload)
        request_id = str(uuid.uuid4())
        record = SecurityEvaluation(
            request_id=request_id,
            idempotency_key=idempotency_key,
            payload_fingerprint=fingerprint,
            sender=payload.sender,
            agent_id=payload.agent_id,
            recipient=payload.recipient,
            amount_near=payload.amount_near,
            network=payload.network,
            policy_version=policy.policy_version,
            prompt=payload.prompt,
            memo=payload.memo,
            tool_name=payload.tool_name,
            contract_account=payload.contract_account,
            status=result.decision,
            risk_score=result.risk_score,
            explanation=result.explanation,
            checks=result.checks,
            review_expires_at=(datetime.now(timezone.utc) + timedelta(minutes=15))
            if result.decision == "REVIEW"
            else None,
        )
        db.add(record)
        write_audit(
            db,
            request_id=request_id,
            event_type="POLICY_DECISION",
            decision=result.decision,
            details={"risk_score": result.risk_score, "checks": result.checks, "network": payload.network},
            agent_id=payload.agent_id,
        )
        db.commit()
        db.refresh(record)
        if result.decision == "BLOCK":
            send_telegram(request.app.state.settings, "BLOCKED_TRANSACTION", f"request {record.request_id} was blocked")
            if result.checks.get("prompt_injection") == "FAIL":
                send_telegram(request.app.state.settings, "PROMPT_INJECTION", f"request {record.request_id} was blocked")
        elif result.decision == "REVIEW":
            send_telegram(request.app.state.settings, "HUMAN_APPROVAL_REQUIRED", f"request {record.request_id} requires review")
        return evaluation_response(record)


@router.get("/evaluations/pending", tags=["human approval"], dependencies=[Depends(require_admin)])
def pending_evaluations(db: Session = Depends(database_session)) -> list[EvaluationAccepted]:
    records = db.scalars(
        select(SecurityEvaluation).where(SecurityEvaluation.status == "REVIEW").order_by(SecurityEvaluation.created_at)
    ).all()
    return [evaluation_response(record) for record in records]


@router.post("/evaluations/{request_id}/decision", response_model=EvaluationAccepted, tags=["human approval"])
def resolve_review(
    request_id: str,
    action: HumanDecision,
    db: Session = Depends(database_session),
    _admin: str = Depends(require_admin),
) -> EvaluationAccepted:
    # Reserve the SQLite writer before loading the review record. This prevents
    # two workers from both acting on the same REVIEW snapshot.
    db.execute(text("BEGIN IMMEDIATE"))
    record = db.scalar(select(SecurityEvaluation).where(SecurityEvaluation.request_id == request_id))
    if record is None:
        raise HTTPException(status_code=404, detail={"code": "REQUEST_NOT_FOUND"})
    try:
        record = resolve_human_decision(db, record, action.action)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"code": "REQUEST_NOT_PENDING_REVIEW"}) from exc
    return evaluation_response(record)


@router.get("/policy", tags=["policy"])
def get_policy(db: Session = Depends(database_session)) -> dict:
    ensure_default_policy(db)
    policy = db.get(PolicyConfiguration, 1)
    return {
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
        "policy_version": policy.policy_version,
    }


@router.get("/policy/history", tags=["policy"])
def policy_history(db: Session = Depends(database_session)) -> list[dict]:
    rows = db.scalars(select(PolicyRevision).order_by(PolicyRevision.version)).all()
    return [{"version": row.version, "snapshot": row.snapshot, "created_at": row.created_at.isoformat()} for row in rows]


@router.put("/policy", tags=["policy"], dependencies=[Depends(require_admin)])
def update_policy(payload: PolicyUpdate, db: Session = Depends(database_session)) -> dict:
    ensure_default_policy(db)
    policy = db.get(PolicyConfiguration, 1)
    if payload.policy_version is not None and payload.policy_version != policy.policy_version:
        raise HTTPException(status_code=409, detail={"code": "POLICY_VERSION_CONFLICT"})
    updates = payload.model_dump(exclude_unset=True, exclude={"policy_version"})
    changed = any(getattr(policy, key) != value for key, value in updates.items())
    if changed:
        policy.policy_version += 1
        for key, value in updates.items():
            setattr(policy, key, value)
        db.add(PolicyRevision(version=policy.policy_version, snapshot=policy_snapshot(policy)))
    write_audit(
        db,
        request_id=str(uuid.uuid4()),
        event_type="POLICY_UPDATED",
        decision="UPDATED",
        details={"fields": sorted(payload.model_fields_set), "policy_version": policy.policy_version},
    )
    db.commit()
    return {"status": "updated", "policy": get_policy(db)}


@router.put("/agents/{agent_id}", tags=["agents"], dependencies=[Depends(require_admin)])
def update_agent(
    request: Request,
    agent_id: str = Path(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,63}$"),
    payload: AgentUpdate = ...,
    db: Session = Depends(database_session),
) -> dict:
    agent = db.get(AgentState, agent_id)
    if agent is None:
        agent = AgentState(agent_id=agent_id, frozen=payload.frozen)
        db.add(agent)
    else:
        agent.frozen = payload.frozen
    write_audit(
        db,
        request_id=str(uuid.uuid4()),
        event_type="AGENT_STATE_UPDATED",
        decision="UPDATED",
        details={"agent_id": agent_id, "frozen": payload.frozen},
        agent_id=agent_id,
    )
    db.commit()
    if payload.frozen:
        send_telegram(request.app.state.settings, "AGENT_FROZEN", f"agent {agent_id} was frozen")
    return {"agent_id": agent_id, "frozen": payload.frozen}


@router.get("/audit", tags=["audit"], dependencies=[Depends(require_admin)])
def list_audit_events(db: Session = Depends(database_session), limit: int = 100) -> list[dict]:
    if not 1 <= limit <= 1000:
        raise HTTPException(status_code=422, detail={"code": "INVALID_LIMIT"})
    rows = db.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)).all()
    return [
        {
            "id": row.id,
            "request_id": row.request_id,
            "event_type": row.event_type,
            "decision": row.decision,
            "agent_id": row.agent_id,
            "policy_version": row.policy_version,
            "details": row.details,
            "previous_hash": row.previous_hash,
            "event_hash": row.event_hash,
            "created_at": row.created_at.replace(tzinfo=timezone.utc).isoformat(),
        }
        for row in rows
    ]


@router.get("/activity", tags=["dashboard"])
def recent_activity(db: Session = Depends(database_session), limit: int = 6) -> list[dict]:
    if not 1 <= limit <= 50:
        raise HTTPException(status_code=422, detail={"code": "INVALID_LIMIT"})
    rows = db.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)).all()
    return [
        {
            "request_id": row.request_id,
            "event_type": row.event_type,
            "decision": row.decision,
            "created_at": row.created_at.replace(tzinfo=timezone.utc).isoformat()
            if row.created_at.tzinfo is None else row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get("/audit/verify", tags=["audit"], dependencies=[Depends(require_admin)])
def verify_audit(db: Session = Depends(database_session)) -> dict:
    return verify_audit_chain(db)


@router.get("/audit/export", tags=["audit"], dependencies=[Depends(require_admin)])
def export_audit(format: str = "json", db: Session = Depends(database_session)):
    if format not in {"json", "csv"}:
        raise HTTPException(status_code=422, detail={"code": "INVALID_EXPORT_FORMAT"})
    rows = db.scalars(select(AuditEvent).order_by(AuditEvent.id)).all()
    data = [
        {
            "id": row.id, "request_id": row.request_id, "event_type": row.event_type,
            "decision": row.decision, "agent_id": row.agent_id,
            "policy_version": row.policy_version, "details": row.details,
            "created_at": row.created_at.replace(tzinfo=timezone.utc).isoformat()
            if row.created_at.tzinfo is None else row.created_at.isoformat(),
            "previous_hash": row.previous_hash, "event_hash": row.event_hash,
        }
        for row in rows
    ]
    if format == "json":
        return {"events": data, "integrity": verify_audit_chain(db)}
    output = io.StringIO(newline="")
    fields = ["id", "request_id", "event_type", "decision", "agent_id", "policy_version", "created_at", "details", "previous_hash", "event_hash"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in data:
        row["details"] = json.dumps(row["details"], sort_keys=True)
        writer.writerow(row)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=agentguard-audit.csv"})


@router.get("/audit/incidents/{request_id}", tags=["audit"], dependencies=[Depends(require_admin)])
def incident_report(request_id: str, db: Session = Depends(database_session)) -> dict:
    evaluation = db.scalar(select(SecurityEvaluation).where(SecurityEvaluation.request_id == request_id))
    events = db.scalars(select(AuditEvent).where(AuditEvent.request_id == request_id).order_by(AuditEvent.id)).all()
    if evaluation is None and not events:
        raise HTTPException(status_code=404, detail={"code": "INCIDENT_NOT_FOUND"})
    return {
        "request_id": request_id,
        "evaluation": ({
            "agent_id": evaluation.agent_id, "recipient": evaluation.recipient,
            "amount_near": evaluation.amount_near, "network": evaluation.network,
            "decision": evaluation.status, "risk_score": evaluation.risk_score,
            "policy_version": evaluation.policy_version, "created_at": evaluation.created_at.isoformat(),
            "explanation": evaluation.explanation, "checks": evaluation.checks,
        } if evaluation else None),
        "events": [{"event_type": e.event_type, "decision": e.decision, "created_at": e.created_at.isoformat(), "event_hash": e.event_hash} for e in events],
    }


@router.get("/kill-switch", tags=["emergency response"])
def get_kill_switch(db: Session = Depends(database_session)) -> dict:
    ensure_default_policy(db)
    policy = db.get(PolicyConfiguration, 1)
    return {"enabled": policy.global_kill_switch, "policy_version": policy.policy_version}


@router.put("/kill-switch", tags=["emergency response"], dependencies=[Depends(require_admin)])
def set_kill_switch(payload: KillSwitchUpdate, request: Request, db: Session = Depends(database_session)) -> dict:
    ensure_default_policy(db)
    policy = db.get(PolicyConfiguration, 1)
    if policy.global_kill_switch != payload.enabled:
        policy.global_kill_switch = payload.enabled
        policy.policy_version += 1
        db.add(PolicyRevision(version=policy.policy_version, snapshot=policy_snapshot(policy)))
        write_audit(
            db, request_id=str(uuid.uuid4()), event_type="GLOBAL_KILL_SWITCH",
            decision="ENABLED" if payload.enabled else "DISABLED",
            details={"enabled": payload.enabled, "policy_version": policy.policy_version},
        )
        db.commit()
        if payload.enabled:
            send_telegram(request.app.state.settings, "GLOBAL_KILL_SWITCH", "the global kill switch was enabled")
    return {"enabled": policy.global_kill_switch, "policy_version": policy.policy_version}


@router.post("/telegram/test", tags=["monitoring"], dependencies=[Depends(require_admin)])
def test_telegram(request: Request) -> dict:
    settings = request.app.state.settings
    if not telegram_configured(settings):
        raise HTTPException(status_code=409, detail={"code": "TELEGRAM_NOT_CONFIGURED"})
    result = send_telegram(settings, "TEST", "operator requested a delivery check")
    if not result["delivered"]:
        raise HTTPException(status_code=502, detail={"code": "TELEGRAM_DELIVERY_FAILED"})
    return result
