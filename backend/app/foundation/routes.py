"""HTTP routes for policy evaluation, approvals, and protected administration."""

from __future__ import annotations

import hmac
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .approval_workflow import resolve_human_decision
from .models import AgentState, AuditEvent, PolicyConfiguration, SecurityEvaluation
from .schemas import (
    AgentUpdate,
    EvaluationAccepted,
    EvaluationIntake,
    HealthResponse,
    HumanDecision,
    PolicyUpdate,
)
from .security_engine import ensure_default_policy, evaluate_policy, payload_fingerprint

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
) -> None:
    db.add(AuditEvent(request_id=request_id, event_type=event_type, decision=decision, details=details))


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
            details={"risk_score": result.risk_score, "checks": result.checks},
        )
        db.commit()
        db.refresh(record)
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
    }


@router.put("/policy", tags=["policy"], dependencies=[Depends(require_admin)])
def update_policy(payload: PolicyUpdate, db: Session = Depends(database_session)) -> dict:
    ensure_default_policy(db)
    policy = db.get(PolicyConfiguration, 1)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(policy, key, value)
    write_audit(
        db,
        request_id=str(uuid.uuid4()),
        event_type="POLICY_UPDATED",
        decision="UPDATED",
        details={"fields": sorted(payload.model_fields_set)},
    )
    db.commit()
    return {"status": "updated", "policy": get_policy(db)}


@router.put("/agents/{agent_id}", tags=["agents"], dependencies=[Depends(require_admin)])
def update_agent(
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
    )
    db.commit()
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
            "details": row.details,
            "created_at": row.created_at.replace(tzinfo=timezone.utc).isoformat(),
        }
        for row in rows
    ]
