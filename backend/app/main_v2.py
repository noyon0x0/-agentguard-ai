import hashlib
import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="AgentGuard AI - Enterprise Web3 Firewall", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Dynamic Security Policy State ---
POLICY_STATE = {
    "max_single_tx_near": 10.0,
    "daily_spend_limit_near": 25.0,
    "hitl_threshold_near": 5.0,  # Transactions above this need Human-in-the-Loop approval
    "block_prompt_injection": True,
    "strict_whitelist_mode": True,
    "whitelisted_wallets": [
        "treasury.testnet",
        "vendor.testnet",
        "staking.pool.testnet",
        "payroll.dao.testnet",
    ],
}

# --- Multi-Agent Profiles ---
AGENTS_DB = {
    "DeFi-Trader-Bot": {"role": "Automated Liquidity & Swap", "trust_level": "HIGH", "daily_spent": 3.5},
    "Auto-Payroll-Agent": {"role": "Contributor Disbursements", "trust_level": "HIGH", "daily_spent": 8.0},
    "Marketing-Grant-Bot": {"role": "Community Bounties", "trust_level": "MEDIUM", "daily_spent": 1.2},
    "External-Plugin-Agent": {"role": "Untrusted 3rd-Party Plugin", "trust_level": "LOW", "daily_spent": 0.0},
}

# --- Audit Logs & Pending Approvals ---
AUDIT_LOGS: List[Dict] = []
PENDING_QUEUE: Dict[str, Dict] = {}

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"bypass\s+(security|guard|policy|limit)",
    r"system\s+override",
    r"drain\s+(wallet|funds|all)",
    r"transfer\s+everything",
    r"act\s+as\s+admin",
    r"sudo\s+mode",
    r"forget\s+rules",
]


class TransactionRequest(BaseModel):
    agent_id: str = "DeFi-Trader-Bot"
    prompt: str
    recipient: str
    amount_near: float


class PolicyUpdate(BaseModel):
    max_single_tx_near: float
    daily_spend_limit_near: float
    hitl_threshold_near: float
    block_prompt_injection: bool
    strict_whitelist_mode: bool


class ApprovalAction(BaseModel):
    tx_id: str
    action: str  # "APPROVE" or "REJECT"


def compute_sha256_proof(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def check_near_testnet_account(account_id: str) -> dict:
    try:
        url = "https://rpc.testnet.near.org"
        def call(method, params=None):
            payload = {"jsonrpc": "2.0", "id": "agentguard-readonly", "method": method}
            if params is not None:
                payload["params"] = params
            request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=3) as response:
                return json.loads(response.read().decode("utf-8"))
        status = call("status")
        if status.get("result", {}).get("chain_id") != "testnet":
            return {"exists": None, "balance_near": None, "network": "wrong_network", "verified": False}
        account = call("query", {"request_type": "view_account", "finality": "final", "account_id": account_id})
        result = account.get("result")
        if not isinstance(result, dict):
            return {"exists": False, "balance_near": None, "network": "testnet", "verified": True}
        balance = int(result.get("amount", "0")) / 1e24
        return {"exists": True, "balance_near": round(balance, 8), "network": "testnet", "verified": True}
    except Exception:
        return {"exists": None, "balance_near": None, "network": "unavailable", "verified": False, "status": "rpc_unavailable"}


