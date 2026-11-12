# Installation

## Requirements

- Python 3.12+.
- PowerShell on Windows (commands below use PowerShell).
- Network access to install Python dependencies and, for live NEAR monitoring, reach the configured RPC endpoint.

## Create the environment

Run from the repository root:

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements-foundation.txt
```

The overlay installs the existing backend dependencies plus SQLAlchemy without replacing `backend/requirements.txt`.

## Configure and start

The local demo uses `agentguard-local-demo-token` when no token is configured. Set
your own token in the shell, then launch the combined app:

```powershell
$env:AGENTGUARD_ADMIN_TOKEN = 'use-a-long-random-value-for-this-local-session'
uvicorn app.main_v3:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

This binds to loopback. Keep it that way for the demo. The v4 dashboard is at `http://127.0.0.1:8000/dashboard-v4`; its foundation API is mounted under `/v4/api/v1`, and the original v3 endpoints remain at `/api/...`.

## Environment variables

| Variable | Default | Notes |
| --- | --- | --- |
| `AGENTGUARD_APP_NAME` | `AgentGuard AI API` | OpenAPI title. |
| `AGENTGUARD_ENVIRONMENT` | `development` | Displayed environment label. |
| `AGENTGUARD_DATABASE_URL` | `sqlite:///./agentguard_foundation.db` | SQLite database path relative to process working directory. Other dialects are rejected. |
| `AGENTGUARD_LOG_LEVEL` | `INFO` | Structured log threshold. |
| `AGENTGUARD_ADMIN_TOKEN` | `agentguard-local-demo-token` | Bearer token for operator actions. Override it with a unique secret outside local demos. |
| `AGENTGUARD_NEAR_TESTNET_RPC_URL` | `https://rpc.testnet.near.org` | HTTPS Testnet JSON-RPC URL; HTTP is accepted only for localhost. |
| `AGENTGUARD_NEAR_RPC_TIMEOUT_SECONDS` | `5` | Must be from 0.1 to 60 seconds. |

The settings endpoint never returns the RPC URL or admin token. The default token is for loopback demos only; set a unique secret before any shared deployment. Use a fresh shell and do not paste secrets into screenshots or source files.

## Local routes

- Dashboard: `/dashboard-v4`
- v3 API docs: `/docs`
- v4 API docs: `/v4/docs`
- v4 OpenAPI schema: `/v4/openapi.json`
- v4 API health: `/v4/api/v1/health`
- v4 NEAR RPC health: `/v4/api/v1/near/health`

## Stop

Stop the Uvicorn process with `Ctrl+C`. The shared demo token set in that shell ends with the shell session. The SQLite database remains on disk; preserve or remove it according to your local demo-data needs.
