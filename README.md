# AgentGuard AI — NEAR Hackathon 2026 Edition

An independent NEAR Testnet security demonstration for the AI Security & Defense track. This folder is self-contained and does not import from the parent AgentGuard repository.

## What it does

AgentGuard evaluates agent payment requests with deterministic server-side policy. It enforces recipient allowlists, per-transfer and daily spending limits, duplicate/idempotency checks, prompt-injection checks, human approval, agent controls, and a persisted audit chain. The dashboard reads decisions from this backend.

The default transaction path is simulation/policy evaluation: it never signs or submits a payment. Read-only NEAR Testnet monitoring can query public RPC data. A separate, admin-protected Testnet experiment supports tightly gated execution with a **0.01 NEAR maximum**, backend-isolated signing, explicit human approval for WARN decisions, a second broadcast confirmation, and final network status verification. Execution is disabled unless an operator explicitly configures it. No Mainnet execution is supported.

## Architecture

- `backend/app/main.py` is the standalone ASGI entrypoint.
- `backend/app/foundation/` contains the copied, tested v4 policy, database, audit, NEAR read client, isolated signer, and experiment modules.
- `frontend/dashboard.html` is the dedicated dashboard, served at `/` and `/dashboard`.
- SQLite defaults to `backend/near_hackathon_agentguard.sqlite3`; no database file is included.
- Environment names are prefixed `NEAR_HACKATHON_AGENTGUARD_` to prevent accidental configuration sharing with the parent project.
- Private signing material is never sent to the frontend or agent. Prefer the official near-cli-rs OS keychain signer. Do not put private keys in `.env`.

## Install and run

Requires Python 3.12+. From this folder:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
# Edit .env and set a unique NEAR_HACKATHON_AGENTGUARD_ADMIN_TOKEN.
python -m uvicorn app.main:app --app-dir backend --env-file .env --host 127.0.0.1 --port 8000
```

On macOS/Linux, create/activate `.venv` with `python3.12 -m venv .venv` and `source .venv/bin/activate`, install the same requirements, copy `.env.example` to `.env`, and run:

```sh
python -m uvicorn app.main:app --app-dir backend --env-file .env --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`. The dashboard operator-token field uses the configured token in page memory only.

## Verify the API and Testnet settings

```sh
curl http://127.0.0.1:8000/api/v1/health
curl http://127.0.0.1:8000/api/v1/near/health
```

The NEAR status endpoint checks the configured RPC and requires `chain_id=testnet`. Account checks and balance/access-key inspections are read-only. A missing sender account setting is reported as not configured, not fabricated.

## Tests

Install the browser extra and its browser runtime for the full UI smoke test:

```sh
python -m pip install -r backend/requirements-browser.txt
python -m playwright install chromium
python -m pytest -q
```

The suite uses mocked RPC and signers for transaction-related regressions. The opt-in live Testnet transfer test is skipped unless explicitly enabled; it spends Testnet funds and must only be used with a disposable wallet and explicit operator authorization. Never run it as part of routine CI. Do not describe mocked tests as on-chain transaction evidence.

Verified in the isolated environment on 2026-11-14: **88 passed, 1 skipped, 1 warning**. The skipped test is the opt-in live Testnet transfer test; the warning is the Starlette `TestClient`/`httpx` deprecation. The browser smoke test passed against the dedicated dashboard and standalone backend.

Attack demonstrations are available in the dashboard Simulation Lab and the API under `/api/v1/simulation/`. They execute the real local policy engine and write audit evidence, but are simulations—not Testnet transactions.

## Configuration

See [.env.example](.env.example). Key settings:

| Setting | Default | Purpose |
|---|---|---|
| `NEAR_HACKATHON_AGENTGUARD_ADMIN_TOKEN` | unset | Required for operator-only actions; no built-in credential. |
| `NEAR_HACKATHON_AGENTGUARD_NEAR_TESTNET_RPC_URL` | `https://rpc.testnet.near.org` | Read-only NEAR Testnet JSON-RPC. Execution refuses any other URL. |
| `NEAR_HACKATHON_AGENTGUARD_NEAR_SENDER_ACCOUNT` | unset | Public Testnet account ID for monitoring and optional execution. |
| `NEAR_HACKATHON_AGENTGUARD_NEAR_PUBLIC_KEY` | unset | Public key used to verify the on-chain permission. |
| `NEAR_HACKATHON_AGENTGUARD_NEAR_AUTHORIZED_RECIPIENT` | unset | Explicitly authorized Testnet recipient. |
| `NEAR_HACKATHON_AGENTGUARD_NEAR_TRANSACTIONS_ENABLED` | `false` | Must remain false for simulation-only use. |
| `NEAR_HACKATHON_AGENTGUARD_DATABASE_URL` | project-local SQLite | Separate local database location. |

Live execution additionally requires an isolated Testnet signer/keychain profile, account and permission verification, admin authentication, policy ALLOW or approved WARN, a dedicated disposable account, and a second explicit confirmation. The dashboard never receives private key material. Do not enable execution or initiate a live transfer without explicit human authorization.

## Limitations

This is a hackathon prototype, not a custody service or production financial control. The shared bearer token is not a production identity system. SQLite audit history can be edited by an operator despite linked hashes. NEAR RPC and faucet availability are external dependencies. A Testnet account and live transaction are not configured or claimed by this separate edition.

For the security boundary and threat assumptions, see [SECURITY.md](SECURITY.md). API details and reproducible scenarios are documented in [docs/API.md](docs/API.md), [docs/DEMO.md](docs/DEMO.md), and [docs/TESTING.md](docs/TESTING.md).
