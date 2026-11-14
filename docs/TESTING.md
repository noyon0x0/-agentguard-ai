# Test Instructions and Evidence

## Run the suite

From the repository root with the project virtual environment:

```powershell
backend\.venv\Scripts\python.exe -m pytest -p no:cacheprovider -p no:tmpdir -q
```

The root `pytest.ini` adds `backend` to the import path and selects `backend/tests`.
The plugin flags avoid restricted cache and temporary directories in this environment.

## Run the v4 browser smoke test

Install the optional browser-test dependencies from `backend/` and run the focused test:

```powershell
python -m pip install -r requirements-browser.txt
python -m pytest -p no:cacheprovider -p no:tmpdir tests/browser/test_v4_dashboard_smoke.py -q
```

The smoke test launches the combined FastAPI app against a temporary SQLite database and uses the installed Microsoft Edge executable in headless mode. It supplies a test-only admin token, stubs the dashboard's automatic NEAR health display request, checks the protected dashboard API calls, submits one approved and one blocked evaluation through the browser, checks the visible totals, and reads the temporary database in read-only mode. It does not alter the project database or send blockchain requests.

## Latest verification record

Clean-environment suite on 2026-11-13: `70 passed, 1 warning in 22.21s`, exit code 0, in a disposable Python 3.12 environment installed from `requirements-foundation.txt` and `requirements-browser.txt`. `pip check` found no broken requirements; the Edge browser smoke test was included. The final full working-tree rerun passed: `70 passed, 1 warning in 20.76s`, exit code 0. The single warning is Starlette's `TestClient`/`httpx` deprecation. Automated NEAR RPC tests use mocked provider replies and are not live network evidence.

Separate point-in-time read-only check on 2026-11-13: `/v4/api/v1/near/health` returned HTTP 200 with `network=testnet` and 3813 ms latency; `/v4/api/v1/near/accounts/wrap.testnet` returned HTTP 200 with Testnet account metadata. This confirms RPC status/account queries at that time only; it is not a transaction test or an availability guarantee.

## Coverage inventory

- Unit tests: policy conditions, configuration, input validation, safe log formatting, RPC URL/hash/account validation, and additive SQLite schema migration.
- API integration tests: decisions, human review, admin authorization, idempotency, persistence, structured errors, audit events, and dashboard projection endpoints.
- Security concurrency regressions: separate app instances share disposable file-backed SQLite to test spending limits, duplicate decisions, and single-resolution human review. Audit/evaluation atomic rollback and API audit access are also checked.
- NEAR integration tests: RPC responses are mocked for Testnet identity, account balance, contract metadata, transaction status, missing accounts/transactions, wrong-network behavior, RPC unavailability/timeouts, and explorer-link validation. Unit tests reject broadcast RPC methods and verify read-only calls contain no wallet credentials.
- Simulation test: invokes `/api/v1/simulation/run-all` and checks every scenario against the actual engine, verifies unique test IDs, times, scorecard, persisted rows, and audit events.
- Dashboard checks: served route, all panel sections, no `innerHTML` or inline event handlers, and JavaScript syntax via Node.
- Browser smoke: end-to-end dashboard/API workflow using temporary SQLite and local Edge (optional Playwright dependency).

## Not covered by automated tests

Automated tests exercise the transaction boundary with mocked signer/RPC responses and never broadcast a real transaction. They do not prove the soundness of regex injection detection; conduct load, penetration, or full assistive-technology testing; or establish third-party RPC availability/correctness. The explicitly enabled live Testnet test is skipped by default.

## AgentGuard v4 integration upgrade (2026-11-14)

The pinned `py-near==1.2.22` compatibility dependency installed successfully and `pip check` reported no broken requirements. The preferred transaction signer uses near-cli-rs OS-keychain credentials. The suite includes the optional Edge/Playwright dashboard smoke test and temporary-database tests. New coverage exercises mocked Testnet transfers, Testnet-only signer configuration, signer key-to-access-key matching, all four no-broadcast Testnet attack scenarios, WARN approval, the separate explicit-confirmation boundary, final status failure, and persisted audit evidence.

Final complete suite after the keychain signer, explicit confirmation boundary, and dashboard account panel changes: `96 passed, 1 skipped, 1 warning in 20.02s`, exit code 0. The skipped case is the opt-in live Testnet transfer test. The warning is Starlette's existing `TestClient`/httpx deprecation. No payment transaction was submitted; the live transfer test remains opt-in and skipped by default.

Live read-only verification on 2026-11-14: official RPC `https://rpc.testnet.near.org` returned `chain_id=testnet`; the dashboard-facing status API returned HTTP 200, account and authorized recipient verified, `10 NEAR` balance, and the configured public key matched an active FullAccess permission. The account was created using the faucet-sponsored near-cli-rs flow and its generated key was retrieved only as a public key from the OS keychain. No live payment transaction was signed or broadcast. The custom CLI RPC connection remains pending operator selection at the CLI's API-key prompt; therefore the signer is not ready and live transfers remain disabled.
