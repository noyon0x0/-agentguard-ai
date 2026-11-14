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
| `AGENTGUARD_NEAR_SENDER_ACCOUNT` | Provisioned AgentGuard Testnet account | Account ID to monitor and use as the isolated sender. |
| `AGENTGUARD_NEAR_PUBLIC_KEY` | Provisioned AgentGuard public key | Public key only; used to match the active on-chain FullAccess permission. |
| `AGENTGUARD_NEAR_AUTHORIZED_RECIPIENT` | `merchant.testnet` | Exact recipient allowed by the live Testnet experiment; verified against current Testnet RPC during setup. |
| `AGENTGUARD_NEAR_UNAUTHORIZED_RECIPIENT` | `attacker.testnet` | `.testnet` account ID used only by non-broadcasting security checks. |
| `AGENTGUARD_NEAR_TRANSACTIONS_ENABLED` | `false` | Must be explicitly set to `true` to enable the experiment signer. |
| `AGENTGUARD_NEAR_TESTNET_PRIVATE_KEY` | unset | Compatibility fallback only. Prefer the near-cli-rs OS-keychain signer; never place a key in the repository, frontend, or agent prompt. |
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

## Optional controlled NEAR Testnet transaction experiment

Transaction submission is disabled unless explicitly enabled. The backend requires the official Testnet RPC, three `.testnet` account IDs, a near-cli-rs OS-keychain signer, a matching active FullAccess public key, and a disposable sender account. Native NEAR transfers cannot be signed with a FunctionCall access key. No private key is accepted by an API request or returned to the dashboard. Transfers are capped at 0.01 NEAR and preflight requires a 0.1 NEAR balance reserve for gas.

| Variable | Default | Purpose |
| --- | --- | --- |
| `AGENTGUARD_NEAR_TRANSACTIONS_ENABLED` | `false` | Explicit opt-in to the live Testnet transfer endpoint. |
| `AGENTGUARD_NEAR_SENDER_ACCOUNT` | Provisioned AgentGuard Testnet account | Dedicated sender account ending in `.testnet`. |
| `AGENTGUARD_NEAR_PUBLIC_KEY` | Provisioned AgentGuard Testnet public key | Public key checked against an active FullAccess key. |
| `AGENTGUARD_NEAR_AUTHORIZED_RECIPIENT` | `merchant.testnet` | Exact account allowed for actual transfer, ending in `.testnet`. |
| `AGENTGUARD_NEAR_UNAUTHORIZED_RECIPIENT` | `attacker.testnet` | Testnet recipient ID used by the unauthorized-recipient attack scenario. |
| `AGENTGUARD_NEAR_TESTNET_PRIVATE_KEY` | unset | Legacy compatibility fallback. Use the near-cli-rs OS keychain by default. |
| `AGENTGUARD_RUN_LIVE_NEAR_TEST` | unset | Separate test opt-in; submits one real 0.01 NEAR Testnet transfer. |

Use a private shell session, configure these values only after obtaining a Testnet account/key and faucet funds, then restart the backend. Verify `/v4/api/v1/near/experiment/status` with admin authentication before sending. A Testnet transfer spends Testnet tokens; the live pytest is skipped unless explicitly opted in. No live transfer was performed during this implementation.

### Dedicated account provisioning with near-cli-rs

The project uses NEAR Testnet only. Check whether `near-cli-rs` is available:

```powershell
Get-Command near -ErrorAction SilentlyContinue
near --version
```

If it is missing, install from the official NEAR release page. The official
PowerShell installer command for the current release is listed on
[near/near-cli-rs Releases](https://github.com/near/near-cli-rs/releases):

```powershell
irm https://github.com/near/near-cli-rs/releases/latest/download/near-cli-rs-installer.ps1 | iex
```

Restart PowerShell, then verify `near --version`. You can also download the
Windows MSI from that release page and verify its published SHA-256 checksum
before installing.

Generate a fresh, unique-looking account ID locally, check it through the RPC,
then create it with the Testnet faucet sponsor. `near-cli-rs` generates the
keypair itself and saves the key in the local OS keychain; the command does
not export the key to the terminal:

```powershell
$suffix = [guid]::NewGuid().ToString('N').Substring(0, 12)
$account = "agentguard-v4-$suffix.testnet"
near account create-account sponsor-by-faucet-service $account autogenerate-new-keypair save-to-keychain network-config testnet create
```

The faucet may rate-limit or require an interactive step. Stop and complete
any CAPTCHA, browser authorization, or approval yourself; do not automate or
bypass it. After CLI success, verify the account and balance from the official
RPC and use a keychain-only public-key lookup:

```powershell
near account view-account-summary $account network-config testnet now
near account get-public-key from-keychain $account network-config testnet
```

These commands display public account information. Do not run an export
command that prints a private key or recovery phrase to a shared, recorded, or
AI-visible terminal.

Configure a separate CLI connection for AgentGuard so signing uses the exact
official RPC endpoint. The CLI asks whether the endpoint requires an API key;
for `https://rpc.testnet.near.org`, select **No**. If you do not approve this
configuration prompt, leave the live signer disabled:

```powershell
near config add-connection --network-name testnet --connection-name agentguard-testnet --rpc-url https://rpc.testnet.near.org/ --wallet-url https://wallet.testnet.near.org/ --explorer-transaction-url https://explorer.testnet.near.org/transactions/ --linkdrop-account-id testnet --faucet-url https://helper.nearprotocol.com/account
near config show-connections
```

Verify that the `agentguard-testnet` connection has `network_name = "testnet"`
and `rpc_url = "https://rpc.testnet.near.org/"`. The app's defaults expose the
provisioned public account and public key; override them with
`AGENTGUARD_NEAR_SENDER_ACCOUNT` and `AGENTGUARD_NEAR_PUBLIC_KEY` when using a
different wallet. Keep transactions disabled until an authorized recipient,
an unauthorized demo recipient, and the correct public key are configured.

The dashboard reports balance only after a current RPC account query. The
account RPC cannot prove which party funded the balance, so it labels the
balance as RPC-confirmed and does not claim faucet provenance. Faucet-sponsored
account creation is confirmed separately by the CLI result and account
existence check.

### Recovery backup

The live signer reads the key from the OS keychain through near-cli-rs. Keep
the computer account protected with disk encryption and a strong login. For a
recovery copy, use near-cli-rs's account export in a private, non-recorded
local session and store the recovery phrase in an encrypted offline password
manager or sealed offline backup. Never paste the phrase into this app, a
terminal command argument, chat, issue, README, or source control. No recovery
phrase was displayed or copied during provisioning here.

### Explicit transaction confirmation

The initial Testnet payment request only evaluates policy. ALLOW and approved
WARN responses both wait. The operator must separately confirm the exact
sender, recipient, amount, and Testnet network in the dashboard; the backend
confirmation endpoint enforces this step before accessing the signer. BLOCK
never invokes the signer. A final success is displayed only after the RPC
verifies final execution status.
