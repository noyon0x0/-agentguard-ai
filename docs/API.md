# API Reference

The combined port 8000 app mounts the v4 foundation API under `/v4`. Use `/v4/docs` for its interactive OpenAPI docs and `/v4/openapi.json` for its schema. The tables below show the full request paths as exposed by `app.main_v3:app` (also mounted by `app.main:app`).

## Authentication

Send `Authorization: Bearer <AGENTGUARD_ADMIN_TOKEN>` to operator-only routes. For a fresh loopback demo with no environment override, use `agentguard-local-demo-token`. No token is returned by the API. Invalid or missing credentials return `401`.

## Health and dashboard projections

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/v4/api/v1/health` | No | SQLite connectivity; normal evaluation remains non-executing. |
| GET | `/v4/api/v1/overview` | No | Persisted evaluation counts, volume, latest evaluation. |
| GET | `/v4/api/v1/agents` | No | Registered agent frozen state and persisted evaluation counts. |
| GET | `/v4/api/v1/threats` | No | Local policy rules and recent persisted BLOCK records; no external feed. `limit` 1â€“100. |
| GET | `/v4/api/v1/settings` | No | Safe runtime settings; secrets omitted. |
| GET | `/v4/api/v1/telegram/status` | No | Reports whether optional server-side Telegram delivery is configured. |
| GET | `/v4/api/v1/audit/summary` | No | Audit event count and latest timestamp. |
| GET | `/v4/api/v1/activity?limit=20` | No | Sanitized recent persisted evaluations for the dashboard; no prompt or credential fields. |
| GET | `/v4/api/v1/kill-switch` | No | Current global emergency-stop state and policy version. |

## Policy and evaluations

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/v4/api/v1/policy` | No | Current policy, lists, and thresholds. |
| PUT | `/v4/api/v1/policy` | Admin | Validate and update policy, wallet lists, tools, and contract list. |
| PUT | `/v4/api/v1/agents/{agent_id}` | Admin | Freeze/unfreeze an agent. |
| POST | `/v4/api/v1/evaluations` | No | Evaluate and persist a request; requires unique `Idempotency-Key` header. Returns `202`. |
| GET | `/v4/api/v1/evaluations/pending` | Admin | List pending human reviews. |
| POST | `/v4/api/v1/evaluations/{request_id}/decision` | Admin | Approve/reject a review, subject to expiry and current policy checks. |
| GET | `/v4/api/v1/audit?limit=100` | Admin | Recent persisted audit events; limit 1â€“1000. |
| GET | `/v4/api/v1/policy/history` | No | Persisted policy snapshots by version. |
| PUT | `/v4/api/v1/kill-switch` | Admin | Enable/disable the global evaluation block. |
| GET | `/v4/api/v1/audit/verify` | Admin | Verify linked SHA-256 audit event hashes. |
| GET | `/v4/api/v1/audit/export?format=json|csv` | Admin | Export audit rows in JSON or CSV. |
| GET | `/v4/api/v1/audit/incidents/{request_id}` | Admin | Get audit evidence for one request ID. |
| POST | `/v4/api/v1/telegram/test` | Admin | Test configured Telegram delivery; returns conflict when disabled. |

Example request:

```http
POST /v4/api/v1/evaluations
Idempotency-Key: demo-request-0001
Content-Type: application/json
```

```json
{
  "sender": "agent.testnet",
  "agent_id": "agent.testnet",
  "recipient": "treasury.testnet",
  "amount_near": 1.25,
  "prompt": "Routine scheduled payment."
}
```

The response contains `request_id`, `decision`, `risk_score`, `explanation`, `checks`, and `transaction_execution: "disabled"`. A policy `APPROVE` is not a transaction receipt.

