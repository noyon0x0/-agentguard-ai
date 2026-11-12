# Test Instructions and Evidence

## Run the suite

From `backend/` with the project virtual environment:

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider -p no:tmpdir tests -q
```

The plugin flags avoid restricted cache and temporary directories in this environment. On a normal developer machine, `python -m pytest tests -q` is also suitable.

## Run the v4 browser smoke test

Install the optional browser-test dependencies from `backend/` and run the focused test:

```powershell
python -m pip install -r requirements-browser.txt
python -m pytest -p no:cacheprovider -p no:tmpdir tests/browser/test_v4_dashboard_smoke.py -q
```

The smoke test launches the combined FastAPI app against a temporary SQLite database and uses the installed Microsoft Edge executable in headless mode. It supplies a test-only admin token, stubs the dashboard's automatic NEAR health display request, checks the protected dashboard API calls, submits one approved and one blocked evaluation through the browser, checks the visible totals, and reads the temporary database in read-only mode. It does not alter the project database or send blockchain requests.

## Last recorded result

```text
60 passed, 1 warning in 29.91s
```

The warning was emitted by the installed Starlette `TestClient` integration because it currently relies on the installed `httpx` version. The run completed with exit status 0.

## Coverage inventory

- Unit tests: policy conditions, configuration, input validation, safe log formatting, RPC URL/hash/account validation, and additive SQLite schema migration.
- API integration tests: decisions, human review, admin authorization, idempotency, persistence, structured errors, audit events, and dashboard projection endpoints.
- Security concurrency regressions: separate app instances share disposable file-backed SQLite to test spending limits, duplicate decisions, and single-resolution human review. Audit/evaluation atomic rollback and API audit access are also checked.
- NEAR integration tests: RPC responses are mocked for Testnet identity, account balance, contract metadata, transaction status, missing accounts/transactions, wrong-network behavior, RPC unavailability/timeouts, and explorer-link validation. Unit tests reject broadcast RPC methods and verify read-only calls contain no wallet credentials.
- Simulation test: invokes `/api/v1/simulation/run-all` and checks every scenario against the actual engine, verifies unique test IDs, times, scorecard, persisted rows, and audit events.
- Dashboard checks: served route, all panel sections, no `innerHTML` or inline event handlers, and JavaScript syntax via Node.
- Browser smoke: end-to-end dashboard/API workflow using temporary SQLite and local Edge (optional Playwright dependency).

## Not covered by automated tests

Automated tests do not sign or submit transactions; do not prove the soundness of regex injection detection; do not conduct load, penetration, or full assistive-technology testing; and do not establish the availability or correctness of third-party RPC providers. NEAR RPC integration tests are mocked. A separate live read-only Testnet `status` and finalized `view_account` request succeeded on 2026-11-12; this is a point-in-time observation. No live transaction lookup was performed.
