# Verified workflows and evidence boundaries

This document records what the portfolio demonstrations establish and what they do not establish.

## Evidence levels

| Level | Meaning |
|---|---|
| Portable unit/integration test | Behavior runs in the public CI environment without private infrastructure |
| External execution validation | A configured local or remote application completed the intended software path |
| Artifact validation | Expected output was registered with metadata and SHA-256 identity evidence |
| Scientific or numerical validation | Results were compared with an appropriate experimental, analytical, or accepted reference |

The repository contains strong evidence for the first two levels and workflow-dependent support for the third. It does not broadly claim the fourth.

## Portable CI

The verified CI snapshot completed:

- 92 passing tests
- 15 skipped external tests
- Ruff checks with no errors
- Python 3.12 execution

Skipped tests require local models, private data, WSL, or an SSH-accessible scientific worker.

## Public GraphRAG benchmark

The benchmark downloads official public RDKit, AutoDock Vina, and GROMACS documentation, records hashes of extracted sources, uses real Chroma retrieval, and keeps gold claims separate from the curated graph.

The deterministic router was executed against the current 32-question public development suite:

| Expected route | Selected vector | Selected graph |
|---|---:|---:|
| Vector | **17** | 0 |
| Graph | 0 | **15** |

Router accuracy was **32/32 (100%)**. The [machine-readable result](../evaluation/public_graphrag/published/router_results.json) preserves every decision and the SHA-256 identity of the gold-question file. Because the expected-route labels are part of the current development suite rather than an independently held-out dataset, this verifies the implemented routing rules but does not establish generalization to unseen questions.

### Controlled 32-question run

The protocol-v2 run used `qwen3:8b`, `nomic-embed-text:latest`, temperature 0,
seed 42, three repetitions per mode, disabled model thinking, and a 512-token
generation cap. All 192 generations completed with a normal stop reason and no
empty answers.

| Automated metric | Vector RAG | GraphRAG | Router-selected path |
|---|---:|---:|---:|
| Strict claim coverage | 65.1% | 66.1% | **71.4%** |
| Claim-group coverage | 85.0% | 86.5% | **88.6%** |
| Mean prompt tokens | **2,122** | 2,242 | 2,188 |
| Mean answer tokens | 90.4 | 92.2 | **90.0** |
| Mean generation latency | **4.69 s** | 4.76 s | 4.70 s |

The category-level claim-group result explains the router benefit:

| Category | Questions | Vector RAG | GraphRAG |
|---|---:|---:|---:|
| Direct | 17 | **95.1%** | 91.2% |
| Cross-source | 10 | 76.2% | **76.9%** |
| Boundary | 5 | 68.3% | **90.0%** |

Every generated answer was manually compared with the retrieved evidence. The
rubric classified an answer as fully supported only when it was materially
correct, complete, and supported by the cited context.

| Manual outcome | Vector RAG | GraphRAG | Router-selected path |
|---|---:|---:|---:|
| Fully supported | 69/96 | 74/96 | **77/96** |
| Correct core, but partial | 9/96 | 7/96 | 4/96 |
| Incomplete | 12/96 | 9/96 | 9/96 |
| Unsupported central bridge | 3/96 | 3/96 | 3/96 |
| Factually incorrect | 3/96 | 3/96 | 3/96 |

The six incorrect answers are the same systematic error across both modes and
three repetitions: `gmx rms` was named for radius of gyration instead of the
documented `gmx gyrate`. Automatic lexical coverage also produced both false
positives and false negatives, so it is reported as an audit aid rather than
answer accuracy. The [machine-readable audit](../evaluation/public_graphrag/published/qwen3_8b_protocol_v2_audit.json)
preserves all answers, judgments, evidence identities, aggregate metrics,
source hashes, and review limitations.

This result supports conditional routing within this small public development
suite. It does not establish generalization, universal GraphRAG superiority, or
scientific validity.

### Historical pilot

The following result is the original six-question pilot. It is retained for historical reproducibility and is not representative evidence for the current 32-question suite.

| Metric | Vector RAG | GraphRAG |
|---|---:|---:|
| Claim coverage | **0.667** | 0.639 |
| Average prompt tokens | **2,580** | 2,768 |
| Average answer tokens | **178** | 208 |
| Average generation latency | **23.1 s** | 28.0 s |

Vector RAG performed better on direct questions. Graph augmentation showed selective benefit on the single boundary question. The result motivated a larger evaluation; it does not support a general conclusion.

Full methodology: [evaluation/public_graphrag/README.md](../evaluation/public_graphrag/README.md).

## Drug discovery

Implemented paths include:

- RDKit canonicalization, descriptors, molecular formula, Lipinski, and Veber calculations
- ADMET-AI v2 predictions
- AutoDock Vina and Smina docking adapters
- GROMACS molecular-dynamics execution
- Scientific relationships represented in the knowledge graph
- Direct, registry, persistent-job, named-agent, and API execution paths

ADMET, toxicity, docking, and MD outputs are computational results. They are not experimental evidence, clinical recommendations, or regulatory conclusions.

## CAD, CFD, and visualization

The reproducible demonstration under `demos/cad_flow_channel/` executes:

1. FreeCAD geometry generation for a 200 × 50 × 20 mm rectangular flow domain.
2. OpenFOAM 12 mesh generation and validation.
3. A laminar simulation through 1 second of simulated time.
4. Blender 5.0.1 generation of a 96-frame visualization.

Observed demonstration values:

| Metric | Result |
|---|---:|
| Mesh cells | 1,600 |
| Maximum mesh non-orthogonality | 0 |
| Maximum Courant number | approximately 0.551 |
| Mean final velocity magnitude | approximately 1.000 m/s |
| Maximum final velocity magnitude | approximately 1.100 m/s |

This demonstrates cross-tool orchestration and reproducibility. It is not presented as a validated CFD benchmark.

## Structural FEA

CalculiX was added after the generic orchestration system to test architectural extensibility.

The verified asynchronous path was:

```text
POST /jobs
  → engineering-agent
  → persistent dispatcher
  → required capability: calculix
  → worker health and capability routing
  → structural_fea:calculix
  → remote worker over SSH
  → CalculiX
  → return code 0
  → durable COMPLETED state
```

No FEA-specific routing algorithm was added to the generic job store, dispatcher, worker registry, workload router, or API endpoints.

The cantilever case establishes solver and orchestration execution. It is not a high-fidelity numerical benchmark. CalculiX `.dat`, `.frd`, and `.sta` outputs are not yet registered through the generic artifact-manifest pipeline.

## Defensive cybersecurity

The defensive discovery workflow validates its authorization flag and accepts only one private or loopback IP address plus an explicit list of no more than 32 ports.

It performs TCP connection checks and produces informational findings with limitations and NIST SP 800-115 discovery-phase metadata. It does not exploit targets or attempt authentication.

## AWS infrastructure

A full Terraform deployment lifecycle was verified in `eu-north-1` on 2026-08-28:

- 17 expected resources created without warnings
- Containerized API reported healthy status and a running dispatcher
- Three domains exposed through `/capabilities` at the time of deployment
- EC2 registered with Systems Manager without inbound SSH
- Runtime SQLite state synchronized to the private S3 prefix
- Post-deployment plan reported no drift
- Reviewed destroy plan removed all 17 resources and left empty state

This validates provisioning, bootstrap, API discovery, artifact synchronization, drift detection, and cleanup. It does not move scientific executors into AWS.

Full deployment record: [infra/terraform/README.md](../infra/terraform/README.md).
