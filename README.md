# AgentGuard AI v4

**A NEAR Testnet security prototype with an explicitly gated 0.01 NEAR transfer experiment.**

AgentGuard AI evaluates agent payment requests, records decisions in SQLite,
and routes higher-risk requests to authenticated human review. Normal policy
evaluation remains non-executing. A separate admin-only experiment can send
at most 0.01 NEAR on Testnet when explicitly enabled and configured with a
dedicated disposable account and a backend-only key.

## Problem and approach

Autonomous agents can generate payment requests faster than a human can review
them. Server-side controls include recipient allowlists, spending limits,
duplicate and velocity checks, prompt-pattern checks, a kill switch, and human
review. Only the isolated Testnet experiment adapter can reach the signer.

The word â€œAIâ€ in the project name does not mean a model decides whether a
request passes. Security decisions use deterministic backend rules; model
inference is not a policy input in this implementation.

AgentGuard AI records explainable `APPROVE`, `REVIEW`, and `BLOCK` decisions using deterministic server-side rules. Ordinary evaluations never sign or submit. The separately configured Testnet experiment maps these outcomes to `ALLOW`, `WARN`, or `BLOCK` and verifies final status after submission. Security decisions do not use model output.

The v4 dashboard is served by `app.main_v3:app` at `/dashboard-v4` on port 8000. Its foundation API is mounted at `/v4/api/v1`; existing v3 API routes remain available at their original paths. Earlier dashboard files remain in the repository.

> **Hackathon prototype:** The policy engine, local audit store, and tests demonstrate a security workflow. They are not a production financial authorization service and do not provide tamper-proof audit guarantees.

## Project status

| Status | Features |
| --- | --- |
| **Implemented** | FastAPI foundation; deterministic policy; SQLite persistence; idempotency, limits, recipient allowlists, approvals and audit chain; read-only NEAR monitoring; explicitly gated Testnet transfer endpoint with a 0.01 NEAR cap, OS-keychain-backed near-cli-rs signer, explicit pre-broadcast confirmation, preflight checks, final status verification, and transaction audit history; simulated and Testnet attack checks. |
| **Tested** | The complete suite passed **113 tests, 1 live transaction test skipped, and 1 existing warning** during the 2026-11-14 security follow-up, including the browser smoke test. |
| **Mocked** | Automated NEAR RPC tests use mocked provider replies. Simulations use generated requests but execute the real local policy engine. Telegram delivery tests must mock the provider; no real delivery is implied. |
| **Unverified** | Continued NEAR RPC availability beyond the point-in-time checks below, actual Telegram delivery, cross-browser/mobile/accessibility review, deployment security, and multi-process consistency. |
| **Planned / limited** | A SHA-256 chain detects edits but SQLite remains operator-editable; no external immutable anchor/signature exists. Authentication is one shared bearer token, migrations are additive rather than managed by Alembic, and public threat intelligence is not connected. |

See [Architecture](docs/ARCHITECTURE.md), [Threat Model](docs/THREAT_MODEL.md), [Security Policy](docs/SECURITY_POLICY.md), [API Reference](docs/API.md), [Demo Walkthrough](docs/DEMO.md), [Known Limitations](docs/LIMITATIONS.md), and the [Submission Checklist](docs/SUBMISSION_CHECKLIST.md).

## Key features

- Deterministic recipient, spending, duplicate, velocity, prompt-pattern,
  tool, contract, and agent-state checks.
- Authenticated human approval and rejection with expiry and policy
  re-evaluation.
- SQLite persistence for policy, evaluations, simulations, and audit events;
  SHA-256 links detect sequence edits but are not tamper-proof.
- Emergency kill switch, policy history, request correlation, and sanitized
  public activity views.
- Read-only NEAR Testnet status and account monitoring. RPC availability can
  change independently of the application.
- Read-only Testnet access-key permission inspection. The system does not
  return private keys to the frontend or agent. Live transfer uses the
  isolated backend key only when the Testnet feature flag is enabled.

## Installation and configuration

