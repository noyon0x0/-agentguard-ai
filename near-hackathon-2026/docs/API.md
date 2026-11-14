# API quick reference

Interactive docs: `/docs`; health: `GET /api/v1/health`; NEAR Testnet RPC status: `GET /api/v1/near/health`; dashboard: `/` or `/dashboard`.

Normal policy evaluation is `POST /api/v1/evaluations` with an `Idempotency-Key` header and a JSON request containing agent, sender, recipient, and `amount_near`. It returns a persisted decision and never signs. Operator-only endpoints require `Authorization: Bearer <NEAR_HACKATHON_AGENTGUARD_ADMIN_TOKEN>`.

Read-only NEAR endpoints inspect account balance, public access-key permissions, contract code presence, and a supplied finalized transaction hash. The `/api/v1/near/experiment/` routes expose the separately disabled-by-default Testnet transfer experiment and attack scenarios; consult OpenAPI for request schemas. Simulation routes persist evidence but do not broadcast.
