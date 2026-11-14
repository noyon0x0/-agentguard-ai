# Security

AgentGuard AI is a hackathon prototype. Security decisions are deterministic and enforced by the backend. Ordinary `APPROVE` means policy approval only and never signs or submits. A separate, default-disabled experiment can submit native NEAR transfers on Testnet only after policy approval, account/key preflight, explicit operator confirmation, and a 0.01 NEAR cap. It uses a disposable Testnet account and must never be configured with Mainnet credentials. Do not provide signing credentials to the agent or frontend.

## Reporting

Please report suspected vulnerabilities privately to the project maintainer before public disclosure. Include the affected version, reproduction steps, and impact. Do not include secrets, private keys, or personal data in reports.

## Scope and limits

The supported combined app protects v4 operator actions and retained legacy v1/v2/v3 sensitive API routes with one configured bearer token. No default token is shipped; protected actions fail closed until `AGENTGUARD_ADMIN_TOKEN` is configured. The older standalone v1/v2 demo entrypoints are not supported deployment targets and should remain loopback-only despite their bearer protection. The SHA-256 audit chain detects sequence edits but is not immutable or externally anchored. The project is not suitable for custody, production financial authorization, or internet exposure without a separate security review, operator identity hardening, and deployment controls.