## NEAR Testnet monitoring and controlled transfer experiment

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/v4/api/v1/near/health` | No | Query RPC `status`, require `chain_id=testnet`, record latest check and latency. |
| GET | `/v4/api/v1/near/accounts/{account_id}` | No | Finalized `view_account` and balance metadata. |
| GET | `/v4/api/v1/near/accounts/{account_id}/access-keys` | No | Finalized public access-key permission list; no private key material. |
| GET | `/v4/api/v1/near/contracts/{account_id}` | No | Code-hash-based contract presence on Testnet. |
| GET | `/v4/api/v1/near/transactions/{tx_hash}?sender_account_id=...` | No | Read-only final transaction status; returns Testnet explorer URL only after hash/signer match; execution success is reported separately from identity verification. |
| GET | `/v4/api/v1/near/experiment/status` | Admin | Live Testnet RPC, configured account, balance, and recipient verification; never returns key material. |
| POST | `/v4/api/v1/near/experiment/transactions` | Admin | Policy evaluation only; returns BLOCK/WARN/ALLOW without signing. Requires `Idempotency-Key`. |
| POST | `/v4/api/v1/near/experiment/transactions/{request_id}/approve` | Admin | Approve a WARN request; this does not sign or submit. |
| POST | `/v4/api/v1/near/experiment/transactions/{request_id}/confirm` | Admin | Separate explicit broadcast confirmation; required before the isolated signer is invoked. |
| POST | `/v4/api/v1/near/experiment/attacks/{scenario}` | Admin | Run one of four non-broadcasting backend attacks. |
| GET | `/v4/api/v1/near/experiment/history` | Admin | Persisted transaction and attack audit evidence. |

Live submission is disabled unless `AGENTGUARD_NEAR_TRANSACTIONS_ENABLED=true` and sender, public key, recipients, keychain, and exact near-cli-rs Testnet connection are configured. Policy evaluation itself never signs. ALLOW waits for `/confirm`; WARN first requires `/approve` and then `/confirm`. Confirmation requires `X-Live-Testnet-Transfer-Confirmation: CONFIRM TESTNET TRANSFER`. The signer invokes near-cli-rs `sign-with-keychain` and never loads a key into an agent or frontend. It is fixed to the official Testnet RPC, `.testnet` account IDs, an active FullAccess key matching the configured public key, the configured authorized recipient, and a hard 0.01 NEAR maximum. RPC errors and policy failures stop before signing. A submitted hash is not reported as successful until final status is verified. Errors use sanitized structured codes; no Mainnet transaction endpoint exists.

There is no `/v4/values` route. The dashboard uses `/v4/api/v1/overview` for metrics and `/v4/api/v1/activity` for recent activity.

## Security Simulation Lab

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/v4/api/v1/simulation/scenarios` | Admin | Scenario manifest and expected decisions. |
| POST | `/v4/api/v1/simulation/run/{scenario}` | Admin | Run one scenario through the real policy engine. |
| POST | `/v4/api/v1/simulation/run-all` | Admin | Execute all 17 scenarios and return results plus scorecard. |
| GET | `/v4/api/v1/simulation/scorecard` | Admin | Persistent counts and recent results. |

Each run records a unique UUID test ID, expected/actual decision, pass/fail, reason, elapsed milliseconds, underlying evaluation IDs, and a `SIMULATION_TEST` audit event. The five legacy policy attack cases additionally persist `ATTACK_EXECUTION_EVIDENCE` with policy checks and a simulated signer invocation count. The separate NEAR experiment attack routes are non-broadcasting.

## Testnet experiment configuration

The transfer endpoint is disabled by default. See [Installation](INSTALLATION.md) for environment variables and account setup. Preferred signing uses near-cli-rs OS-keychain credentials; the legacy `AGENTGUARD_NEAR_TESTNET_PRIVATE_KEY` fallback is backend-only and never appears in a response. Live transfer is pinned to `https://rpc.testnet.near.org`, requires `.testnet` accounts and a matching active FullAccess public key, separate explicit confirmation, and is capped at 0.01 NEAR.
