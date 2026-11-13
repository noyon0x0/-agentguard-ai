import hashlib
import json
import re
import time
import urllib.request
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from .foundation.main import app as v4_api_app
from .foundation.near_client import NearAccountNotFound, NearIntegrationError, validate_account_id
from .foundation.telegram import send_telegram

@asynccontextmanager
async def app_lifespan(_app: FastAPI):
    # The mounted v4 API has its own SQLite engine and startup migrations.
    # Run its lifespan explicitly because mounted sub-app lifespan handling is
    # not automatic in every supported Starlette version.
    async with v4_api_app.router.lifespan_context(v4_api_app):
        yield


app = FastAPI(title="AgentGuard AI v3.0 Ultimate", version="3.0.0", lifespan=app_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

POLICY_STATE = {
    "max_single_tx_near": 10.0,
    "daily_spend_limit_near": 30.0,
    "hitl_threshold_near": 5.0,
    "block_prompt_injection": True,
    "strict_whitelist_mode": True,
    "velocity_guard_enabled": True,
    "telegram_alerts_enabled": True,
    "connected_wallet": "founder.testnet",
    "whitelisted_wallets": [
        "treasury.testnet",
        "vendor.testnet",
        "staking.pool.testnet",
        "payroll.dao.testnet",
    ],
    "blacklisted_wallets": [
        "attacker.testnet",
        "drainer.evil.testnet",
        "tornado-mixer.testnet",
    ],
}

AGENTS_DB = {
    "DeFi-Trader-Bot": {"role": "Automated Yield & Swap", "trust": "HIGH", "daily_spent": 2.5, "frozen": False, "recent_ts": []},
    "Auto-Payroll-Agent": {"role": "DAO Contributor Payouts", "trust": "HIGH", "daily_spent": 5.0, "frozen": False, "recent_ts": []},
    "Marketing-Grant-Bot": {"role": "Community Bounties", "trust": "MEDIUM", "daily_spent": 1.0, "frozen": False, "recent_ts": []},
    "External-Plugin-Agent": {"role": "3rd-Party Plugin", "trust": "LOW", "daily_spent": 0.0, "frozen": False, "recent_ts": []},
}

AUDIT_LOGS: List[Dict] = []
PENDING_QUEUE: Dict[str, Dict] = {}
TELEGRAM_FEED: List[Dict] = []

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"bypass\s+(security|guard|policy|limit)",
    r"system\s+override",
    r"drain\s+(wallet|funds|all)",
    r"transfer\s+everything",
    r"act\s+as\s+admin",
    r"sudo\s+mode",
    r"forget\s+rules",
    r"secret\s+urgent\s+transfer",
]

class TransactionRequest(BaseModel):
    agent_id: str = "DeFi-Trader-Bot"
    prompt: str
    recipient: str
    amount_near: float

class PolicyUpdate(BaseModel):
    max_single_tx_near: float
    hitl_threshold_near: float
    block_prompt_injection: bool
    strict_whitelist_mode: bool
    velocity_guard_enabled: bool
    telegram_alerts_enabled: bool

class WalletListAction(BaseModel):
    list_type: str
    action: str
    wallet: str

class AgentFreezeAction(BaseModel):
    agent_id: str
    frozen: bool

class ApprovalAction(BaseModel):
    tx_id: str
    action: str

class WalletConnectReq(BaseModel):
    wallet_id: str

def sha256_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

def check_near_rpc(account_id: str) -> dict:
    try:
        account_id = validate_account_id(account_id)
        account = v4_api_app.state.near_client.get_account(account_id)
        return {"exists": True, "verified": True, "balance_near": account["balance_near"], "network": "testnet"}
    except NearAccountNotFound:
        return {"exists": False, "verified": True, "balance_near": None, "network": "testnet"}
    except NearIntegrationError:
        return {"exists": None, "verified": False, "balance_near": None, "network": "unavailable", "status": "rpc_unavailable"}

def send_telegram_alert(title: str, message: str, severity: str):
    if not POLICY_STATE["telegram_alerts_enabled"]:
        return
    TELEGRAM_FEED.insert(0, {
        "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
        "title": title,
        "message": message,
        "severity": severity,
    })
    if len(TELEGRAM_FEED) > 15:
        TELEGRAM_FEED.pop()
    delivery = send_telegram(v4_api_app.state.settings, title, message)
    TELEGRAM_FEED[0]["delivery_status"] = delivery["status"]

