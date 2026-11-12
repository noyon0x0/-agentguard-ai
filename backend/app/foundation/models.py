"""Database models for security decision intake and audit metadata."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SecurityEvaluation(Base):
    """Persisted request record; it is not a signed transaction."""

    __tablename__ = "security_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    sender: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    recipient: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_near: Mapped[float] = mapped_column(Float, nullable=False)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contract_account: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="REVIEW", index=True)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    checks: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    payload_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    review_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class PolicyConfiguration(Base):
    __tablename__ = "policy_configuration"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    max_transaction_near: Mapped[float] = mapped_column(Float, nullable=False, default=10.0)
    daily_limit_near: Mapped[float] = mapped_column(Float, nullable=False, default=25.0)
    review_threshold_near: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    allowlist: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    blocklist: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    prompt_detection_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    velocity_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    velocity_max_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    velocity_window_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    duplicate_window_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    allowed_tools: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    allowed_contracts: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)


class AgentState(Base):
    __tablename__ = "agent_states"

    agent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    frozen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    scenario: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    expected_decision: Mapped[str] = mapped_column(String(16), nullable=False)
    actual_decision: Mapped[str] = mapped_column(String(16), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    execution_ms: Mapped[float] = mapped_column(Float, nullable=False)
    request_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
