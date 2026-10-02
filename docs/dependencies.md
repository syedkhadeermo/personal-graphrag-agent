# Dependency and runtime profiles

## Purpose

The repository distinguishes between Python packages required by the portable API and external scientific applications invoked through adapters. An adapter can be implemented and tested without bundling a large solver, CAD package, or platform-specific executable into the base environment.

## Python requirement sets

### Core API — `requirements.txt`

The core file pins the direct Python dependencies required by the portable application:

| Package | Role |
|---|---|
| `fastapi` | HTTP API and request lifecycle |
| `uvicorn[standard]` | ASGI server |
| `pydantic` | Request and response validation |
| `chromadb` | Vector storage and retrieval |
| `ollama` | Default local generation client |
| `pypdf` | PDF ingestion |
| `rdkit` | Portable molecular descriptors and canonicalization |

Install with:

```bash
python -m pip install -r requirements.txt
```

### Development and CI — `requirements-dev.txt`

The development profile includes the core file plus pinned pytest and Ruff versions:

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check app tests
python -m pytest -q
```

### Optional ADMET stack — `requirements-sci.txt`

ADMET prediction is intentionally separated because its PyTorch/model stack is substantially heavier than the portable API:

```bash
python -m pip install -r requirements-sci.txt
```

This profile includes the core requirements plus pinned `torch` and `admet-ai` packages. The runner can also target a dedicated WSL Conda environment.

## External applications

The following capabilities invoke installed applications rather than importable Python packages:

| Capability | Expected executable or environment | Invocation model |
|---|---|---|
| AutoDock Vina | `vina` | Local subprocess |
| Smina | `smina` | Local subprocess |
| GROMACS | `gmx` | Local subprocess or configured worker |
| FreeCAD | FreeCAD installation | Remote worker |
| OpenFOAM | OpenFOAM/WSL environment | Remote worker |
| Blender | Blender installation | Remote worker |
| CalculiX | `ccx`/configured CalculiX installation | Remote worker |
| SSH transport | System `ssh` executable | Local subprocess connecting to a worker |

These applications have platform-specific installation, licensing, GPU, and environment requirements. They are deliberately not represented as pip dependencies.

## Why certain packages are absent

### NetworkX

NetworkX is not used. `app/knowledge_graph/graph_store.py` implements the repository's small persistent graph and bounded breadth-first traversal using Python data structures and `collections.deque`.

### Paramiko

Paramiko is not used. `RemoteComputeWorker` invokes the operating system's OpenSSH client through `subprocess`. The Docker image installs `openssh-client` for this purpose.

### aiohttp

The application does not directly import `aiohttp`. Cloud generation requests use `urllib.request` from the Python standard library. A package may still appear transitively after installing ChromaDB or another dependency, but transitive presence does not make it a direct project requirement.

### Provider SDKs

OpenAI, Anthropic, and Gemini SDK packages are not required. The provider-neutral generators make authenticated HTTPS requests through the standard-library transport. Ollama uses its pinned Python client because it is the default local provider.

## What “supported” means

A supported capability means that the repository contains:

- A validated domain-facing adapter
- Tool-registry and named-agent routing
- Worker-capability integration where required
- Structured execution results
- Portable tests and/or clearly bounded external validation evidence

It does not mean every optional scientific executable is installed by `requirements.txt` or included in the Docker image. The base image intentionally supports portable API and RDKit workflows; machine-specific scientific workloads run only when an appropriately configured worker is available.

## Adding a dependency

Add a package to a requirement file only when application code imports it directly for that profile. Pin its version, add tests, document its purpose, and keep heavyweight or platform-specific stacks out of the core environment unless they are required for the portable API.
