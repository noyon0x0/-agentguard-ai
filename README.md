# AgentGuard AI

**A NEAR Testnet read-only security prototype for evaluating agent payment requests.**

AgentGuard AI records explainable `APPROVE`, `REVIEW`, and `BLOCK` decisions using deterministic server-side rules. It does not sign, authorize, or submit blockchain transactions. It does not use an AI model to make security decisions.

The v4 dashboard is served by `app.main_v3:app` at `/dashboard-v4` on port 8000. Its foundation API is mounted at `/v4/api/v1`; existing v3 API routes remain available at their original paths. Earlier dashboard files remain in the repository.

> **Hackathon prototype:** The policy engine, local audit store, and tests demonstrate a security workflow. They are not a production financial authorization service and do not provide tamper-proof audit guarantees.

## Project status

| Status | Features |
| --- | --- |
| **Implemented** | FastAPI foundation; Pydantic validation; SQLite and SQLAlchemy; deterministic payment policy engine; allowlist/blocklist; limits; velocity and duplicate detection; frozen agents; admin-protected policy changes and approvals; expiring human review; audit events; v4 dashboard; persisted simulation scorecard; read-only NEAR Testnet client. |
| **Tested** | Backend unit and integration tests, including file-backed SQLite concurrency checks; all 12 deterministic simulation scenarios; mocked NEAR RPC health, account, contract, transaction, timeout and error responses; headless Edge v4 dashboard smoke test. The current suite result is recorded below. |
| **Mocked** | NEAR RPC responses in automated integration tests. Simulation scenarios run against the real local policy engine but use generated inputs and test agents. |
| **Live-verified (point-in-time)** | On 2026-11-12, a read-only JSON-RPC `status` request to `https://rpc.testnet.near.org` returned HTTP 200 and `chain_id=testnet`; a finalized `view_account` query for public account `wrap.testnet` returned balance, code-hash and storage-usage fields. No transaction lookup was made live. This does not guarantee ongoing RPC availability. |
| **Unverified** | Current/ongoing NEAR RPC availability, production deployment, multi-process policy consistency, browser behavior across the full device/browser matrix, third-party RPC reliability, and external Telegram delivery. |
| **Planned** | Versioned migrations, stronger operator identity and roles, durable/immutable audit storage, production-grade concurrency controls, optional real alert delivery, and broader browser accessibility testing. |

See [Architecture](docs/ARCHITECTURE.md), [Threat Model](docs/THREAT_MODEL.md), [Security Policy](docs/SECURITY_POLICY.md), [API Reference](docs/API.md), [Demo Walkthrough](docs/DEMO.md), [Known Limitations](docs/LIMITATIONS.md), and the [Submission Checklist](docs/SUBMISSION_CHECKLIST.md).

## Installation and configuration

Requirements: Python 3.12 or newer and PowerShell on Windows. From the repository root:

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements-foundation.txt
$env:AGENTGUARD_ADMIN_TOKEN = 'replace-with-a-long-random-local-demo-token'
uvicorn app.main_v3:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

Open these local URLs:

- Dashboard: `http://127.0.0.1:8000/dashboard-v4`
- v3 interactive API docs: `http://127.0.0.1:8000/docs`
- v4 interactive API docs: `http://127.0.0.1:8000/v4/docs`
- v4 OpenAPI schema: `http://127.0.0.1:8000/v4/openapi.json`
- v4 database health: `http://127.0.0.1:8000/v4/api/v1/health`
- v4 NEAR RPC health: `http://127.0.0.1:8000/v4/api/v1/near/health`

The database defaults to `./agentguard_foundation.db` relative to the process working directory. The supported configuration variables are:

| Variable | Default | Purpose |
| --- | --- | --- |
| `AGENTGUARD_ADMIN_TOKEN` | `agentguard-local-demo-token` | Bearer token for admin-only policy changes, reviews, audit listing and simulation operations. Override for shared deployments. |
| `AGENTGUARD_DATABASE_URL` | `sqlite:///./agentguard_foundation.db` | SQLite storage location. |
| `AGENTGUARD_NEAR_TESTNET_RPC_URL` | `https://rpc.testnet.near.org` | HTTPS NEAR RPC endpoint; client rejects non-Testnet chain IDs. |
| `AGENTGUARD_NEAR_RPC_TIMEOUT_SECONDS` | `5` | RPC request timeout, from 0.1 to 60 seconds. |
| `AGENTGUARD_ENVIRONMENT` | `development` | Runtime environment label. |
| `AGENTGUARD_LOG_LEVEL` | `INFO` | Structured log level. |

