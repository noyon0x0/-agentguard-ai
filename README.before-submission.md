# AgentGuard AI

AgentGuard AI is a hackathon demo for putting a security gate in front of agent initiated NEAR payments. It evaluates a proposed transfer, returns an explainable approve or block decision, and records the result in an in-memory audit log. The dashboard includes one-click scenarios for normal activity and common attacks.

> **Simulation only:** an approved request returns a simulated authorization receipt. This project does not sign or submit a blockchain transaction and never handles wallet keys.

## Architecture

```text
Browser (frontend/index.html)
  ├── POST /payment/check ──> FastAPI payment policy
  │                            ├── deterministic local policy checks
  │                            └── read-only NEAR Testnet account query
  └── GET /audit-logs ──────> in-memory decision log
```

- **Frontend:** a single-file dark dashboard using Tailwind CSS from its CDN. It sends payment details to the API, displays the decision and Testnet verification status, and polls the audit log.
- **Backend:** FastAPI and Pydantic validate requests. The policy engine makes deterministic decisions; the API records each result and creates a simulated receipt for approved payments.
- **NEAR integration:** for an otherwise approved `.testnet` recipient, the backend calls the public NEAR Testnet RPC `view_account` query. It is read-only and uses no credentials. An RPC error or unavailable RPC is treated as a block because the recipient could not be verified. Non-Testnet allowlisted demo IDs are format checked but are not queried on-chain.
- **Data storage:** audit entries and duplicate-request tracking live in process memory and reset when the server restarts. This is demo infrastructure, not production storage.

## Security rules

The backend evaluates checks in this order:

1. Block suspicious memo phrases such as `ignore previous`, `urgent`, `seed`, `private key`, or `drain` (risk 100).
2. Block amounts greater than **10 NEAR** (risk 80).
3. Block recipients outside the allowlist: `demo.near`, `treasury.testnet`, and `merchant.testnet` (risk 90).
4. Block an identical sender, recipient, and amount repeated within 60 seconds (risk 85).
5. For remaining requests, validate NEAR account ID formatting. For `.testnet` recipients, verify account existence using the public RPC. A missing account is blocked (risk 90); an unavailable or inconclusive RPC verification is blocked (risk 75).
6. Approve a request that passes these rules (risk 0), returning a `sim_…` authorization receipt. No transaction is broadcast.

Policy blocks happen before any RPC call. The sender defaults to `agent.testnet` when omitted. The demo's policy and audit log are in-memory, so they are not suitable as a production authorization service.

## Run locally

### 1. Start the backend

From the repository root, create and activate a virtual environment, install dependencies, and start the API:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

The API health check is at `http://127.0.0.1:8000/`; interactive API documentation is at `http://127.0.0.1:8000/docs`.

### 2. Open the dashboard

Open `frontend/index.html` in a browser. It connects to `http://127.0.0.1:8000`, posts evaluations to `/payment/check`, and fetches decisions from `/audit-logs` every eight seconds. The backend enables CORS for this local demo.

Choose a preset or enter a payment and select **Evaluate Payment**. The prompt injection preset puts suspicious text into the memo field. The unknown Testnet recipient preset can trigger a live public RPC lookup if it reaches the NEAR verification step.

### API endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Health and network status |
| `POST` | `/payment/check` | Evaluate a payment and append its decision to the audit log |
| `GET` | `/audit-logs` | Return logged decisions |
| `POST` | `/audit-logs/clear` | Clear the in-memory audit log and duplicate tracking |

Example request:

```json
{
  "sender": "agent.testnet",
  "recipient": "demo.near",
  "amount": 5,
  "memo": "Monthly demo payment"
}
```

## Project layout

```text
backend/app/main.py             FastAPI routes and orchestration
backend/app/security/policy.py  Deterministic payment policy
backend/app/near/testnet.py     NEAR Testnet read-only verification and receipt simulation
backend/tests/test_security.py  Policy and API tests
frontend/index.html             Single-file dashboard
```