Requirements: Python 3.12 or newer and PowerShell on Windows. From the repository root:

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements-foundation.txt
$env:AGENTGUARD_ADMIN_TOKEN = 'replace-with-a-long-random-local-demo-token'
$port = if ($env:AGENTGUARD_PORT) { [int]$env:AGENTGUARD_PORT } else { 8000 }
if ($port -lt 1 -or $port -gt 65535) { throw 'AGENTGUARD_PORT must be between 1 and 65535' }
python -m uvicorn app.main_v3:app --app-dir backend --host 127.0.0.1 --port $port
```

`app.main_v3:app` is the primary combined entry point for the v4 dashboard and
the existing API routes. The standalone `app.foundation.main:app` app is for
isolated foundation use and is not the dashboard server documented here.

If Uvicorn reports that port 8000 is already in use, inspect the listener
before starting another copy:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object LocalAddress, LocalPort, OwningProcess
Get-Process -Id <PID>
```

Only stop a process after confirming it is the AgentGuard instance you intend
to replace. If another process must keep that port, set `$env:AGENTGUARD_PORT`
to a free port (for example, `8002`) and rerun the startup block. The URLs then
use that port. The normal startup command omits Uvicorn reload mode to keep one
server process; add `--reload` only during active development.

Open these local URLs:

- Dashboard: `http://127.0.0.1:8000/dashboard-v4`
- v3 interactive API docs: `http://127.0.0.1:8000/docs`
- v4 interactive API docs: `http://127.0.0.1:8000/v4/docs`
- v4 OpenAPI schema: `http://127.0.0.1:8000/v4/openapi.json`
- v4 database health: `http://127.0.0.1:8000/v4/api/v1/health`
- v4 NEAR RPC health: `http://127.0.0.1:8000/v4/api/v1/near/health`

The database defaults to `backend/agentguard_foundation.db`, independent of the process working directory. Set `AGENTGUARD_DATABASE_URL` to select another SQLite file; missing parent directories are created during engine setup. The supported configuration variables are:

| Variable | Default | Purpose |
| --- | --- | --- |
| `AGENTGUARD_PORT` | `8000` | Loopback Uvicorn port used by the documented PowerShell startup command. |
| `AGENTGUARD_ADMIN_TOKEN` | unset | Required bearer token for admin-only actions and sensitive legacy v1/v2/v3 routes. Protected actions return `503` until configured. |
| `AGENTGUARD_DATABASE_URL` | `backend/agentguard_foundation.db` | SQLite storage location; relative override paths resolve from the process working directory. |
| `AGENTGUARD_NEAR_TESTNET_RPC_URL` | `https://rpc.testnet.near.org` | HTTPS NEAR RPC endpoint; client rejects non-Testnet chain IDs. |
| `AGENTGUARD_NEAR_RPC_TIMEOUT_SECONDS` | `5` | RPC request timeout, from 0.1 to 60 seconds. |
| `AGENTGUARD_NEAR_TRANSACTIONS_ENABLED` | `false` | Explicitly enables the isolated live Testnet transfer route. |
| `AGENTGUARD_NEAR_SENDER_ACCOUNT` | provisioned AgentGuard Testnet account | Dedicated sender account; must end in `.testnet`. |
| `AGENTGUARD_NEAR_PUBLIC_KEY` | provisioned AgentGuard Testnet public key | Public key used to match the account's active FullAccess key. |
| `AGENTGUARD_NEAR_AUTHORIZED_RECIPIENT` | `merchant.testnet` | Exact allowlisted Testnet payment destination; override as needed. |
| `AGENTGUARD_NEAR_UNAUTHORIZED_RECIPIENT` | `attacker.testnet` | Test account used only for unauthorized-recipient attack checks. |
| `AGENTGUARD_NEAR_TESTNET_PRIVATE_KEY` | unset | Legacy backend-only fallback. Prefer near-cli-rs OS-keychain signing; never expose keys to the agent or browser. |
| `AGENTGUARD_ENVIRONMENT` | `development` | Runtime environment label. |
| `AGENTGUARD_LOG_LEVEL` | `INFO` | Structured log level. |

No default admin credential is shipped. Set a unique token in the server environment; keep Uvicorn bound to `127.0.0.1` for local use. Optional Telegram settings are `AGENTGUARD_TELEGRAM_BOT_TOKEN` and `AGENTGUARD_TELEGRAM_CHAT_ID`; secrets are never returned to the browser. Full steps are in [Installation](docs/INSTALLATION.md).

## Payment security workflow

