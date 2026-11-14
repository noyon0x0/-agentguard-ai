# Test instructions and evidence

From this project folder with its virtual environment active:

```sh
python -m pip install -r backend/requirements-browser.txt
python -m playwright install chromium
python -m pytest -q
```

Automated tests use temporary SQLite databases plus mocked NEAR RPC and signer responses. The opt-in live Testnet transfer case is skipped by default; do not enable it without explicit approval and a disposable funded Testnet account. No test should print credentials or use Mainnet.

Isolated project run on 2026-11-14: `88 passed, 1 skipped, 1 warning in 19.76s`. The browser smoke test passed. The sole skip is the opt-in live Testnet transfer test; no real transaction was submitted. The warning is Starlette's `TestClient`/`httpx` deprecation.
