# Reproducible demo

1. Start the standalone app as described in the project README.
2. Open the dashboard at `http://127.0.0.1:8000/` and unlock operator controls with the local admin token.
3. Open the Simulation Lab and run all scenarios. Confirm the response contains a decision and audit evidence from this backend.
4. Confirm a blocked request reports signer invocation as false. WARN remains in human review until an authenticated decision.
5. Check the NEAR panel. RPC health and account metadata are live read-only results; transaction demonstrations remain simulated unless the separately gated Testnet experiment is configured and explicitly approved.

No demo scenario transfers funds. Do not call the live transfer endpoint as part of routine judging. Do not present simulation output as an on-chain transaction.