@app.get("/api/state")
def get_state():
    approved = [x for x in AUDIT_LOGS if x["decision"] == "APPROVE"]
    blocked = [x for x in AUDIT_LOGS if x["decision"] == "BLOCK"]
    return {
        "stats": {
            "total": len(AUDIT_LOGS),
            "approved_count": len(approved),
            "blocked_count": len(blocked),
            "pending_count": len(PENDING_QUEUE),
            "approved_vol": round(sum(x["amount_near"] for x in approved), 2),
            "blocked_vol": round(sum(x["amount_near"] for x in blocked), 2),
        },
        "policy": {key: value for key, value in POLICY_STATE.items() if "token" not in key.casefold() and "secret" not in key.casefold()},
        "agents": AGENTS_DB,
        "pending_queue": list(PENDING_QUEUE.values()),
        "audit_logs": list(reversed(AUDIT_LOGS[-30:])),
        "telegram_feed": TELEGRAM_FEED[:8],
    }

@app.post("/api/wallet/connect")
def connect_wallet(req: WalletConnectReq):
    w = req.wallet_id.strip().lower()
    rpc = check_near_rpc(w)
    if rpc.get("verified") and rpc.get("exists"):
        POLICY_STATE["connected_wallet"] = w
    return {"wallet": w, "rpc": rpc, "status": "account_verified" if rpc.get("verified") and rpc.get("exists") else "verification_unavailable" if not rpc.get("verified") else "account_not_found"}

@app.post("/api/policy")
def update_policy(p: PolicyUpdate):
    POLICY_STATE["max_single_tx_near"] = p.max_single_tx_near
    POLICY_STATE["hitl_threshold_near"] = p.hitl_threshold_near
    POLICY_STATE["block_prompt_injection"] = p.block_prompt_injection
    POLICY_STATE["strict_whitelist_mode"] = p.strict_whitelist_mode
    POLICY_STATE["velocity_guard_enabled"] = p.velocity_guard_enabled
    POLICY_STATE["telegram_alerts_enabled"] = p.telegram_alerts_enabled
    return {"status": "ok", "policy": {key: value for key, value in POLICY_STATE.items() if "token" not in key.casefold() and "secret" not in key.casefold()}}

@app.post("/api/wallets")
def manage_wallets(item: WalletListAction):
    target = "whitelisted_wallets" if item.list_type == "whitelist" else "blacklisted_wallets"
    w = item.wallet.strip().lower()
    if not w:
        raise HTTPException(status_code=400, detail="Empty wallet")
    if item.action == "add" and w not in POLICY_STATE[target]:
        POLICY_STATE[target].append(w)
    elif item.action == "remove" and w in POLICY_STATE[target]:
        POLICY_STATE[target].remove(w)
    return {"status": "ok", "policy": POLICY_STATE}

@app.post("/api/agent/freeze")
def toggle_agent_freeze(item: AgentFreezeAction):
    if item.agent_id in AGENTS_DB:
        AGENTS_DB[item.agent_id]["frozen"] = item.frozen
        st = "FROZEN (Kill-Switch Active)" if item.frozen else "ACTIVE"
        send_telegram_alert(f"Agent {st}", f"{item.agent_id} changed by operator.", "WARN" if item.frozen else "INFO")
    return {"status": "ok", "agents": AGENTS_DB}

