"""Validated API schemas. No wallet credentials or signing material are accepted."""

from __future__ import annotations

import math
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EvaluationIntake(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    sender: str = Field(default="agent.testnet", min_length=2, max_length=64)
    agent_id: str = Field(default="agent.testnet", min_length=2, max_length=64)
    recipient: str = Field(min_length=2, max_length=64)
    amount_near: float = Field(gt=0, le=10_000_000)
    prompt: str | None = Field(default=None, max_length=4000)
    memo: str | None = Field(default=None, max_length=512)
    tool_name: str | None = Field(default=None, max_length=64)
    contract_account: str | None = Field(default=None, max_length=128)

    @field_validator("amount_near")
    @classmethod
    def amount_must_be_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("amount_near must be finite")
        return value

    @field_validator("sender", "recipient")
    @classmethod
    def validate_account_id(cls, value: str) -> str:
        if len(value) > 64 or not re.fullmatch(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", value):
            raise ValueError("must be a valid lowercase NEAR account identifier")
        return value

    @field_validator("agent_id")
    @classmethod
    def validate_agent_id(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,63}", value):
            raise ValueError("must be a valid agent identifier")
        return value

    @field_validator("tool_name")
    @classmethod
    def validate_tool_name(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", value):
            raise ValueError("must be a valid tool identifier")
        return value


class EvaluationAccepted(BaseModel):
    request_id: str
    decision: str
    status: str
    risk_score: int
    explanation: str
    checks: dict[str, str]
    review_expires_at: str | None = None
    transaction_execution: str = "disabled"


class PolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_transaction_near: float = Field(gt=0, le=10_000_000)
    daily_limit_near: float = Field(gt=0, le=100_000_000)
    review_threshold_near: float = Field(ge=0, le=10_000_000)
    allowlist: list[str] = Field(max_length=500)
    blocklist: list[str] = Field(max_length=500)
    prompt_detection_enabled: bool = True
    velocity_enabled: bool = True
    velocity_max_requests: int = Field(ge=1, le=1000)
    velocity_window_seconds: int = Field(ge=1, le=86400)
    duplicate_window_seconds: int = Field(ge=1, le=86400)
    allowed_tools: list[str] | None = Field(default=None, max_length=100)
    allowed_contracts: list[str] | None = Field(default=None, max_length=500)

    @field_validator("max_transaction_near", "daily_limit_near", "review_threshold_near")
    @classmethod
    def finite_policy_amount(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("policy amounts must be finite")
        return value

    @field_validator("allowlist", "blocklist")
    @classmethod
    def validate_wallet_lists(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().lower() for value in values]
        if any(not re.fullmatch(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", item) or len(item) > 64 for item in normalized):
            raise ValueError("wallet list contains an invalid account identifier")
        return sorted(set(normalized))

    @field_validator("allowed_tools")
    @classmethod
    def validate_allowed_tools(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        if any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", item) for item in values):
            raise ValueError("allowed_tools contains an invalid tool identifier")
        return sorted(set(values))

    @field_validator("allowed_contracts")
    @classmethod
    def validate_allowed_contracts(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        normalized = [value.strip().lower() for value in values]
        if any(len(item) > 64 or not re.fullmatch(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", item) for item in normalized):
            raise ValueError("allowed_contracts contains an invalid NEAR account ID")
        return sorted(set(normalized))


class AgentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frozen: bool


class HumanDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str

    @field_validator("action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        value = value.upper()
        if value not in {"APPROVE", "REJECT"}:
            raise ValueError("action must be APPROVE or REJECT")
        return value


class HealthResponse(BaseModel):
    status: str
    database: str
    execution: str = "disabled"


class NearHealthResponse(BaseModel):
    status: Literal["healthy"]
    network: Literal["testnet"]
    latency_ms: int = Field(ge=0)
    checked_at: str


class NearAccountResponse(BaseModel):
    account_id: str
    network: Literal["testnet"]
    balance_near: str
    locked_near: str
    storage_usage: int | None
    code_hash: str
    is_contract: bool


class NearContractResponse(BaseModel):
    account_id: str
    network: Literal["testnet"]
    is_contract: bool
    code_hash: str


class NearTransactionResponse(BaseModel):
    verified: Literal[True]
    network: Literal["testnet"]
    transaction_hash: str
    sender_account_id: str
    execution_status: dict[str, Any]
    explorer_url: str
