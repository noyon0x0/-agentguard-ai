# API Reference

The combined port 8000 app mounts the v4 foundation API under `/v4`. Use `/v4/docs` for its interactive OpenAPI docs and `/v4/openapi.json` for its schema. The tables below show the full request paths as exposed by `app.main_v3:app` (also mounted by `app.main:app`).

## Authentication

Send `Authorization: Bearer <AGENTGUARD_ADMIN_TOKEN>` to operator-only routes. For a fresh loopback demo with no environment override, use `agentguard-local-demo-token`. No token is returned by the API. Invalid or missing credentials return `401`.

## Health and dashboard projections

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/v4/api/v1/health` | No | SQLite connectivity and execution-disabled indicator. |
| GET | `/v4/api/v1/overview` | No | Persisted evaluation counts, volume, latest evaluation. |
| GET | `/v4/api/v1/agents` | No | Registered agent frozen state and persisted evaluation counts. |
| GET | `/v4/api/v1/threats` | No | Local policy rules and recent persisted BLOCK records; no external feed. `limit` 1–100. |
| GET | `/v4/api/v1/settings` | No | Safe runtime settings; secrets omitted. |
| GET | `/v4/api/v1/telegram/status` | No | Reports Telegram as not configured. |
| GET | `/v4/api/v1/audit/summary` | No | Audit event count and latest timestamp. |

## Policy and evaluations

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/v4/api/v1/policy` | No | Current policy, lists, and thresholds. |
| PUT | `/v4/api/v1/policy` | Admin | Validate and update policy, wallet lists, tools, and contract list. |
| PUT | `/v4/api/v1/agents/{agent_id}` | Admin | Freeze/unfreeze an agent. |
| POST | `/v4/api/v1/evaluations` | No | Evaluate and persist a request; requires unique `Idempotency-Key` header. Returns `202`. |
| GET | `/v4/api/v1/evaluations/pending` | Admin | List pending human reviews. |
| POST | `/v4/api/v1/evaluations/{request_id}/decision` | Admin | Approve/reject a review, subject to expiry and current policy checks. |
| GET | `/v4/api/v1/audit?limit=100` | Admin | Recent persisted audit events; limit 1–1000. |

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

## NEAR Testnet (read-only)

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/v4/api/v1/near/health` | No | Query RPC `status`, require `chain_id=testnet`, record latest check and latency. |
| GET | `/v4/api/v1/near/accounts/{account_id}` | No | Finalized `view_account` and balance metadata. |
| GET | `/v4/api/v1/near/contracts/{account_id}` | No | Code-hash-based contract presence on Testnet. |
| GET | `/v4/api/v1/near/transactions/{tx_hash}?sender_account_id=...` | No | Read-only final transaction status; returns Testnet explorer URL only after hash/signer match. |

Errors return structured codes such as `INVALID_NEAR_ACCOUNT_ID`, `NEAR_ACCOUNT_NOT_FOUND`, `NEAR_WRONG_NETWORK`, and `NEAR_RPC_UNAVAILABLE`. No transaction submission route exists.

## Security Simulation Lab

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/v4/api/v1/simulation/scenarios` | Admin | Scenario manifest and expected decisions. |
| POST | `/v4/api/v1/simulation/run/{scenario}` | Admin | Run one scenario through the real policy engine. |
| POST | `/v4/api/v1/simulation/run-all` | Admin | Execute all 12 scenarios and return results plus scorecard. |
| GET | `/v4/api/v1/simulation/scorecard` | Admin | Persistent counts and recent results. |

Each run records a unique UUID test ID, expected/actual decision, pass/fail, reason, elapsed milliseconds, underlying evaluation IDs, and a `SIMULATION_TEST` audit event. Duplicate and rapid-burst scenarios create multiple underlying evaluation records. All are non-executing.
