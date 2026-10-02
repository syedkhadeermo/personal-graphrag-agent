# Security policy

## Supported version

Security fixes are applied to the latest revision of the default branch. Older tags and local deployments may not receive fixes automatically.

## Reporting a vulnerability

Please do not publish exploit details, credentials, private host information, or sensitive scientific data in a public issue.

If GitHub private vulnerability reporting is available in the repository's **Security** tab, use **Report a vulnerability**. Otherwise, contact the repository owner through GitHub and request a private channel before sharing technical details.

Include only information needed to reproduce and assess the issue:

- Affected component and revision
- Preconditions and trust boundary
- Minimal reproduction steps
- Expected and observed behavior
- Potential impact
- Suggested mitigation, if known

Reports are reviewed on a best-effort basis. Please allow time for validation and remediation before public disclosure.

## Security boundaries

This repository orchestrates optional local and remote scientific applications. Its safety depends on deployment configuration as well as application code.

Operators must:

- Set a strong `GRAPH_RAG_API_KEY` before exposing job endpoints.
- Keep the API bound to localhost or place it behind an authenticated, encrypted reverse proxy.
- Restrict CORS to explicit trusted origins.
- Use a dedicated, least-privilege account for remote workers.
- Constrain remote job, artifact, and solver roots through the documented allowlists.
- Protect SSH configuration and private keys outside the repository.
- Review scientific inputs before executing third-party solvers or scripts.
- Keep generated databases, private knowledge, model files, credentials, and runtime artifacts out of Git.

The API key is an access-control mechanism for this portfolio service; it is not a complete multi-user identity or authorization system.

## Defensive-security scope

The cybersecurity domain is intentionally limited to explicitly authorized discovery against one private or loopback IP address and no more than 32 explicitly supplied ports.

The tool rejects public IP addresses, hostnames, and network ranges. It does not perform exploitation, credential attacks, password testing, banner collection, persistence, evasion, or unrestricted scanning.

Use it only on systems you own or are explicitly authorized to assess.

## Scientific and engineering safety

Outputs from ADMET, docking, molecular dynamics, CFD, and FEA workflows require qualified human review. Successful software execution does not establish experimental efficacy, clinical safety, regulatory acceptability, or numerical-model validity.

For a detailed threat model and deployment guidance, see [docs/security-model.md](docs/security-model.md).
