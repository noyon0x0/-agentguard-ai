# Threat Model

## Scope

This model covers the v4 dashboard, FastAPI foundation, deterministic transaction policy checks, local SQLite state, protected operator routes, read-only NEAR monitoring, and the explicitly disabled-by-default Testnet experiment. The preferred signer uses near-cli-rs to access a dedicated test account key in the OS keychain and can submit at most 0.01 NEAR after policy, preflight, and separate explicit operator confirmation.

## Assets

- Integrity of policy decisions and human-review state.
- Integrity and availability of policy, agent, evaluation, simulation, and audit records.
- Admin bearer token used to change policy, freeze agents, inspect protected audit data, and resolve approvals.
- Correct identification of the NEAR network and returned account/transaction data.
- Browser users’ confidence that a decision is not represented as an executed payment.

## Trust boundaries and entry points

- Untrusted evaluation fields: sender, recipient, amount, prompt, memo, tool name, and contract account.
- Admin routes: policy update, agent freeze, human approval/rejection, audit query, and simulation run.
- External RPC responses: status, view-account, and transaction-status JSON.
- Browser rendering of API responses and operator-entered values.
- Local SQLite file and process-local state/locking.

## Threats and current controls

| Threat | Controls in this prototype | Remaining exposure |
| --- | --- | --- |
| Prompt injection in agent text | Deterministic pattern checks; failed check blocks and is explained. | Pattern matching is heuristic and can miss variants or flag benign text. |
| Unauthorized recipient or wallet drain | Server-side allowlist/blocklist; blocklist takes precedence. | List correctness and updates depend on the operator; no external reputation feed. |
| Overspend or replay | Positive finite bounded amount validation, per-transaction and daily limits, duplicate window, idempotency key. | Process-local serialization does not coordinate multiple workers; daily usage follows persisted approved evaluations, not chain settlement. |
| Rapid request burst | Persisted time-window count blocks over-limit requests. | Single-process assumptions; no distributed rate limiter. |
| Compromised agent | Persisted frozen state is enforced during every policy evaluation. | Freeze does not revoke keys, interrupt external systems, or cancel any transaction. |
| Unauthorized control-plane request | Admin endpoints compare a bearer token using constant-time comparison; missing token fails closed. | One shared token; no operator identity, MFA, rotation workflow, or role separation. Use only on loopback/demo network. |
| Human-review abuse or stale approval | Admin authentication, 15-minute expiry, current policy revalidation, audit event. | Shared bearer identity and single-process state; no multi-person approval. |
| XSS from backend/API content | v4 renders dynamic values with `textContent`/DOM node APIs and restricts explorer links to HTTPS Testnet explorer host. | Browser matrix and content security policy have not been exhaustively verified. |
| RPC spoofing or wrong network | HTTPS requirement for non-local RPC, `status` chain ID must be `testnet`, RPC errors/timeouts fail closed. | Trust still depends on configured provider; no independent proof/light-client verification. |
| RPC error misrepresented as success | No fabricated balances; response/timeout errors return service errors. | Public RPC may rate-limit or be unavailable; no failover health consensus. |
| Secret disclosure | No signing secrets accepted; config endpoint omits RPC URL and admin token; safe logs omit request bodies and exception messages. | Operators can still leak the shared admin token outside this app. |
| Audit tampering/loss | Persisted events link to previous SHA-256 hashes; an admin endpoint checks integrity. | SQLite is mutable; an operator can rewrite all hashes. There is no signature, external anchor, or automatic backup. |
| Resource exhaustion | Request field bounds, RPC timeout, bounded audit page size. | No general rate limit, request-size policy, or load testing. |

## Security assumptions

- The process and SQLite file are controlled by the local operator.
- Admin token is configured and kept out of source control and screenshots.
- The browser reaches the API over loopback for the demo.
- A `BLOCK`, `REVIEW`, or `APPROVE` is an application policy result only. It cannot submit unless the operator separately confirms the exact Testnet transaction.

## Out of scope

Mainnet custody or transactions, smart-contract execution, production key management, production threat intelligence, Telegram message delivery, multi-tenant identity, and production availability guarantees. The only live execution path is the opt-in Testnet native transfer boundary described above.
