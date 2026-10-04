# Security model

## Trust boundaries

The platform crosses four important boundaries:

1. An API client submits structured input.
2. The orchestration layer selects a tool and worker.
3. A local or SSH-accessible worker invokes scientific software.
4. Generated results and artifacts return to persistent storage.

Every field that can influence a path, executable, solver, remote command, artifact, or network target must be treated as untrusted.

## API boundary

All endpoints except `/health` require the `X-API-Key` header. Comparison uses a constant-time digest comparison. Startup fails closed when `GRAPH_RAG_API_KEY` is absent.

The only unauthenticated endpoint is:

- `/health`

For loopback-only development, `GRAPH_RAG_ALLOW_INSECURE_LOCAL=true` explicitly disables the API-key requirement. This bypass is never suitable for a shared or remotely reachable service.

Docker Compose binds the service to `127.0.0.1:8000`. Do not change this to all interfaces without adding an authenticated TLS termination layer and reviewing the exposed discovery information.

CORS uses an explicit allowlist configured through `GRAPH_RAG_CORS_ORIGINS`.

## Remote-execution boundary

Remote execution is optional. When configured, use a dedicated least-privilege account and restrict it to the required software and directories.

Relevant controls include:

- Explicit remote host and username configuration
- Allowed remote job root
- Allowed artifact roots
- Allowed OpenFOAM case root
- Approved OpenFOAM solver names
- Capability declarations that prevent incompatible placement
- Worker-health checks before routing
- Tests covering unsafe remote-execution inputs

Do not construct shell commands from unvalidated user-controlled fragments. Prefer structured argument lists, strict allowlists, normalized paths, and containment checks.

The base Compose file does not mount SSH material. Remote-worker users must opt in with `compose.remote.yaml` and `GRAPH_RAG_SSH_DIR`. Use a dedicated SSH configuration and key with the narrowest practical permissions; do not mount an unrestricted personal key set in a shared deployment.

## Artifact boundary

Supported workflows can record artifact metadata and SHA-256 hashes. A hash proves byte identity after registration; it does not prove that an artifact is scientifically correct or safe to open.

Artifact paths must remain within configured roots. Generated files should be treated as untrusted until their producing tool, expected type, size, and location have been checked.

## Defensive-security boundary

The defensive-security adapter requires explicit authorization and limits discovery to:

- One private or loopback IP address
- No hostnames or public addresses
- No network ranges
- At most 32 explicitly listed ports
- TCP connection checks only

It excludes exploitation, credentials, passwords, banners, persistence, evasion, and unrestricted scanning.

## Secrets and private data

Keep the following outside Git:

- API and cloud keys
- SSH private keys
- Private research documents
- Local Chroma collections and SQLite databases
- Generated scientific results containing private data
- Model weights and large datasets
- Terraform state and account identifiers

The repository includes `.gitignore` rules and a privacy-audit script, but automated rules are not a substitute for reviewing staged changes.

## Deployment guidance

For local development:

- Bind to loopback.
- Use a non-example API key.
- Register only workers needed for the current task.
- Stop the service when it is not in use.

For a remotely reachable deployment:

- Terminate TLS at a trusted reverse proxy.
- Add production-grade authentication and per-user authorization.
- Restrict inbound network ranges.
- Separate API, worker, and artifact-storage identities.
- Centralize audit logs without recording secrets or private payloads.
- Rotate credentials and patch dependencies regularly.
- Treat the current API key as insufficient for multi-tenant use.

See [SECURITY.md](../SECURITY.md) for vulnerability reporting.