@app.post("/api/evaluate")
def evaluate_tx(tx: TransactionRequest):
    now_ts = time.time()
    tx_id = f"AG-{int(now_ts * 1000) % 1000000}"
    ts_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    recipient = tx.recipient.strip().lower()
    risk = 5
    reasons = []
    pipeline = {"semantic_ai": "PASS", "velocity_guard": "PASS", "dry_run_rpc": "PASS", "crypto_seal": "PENDING"}

    agent = AGENTS_DB.get(tx.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Unknown Agent")

    if agent["frozen"]:
        risk = 100
        pipeline["semantic_ai"] = "FROZEN"
        pipeline["velocity_guard"] = "BLOCKED"
        pipeline["dry_run_rpc"] = "SKIPPED"
        reasons.append(f"EMERGENCY KILL-SWITCH: {tx.agent_id} is frozen.")

    agent["recent_ts"] = [t for t in agent["recent_ts"] if now_ts - t < 15]
    agent["recent_ts"].append(now_ts)
    if POLICY_STATE["velocity_guard_enabled"] and len(agent["recent_ts"]) > 3:
        risk = max(risk, 92)
        pipeline["velocity_guard"] = "FAIL"
        reasons.append("VELOCITY ANOMALY: Rapid burst (>3 tx in 15s) blocked.")

    if any(re.search(pat, tx.prompt.lower()) for pat in INJECTION_PATTERNS) and POLICY_STATE["block_prompt_injection"]:
        risk = max(risk, 98)
        pipeline["semantic_ai"] = "FAIL"
        reasons.append("SEMANTIC THREAT: Prompt Injection / Jailbreak intent detected.")

    if agent["trust"] == "LOW":
        risk = max(risk, 45)
        reasons.append("Low-trust 3rd-party agent privilege.")

    if recipient in POLICY_STATE["blacklisted_wallets"]:
        risk = 99
        pipeline["dry_run_rpc"] = "FAIL"
        reasons.append(f"BLACKLISTED TARGET: '{recipient}' is a known malicious address.")
    elif POLICY_STATE["strict_whitelist_mode"] and recipient not in POLICY_STATE["whitelisted_wallets"]:
        risk = max(risk, 76)
        pipeline["dry_run_rpc"] = "FAIL"
        reasons.append(f"UNVERIFIED WALLET: '{recipient}' not in trusted Whitelist.")

    if tx.amount_near > POLICY_STATE["max_single_tx_near"]:
        risk = max(risk, 88)
        pipeline["velocity_guard"] = "FAIL"
        reasons.append(f"LIMIT EXCEEDED: {tx.amount_near} NEAR > {POLICY_STATE['max_single_tx_near']} NEAR cap.")

    rpc_info = check_near_rpc(recipient)

    if risk >= 70:
        decision = "BLOCK"
        pipeline["crypto_seal"] = "REJECTED"
        explanation = " | ".join(reasons)
        explorer_hash = None
        send_telegram_alert("🚨 Attack Blocked!", f"{tx.agent_id} -> {tx.amount_near} NEAR to {recipient} (Risk {risk}/100)", "CRITICAL")
    elif tx.amount_near > POLICY_STATE["hitl_threshold_near"] or risk >= 40:
        decision = "PENDING_APPROVAL"
        pipeline["crypto_seal"] = "AWAITING_HUMAN"
        explanation = f"Held for Human-in-the-Loop sign-off ({tx.amount_near} NEAR > {POLICY_STATE['hitl_threshold_near']} NEAR)."
        explorer_hash = None
        send_telegram_alert("⏳ Operator Review Needed", f"{tx.agent_id} requested {tx.amount_near} NEAR to {recipient}.", "WARN")
    else:
        decision = "APPROVE"
        pipeline["crypto_seal"] = "EXECUTION_DISABLED"
        agent["daily_spent"] = round(agent["daily_spent"] + tx.amount_near, 2)
        explanation = "Policy checks passed. No transaction was signed or submitted."
        explorer_hash = None

    record = {
        "tx_id": tx_id,
        "timestamp": ts_str,
        "agent_id": tx.agent_id,
        "prompt": tx.prompt,
        "recipient": recipient,
        "amount_near": tx.amount_near,
        "risk_score": min(risk, 100),
        "decision": decision,
        "explanation": explanation,
        "pipeline": pipeline,
        "rpc_balance": rpc_info["balance_near"],
        "explorer_hash": explorer_hash,
    }
    record["audit_hash"] = sha256_hash(record)

    if decision == "PENDING_APPROVAL":
        PENDING_QUEUE[tx_id] = record
    else:
        AUDIT_LOGS.append(record)

    return record

@app.post("/api/hitl")
def resolve_hitl(item: ApprovalAction):
    if item.tx_id not in PENDING_QUEUE:
        raise HTTPException(status_code=404, detail="Not found")
    rec = PENDING_QUEUE.pop(item.tx_id)
    if item.action == "APPROVE":
        rec["decision"] = "APPROVE"
        rec["pipeline"]["crypto_seal"] = "HUMAN_APPROVED_POLICY_ONLY"
        rec["explanation"] = "Human reviewer approved the policy request; no transaction was signed or submitted."
        rec["explorer_hash"] = None
    else:
        rec["decision"] = "BLOCK"
        rec["pipeline"]["crypto_seal"] = "HUMAN_REJECTED"
        rec["explanation"] = "Rejected by Human Security Operator."
    rec["audit_hash"] = sha256_hash(rec)
    AUDIT_LOGS.append(rec)
    return rec


@app.get("/dashboard-v4", include_in_schema=False)
def serve_dashboard_v4():
    dashboard_file = Path(__file__).resolve().parents[2] / "frontend" / "dashboard_v4.html"
    if not dashboard_file.is_file():
        raise HTTPException(status_code=404, detail="dashboard_v4.html not found")
    return FileResponse(dashboard_file, media_type="text/html")


# Keep established v3 routes intact; v4 uses its own API under this path.
app.mount("/v4", v4_api_app, name="v4-api")

