# NEAR Hackathon Submission Checklist

## Project package

- [ ] Confirm repository URL, team name, project category, and required submission form fields.
- [ ] Confirm hackathon rules, deadline, judging requirements, demo duration, deployed URL requirements, and whether a demo video is required (including length, format, and hosting/access rules).
- [x] Provide project README, architecture, threat model, security policy, API reference, setup, tests, demo, and limitations.
- [x] Keep prior dashboards and APIs; v4 is additive.
- [x] Review screenshots in `docs/screenshots/`; they contain no secrets or misleading transaction state.
- [ ] Confirm license and attribution requirements for all project assets.

## Demo readiness

- [x] Install from a fresh virtual environment using the documented requirements; `pip check` found no broken dependencies.
- [ ] Set a new admin token outside the repository.
- [ ] Start the app bound to loopback unless a reviewed deployment environment is used.
- [ ] Confirm `/v4/api/v1/health`, `/v4/docs`, `/dashboard-v4`, and `/v4/api/v1/near/health`.
- [ ] Run all 17 simulations and capture the API scorecard result.
- [ ] Confirm audit events are visible in the configured database.
- [ ] Confirm Telegram is described as not configured.
- [ ] Do not present `APPROVE` as a signed authorization or on-chain transfer.

## Security and accuracy

- [x] No private keys or wallet credentials in source or demo flow.
- [x] Signing and transaction submission are isolated in the opt-in Testnet experiment; ordinary evaluation remains non-executing.
- [x] NEAR responses fail closed on wrong network, timeout, malformed response, or RPC error.
- [x] Claims separate automated mocked RPC tests from point-in-time live RPC checks.
- [x] Re-run the complete test suite on the final pre-commit source: 96 passed, 1 opt-in live Testnet transaction test skipped, and 1 existing deprecation warning.
- [ ] Review `docs/LIMITATIONS.md` before making security claims.
- [x] Review the intended Git diff and exclude local SQLite databases, tokens, and temporary artifacts from the staged submission.

## Final review

- [ ] Verify README backup/current README changes are intentional.
- [ ] Verify screenshots are actual local app captures and match the documented run state.
- [ ] Verify install instructions work in a clean environment.
- [ ] Verify demo output matches the submitted source revision.
- [ ] Submit only after all unchecked items required by the event are resolved.
