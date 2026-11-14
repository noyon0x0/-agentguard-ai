# Architecture

## System boundaries

```text
Browser
  └─ same-origin GET /dashboard-v4
       └─ FastAPI app: app.main_v3:app (port 8000)
            ├─ Existing v3 routes ─────── /api/...
            └─ Mounted foundation app ── /v4/api/v1/...
            ├─ /api/v1/evaluations ── deterministic security engine
            │                          ├─ SQLite policy + agent state
            │                          ├─ persisted evaluation records
            │                          └─ append-only-by-convention audit events
            ├─ /api/v1/simulation ───── actual engine scenarios + scorecard
            ├─ /api/v1/near ─────────── read-only NEAR Testnet JSON-RPC client
            └─ dashboard read models ── overview, agents, threats, audit, settings
```

The v4 page is a static HTML/CSS/JavaScript document. It builds dynamic text with DOM text nodes; it does not insert API strings through `innerHTML`. The static page is served by the same FastAPI origin to avoid cross-origin configuration for the local demo.

## Components

- **API composition:** `backend/app/main_v3.py` retains existing v3 routes, serves the v4 page, and mounts `backend/app/foundation/main.py` under `/v4`. All seven legacy `/api/...` routes require the configured bearer token; with no token configured they fail closed. The foundation app owns its database engine, SQLite migrations, NEAR client, routes, and safe request logging.
- **Schemas:** Pydantic models validate evaluation, policy, agent and human-review inputs. Unknown fields are rejected. Signing and credential fields are not accepted.
- **Policy engine:** `security_engine.py` applies deterministic server rules. AI output is not an input to the decision function.
- **Approval workflow:** `approval_workflow.py` enforces expiry and re-evaluates current blocking policy before an admin approval is accepted.
- **Persistence:** SQLAlchemy stores policy configuration, registered agent state, evaluations, simulation runs, and audit events in SQLite.
- **NEAR client:** `near_client.py` allows only `status`, `query`, and `tx` methods. It verifies Testnet identity before state/status lookups, inspects public access-key permissions, and uses a bounded timeout. It cannot broadcast.
- **Testnet experiment:** `near_experiment.py` evaluates each admin-authorized payment with the existing policy, enforces the configured recipient and 0.01 NEAR cap, checks account/balance/access keys, then calls `near_signer.py` only for ALLOW or explicitly approved WARN. It requires an enable flag, official Testnet RPC, dedicated sender, and backend-only key. Final transaction status is verified through the read-only client and persisted in the audit chain.
- **Simulation lab:** `simulation_lab.py` executes named scenario inputs through the policy engine, checks expected decisions and control-specific checks, measures duration, and persists results. Five attack scenarios additionally invoke `execution_boundary.py`, whose `SimulatedSigner` only records an in-process call and cannot sign or broadcast.
- **Dashboard projections:** `dashboard_routes.py` derives metrics and event lists from persisted state. Telegram explicitly reports unconfigured.

## Evaluation flow

1. Validate the request and required `Idempotency-Key`.
2. Return the original result for the same idempotency key and payload; reject reuse with a different payload.
3. Read persisted policy and agent status.
4. Evaluate prompt patterns, tool authorization, contract account format and allowlist, recipient blocklist/allowlist, single and daily limits, duplicate window, velocity, and agent freeze state.
5. Choose `BLOCK` for failed hard checks, `REVIEW` above the auto-approval threshold, or `APPROVE` if the required checks pass.
6. Persist the decision and audit event in the same database transaction.
7. Normal policy evaluation never signs or submits. Only the separate configured Testnet experiment can proceed to the signer after a decision.

Human approval uses a separate authenticated workflow. A review expires after 15 minutes. Before approval, the service rechecks current hard policy; an expired or newly blocked request becomes `BLOCK` and is audited.

## NEAR query flow

The client validates account/hash input, calls `status` and requires `chain_id == "testnet"`, then performs the requested read-only query. Balance values are converted from yoctoNEAR using decimal arithmetic. Access-key results expose public keys and their permissions only. Contract status is based on the returned code hash. Transaction explorer URLs are formed only after `tx` status data matches both the requested hash and sender account. `execution_succeeded` is separately derived from a recognized final success status; identity verification alone is not transaction success.

## Simulated execution boundary

The lab boundary evaluates `BLOCK` and `ERROR` without invoking the signer. `REVIEW` or `WARN` returns approval-required without invoking it; a human-approved review may proceed only to the simulation signer. `APPROVE` also reaches only that simulated signer. The separate Testnet adapter uses a dedicated environment-configured key, is disabled by default, enforces a 0.01 NEAR ceiling, and waits for final RPC status. It is not a production wallet integration or general-purpose agent signer.

## Data and operations

The default database URL is SQLite. Startup creates tables and runs additive compatibility migrations. There is no migration history/version table yet. Evaluation and policy operations are serialized with a process-local lock; this does not provide distributed coordination across multiple server processes. Use a single process for the demo.

Policy and kill-switch changes save version snapshots. Requests receive an `X-Request-ID`; sanitized recent activity is public while full audit views and exports require admin authorization. The global kill switch is enforced by the backend policy engine. Audit hashes detect edits to the stored sequence but are not immutable: a database operator can rewrite records and hashes together. Legacy events receive a deterministic chain during migration. Optional Telegram delivery is configured only through server environment variables; no delivery is implied when disabled.

Audit rows are linked by SHA-256 hashes to detect sequence edits. The database
is still operator-editable, and hashes are neither externally anchored nor
tamper-proof.

## Deployment shape

Use `uvicorn app.main_v3:app --app-dir backend --host 127.0.0.1 --port 8000` for the combined local demo. The dashboard uses the mounted `/v4` API. Do not expose the service publicly without TLS, operator authentication hardening, origin/rate controls, database backups, and production concurrency review. The v4 admin mechanism is one shared bearer token configured through `AGENTGUARD_ADMIN_TOKEN`.

## Live Testnet transaction flow

`POST /api/v1/near/experiment/transactions` requires admin authentication, an idempotency key, the live-transfer feature flag, and server-only account/key configuration. It evaluates persisted policy and records BLOCK/WARN/ALLOW without invoking a signer. WARN requires the human approval route. Both ALLOW and approved WARN then require a separate confirmation route with an explicit confirmation header before signing. Before signing, the adapter verifies Testnet chain identity, sender and recipient accounts, sender balance plus a gas reserve, and an active FullAccess key. The default signer delegates key retrieval and signing to near-cli-rs `sign-with-keychain`; it never exports key material into the AgentGuard process, agent, or browser. The exact named CLI connection is checked to target the official Testnet RPC. It independently waits for FINAL via read-only RPC. A hash without verified final success is never presented as success. Each request and execution outcome is persisted as linked audit events.
