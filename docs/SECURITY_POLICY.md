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

Policy updates, agent state changes, pending review resolution, audit listing, simulation operations, and sensitive legacy v1/v2/v3 API routes require the bearer token. No default token is shipped; protected actions fail closed until `AGENTGUARD_ADMIN_TOKEN` is configured. The shared-token design is not a production identity system.

The global kill switch is admin-controlled, increments the policy version, and causes the backend evaluation engine to block new v4 requests. Policy changes and kill-switch changes create version snapshots. Human approval rechecks current hard policy and cannot override a current block. Normal `APPROVE` remains policy-only; live submission is available only through the separate admin-protected, disabled-by-default Testnet experiment.

## NEAR Testnet transaction policy

The read-only NEAR client permits only the `status`, `query`, and `tx` JSON-RPC methods. Live submission requires the official Testnet URL, `.testnet` accounts, a key in the near-cli-rs OS keychain, explicit environment enablement, admin authentication, configured recipient, existing policy ALLOW or explicit WARN approval, balance and access-key preflight, a second explicit broadcast confirmation, and a 0.01 NEAR cap. BLOCK never reaches the signer. Transaction status is independently queried at `FINAL`; a hash without verified success is not described as successful. RPC errors fail closed before signing where possible. Never configure a Mainnet key or use a funded production wallet.