```text
Payment Request â†’ Policy Evaluation â†’ APPROVE / BLOCK / REVIEW â†’ Human Approval (for REVIEW) â†’ Audit Record
```

1. **Payment request:** `POST /v4/api/v1/evaluations` validates the request and requires an `Idempotency-Key`. It accepts no private key, seed phrase, or signing material.
2. **Policy evaluation:** the backend checks agent state, prompt patterns, recipient allow/block lists, spending thresholds, duplicate history, velocity, and optional tool/contract policy.
3. **Decision:** a passing request below the review threshold is `APPROVE`; a failed check is `BLOCK`; a request above the review threshold is `REVIEW`. `APPROVE` is only a policy result and never submits a transaction.
4. **Human approval:** a `REVIEW` request is persisted as pending. Admin-only approve/reject calls require the bearer token. Approval rechecks current policy; expired requests are blocked.
5. **Audit record:** the initial policy result and its audit event are committed together. Human decisions, expirations, policy changes and other covered events add further audit rows. Audit listing is admin-only. The SQLite log is not tamper-proof against direct database edits.

The request and review API details are in [API Reference](docs/API.md). No NEAR account is needed for policy evaluation; the separate Testnet monitor performs public read-only queries.

## System architecture

```text
Browser dashboard
  â””â”€ FastAPI app: app.main_v3:app
       â”œâ”€ existing v3 routes
       â””â”€ /v4 mount: foundation API
            â”œâ”€ deterministic policy + human review
            â”œâ”€ SQLite persistence + linked audit events
            â””â”€ read-only NEAR Testnet RPC client
```

The combined app serves `/dashboard-v4` and mounts the v4 API at
`/v4/api/v1/`. The foundation app owns its configuration, database lifecycle,
routes, and NEAR client. See [Architecture](docs/ARCHITECTURE.md) for details.
The legacy v3 `/api/...` routes remain available for compatibility and require
the same configured bearer token as v4 operator actions. With no configured
token, they fail closed. The shared-token design remains intended for a local
demo, not a production identity system.

The main API surfaces are health (`GET /v4/api/v1/health`), policy evaluation
(`POST /v4/api/v1/evaluations`), admin-only review decisions and audit
operations, and read-only NEAR monitoring under `/v4/api/v1/near/`. Full paths,
request examples, and authentication requirements are in the [API Reference](docs/API.md).

## Testing

From the repository root, install the project requirements and run all backend tests:

```powershell
python -m pip install -r backend\requirements.txt
backend\.venv\Scripts\python.exe -m pytest -p no:cacheprovider -p no:tmpdir -q
```

The browser smoke test requires Playwright and Microsoft Edge; install `backend/requirements-browser.txt` to include it. Tests use disposable SQLite data and mocked NEAR RPC and signer responses; they do not broadcast a real transaction. The latest complete run in this audit on 2026-11-14 passed **130 tests, 1 live Testnet transaction test skipped, and 1 warning** (exit 0), including the browser smoke test and legacy v1/v2/v3 API authorization tests. The warning is Starlette's `TestClient`/`httpx` deprecation. See [Test Instructions](docs/TESTING.md) for commands and coverage limits.

## Local demo

1. Start Uvicorn using the installation command and open `http://127.0.0.1:8000/dashboard-v4`.
2. Enter the configured admin token under **System Settings** to load protected approvals, audit, and simulation views.
3. Submit a small request to `treasury.testnet` and observe the server decision and updated counts.
4. Submit a request above the review threshold, then approve or reject it in Human Approval Center. The approval is revalidated and does not execute a payment.
5. Submit a request to `attacker.testnet` to demonstrate the blocklist, or use Simulation Lab to run all 17 backend scenarios.
6. Review the persisted Recent Activity. Enter the admin token to access full audit data, verify the audit hash chain, or export JSON/CSV.
7. Optionally enable the global kill switch; it blocks all new v4 evaluations until an authenticated operator disables it.
8. Check the NEAR monitor separately. It reports current RPC results when available; mocked tests are not live-chain evidence. Telegram stays disabled unless both server environment settings are configured.

See [Demo Walkthrough](docs/DEMO.md) for a fuller presentation sequence.

## Demo video

