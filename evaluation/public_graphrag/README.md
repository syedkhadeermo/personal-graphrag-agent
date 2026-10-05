# Public-document GraphRAG benchmark

This benchmark compares Vector RAG with retrieval-seeded GraphRAG over the
same real Chroma retrieval results. It focuses on one deep workflow domain:
drug discovery from molecular preparation and docking to MD analysis.

The corpus is downloaded at run time from official RDKit, AutoDock Vina, and
GROMACS documentation listed in `sources.json`. Downloaded text, Chroma data,
and the isolated benchmark graph stay under `runtime/` and are not committed.
SHA-256 hashes of the exact extracted source text are saved with every result.
The default relevance threshold is the project's production value of `0.85`.

Gold questions, expected router modes, and required claims are stored separately
in `gold_questions.json`. The 32-question set includes:

- 17 direct questions where Vector RAG should be sufficient;
- 10 cross-source questions where graph relationships may help;
- 5 boundary questions that test whether the system avoids unsupported
  conclusions from parsing, docking, or trajectory-analysis outputs.

## Requirements

Start Ollama and ensure both models are available:

```cmd
ollama pull nomic-embed-text:latest
ollama pull qwen3:8b
ollama pull deepseek-coder:6.7b
```

## Run

From the repository root:

Measure the deterministic router without downloading the corpus or starting
Ollama:

```cmd
python -m evaluation.public_graphrag.benchmark --router-only
```

The current public development suite produces 32/32 expected routes (17 vector
and 15 graph, with no cross-route errors). Because this is not an independently
held-out question set, the result verifies the current rules rather than
generalization to unseen questions. The committed
[`published/router_results.json`](published/router_results.json) records every
decision and the SHA-256 identity of the gold-question file.

Run the complete retrieval and generation comparison with:

```cmd
python -m evaluation.public_graphrag.benchmark
```

For a thermally constrained workstation, pause between generation calls and
between completed questions:

```cmd
python -m evaluation.public_graphrag.benchmark ^
  --model qwen3:8b ^
  --repetitions 3 ^
  --generation-cooldown-seconds 15 ^
  --cooldown-seconds 60 ^
  --results evaluation/public_graphrag/results/qwen3-8b
```

The runner writes `benchmark_checkpoint.json` atomically after every completed
question. If a run is stopped, repeat the identical command with `--resume`.
The model, host, retrieval settings, repetition count, question-set hash, and
downloaded source hashes must match the checkpoint. An interruption during a
question loses only that incomplete question.

The controlled protocol disables model thinking and caps each generation at
512 tokens. Empty answers fail the current question instead of silently
entering the aggregate. The output reports both strict all-groups claim
coverage and fine-grained claim-group coverage. Run-to-run dispersion is
calculated within each question before being summarized, so question-difficulty
variation is not mislabeled as repeatability variation.

`qwen3:8b` is the default general-purpose generation model. To compare it with
the original code-oriented baseline, keep separate output directories:

```cmd
python -m evaluation.public_graphrag.benchmark ^
  --model qwen3:8b ^
  --results evaluation/public_graphrag/results/qwen3-8b

python -m evaluation.public_graphrag.benchmark ^
  --model deepseek-coder:6.7b ^
  --results evaluation/public_graphrag/results/deepseek-coder-6.7b
```

Outputs:

- `evaluation/public_graphrag/results/router_results.json` for `--router-only`
- `evaluation/public_graphrag/results/benchmark_checkpoint.json` during a run
- `evaluation/public_graphrag/results/benchmark_results.json`
- `evaluation/public_graphrag/results/benchmark_summary.csv`

Do not place private research documents in this benchmark. Do not publish a
comparison table until the generated answers and claim-level scores have been
manually reviewed.

## Published controlled result

The controlled protocol-v2 `qwen3:8b` run completed 32 questions, three
repetitions, and both retrieval modes: 192 generated answers in total. Every
answer stopped normally, no answer was empty, and the maximum recorded answer
length stayed below the 512-token cap.

| Metric | Vector RAG | GraphRAG | Router-selected path |
|---|---:|---:|---:|
| Strict claim coverage | 65.1% | 66.1% | **71.4%** |
| Claim-group coverage | 85.0% | 86.5% | **88.6%** |
| Mean latency | **4.69 s** | 4.76 s | 4.70 s |
| Manually fully supported | 69/96 | 74/96 | **77/96** |

The router-selected column uses the Vector answer for each direct question and
the GraphRAG answer for each cross-source or boundary question. It reuses the
same completed comparison runs; it is not a third generation pass.

The manual review found six factually incorrect answers, all caused by the same
command substitution across both modes and all repetitions: `gmx rms` was used
for radius of gyration instead of `gmx gyrate`. It also found safe abstentions,
incomplete API workflows, and unsupported RDKit-to-docking bridges that the
lexical score alone does not reliably identify.

The [machine-readable audit](published/qwen3_8b_protocol_v2_audit.json) contains
all 192 generated answers, per-run review judgments, sanitized evidence
identities, automated metrics, source hashes, artifact hashes, the review
rubric, and interpretation limits. Retrieved documentation text is omitted from
the published audit to avoid duplicating large source excerpts; source URL,
source ID, chunk number, and distance are retained.

## Interpretation limits

This is a transparent portfolio benchmark rather than a general claim that
GraphRAG is universally superior. Both modes use identical retrieved
chunks, model, prompt, temperature, seed, and top-k. The comparison records
retrieval source recall, claim coverage, prompt/output tokens, latency, graph
seeds, and graph-context size.
The generator is warmed once and Vector RAG/GraphRAG execution order alternates
between repetitions to reduce systematic latency bias. Each answer mode runs
three times by default. Results retain retrieved chunk IDs, distances, text,
graph relationships, per-category summaries, and explicit manual-review fields.
The output includes router accuracy, a vector/graph confusion matrix, pooled
population dispersion for descriptive completeness, and a separate
within-question run-to-run dispersion summary. Automatic lexical claim and
claim-group coverage are audit aids, not substitutes for checking contradictions
and unsupported statements in every generated answer. Do not publish
model-comparison figures until the controlled run has completed and every
generated answer has been manually reviewed.
