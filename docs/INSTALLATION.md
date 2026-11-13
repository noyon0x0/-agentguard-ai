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

`backend/requirements.txt` contains the complete runtime dependencies for the
primary combined app, including SQLAlchemy. `requirements-foundation.txt` is
kept as a compatible installer alias.

## Configure and start

The local demo uses `agentguard-local-demo-token` when no token is configured. Set
your own token in the shell, then launch the combined app:

```powershell
$env:AGENTGUARD_ADMIN_TOKEN = 'use-a-long-random-value-for-this-local-session'
$port = if ($env:AGENTGUARD_PORT) { [int]$env:AGENTGUARD_PORT } else { 8000 }
if ($port -lt 1 -or $port -gt 65535) { throw 'AGENTGUARD_PORT must be between 1 and 65535' }
python -m uvicorn app.main_v3:app --app-dir backend --host 127.0.0.1 --port $port
```

`app.main_v3:app` is the primary entry point for the combined dashboard and
API. If startup reports that port 8000 is already in use, inspect the listener
before starting another server:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object LocalAddress, LocalPort, OwningProcess
Get-Process -Id <PID>
```

Stop only a process you have confirmed is the AgentGuard instance you intend
to replace. If the port is needed by another process, set `$env:AGENTGUARD_PORT`
to a free port, such as `8002`, and rerun the startup block. The normal command
omits Uvicorn reload mode to keep the process layout simple; add `--reload` only
during active development. `app.foundation.main:app` is a standalone foundation
app, not the primary combined dashboard server.

This binds to loopback. Keep it that way for the demo. The v4 dashboard is at `http://127.0.0.1:8000/dashboard-v4`; its foundation API is mounted under `/v4/api/v1`, and the original v3 endpoints remain at `/api/...`.

## Environment variables

| Variable | Default | Notes |
| --- | --- | --- |
| `AGENTGUARD_PORT` | `8000` | Loopback port used by the documented Uvicorn startup command. |
| `AGENTGUARD_APP_NAME` | `AgentGuard AI API` | OpenAPI title. |
| `AGENTGUARD_ENVIRONMENT` | `development` | Displayed environment label. |
| `AGENTGUARD_DATABASE_URL` | `backend/agentguard_foundation.db` | SQLite database file. The default is independent of working directory; relative override paths resolve from the process working directory. Other dialects are rejected. |
| `AGENTGUARD_LOG_LEVEL` | `INFO` | Structured log threshold. |
| `AGENTGUARD_ADMIN_TOKEN` | `agentguard-local-demo-token` | Bearer token for operator actions. Override it with a unique secret outside local demos. |
| `AGENTGUARD_NEAR_TESTNET_RPC_URL` | `https://rpc.testnet.near.org` | HTTPS Testnet JSON-RPC URL; HTTP is accepted only for localhost. |
| `AGENTGUARD_NEAR_RPC_TIMEOUT_SECONDS` | `5` | Must be from 0.1 to 60 seconds. |
| `AGENTGUARD_TELEGRAM_BOT_TOKEN` | unset | Optional server-only Telegram bot token. |
| `AGENTGUARD_TELEGRAM_CHAT_ID` | unset | Optional destination chat; alerts remain disabled unless both Telegram settings are configured. |

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
