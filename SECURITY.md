# Security

AgentGuard AI is a hackathon prototype. Security decisions are deterministic and enforced by the backend. `APPROVE` means policy approval only: signing and transaction submission are disabled. Do not provide private keys, seed phrases, wallet credentials, or real funds.

## Reporting

Please report suspected vulnerabilities privately to the project maintainer before public disclosure. Include the affected version, reproduction steps, and impact. Do not include secrets, private keys, or personal data in reports.

## Scope and limits

The project uses a shared bearer token for operator actions and local SQLite storage. Its SHA-256 audit chain detects sequence edits but is not immutable or externally anchored. It is not suitable for custody, production financial authorization, or internet exposure without a separate security review.
