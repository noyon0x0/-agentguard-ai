"""Read-only dashboard projections backed by persisted backend state."""

from __future__ import annotations

from datetime import timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from .models import AgentState, AuditEvent, PolicyConfiguration, SecurityEvaluation
from .routes import database_session
from .security_engine import PROMPT_ATTACK_PATTERNS, ensure_default_policy
from .telegram import telegram_configured

router = APIRouter(prefix="/api/v1")


def _utc(value) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


@router.get("/overview", tags=["dashboard"])
def dashboard_overview(db: Session = Depends(database_session)) -> dict:
    result = db.execute(
        select(
            func.count(SecurityEvaluation.id),
            func.sum(case((SecurityEvaluation.status == "APPROVE", 1), else_=0)),
            func.sum(case((SecurityEvaluation.status == "REVIEW", 1), else_=0)),
            func.sum(case((SecurityEvaluation.status == "BLOCK", 1), else_=0)),
            func.coalesce(func.sum(SecurityEvaluation.amount_near), 0.0),
            func.max(SecurityEvaluation.created_at),
        )
    ).one()
    policy = db.get(PolicyConfiguration, 1)
    return {
        "total_requests": result[0] or 0,
        "approved_count": result[1] or 0,
        "review_count": result[2] or 0,
        "blocked_count": result[3] or 0,
        "evaluated_amount_near": round(float(result[4] or 0), 8),
        "last_evaluation_at": _utc(result[5]),
        "execution_enabled": False,
        "policy_version": policy.policy_version if policy else 1,
        "global_kill_switch": policy.global_kill_switch if policy else True,
    }


@router.get("/agents", tags=["agents"])
def list_agents(db: Session = Depends(database_session)) -> list[dict]:
    ensure_default_policy(db)
    grouped = db.execute(
        select(
            SecurityEvaluation.agent_id,
            func.count(SecurityEvaluation.id),
            func.max(SecurityEvaluation.created_at),
        ).group_by(SecurityEvaluation.agent_id)
    ).all()
    activity = {agent_id: (count, last_seen) for agent_id, count, last_seen in grouped}
    agents = db.scalars(select(AgentState).order_by(AgentState.agent_id)).all()
    return [
        {
            "agent_id": agent.agent_id,
            "frozen": agent.frozen,
            "evaluation_count": activity.get(agent.agent_id, (0, None))[0],
            "last_evaluation_at": _utc(activity.get(agent.agent_id, (0, None))[1]),
        }
        for agent in agents
    ]


@router.get("/threats", tags=["threat intelligence"])
def threat_center(db: Session = Depends(database_session), limit: int = 30) -> dict:
    if not 1 <= limit <= 100:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail={"code": "INVALID_LIMIT"})
    ensure_default_policy(db)
    policy = db.get(PolicyConfiguration, 1)
    recent_blocks = db.scalars(
        select(SecurityEvaluation)
        .where(SecurityEvaluation.status == "BLOCK")
        .order_by(SecurityEvaluation.created_at.desc())
        .limit(limit)
    ).all()
    return {
        "source": "local_policy_engine",
        "external_feed_configured": False,
        "rules": [
            {
                "id": "prompt_injection",
                "enabled": policy.prompt_detection_enabled,
                "description": f"{len(PROMPT_ATTACK_PATTERNS)} deterministic patterns loaded",
            },
            {
                "id": "wallet_allowlist_blocklist",
                "enabled": True,
                "description": f"{len(policy.allowlist)} allowlist and {len(policy.blocklist)} blocklist entries",
            },
            {
                "id": "transaction_and_daily_limits",
                "enabled": True,
                "description": f"Maximum {policy.max_transaction_near} NEAR per request; daily limit {policy.daily_limit_near} NEAR",
            },
            {
                "id": "velocity_and_duplicate_detection",
                "enabled": policy.velocity_enabled,
                "description": f"Velocity: {policy.velocity_max_requests} requests/{policy.velocity_window_seconds}s; duplicate window {policy.duplicate_window_seconds}s",
            },
            {
                "id": "tool_authorization",
                "enabled": True,
                "description": f"{len(policy.allowed_tools)} allowed tool identifiers",
            },
            {
                "id": "contract_allowlist",
                "enabled": True,
                "description": f"{len(policy.allowed_contracts)} approved contract accounts",
            },
            {"id": "frozen_agent_enforcement", "enabled": True, "description": "Frozen state enforced for registered agents"},
        ],
        "recent_blocks": [
            {
                "request_id": item.request_id,
                "agent_id": item.agent_id,
                "recipient": item.recipient,
                "amount_near": item.amount_near,
                "risk_score": item.risk_score,
                "explanation": item.explanation,
                "created_at": _utc(item.created_at),
            }
            for item in recent_blocks
        ],
    }


@router.get("/telegram/status", tags=["monitoring"])
def telegram_status(request: Request) -> dict:
    configured = telegram_configured(request.app.state.settings)
    return {
        "enabled": configured,
        "configured": configured,
        "status": "configured" if configured else "not_configured",
        "message": "Server-side Telegram alerts are configured." if configured else "Telegram delivery is not configured for this backend.",
    }


@router.get("/settings", tags=["settings"])
def system_settings(request: Request) -> dict:
    settings = request.app.state.settings
    return {
        "app_name": settings.app_name,
        "environment": settings.environment,
        "database_backend": request.app.state.database_engine.dialect.name,
        "near_rpc_configured": bool(settings.near_testnet_rpc_url),
        "near_rpc_timeout_seconds": settings.near_rpc_timeout_seconds,
        "near_network_required": "testnet",
        "admin_auth_configured": bool(settings.admin_token),
        "telegram_configured": telegram_configured(settings),
        "transaction_signing_enabled": bool(settings.near_transactions_enabled and settings.near_testnet_private_key),
        "transaction_submission_enabled": bool(settings.near_transactions_enabled and settings.near_testnet_private_key),
    }


@router.get("/audit/summary", tags=["audit"])
def audit_summary(db: Session = Depends(database_session)) -> dict:
    count = db.scalar(select(func.count(AuditEvent.id))) or 0
    latest = db.scalar(select(func.max(AuditEvent.created_at)))
    return {"event_count": count, "latest_event_at": _utc(latest), "storage": "sqlite"}
