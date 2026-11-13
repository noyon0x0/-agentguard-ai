# Security Policy

## Decision model

The backend makes deterministic decisions. No model-generated score or AI response can approve a request. Hard-check failures produce `BLOCK`; a request that passes hard checks but exceeds the human-review threshold produces `REVIEW`; a request that passes all required checks below threshold produces `APPROVE`.

## Evaluation checks

1. **Agent:** agent must be registered and not frozen.
2. **Prompt injection:** configured deterministic patterns in prompt or memo block the request when detection is enabled.
3. **Tool authorization:** a requested tool must be in the persisted `allowed_tools` policy.
4. **Contract reference:** a supplied contract account must be a syntactically valid NEAR account and present in `allowed_contracts`. This check is a policy allowlist check; it does not itself query deployed code. The separate NEAR contract endpoint can inspect the Testnet code hash.
5. **Wallet blocklist:** blocked recipient is rejected.
6. **Wallet allowlist:** recipient outside the allowlist is rejected.
7. **Transaction cap:** amount cannot exceed `max_transaction_near`.
8. **Daily cap:** amount plus persisted same-day approved evaluations cannot exceed `daily_limit_near` for that agent.
9. **Duplicate window:** an identical sender, agent, recipient and amount within the configured period is blocked. Repeated idempotency key with same payload returns the first decision; different payload returns conflict.
10. **Velocity:** requests in the configured window cannot reach or exceed the configured burst threshold before the next request.
11. **Human review:** a request above `review_threshold_near` enters `REVIEW`; it expires after 15 minutes. Admin approval re-runs current hard checks.

Checks and explanations are stored with each evaluation. Simulation runs additionally store expected/actual decisions, required check results, elapsed milliseconds, unique test IDs, and references to evaluation IDs.

## Defaults

- Maximum single request: 10 NEAR.
- Daily limit: 25 NEAR per agent.
- Human review above 5 NEAR.
- Velocity threshold: more than 3 requests in a 15-second window is blocked on the next request.
- Duplicate window: 60 seconds.
- Initial wallet allowlist: `demo.near`, `treasury.testnet`, `merchant.testnet`.
- Initial wallet blocklist: `attacker.testnet`, `drainer.evil.testnet`.
- Initial allowed tools: `view_account`, `view_contract`, `evaluate_policy`.
- Initial approved contract list: empty.

These defaults are demo policy values, not recommendations or guarantees. Policy can be changed only through authenticated API routes. The UI does not override server-side evaluation.

## Human/operator controls

Policy updates, agent state changes, pending review resolution, audit listing, and simulation operations require the bearer token. A fresh local demo defaults to `agentguard-local-demo-token`; set `AGENTGUARD_ADMIN_TOKEN` to a unique secret outside source control for any shared deployment. The default is a shared local-demo credential, not a production identity system.

The global kill switch is admin-controlled, increments the policy version, and causes the backend evaluation engine to block new v4 requests. Policy changes and kill-switch changes create version snapshots. Human approval rechecks current hard policy and cannot override a current block. `APPROVE` remains policy-only; signing and transaction submission are disabled.

## NEAR read-only policy

The NEAR client permits only the `status`, `query`, and `tx` JSON-RPC methods. Network identity must report `testnet`. Account queries use `view_account` at finality. Transaction status is queried at `FINAL` and must return the requested hash and signer before an explorer URL is returned. Timeouts, malformed results, RPC errors, and wrong network fail closed. No transaction broadcast or signing API is exposed by this app.
