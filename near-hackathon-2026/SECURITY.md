# Security model and reporting

## Enforcement

All payment policy decisions occur in the backend. The normal evaluation API does not sign or broadcast. Recipient and amount rules, replay/idempotency checks, prompt-injection detection, and persistent audit recording run before any optional execution boundary. BLOCK terminates before signer invocation; WARN remains pending until an authenticated human decision; internal errors fail closed.

Read-only NEAR integration is restricted to status, account/access-key queries, and final transaction lookup on the official Testnet RPC. The optional transaction experiment is disabled by default, requires the exact Testnet RPC, `.testnet` account IDs, an isolated backend signer, policy approval, recipient and spend checks, and a separate broadcast confirmation. It caps a transfer at 0.01 NEAR. The frontend and model/agent request never receive credentials.

Never use Mainnet credentials, commit `.env`, database files, key files, private keys, or seed phrases. Use a disposable Testnet account and OS keychain signer for any manually approved live demonstration. Disable execution after the demonstration.

## Reporting

Do not use live funds to reproduce attack scenarios. Use the included simulation tests and mocked signer/RPC. For a suspected vulnerability, do not include secrets or personal data in an issue; contact the project maintainer privately with a minimal reproduction.

## Limitations

The shared bearer token is suitable only for local demonstration. The SQLite database is not immutable storage, and audit hashes are not externally anchored. This prototype has not received an independent penetration test and must not be used to custody funds or authorize production payments.
