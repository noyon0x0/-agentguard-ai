# Demo Walkthrough

## Before presenting

1. Start the foundation app on loopback using [Installation](INSTALLATION.md).
2. Open `/dashboard-v4` and confirm API status is online.
3. Enter the demo admin token in **System Settings**. The page keeps it in memory only. Confirm policy, human approvals, audit, and simulation lab load.
4. Check **NEAR Testnet Monitor**. A live status response must identify `testnet`; otherwise describe the RPC as unavailable and do not present account data as verified.
5. Keep the screen clear of secrets. No wallet credentials or private keys are needed.

## Suggested sequence

1. **Overview:** show counts from the configured SQLite database. A fresh database should show empty-state/zero values, not seeded metrics.
2. **Transaction Security:** submit a small request to `treasury.testnet`. Explain that `APPROVE` is only a policy decision.
3. **Prompt injection / recipient attacks:** use the Simulation Lab or enter a test request. Each run creates evaluation and audit records.
4. **Human review:** run the large-payout case, then resolve it from Human Approval Center. Approval is admin-protected, revalidated, and expires after 15 minutes.
5. **Agent freeze:** freeze an agent in Agent Management and run another evaluation for that agent. The backend should block it. Unfreeze after the demo if desired.
6. **Simulation scorecard:** run all 12 scenarios. Show actual expected/actual decision, pass/fail, reason, test ID, duration, and associated audit request IDs returned by the API.
7. **NEAR Testnet:** query a public account such as `wrap.testnet`. Distinguish RPC account/contract metadata from any transaction execution.
8. **Audit & Forensics:** show the persisted events if admin access and records are available.
9. **Telegram:** point out that delivery is not configured; no alert should be represented as sent.

## Safety language for the presentation

Say: “The backend evaluated this request and persisted its policy decision.” Do not say that funds were protected on-chain, a transaction was simulated on-chain, an approval was signed, or the ledger is tamper-proof. This project does not submit payments.
