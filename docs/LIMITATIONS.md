# Known Limitations

- This is a hackathon prototype, not a production authorization or custody service.
- The evaluator is deterministic and heuristic. Prompt injection patterns do not understand all semantic attacks and can have false positives/negatives.
- Contract account policy validates account ID syntax and configured contract allowlist. It does not perform an RPC code-hash check inside transaction policy evaluation. The separate NEAR contract lookup endpoint reads Testnet account metadata.
- Approval, policy, and freeze operations use one shared bearer token. There are no user identities, roles, MFA, or multi-operator approval.
- SQLite state is single-process-oriented. A process-local lock is not sufficient coordination across multiple server workers or replicas.
- Audit records are linked with SHA-256 hashes and verified as a sequence, but a database administrator can rewrite rows and hashes together. There is no external anchor, signature, or immutable storage.
- Schema upgrades are additive compatibility helpers rather than a full versioned migration framework.
- Ordinary evaluation and the simulated attack lab do not execute payments. The separate gated Testnet experiment performs final status verification; daily spending totals still come from local policy/execution records and are not a general chain-wide accounting source.
- Public RPC endpoints can fail or rate-limit. A health check is a point-in-time observation and not an SLA. No light-client proof verifies provider responses.
- Telegram is optional and disabled unless both server environment variables are configured. Actual delivery has not been verified in this environment.
- Threat intelligence is local policy output only; no external intelligence provider is connected.
- The dashboard has API loading/error/empty states and safe DOM text rendering, but full browser, screen-reader, keyboard-only, and color-contrast audits have not been completed.
- No general request rate limit, production backup/restore process, or load/penetration test has been implemented.
- Live transaction support is restricted to an explicitly enabled, admin-protected Testnet experiment capped at 0.01 NEAR and a dedicated `.testnet` account. It is disabled by default, requires a matching on-chain FullAccess key plus a separate explicit confirmation, and is not a production custody or wallet service.
- Full-access keys are required for native NEAR transfers; NEAR FunctionCall access keys cannot perform native transfers. The preferred near-cli-rs signer leaves the private key in the OS keychain and calls the CLI only after policy and operator confirmation. A legacy environment-key fallback remains available for compatibility.
- The dedicated Testnet account was faucet-sponsored and its balance was confirmed by official Testnet RPC. No payment transaction was sent. Faucet sponsorship provenance is confirmed by CLI operation/account creation, while the account RPC itself only confirms existence and balance. Current RPC read succeeded during provisioning; availability is not guaranteed.
- The live Testnet test is opt-in and submits one 0.01 NEAR transfer. It is skipped by default and consumes Testnet funds when enabled.
- The attack lab's simulated signer is separate from the live Testnet signer. The agent process does not receive key material, and live transaction routes require admin authorization, but this prototype is not a production authorization boundary against a compromised backend host.
