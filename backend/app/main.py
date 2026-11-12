from __future__ import annotations

import math
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from app.near.testnet import create_authorization_receipt, is_valid_account_id, verify_testnet_account
from app.security.policy import policy_engine
from app.foundation.main import app as v4_api_app


@asynccontextmanager
async def app_lifespan(_app: FastAPI):
    async with v4_api_app.router.lifespan_context(v4_api_app):
        yield


app = FastAPI(title="AgentGuard AI", description="Payment security demo API", lifespan=app_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

audit_logs: list[dict] = []
_audit_lock = threading.Lock()


class PaymentCheck(BaseModel):
    sender: str = "agent.testnet"
    recipient: str
    amount: float = Field(gt=0)
    memo: str | None = None

    @field_validator("amount")
    @classmethod
    def amount_must_be_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("amount must be finite")
        return value


class PaymentReview(BaseModel):
    action: str

    @field_validator("action")
    @classmethod
    def action_is_valid(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"APPROVE", "REJECT"}:
            raise ValueError("action must be APPROVE or REJECT")
        return normalized


@app.get("/")
def health_check():
    return {"project": "AgentGuard AI", "status": "running", "network": "NEAR Testnet"}


@app.post("/payment/check")
def check_payment(payment: PaymentCheck):
    result = policy_engine.evaluate(payment.sender, payment.recipient, payment.amount, payment.memo)
    near_status = "not_checked_policy_block"
    decision, reason, risk_score = result.decision, result.reason, result.risk_score
    receipt = None

    # Do not perform RPC calls for policy-rejected requests. Non-testnet allowlisted
    # demo account IDs are format-checked but cannot be verified on Testnet.
    if decision in {"APPROVE", "PENDING_APPROVAL"}:
        if not is_valid_account_id(payment.sender) or not is_valid_account_id(payment.recipient):
            decision, reason, risk_score = "BLOCK", "Invalid NEAR account format", 90
            near_status = "invalid_account_format"
        elif payment.recipient.endswith(".testnet"):
            exists, near_status = verify_testnet_account(payment.recipient)
            if exists is False:
                decision, reason, risk_score = "BLOCK", "Recipient account does not exist on NEAR Testnet", 90
            elif exists is None:
                decision, reason, risk_score = "BLOCK", "Recipient could not be verified on NEAR Testnet", 75
        else:
            near_status = "valid_format_non_testnet_unverified"

    if decision == "APPROVE":
        receipt = create_authorization_receipt(payment.sender, payment.recipient, payment.amount)
        reason = "Payment passed policy; authorization receipt is simulated (no transaction submitted)"

    tx_id = receipt or ("pending_" + uuid.uuid4().hex[:20] if decision == "PENDING_APPROVAL" else None)

    response = {
        "decision": decision,
        "reason": reason,
        "risk_score": risk_score,
        "near_status": near_status,
        "tx_simulation_id": tx_id,
    }
    log_item = {**payment.model_dump(), **response, "timestamp": datetime.now(timezone.utc).isoformat()}
    with _audit_lock:
        log_item["tx_id"] = tx_id or ("blocked_" + uuid.uuid4().hex[:16])
        audit_logs.append(log_item)
    return response


@app.post("/payment/review/{tx_id}")
def review_payment(tx_id: str, review: PaymentReview):
    with _audit_lock:
        item = next((entry for entry in audit_logs if entry.get("tx_id") == tx_id), None)
        if item is None:
            raise HTTPException(status_code=404, detail="Payment not found")
        if item["decision"] != "PENDING_APPROVAL":
            raise HTTPException(status_code=409, detail="Payment is no longer pending approval")
        if review.action == "APPROVE":
            item["decision"] = "APPROVE"
            item["reason"] = "Approved by human reviewer; authorization receipt is simulated (no transaction submitted)"
            item["risk_score"] = min(item["risk_score"], 35)
            item["tx_simulation_id"] = create_authorization_receipt(item["sender"], item["recipient"], item["amount"])
        else:
            item["decision"] = "BLOCK"
            item["reason"] = "Rejected by human reviewer"
            item["risk_score"] = max(item["risk_score"], 70)
            item["tx_simulation_id"] = None
        item["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        item["review_action"] = review.action
        return dict(item)


@app.get("/audit-logs")
def get_audit_logs():
    with _audit_lock:
        return list(audit_logs)


@app.post("/audit-logs/clear")
def clear_audit_logs():
    with _audit_lock:
        audit_logs.clear()
    policy_engine.clear()
    return {"status": "cleared"}


@app.get("/dashboard-v4", include_in_schema=False)
def serve_dashboard_v4():
    dashboard_file = Path(__file__).resolve().parents[2] / "frontend" / "dashboard_v4.html"
    if not dashboard_file.is_file():
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="dashboard_v4.html not found")
    return FileResponse(dashboard_file, media_type="text/html")


# Preserve the original payment API and expose the v4 API without route overlap.
app.mount("/v4", v4_api_app, name="v4-api")
