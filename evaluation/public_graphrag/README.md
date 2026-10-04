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

```cmd
python -m evaluation.public_graphrag.benchmark
```

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

- `evaluation/public_graphrag/results/benchmark_results.json`
- `evaluation/public_graphrag/results/benchmark_summary.csv`

Do not place private research documents in this benchmark. Do not publish a
comparison table until the generated answers and claim-level scores have been
manually reviewed.

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
The output includes router accuracy, a vector/graph confusion matrix, and the
population standard deviation for claim coverage, token use, and latency across
repetitions. Automatic lexical claim coverage is an audit aid, not a substitute
for checking contradictions and unsupported statements in every generated
answer. Do not publish model-comparison figures until both runs have completed
and every generated answer has been manually reviewed.