The local token is intended for loopback demos only. Keep Uvicorn bound to `127.0.0.1` for local use, and use a unique token outside the local demo. Full steps are in [Installation](docs/INSTALLATION.md).

## Payment security workflow

```text
Payment Request → Policy Evaluation → APPROVE / BLOCK / REVIEW → Human Approval (for REVIEW) → Audit Record
```

1. **Payment request:** `POST /v4/api/v1/evaluations` validates the request and requires an `Idempotency-Key`. It accepts no private key, seed phrase, or signing material.
2. **Policy evaluation:** the backend checks agent state, prompt patterns, recipient allow/block lists, spending thresholds, duplicate history, velocity, and optional tool/contract policy.
3. **Decision:** a passing request below the review threshold is `APPROVE`; a failed check is `BLOCK`; a request above the review threshold is `REVIEW`. `APPROVE` is only a policy result and never submits a transaction.
4. **Human approval:** a `REVIEW` request is persisted as pending. Admin-only approve/reject calls require the bearer token. Approval rechecks current policy; expired requests are blocked.
5. **Audit record:** the initial policy result and its audit event are committed together. Human decisions, expirations, policy changes and other covered events add further audit rows. Audit listing is admin-only. The SQLite log is not tamper-proof against direct database edits.

The request and review API details are in [API Reference](docs/API.md). No NEAR account is needed for policy evaluation; the separate Testnet monitor performs public read-only queries.

## Testing

From `backend/`, install the project requirements and run all backend tests:

```powershell
python -m pip install -r requirements-foundation.txt
.venv\Scripts\python.exe -m pytest -p no:cacheprovider -p no:tmpdir tests -q
```

The optional browser smoke test requires Playwright and Microsoft Edge. Install `requirements-browser.txt` before running the full suite to include it. Tests use disposable SQLite data and mocked NEAR RPC responses; they do not broadcast transactions. See [Test Instructions](docs/TESTING.md) for the focused browser-test command. Test results change as code changes; the current observed result is **60 passed, 1 warning**.

## Local demo

1. Start Uvicorn using the installation command and open `http://127.0.0.1:8000/dashboard-v4`.
2. Enter the configured admin token under **System Settings** to load protected approvals, audit, and simulation views.
3. Submit a small request to `treasury.testnet` and observe the server decision and updated counts.
4. Submit a request above the review threshold, then approve or reject it in Human Approval Center. The approval is revalidated and does not execute a payment.
5. Submit a request to `attacker.testnet` to demonstrate the blocklist, or use Simulation Lab to run all 12 backend scenarios.
6. Review the persisted audit events. The simulator records runs, underlying evaluation records and audit events in the configured database.
7. Check the NEAR monitor separately. It reports current RPC results when available; mocked tests are not live-chain evidence.

See [Demo Walkthrough](docs/DEMO.md) for a fuller presentation sequence.

## NEAR integration boundary

The NEAR client permits only read-only `status`, `query`, and `tx` status methods. It checks the RPC `chain_id` before account and transaction lookups. Account lookup uses finalized `view_account`; transaction lookup uses status at `FINAL`. The explorer URL is returned only after the RPC result’s hash and signer match the request. See the [NEAR RPC account documentation](https://docs.near.org/api/rpc/contracts) and [transaction status documentation](https://docs.near.org/api/rpc/transactions).

There is no transaction signing, broadcasting, wallet connection, private-key handling, or automatic execution code in the v4 foundation app. An `APPROVE` is a policy decision only. Read the [limitations](docs/LIMITATIONS.md) before presenting the prototype as a guarantee or production control.

## Screenshots

See [verified local screenshots](docs/screenshots/README.md). They were captured from the locally running app and show its actual empty-database and RPC-unavailable states; no seeded metrics or success state is implied.

## Exact next steps for submission

1. On the final checkout, follow [Installation](docs/INSTALLATION.md) from a clean virtual environment and run the full suite using [Test Instructions](docs/TESTING.md).
2. Start the app on loopback, check API health and OpenAPI docs, and run the 12-scenario suite through the authenticated Simulation Lab. Save the resulting actual scorecard and audit output for the demo.
3. Recheck the Testnet RPC immediately before the presentation. If it remains unavailable, show the documented error state and identify the automated RPC checks as mocked.
4. Fill in the team, repository, project category, demo link and event-specific form fields after confirming the current hackathon rules and deadline.
5. Review the final Git diff, license and assets, README claims, screenshots, and [submission checklist](docs/SUBMISSION_CHECKLIST.md); submit only the revision that was reviewed.

## License

MIT; see [LICENSE](LICENSE).
