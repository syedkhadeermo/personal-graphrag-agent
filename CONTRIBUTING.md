# Contributing

Focused bug fixes, tests, documentation improvements, and well-bounded adapters are welcome.

## Before making a large change

Open an issue before introducing a new domain, persistence backend, worker protocol, or major dependency. Describe the use case, trust boundary, portability impact, and how the change will be tested.

## Development setup

Use Python 3.12 from the repository root:

```bash
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows PowerShell
# .venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Optional scientific dependencies are listed separately in `requirements-sci.txt` because they are larger and may require platform-specific installation.

## Required checks

Run the portable checks before opening a pull request:

```bash
python -m ruff check app tests
python -m pytest -q
```

Tests marked `external` require local models, WSL, private data, or an SSH worker. Do not make the portable suite depend on private infrastructure.

## Design expectations

- Keep generic orchestration independent from domain-specific executables.
- Add scientific applications through a domain adapter, capability declaration, tool registration, and named-agent route.
- Validate API inputs at the boundary.
- Treat paths, solver names, remote commands, and artifact locations as untrusted input.
- Preserve durable job-state transitions and restart behavior.
- Do not weaken the defensive-security scope.
- Distinguish execution success from scientific or numerical validation.
- Never commit credentials, private research documents, local databases, generated model files, or identifying infrastructure details.

## Pull-request checklist

- [ ] The change is narrowly scoped and explained.
- [ ] Portable lint and tests pass.
- [ ] New behavior includes tests.
- [ ] External requirements and skip conditions are documented.
- [ ] Security and privacy boundaries remain explicit.
- [ ] README or focused documentation is updated when behavior changes.
- [ ] Scientific claims are evidence-bound and do not exceed the validation performed.

## Documentation style

Prefer a short explanation followed by a reproducible command or linked evidence. Keep the root README focused on project value, onboarding, and verified results; place deep implementation material under `docs/`.
