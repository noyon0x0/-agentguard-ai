# AgentGuard backend foundation

This additive foundation is a standalone FastAPI application for isolated
foundation use. The primary combined dashboard server is `app.main_v3:app`
on port 8000, as documented in the repository README. This standalone app does
not replace the combined server or the existing dashboard entry points.

## Install and run

From the repository root, use the dedicated dependency overlay and launch the
new app:

```powershell
python -m pip install -r backend\requirements-foundation.txt
python -m uvicorn app.foundation.main:app --app-dir backend --host 127.0.0.1 --port 8001
```

The additive v4 dashboard is served by the API at
`http://127.0.0.1:8001/dashboard-v4`, keeping browser requests same-origin. The
existing v3 dashboard file and entry points are unchanged.

Configuration uses environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `AGENTGUARD_APP_NAME` | `AgentGuard AI API` | OpenAPI title |
| `AGENTGUARD_ENVIRONMENT` | `development` | Deployment environment label |
| `AGENTGUARD_DATABASE_URL` | `backend/agentguard_foundation.db` | SQLite database URL; the default resolves from the project location |
| `AGENTGUARD_LOG_LEVEL` | `INFO` | Log threshold |
| `AGENTGUARD_NEAR_TESTNET_RPC_URL` | `https://rpc.testnet.near.org` | Read-only NEAR RPC endpoint |
| `AGENTGUARD_NEAR_RPC_TIMEOUT_SECONDS` | `5` | RPC request timeout, from 0.1 to 60 seconds |

Set `AGENTGUARD_ADMIN_TOKEN` to a long, unique secret before enabling operator
actions. Operator changes fail closed when this setting is absent. Send it as a
Bearer token for protected endpoints.

Interactive OpenAPI docs are at `/docs`, ReDoc at `/redoc`, and the OpenAPI
schema at `/openapi.json`.

## Foundation endpoints

- `GET /api/v1/health` checks database connectivity.
- `POST /api/v1/evaluations` validates an intake request, evaluates server-side
  policy, stores the decision and audit event, and requires an `Idempotency-Key`
  header. It returns `APPROVE`, `REVIEW`, or `BLOCK` with explanations and
  `transaction_execution: "disabled"`.
- `GET /api/v1/policy` returns the non-secret policy configuration.
- `PUT /api/v1/policy` updates policy and `PUT /api/v1/agents/{agent_id}` changes
  freeze state. Both require an authenticated admin Bearer token.
- `GET /api/v1/evaluations/pending` lists human-review requests; `POST
  /api/v1/evaluations/{request_id}/decision` resolves one. Both require admin
  authentication. Human approval rechecks current blocking policy.
- `GET /api/v1/audit` returns recent audit events and requires admin auth.
- `/api/v1/simulation/scenarios`, `/scorecard`, `/run/{scenario}`, and `/run-all`
  provide the persisted security simulation lab. Run endpoints require admin
  auth; each run records an expected/actual decision, reason, elapsed time, test
  ID, underlying evaluation IDs, and audit event. Scenarios use the real policy
  engine and never sign or submit transactions.
- `GET /api/v1/overview`, `/api/v1/agents`, `/api/v1/threats`,
  `/api/v1/audit/summary`, `/api/v1/telegram/status`, and `/api/v1/settings`
  provide actual backend-backed dashboard projections. Telegram reports
  `not_configured` until a real delivery integration is added.
- `GET /api/v1/near/health` queries the RPC `status` method, verifies `chain_id`
  is `testnet`, and records the latest health check and latency in memory.
- `GET /api/v1/near/accounts/{account_id}` validates the NEAR account ID and
  retrieves finalized balance and account metadata through `view_account`.
- `GET /api/v1/near/contracts/{account_id}` checks whether the account has a
  deployed contract code hash.
- `GET /api/v1/near/transactions/{tx_hash}?sender_account_id=...` verifies the
  hash and signer with the read-only `tx` status query at `FINAL` on Testnet. It returns an
  explorer URL only after the RPC response matches both requested values.

No private keys, wallet credentials, or signing data are accepted. The policy
engine is deterministic and never consumes an AI decision. Decisions, policy
changes, agent state changes, and human approval outcomes are stored in SQLite.
Structured logs contain method/status metadata and exception class only; request
bodies, authorization headers, account strings, and exception messages are not
logged.

The NEAR client permits only `status`, `query`, and `tx` status methods. It rejects non-Testnet RPC network identities,
uses a bounded timeout, and does not expose the configured endpoint in API
responses. No transaction submission or signing RPC method is available.

The SQLite schema is created on app startup. For production deployment, replace
startup schema creation with versioned migrations before operating against
persistent data.
