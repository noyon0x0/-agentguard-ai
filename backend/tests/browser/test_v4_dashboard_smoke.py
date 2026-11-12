"""Browser smoke coverage for the combined v4 dashboard and API."""

from __future__ import annotations

import os
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest
import requests

playwright = pytest.importorskip("playwright.sync_api", reason="install backend/requirements-browser.txt")
from playwright.sync_api import expect, sync_playwright


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"
ADMIN_TOKEN = "browser-smoke-test-only-token"
EDGE_PATHS = (
    Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
    / "Microsoft/Edge/Application/msedge.exe",
    Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
    / "Microsoft/Edge/Application/msedge.exe",
)


def _free_port() -> int:
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        return server.getsockname()[1]


@pytest.fixture
def dashboard_server():
    database_fd, database_name = tempfile.mkstemp(
        prefix=".agentguard-v4-browser-", suffix=".sqlite3", dir=REPO_ROOT
    )
    os.close(database_fd)
    database_path = Path(database_name).resolve()
    port = _free_port()
    environment = os.environ.copy()
    environment.update(
        {
            "AGENTGUARD_ADMIN_TOKEN": ADMIN_TOKEN,
            "AGENTGUARD_DATABASE_URL": f"sqlite:///{database_path.as_posix()}",
            "AGENTGUARD_LOG_LEVEL": "CRITICAL",
        }
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main_v3:app",
            "--app-dir",
            str(BACKEND_DIR),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "critical",
        ],
        cwd=REPO_ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    base_url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            error = process.communicate()[0]
            database_path.unlink(missing_ok=True)
            pytest.fail(f"Disposable Uvicorn server exited before becoming ready:\n{error}")
        try:
            response = requests.get(f"{base_url}/v4/api/v1/health", timeout=0.5)
            if response.status_code == 200:
                break
        except requests.RequestException:
            time.sleep(0.1)
    else:
        process.terminate()
        error = process.communicate(timeout=5)[0]
        database_path.unlink(missing_ok=True)
        pytest.fail(f"Disposable Uvicorn server did not become ready:\n{error}")

    try:
        yield base_url, database_path
    finally:
        try:
            if os.name == "nt":
                process.send_signal(signal.CTRL_C_EVENT)
            else:
                process.send_signal(signal.SIGINT)
            process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5)
        for attempt in range(10):
            try:
                database_path.unlink(missing_ok=True)
                break
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(0.2)


def test_v4_dashboard_evaluation_smoke(dashboard_server):
    base_url, database_path = dashboard_server
    edge_path = next((path for path in EDGE_PATHS if path.is_file()), None)
    if edge_path is None:
        edge_path = shutil.which("msedge")
    if not edge_path:
        pytest.fail("Microsoft Edge was not found; install Edge or set PATH to msedge.exe")

    admin_calls: list[tuple[str, str | None]] = []
    with sync_playwright() as playwright_api:
        browser = playwright_api.chromium.launch(
            executable_path=str(edge_path),
            headless=True,
        )
        try:
            page = browser.new_page()
            page.add_init_script(
                f"window.AGENTGUARD_API_BASE = {base_url + '/v4'!r};"
            )
            # The dashboard automatically checks NEAR health during load. Stub
            # that read-only status request so this UI test is deterministic and
            # never depends on or contacts an external chain endpoint.
            page.route(
                "**/v4/api/v1/near/health",
                lambda route: route.fulfill(
                    status=200,
                    content_type="application/json",
                    body='{"status":"healthy","network":"testnet","latency_ms":1,"checked_at":"2026-01-01T00:00:00+00:00"}',
                ),
            )
            page.on(
                "request",
                lambda request: admin_calls.append(
                    (request.url, request.headers.get("authorization"))
                )
                if any(
                    endpoint in request.url
                    for endpoint in (
                        "/api/v1/evaluations/pending",
                        "/api/v1/audit",
                        "/api/v1/simulation/scenarios",
                        "/api/v1/simulation/scorecard",
                    )
                )
                else None,
            )

            response = page.goto(f"{base_url}/dashboard-v4", wait_until="domcontentloaded")
            assert response is not None and response.status == 200
            page.get_by_role("heading", name="Overview Dashboard").wait_for()
            page.locator("#overview-state").get_by_text("Loaded 0 persisted evaluations").wait_for()
            assert page.locator("#api-detail").inner_text().startswith("API reachable")

            # The protected dashboard panels use the operator token. Evaluation
            # intake itself is intentionally unauthenticated and requires an
            # Idempotency-Key; the UI supplies that header per submission.
            page.locator("#admin-token").fill(ADMIN_TOKEN)
            page.locator("#admin-form button[type=submit]").click()
            page.locator("#admin-state").get_by_text("Admin token held in page memory").wait_for()
            with page.expect_response(
                lambda item: "/api/v1/evaluations/pending" in item.url
            ) as pending_response:
                page.locator("#refresh-all").click()
            assert pending_response.value.status == 200, pending_response.value.text()
            page.locator("#approvals-state").get_by_text(
                "pending review requests from backend"
            ).wait_for(timeout=5000)
            page.locator("#simulation-state").get_by_text("backend-defined scenarios loaded").wait_for()

            def submit(recipient: str, amount: str, memo: str) -> str:
                page.locator("#recipient-id").fill(recipient)
                page.locator("#amount-near").fill(amount)
                page.locator("#memo-text").fill(memo)
                with page.expect_response(
                    lambda item: item.request.method == "POST"
                    and item.url.endswith("/v4/api/v1/evaluations")
                ) as api_response:
                    page.locator("#evaluation-form button[type=submit]").click()
                result = api_response.value
                assert result.status == 202
                page.locator("#evaluation-result").get_by_text(
                    "APPROVE" if recipient == "treasury.testnet" else "BLOCK", exact=True
                ).wait_for()
                return result.json()["request_id"]

            approved_id = submit("treasury.testnet", "2.5", "browser smoke approve")
            blocked_id = submit("attacker.testnet", "1", "browser smoke block")

            expect(page.locator("#metric-total")).to_have_text("2")
            expect(page.locator("#metric-approved")).to_have_text("1")
            expect(page.locator("#metric-blocked")).to_have_text("1")
            expect(page.locator("#metric-review")).to_have_text("0")

            connection = sqlite3.connect(database_path.as_uri() + "?mode=ro", uri=True)
            try:
                persisted = connection.execute(
                    "SELECT request_id, status FROM security_evaluations ORDER BY created_at, id"
                ).fetchall()
            finally:
                connection.close()
            assert set(persisted) == {(approved_id, "APPROVE"), (blocked_id, "BLOCK")}

            assert admin_calls
            authenticated_calls = {
                endpoint
                for url, token in admin_calls
                if token == f"Bearer {ADMIN_TOKEN}"
                for endpoint in (
                    "/api/v1/evaluations/pending",
                    "/api/v1/audit",
                    "/api/v1/simulation/scenarios",
                    "/api/v1/simulation/scorecard",
                )
                if endpoint in url
            }
            assert authenticated_calls == {
                "/api/v1/evaluations/pending",
                "/api/v1/audit",
                "/api/v1/simulation/scenarios",
                "/api/v1/simulation/scorecard",
            }
        finally:
            browser.close()
