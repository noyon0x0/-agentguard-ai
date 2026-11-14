# Security

AgentGuard AI is a hackathon prototype. Security decisions are deterministic and enforced by the backend. Ordinary `APPROVE` means policy approval only and never signs or submits. A separate, default-disabled experiment can submit native NEAR transfers on Testnet only after policy approval, account/key preflight, explicit operator confirmation, and a 0.01 NEAR cap. It uses a disposable Testnet account and must never be configured with Mainnet credentials. Do not provide signing credentials to the agent or frontend.

## Reporting

Please report suspected vulnerabilities privately to the project maintainer before public disclosure. Include the affected version, reproduction steps, and impact. Do not include secrets, private keys, or personal data in reports.

## Scope and limits

The v4 routes use a shared bearer token for operator actions and local SQLite storage. The retained legacy v3 routes under `/api/...` do not use this v4 authentication layer; they must only be exposed on loopback or a trusted isolated network. Their payment evaluation is policy-only and does not execute transactions. The SHA-256 audit chain detects sequence edits but is not immutable or externally anchored. The project is not suitable for custody, production financial authorization, or internet exposure without a separate security review and authentication hardening.