The demo recording is not linked in this repository yet. The accessible local
Desktop, Videos, and Downloads recordings were checked; the inspected files do
not demonstrate AgentGuard AI. No public demo URL was present in the project,
so none is fabricated. Before external submission, add the verified recording
at `docs/demo/agentguard-ai-v4-demo.mp4` or add its verified public host URL
here and in [Demo Walkthrough](docs/DEMO.md), then confirm playback and that it
contains no credentials.

## NEAR integration boundary

The read-only NEAR client permits `status`, `query`, and `tx` methods for monitoring. The separate opt-in transaction adapter is pinned to the official Testnet RPC and uses near-cli-rs `sign-with-keychain` by default. It checks network, sender and recipient accounts, balance, matching public FullAccess key, policy, idempotency, and a 0.01 NEAR cap before signing. ALLOW and approved WARN results pause for a separate explicit broadcast confirmation. It verifies final status with the read-only client before returning success. See the [NEAR RPC account documentation](https://docs.near.org/api/rpc/contracts) and [transaction status documentation](https://docs.near.org/api/rpc/transactions).

Read-only verification during the 2026-11-14 follow-up: the official Testnet RPC returned `network=testnet`, confirmed sender `agentguard-v4-d95875f37108.testnet` with **15 NEAR**, matched the configured public key to an active `FullAccess` key, and verified the authorized recipient. No transaction was signed or submitted. The current shell has no `near` executable and the named CLI profile is not ready, so live signing remains unavailable and disabled. RPC availability and balance can change.

Normal `APPROVE` evaluation is policy-only. A separately configured, admin-only Testnet experiment can submit a maximum 0.01 NEAR transfer through a backend-isolated keychain signer. It is disabled by default and requires a dedicated `.testnet` sender, an on-chain FullAccess public key, an explicitly configured authorized recipient, and a second explicit confirmation before submission. The older v2/v3 demos also label approval as policy-only and no longer manufacture chain balances or explorer receipts. Read the [limitations](docs/LIMITATIONS.md) before presenting the prototype as a guarantee or production control.

## Screenshots

See [verified local screenshots](docs/screenshots/README.md). They were captured from the locally running app and document the actual empty-database and RPC-unavailable state at capture time; no seeded metrics or successful RPC state is implied.

![AgentGuard AI v4 dashboard overview](docs/screenshots/dashboard-overview.png)

## Exact next steps for submission

1. On the final checkout, follow [Installation](docs/INSTALLATION.md) from a clean virtual environment and run the full suite using [Test Instructions](docs/TESTING.md).
2. Start the app on loopback, check API health and OpenAPI docs, and run the 17-scenario suite through the authenticated Simulation Lab. Save the resulting actual scorecard and audit output for the demo.
3. Recheck the Testnet RPC immediately before the presentation. If it remains unavailable, show the documented error state and identify the automated RPC checks as mocked.
4. Fill in the team, repository, project category, demo link and event-specific form fields after confirming the current hackathon rules, deadline, and whether a demo video is required (including duration, format, and hosting requirements).
5. Review the final Git diff, license and assets, README claims, screenshots, and [submission checklist](docs/SUBMISSION_CHECKLIST.md); submit only the revision that was reviewed.

## License

MIT; see [LICENSE](LICENSE).

## Technology and contributions

The project uses Python, FastAPI, Pydantic, SQLAlchemy, SQLite, HTML/CSS, and
browser-side JavaScript. NEAR read monitoring uses public JSON-RPC; the isolated signer submits only explicitly authorized Testnet transfers.
Contributions are welcome through focused issues and pull requests; include
relevant tests and documentation, keep credentials out of commits, and retain
the default-disabled Testnet execution boundary. Contributions are under the
MIT License.

## Roadmap

- Broader browser, accessibility, and responsive-layout verification.
- Production-grade operator identity before any deployment beyond a local
  prototype.
- Managed schema migration history and multi-process coordination before
  considering deployment beyond a single-process demo.
- A verified public demo video and event-specific submission details.

## Attack demonstrations

With the API running and the admin bearer token configured, run all scenarios (no wallet or credentials are used):

```powershell
$headers = @{ Authorization = "Bearer $env:AGENTGUARD_ADMIN_TOKEN" }
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v4/api/v1/simulation/run-all -Headers $headers
```

Five generated attacks cover an unlisted recipient, prompt injection, a per-request spending-limit bypass, duplicate replay, and an unauthorized contract/tool call. Each executes the actual policy engine, persists an `ATTACK_EXECUTION_EVIDENCE` audit event, and returns its checks and `signer_invoked` result. Blocked attacks must show `signer_invoked: false` and `broadcast: false`. These are backend simulations, not live Testnet attacks or evidence of real transaction signing.

The NEAR monitor can also inspect finalized public access-key permissions at `GET /v4/api/v1/near/accounts/{account_id}/access-keys`. Transaction identity verification is separate from execution success; only finalized status results with a recognized success outcome report `execution_succeeded: true`.


## Real Testnet transfer experiment

The integration is disabled by default. Provision a disposable Testnet account with the official near-cli-rs faucet sponsor, which generates and saves the key to the local OS keychain. The app's signer delegates key retrieval and signing to `near ... sign-with-keychain`; it never loads the private key into the agent or frontend. The integration rejects RPC URLs other than `https://rpc.testnet.near.org`, requires `.testnet` account IDs, verifies the configured public key against an active full-access key, and caps each transfer at 0.01 NEAR plus a 0.1 NEAR minimum gas reserve.

Check for near-cli-rs and install it from the [official releases](https://github.com/near/near-cli-rs/releases) if missing. Create an account without printing its generated key:

```powershell
$suffix = [guid]::NewGuid().ToString('N').Substring(0, 12)
$account = "agentguard-v4-$suffix.testnet"
near account create-account sponsor-by-faucet-service $account autogenerate-new-keypair save-to-keychain network-config testnet create
near account view-account-summary $account network-config testnet now
near account get-public-key from-keychain $account network-config testnet
```

The RPC balance query confirms the account exists and reports its current balance. Account RPC does not attest the funding source; the UI does not infer that a balance came from the faucet. See [Installation](docs/INSTALLATION.md) for safe recovery and CLI setup.

Configure the official Testnet-only CLI connection:

```powershell
near config add-connection --network-name testnet --connection-name agentguard-testnet --rpc-url https://rpc.testnet.near.org/ --wallet-url https://wallet.testnet.near.org/ --explorer-transaction-url https://explorer.testnet.near.org/transactions/ --linkdrop-account-id testnet --faucet-url https://helper.nearprotocol.com/account
```

If the CLI asks whether this endpoint needs an API key, select **No**. The app verifies this profile's network and RPC URL before enabling the CLI signer.

Set these public configuration values and recipient IDs in the backend environment before starting Uvicorn:

```powershell
$env:AGENTGUARD_NEAR_TRANSACTIONS_ENABLED = 'true'
$env:AGENTGUARD_NEAR_SENDER_ACCOUNT = 'your-isolated-sender.testnet'
$env:AGENTGUARD_NEAR_PUBLIC_KEY = 'ed25519:PUBLIC_KEY_FROM_NEAR_CLI'
$env:AGENTGUARD_NEAR_AUTHORIZED_RECIPIENT = 'your-authorized-recipient.testnet'
$env:AGENTGUARD_NEAR_UNAUTHORIZED_RECIPIENT = 'your-attack-recipient.testnet'
```

Start the server on loopback and verify account balance, public key, Testnet status, and recipient permission in the dashboard. An initial ALLOW has no signer invocation; WARN requires explicit admin approval, and both require a second explicit broadcast confirmation. A successful result appears only after final RPC verification. No live payment is broadcast by running the UI checks or default automated test suite.

Run the no-transfer attack demonstrations from the experiment panel, or call the protected `/v4/api/v1/near/experiment/attacks/{unauthorized-recipient|prompt-injection|spending-limit|duplicate-replay}` endpoints. The separate live test is skipped by default. To intentionally submit one 0.01 NEAR transfer as a live test, configure the variables above and set `AGENTGUARD_RUN_LIVE_NEAR_TEST=true` before running `backend\.venv\Scripts\python.exe -m pytest backend\tests\live\test_near_testnet_live_transfer.py -q`. This spends Testnet funds and must be run only against a disposable test account.

The dedicated Testnet account was created during prior setup; this audit's official RPC query confirmed its current 15 NEAR balance and access-key match. The current shell could not locate near-cli-rs, so the signer profile is not ready. No payment transfer was broadcast. Do not present mocked transaction hashes from automated tests as on-chain evidence.
