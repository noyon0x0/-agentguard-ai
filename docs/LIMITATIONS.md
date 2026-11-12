# Known Limitations

- This is a hackathon prototype, not a production authorization or custody service.
- The evaluator is deterministic and heuristic. Prompt injection patterns do not understand all semantic attacks and can have false positives/negatives.
- Contract account policy validates account ID syntax and configured contract allowlist. It does not perform an RPC code-hash check inside transaction policy evaluation. The separate NEAR contract lookup endpoint reads Testnet account metadata.
- Approval, policy, and freeze operations use one shared bearer token. There are no user identities, roles, MFA, or multi-operator approval.
- SQLite state is single-process-oriented. A process-local lock is not sufficient coordination across multiple server workers or replicas.
- Audit records are persistent but can be altered by a database administrator; the audit system is not cryptographically chained, signed, immutable, or tamper-proof.
- Schema upgrades are additive compatibility helpers rather than a full versioned migration framework.
- Daily spending totals are based on locally approved evaluation records, not chain settlement. No payment is executed.
- Public RPC endpoints can fail or rate-limit. A health check is a point-in-time observation and not an SLA. No light-client proof verifies provider responses.
- Telegram is unconfigured; there is no external delivery or alert feed.
- Threat intelligence is local policy output only; no external intelligence provider is connected.
- The dashboard has API loading/error/empty states and safe DOM text rendering, but full browser, screen-reader, keyboard-only, and color-contrast audits have not been completed.
- No general request rate limit, production backup/restore process, or load/penetration test has been implemented.