@app.get("/")
def health_check():
    return {"status": "ONLINE", "engine": "AgentGuard AI v2.0", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/state")
def get_dashboard_state():
    total = len(AUDIT_LOGS)
    approved = sum(1 for x in AUDIT_LOGS if x["decision"] == "APPROVE")
    blocked = sum(1 for x in AUDIT_LOGS if x["decision"] == "BLOCK")
    pending = len(PENDING_QUEUE)
    saved_volume = round(sum(x["amount_near"] for x in AUDIT_LOGS if x["decision"] == "BLOCK"), 2)
    approved_volume = round(sum(x["amount_near"] for x in AUDIT_LOGS if x["decision"] == "APPROVE"), 2)

    return {
        "stats": {
            "total_requests": total,
            "approved_count": approved,
            "blocked_count": blocked,
            "pending_count": pending,
            "blocked_volume_near": saved_volume,
            "approved_volume_near": approved_volume,
        },
        "policy": POLICY_STATE,
        "agents": AGENTS_DB,
        "pending_queue": list(PENDING_QUEUE.values()),
        "audit_logs": list(reversed(AUDIT_LOGS[-30:])),
    }


@app.post("/api/policy")
def update_policy(update: PolicyUpdate):
    POLICY_STATE["max_single_tx_near"] = update.max_single_tx_near
    POLICY_STATE["daily_spend_limit_near"] = update.daily_spend_limit_near
    POLICY_STATE["hitl_threshold_near"] = update.hitl_threshold_near
    POLICY_STATE["block_prompt_injection"] = update.block_prompt_injection
    POLICY_STATE["strict_whitelist_mode"] = update.strict_whitelist_mode
    return {"message": "Security policy updated live", "policy": POLICY_STATE}


@app.post("/api/evaluate")
def evaluate_transaction(tx: TransactionRequest):
    tx_id = f"TX-{int(time.time() * 1000) % 1000000}"
    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    risk_score = 5
    reasons = []
    pipeline_steps = {
        "prompt_scan": "PASS",
        "budget_check": "PASS",
        "wallet_reputation": "PASS",
        "crypto_sign": "PENDING",
    }

    agent = AGENTS_DB.get(tx.agent_id, {"role": "Unknown", "trust_level": "LOW", "daily_spent": 0.0})
    if agent["trust_level"] == "LOW":
        risk_score += 25
        reasons.append("Agent has LOW trust privilege.")
    elif agent["trust_level"] == "MEDIUM":
        risk_score += 10

    # 1. Prompt Injection Scan
    prompt_lower = tx.prompt.lower()
    injection_detected = any(re.search(pat, prompt_lower) for pat in INJECTION_PATTERNS)
    if injection_detected and POLICY_STATE["block_prompt_injection"]:
        risk_score = 98
        pipeline_steps["prompt_scan"] = "FAIL"
        reasons.append("CRITICAL: Prompt Injection / Jailbreak pattern detected in AI instruction.")

    # 2. Budget & Limit Check
    if tx.amount_near > POLICY_STATE["max_single_tx_near"]:
        risk_score = max(risk_score, 85)
        pipeline_steps["budget_check"] = "FAIL"
        reasons.append(
            f"Amount ({tx.amount_near} NEAR) exceeds single transaction cap ({POLICY_STATE['max_single_tx_near']} NEAR)."
        )
    elif (agent["daily_spent"] + tx.amount_near) > POLICY_STATE["daily_spend_limit_near"]:
        risk_score = max(risk_score, 80)
        pipeline_steps["budget_check"] = "FAIL"
        reasons.append(f"Exceeds agent daily spend limit ({POLICY_STATE['daily_spend_limit_near']} NEAR).")

    # 3. Wallet Whitelist & Reputation Check
    near_info = check_near_testnet_account(tx.recipient)
    if POLICY_STATE["strict_whitelist_mode"] and tx.recipient not in POLICY_STATE["whitelisted_wallets"]:
        risk_score = max(risk_score, 75)
        pipeline_steps["wallet_reputation"] = "FAIL"
        reasons.append(f"Recipient '{tx.recipient}' is not in the approved Whitelist.")

    # Determine Final Decision
    if risk_score >= 70:
        decision = "BLOCK"
        pipeline_steps["crypto_sign"] = "REJECTED"
        explanation = "Blocked by AgentGuard Firewall: " + " ".join(reasons)
    elif tx.amount_near > POLICY_STATE["hitl_threshold_near"] or risk_score >= 40:
        decision = "PENDING_APPROVAL"
        pipeline_steps["crypto_sign"] = "AWAITING_HUMAN"
        explanation = (
            f"Paused for Human-in-the-Loop review: Transaction ({tx.amount_near} NEAR) exceeds auto-approve threshold ({POLICY_STATE['hitl_threshold_near']} NEAR)."
        )
    else:
        decision = "APPROVE"
        pipeline_steps["crypto_sign"] = "EXECUTION_DISABLED"
        AGENTS_DB[tx.agent_id]["daily_spent"] = round(agent["daily_spent"] + tx.amount_near, 2)
        explanation = "Policy checks passed. No transaction was signed or submitted."

    record = {
        "tx_id": tx_id,
        "timestamp": timestamp,
        "agent_id": tx.agent_id,
        "prompt": tx.prompt,
        "recipient": tx.recipient,
        "amount_near": tx.amount_near,
        "risk_score": min(risk_score, 100),
        "decision": decision,
        "explanation": explanation,
        "pipeline": pipeline_steps,
        "near_rpc": near_info,
    }
    record["audit_hash"] = compute_sha256_proof(record)

    if decision == "PENDING_APPROVAL":
        PENDING_QUEUE[tx_id] = record
    else:
        AUDIT_LOGS.append(record)

    return record


@app.post("/api/hitl")
def resolve_human_approval(item: ApprovalAction):
    if item.tx_id not in PENDING_QUEUE:
        raise HTTPException(status_code=404, detail="Transaction not found in pending queue")

    record = PENDING_QUEUE.pop(item.tx_id)
    if item.action == "APPROVE":
        record["decision"] = "APPROVE"
        record["pipeline"]["crypto_sign"] = "HUMAN_APPROVED_POLICY_ONLY"
        record["explanation"] = "Human reviewer approved the policy request; no transaction was signed or submitted."
        agent_id = record["agent_id"]
        if agent_id in AGENTS_DB:
            AGENTS_DB[agent_id]["daily_spent"] = round(AGENTS_DB[agent_id]["daily_spent"] + record["amount_near"], 2)
    else:
        record["decision"] = "BLOCK"
        record["pipeline"]["crypto_sign"] = "HUMAN_REJECTED"
        record["explanation"] = "Manually rejected by Human Security Operator."

    record["audit_hash"] = compute_sha256_proof(record)
    AUDIT_LOGS.append(record)
    return record
