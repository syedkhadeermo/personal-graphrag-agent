import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import time
import urllib.request

from html.parser import HTMLParser
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

from ollama import Client

from app.chunking.text_chunker import TextChunker
from app.embeddings.ollama_embeddings import OllamaEmbeddingService
from app.graphrag.graphrag_service import GraphRAGService
from app.graphrag.retrieval_router import RetrievalRouter
from app.knowledge_graph.graph_builder import KnowledgeGraphBuilder
from app.knowledge_graph.graph_store import KnowledgeGraphStore
from app.retrieval.retrieval_service import RetrievalService
from app.vectorstore.chroma_store import ChromaVectorStore


ROOT = Path(__file__).resolve().parent
DEFAULT_RUNTIME = ROOT / "runtime"
DEFAULT_RESULTS = ROOT / "results"
DOMAIN = "drug_discovery"
COLLECTION = "public_drug_discovery_benchmark"


class MainTextExtractor(HTMLParser):
    """Extract readable text from the main section of documentation HTML."""

    SKIP_TAGS = {"script", "style", "svg", "noscript"}

    def __init__(self) -> None:
        super().__init__()
        self.main_depth = 0
        self.skip_depth = 0
        self.seen_main = False
        self.main_parts: list[str] = []
        self.body_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return

        if tag == "main":
            self.seen_main = True
            self.main_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
            return

        if tag == "main" and self.main_depth:
            self.main_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return

        text = " ".join(data.split())
        if not text:
            return

        self.body_parts.append(text)
        if self.main_depth:
            self.main_parts.append(text)

    def text(self) -> str:
        parts = self.main_parts if self.seen_main and self.main_parts else self.body_parts
        return "\n".join(parts)


class FixedRetrievalService:
    """Return one already-executed Chroma retrieval to both answer modes."""

    def __init__(self, chunks: list[dict]):
        self.chunks = chunks

    def search(self, **_: Any) -> list[dict]:
        return self.chunks


class MeasuredGenerator:
    """Run one deterministic, context-only Ollama generation and record usage."""

    def __init__(self, model: str, host: str):
        self.model = model
        self.client = Client(host=host)
        self.last_metrics: dict[str, Any] = {}

    def generate(self, question: str, context: str) -> str:
        prompt = (
            "Answer using only the supplied context. Do not use outside knowledge. "
            "If the context is insufficient, say so directly.\n\n"
            f"CONTEXT:\n{context}\n\nQUESTION:\n{question}\n\nANSWER:"
        )
        started = time.perf_counter()
        response = self.client.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0, "seed": 42},
        )
        self.last_metrics = {
            "generation_latency_ms": (time.perf_counter() - started) * 1000,
            "prompt_tokens": int(response.get("prompt_eval_count", 0) or 0),
            "answer_tokens": int(response.get("eval_count", 0) or 0),
        }
        return response["message"]["content"].strip()


def load_json(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalized(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def claim_is_present(answer: str, claim: dict) -> bool:
    answer_text = normalized(answer)
    return all(
        any(normalized(term) in answer_text for term in alternatives)
        for alternatives in claim["term_groups"]
    )


def score_answer(answer: str, claims: list[dict]) -> dict:
    passed = [claim["claim_id"] for claim in claims if claim_is_present(answer, claim)]
    return {
        "claims_passed": passed,
        "claims_total": len(claims),
        "claim_coverage": len(passed) / len(claims),
    }


def fetch_public_sources(sources: list[dict], cache_directory: Path) -> list[dict]:
    cache_directory.mkdir(parents=True, exist_ok=True)
    records = []

    for source in sources:
        request = urllib.request.Request(
            source["url"],
            headers={"User-Agent": "personal-graphrag-agent-public-benchmark/1.0"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            html = response.read().decode("utf-8", errors="replace")

        parser = MainTextExtractor()
        parser.feed(html)
        text = parser.text().strip()
        if len(text) < 500:
            raise RuntimeError(f"Insufficient extracted text from {source['url']}")

        cache_path = cache_directory / f"{source['source_id']}.txt"
        cache_path.write_text(text, encoding="utf-8")
        records.append(
            {
                **source,
                "text": text,
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "characters": len(text),
            }
        )

    return records


def build_vector_index(
    records: list[dict],
    runtime_directory: Path,
    embedding_service: OllamaEmbeddingService,
) -> tuple[ChromaVectorStore, list[dict]]:
    chroma_directory = runtime_directory / "chroma"
    if chroma_directory.exists():
        shutil.rmtree(chroma_directory)

    store = ChromaVectorStore(
        persist_directory=str(chroma_directory),
        collection_name=COLLECTION,
    )
    chunker = TextChunker(chunk_size=1200, chunk_overlap=150)
    all_chunks = []

    for record in records:
        chunks = chunker.chunk_document(
            text=record["text"],
            domain=DOMAIN,
            source=record["source_id"],
            metadata={
                "source_id": record["source_id"],
                "title": record["title"],
                "publisher": record["publisher"],
                "url": record["url"],
                "visibility": "public",
                "document_type": "official_documentation",
            },
        )
        all_chunks.extend(chunks)

    texts = [chunk.text for chunk in all_chunks]
    embeddings = embedding_service.embed_batch(texts)
    store.add_documents(
        ids=[chunk.chunk_id for chunk in all_chunks],
        documents=texts,
        embeddings=embeddings,
        metadatas=[chunk.metadata for chunk in all_chunks],
    )
    return store, [chunk.metadata for chunk in all_chunks]


def retrieved_source_ids(chunks: list[dict]) -> set[str]:
    return {
        str(chunk.get("metadata", {}).get("source_id"))
        for chunk in chunks
        if chunk.get("metadata", {}).get("source_id")
    }


def evidence_audit(chunks: list[dict]) -> list[dict]:
    """Preserve the exact retrieved evidence used by both answer modes."""

    return [
        {
            "chunk_id": chunk.get("id") or chunk.get("chunk_id"),
            "distance": chunk.get("distance"),
            "relevance_score": chunk.get("relevance_score"),
            "source_id": chunk.get("metadata", {}).get("source_id"),
            "metadata": chunk.get("metadata", {}),
            "text": chunk.get("text", ""),
        }
        for chunk in chunks
    ]


def answer_vector_only(
    question: str,
    chunks: list[dict],
    generator: MeasuredGenerator,
) -> tuple[str, dict]:
    context = "\n\n".join(chunk["text"] for chunk in chunks)
    answer = generator.generate(question, context)
    return answer, dict(generator.last_metrics)


def answer_with_graph(
    question: str,
    chunks: list[dict],
    graph: KnowledgeGraphStore,
    generator: MeasuredGenerator,
    graph_max_depth: int,
) -> tuple[dict, dict]:
    service = GraphRAGService(
        retrieval_service=FixedRetrievalService(chunks),
        graph_store=graph,
        generator=generator,
    )
    result = service.answer(
        question=question,
        domain=DOMAIN,
        n_results=len(chunks),
        visibility="public",
        graph_max_depth=graph_max_depth,
        retrieval_mode="graph",
    )
    return result, dict(generator.last_metrics)


METRICS = (
    "claim_coverage",
    "prompt_tokens",
    "answer_tokens",
    "generation_latency_ms",
)


def summarize_metrics(records: list[dict]) -> dict:
    summary = {}
    for metric in METRICS:
        values = [record[metric] for record in records]
        summary[metric] = mean(values)
        summary[f"{metric}_stddev"] = pstdev(values)
    return summary


def aggregate(rows: list[dict], mode: str) -> dict:
    runs = [run for row in rows for run in row[mode]["runs"]]
    return summarize_metrics(runs)


def aggregate_runs(runs: list[dict]) -> dict:
    return summarize_metrics(runs)


def routing_summary(rows: list[dict]) -> dict:
    labels = ("vector", "graph")
    confusion_matrix = {
        expected: {selected: 0 for selected in labels} for expected in labels
    }
    for row in rows:
        confusion_matrix[row["expected_retrieval_mode"]][
            row["router_decision"]["selected_mode"]
        ] += 1
    correct = sum(
        row["expected_retrieval_mode"]
        == row["router_decision"]["selected_mode"]
        for row in rows
    )
    return {
        "correct": correct,
        "questions": len(rows),
        "accuracy": correct / len(rows),
        "confusion_matrix": confusion_matrix,
    }


def category_summary(rows: list[dict]) -> dict:
    summary = {}
    for category in sorted({row["category"] for row in rows}):
        category_rows = [row for row in rows if row["category"] == category]
        summary[category] = {
            "questions": len(category_rows),
            "retrieval_source_recall": mean(
                row["retrieval_source_recall"] for row in category_rows
            ),
            "vector": aggregate(category_rows, "vector"),
            "graphrag": aggregate(category_rows, "graphrag"),
        }
    return summary


def pending_manual_review() -> dict:
    return {
        "status": "pending",
        "contradiction_detected": None,
        "unsupported_claim_detected": None,
        "notes": "",
    }


def write_json_atomic(path: Path, payload: dict) -> None:
    """Write JSON through a sibling temporary file before replacing the target."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary_path.replace(path)


def checkpoint_signature(
    *,
    model: str,
    host: str,
    top_k: int,
    graph_max_depth: int,
    relevance_threshold: float,
    repetitions: int,
    gold_questions_sha256: str,
    source_hashes: dict[str, str],
) -> dict:
    """Return the inputs that must match before checkpoint rows can be reused."""

    return {
        "generation_model": model,
        "ollama_host": host,
        "embedding_model": "nomic-embed-text:latest",
        "top_k": top_k,
        "graph_max_depth": graph_max_depth,
        "relevance_threshold": relevance_threshold,
        "temperature": 0,
        "seed": 42,
        "repetitions_per_mode": repetitions,
        "gold_questions_sha256": gold_questions_sha256,
        "source_hashes": source_hashes,
    }


def load_checkpoint(path: Path, expected_signature: dict) -> list[dict]:
    """Load validated completed rows from a previous interrupted run."""

    if not path.is_file():
        raise RuntimeError(f"Resume requested but checkpoint does not exist: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("signature") != expected_signature:
        raise RuntimeError(
            "Checkpoint settings or source hashes do not match this run. "
            "Use the original arguments or choose a new results directory."
        )

    rows = payload.get("questions")
    if not isinstance(rows, list):
        raise RuntimeError("Checkpoint questions must be a list.")
    question_ids = [row.get("question_id") for row in rows]
    if len(question_ids) != len(set(question_ids)):
        raise RuntimeError("Checkpoint contains duplicate question IDs.")
    return rows


def cooldown(seconds: float, reason: str) -> None:
    """Pause between sustained generation steps when cooling is requested."""

    if seconds <= 0:
        return
    print(f"Cooling for {seconds:g} seconds ({reason})...", flush=True)
    time.sleep(seconds)


def run_router_benchmark(results_directory: Path) -> dict:
    """Measure the deterministic router without retrieval or generation models."""

    gold_path = ROOT / "gold_questions.json"
    questions = load_json(gold_path)
    router = RetrievalRouter(GraphRAGService._QUESTION_ENTITY_ALIASES)
    rows = []

    for question in questions:
        decision = router.route(question["question"])
        rows.append(
            {
                "question_id": question["question_id"],
                "category": question["category"],
                "expected_retrieval_mode": question["expected_retrieval_mode"],
                "router_decision": decision.to_dict(),
                "router_correct": (
                    decision.selected_mode
                    == question["expected_retrieval_mode"]
                ),
            }
        )

    payload = {
        "protocol": {
            "questions": len(rows),
            "gold_questions_sha256": hashlib.sha256(
                gold_path.read_bytes()
            ).hexdigest(),
            "scope": "deterministic routing only; no retrieval or generation",
        },
        "summary": routing_summary(rows),
        "questions": rows,
    }
    results_directory.mkdir(parents=True, exist_ok=True)
    write_json_atomic(results_directory / "router_results.json", payload)
    return payload


def run_benchmark(
    runtime_directory: Path,
    results_directory: Path,
    model: str,
    host: str,
    top_k: int,
    graph_max_depth: int,
    relevance_threshold: float,
    repetitions: int = 3,
    resume: bool = False,
    cooldown_seconds: float = 0,
    generation_cooldown_seconds: float = 0,
) -> dict:
    if repetitions <= 0:
        raise ValueError("repetitions must be greater than zero")
    if cooldown_seconds < 0 or generation_cooldown_seconds < 0:
        raise ValueError("cooldown values cannot be negative")

    sources = load_json(ROOT / "sources.json")
    gold_path = ROOT / "gold_questions.json"
    questions = load_json(gold_path)
    records = fetch_public_sources(sources, runtime_directory / "source_cache")
    embedding_service = OllamaEmbeddingService(model="nomic-embed-text:latest", host=host)
    store, chunk_metadata = build_vector_index(
        records, runtime_directory, embedding_service
    )
    retrieval = RetrievalService(
        embedding_service=embedding_service,
        vector_store=store,
        relevance_threshold=relevance_threshold,
    )

    graph_path = runtime_directory / "knowledge_graph.json"
    if graph_path.exists():
        graph_path.unlink()
    graph = KnowledgeGraphStore(str(graph_path))
    KnowledgeGraphBuilder(graph).build_drug_discovery_workflow()
    router = RetrievalRouter(GraphRAGService._QUESTION_ENTITY_ALIASES)
    source_hashes = {
        record["source_id"]: record["sha256"] for record in records
    }
    signature = checkpoint_signature(
        model=model,
        host=host,
        top_k=top_k,
        graph_max_depth=graph_max_depth,
        relevance_threshold=relevance_threshold,
        repetitions=repetitions,
        gold_questions_sha256=hashlib.sha256(gold_path.read_bytes()).hexdigest(),
        source_hashes=source_hashes,
    )
    checkpoint_path = results_directory / "benchmark_checkpoint.json"
    rows = load_checkpoint(checkpoint_path, signature) if resume else []
    completed_question_ids = {row["question_id"] for row in rows}
    known_question_ids = {question["question_id"] for question in questions}
    unknown_question_ids = completed_question_ids - known_question_ids
    if unknown_question_ids:
        raise RuntimeError(
            "Checkpoint contains questions absent from the gold suite: "
            f"{sorted(unknown_question_ids)}"
        )

    pending_questions = [
        question
        for question in questions
        if question["question_id"] not in completed_question_ids
    ]
    if resume:
        print(
            f"Resuming with {len(rows)}/{len(questions)} questions complete; "
            f"{len(pending_questions)} remain.",
            flush=True,
        )

    generator = None
    if pending_questions:
        generator = MeasuredGenerator(model=model, host=host)
        print("Warming the generation model...", flush=True)
        generator.generate(
            "Is this a benchmark warm-up?",
            "This is a benchmark warm-up request.",
        )

    for question_index, question in enumerate(questions):
        if question["question_id"] in completed_question_ids:
            continue

        print(
            f"Question {question_index + 1}/{len(questions)}: "
            f"{question['question_id']}",
            flush=True,
        )
        router_decision = router.route(question["question"])
        retrieval_started = time.perf_counter()
        chunks = retrieval.search(
            query=question["question"],
            n_results=top_k,
            domain=DOMAIN,
            visibility="public",
        )
        retrieval_latency_ms = (time.perf_counter() - retrieval_started) * 1000
        if not chunks:
            raise RuntimeError(f"No chunks retrieved for {question['question_id']}")

        source_ids = retrieved_source_ids(chunks)
        gold_sources = set(question["gold_source_ids"])
        source_recall = len(source_ids & gold_sources) / len(gold_sources)
        vector_runs = []
        graph_runs = []
        generation_orders = []
        for repetition in range(repetitions):
            vector_first = (question_index + repetition) % 2 == 0
            order = ["vector", "graphrag"] if vector_first else ["graphrag", "vector"]
            generation_orders.append(order)
            print(
                f"  Repetition {repetition + 1}/{repetitions}: "
                f"{' -> '.join(order)}",
                flush=True,
            )

            if vector_first:
                vector_answer, vector_metrics = answer_vector_only(
                    question["question"], chunks, generator
                )
                cooldown(generation_cooldown_seconds, "between generations")
                graph_result, graph_metrics = answer_with_graph(
                    question["question"], chunks, graph, generator, graph_max_depth
                )
            else:
                graph_result, graph_metrics = answer_with_graph(
                    question["question"], chunks, graph, generator, graph_max_depth
                )
                cooldown(generation_cooldown_seconds, "between generations")
                vector_answer, vector_metrics = answer_vector_only(
                    question["question"], chunks, generator
                )

            vector_runs.append(
                {
                    "repetition": repetition + 1,
                    "answer": vector_answer,
                    **score_answer(vector_answer, question["claims"]),
                    **vector_metrics,
                    "manual_review": pending_manual_review(),
                }
            )
            if repetition + 1 < repetitions:
                cooldown(generation_cooldown_seconds, "between repetitions")
            graph_runs.append(
                {
                    "repetition": repetition + 1,
                    "answer": graph_result["answer"],
                    "seed_nodes": graph_result["graph_seed_nodes"],
                    "graph_relationships": graph_result["graph_context"],
                    **score_answer(graph_result["answer"], question["claims"]),
                    **graph_metrics,
                    "manual_review": pending_manual_review(),
                }
            )

        vector_summary = aggregate_runs(vector_runs)
        graph_summary = aggregate_runs(graph_runs)

        rows.append(
            {
                "question_id": question["question_id"],
                "category": question["category"],
                "question": question["question"],
                "expected_retrieval_mode": question["expected_retrieval_mode"],
                "router_decision": router_decision.to_dict(),
                "router_correct": (
                    router_decision.selected_mode
                    == question["expected_retrieval_mode"]
                ),
                "gold_source_ids": sorted(gold_sources),
                "retrieved_source_ids": sorted(source_ids),
                "retrieval_source_recall": source_recall,
                "retrieval_latency_ms": retrieval_latency_ms,
                "retrieved_evidence": evidence_audit(chunks),
                "generation_orders": generation_orders,
                "vector": {
                    **vector_summary,
                    "runs": vector_runs,
                },
                "graphrag": {
                    **graph_summary,
                    "runs": graph_runs,
                },
            }
        )
        completed_question_ids.add(question["question_id"])
        write_json_atomic(
            checkpoint_path,
            {
                "signature": signature,
                "completed_questions": len(rows),
                "total_questions": len(questions),
                "questions": rows,
            },
        )
        print(
            f"Checkpoint saved: {len(rows)}/{len(questions)} questions complete.",
            flush=True,
        )
        if len(rows) < len(questions):
            cooldown(cooldown_seconds, "between questions")

    if len(rows) != len(questions):
        raise RuntimeError(
            f"Benchmark ended with {len(rows)}/{len(questions)} questions."
        )

    payload = {
        "protocol": {
            "corpus": "live official public documentation",
            "embedding_model": "nomic-embed-text:latest",
            "generation_model": model,
            "top_k": top_k,
            "graph_max_depth": graph_max_depth,
            "relevance_threshold": relevance_threshold,
            "temperature": 0,
            "seed": 42,
            "questions": len(rows),
            "repetitions_per_mode": repetitions,
            "indexed_chunks": len(chunk_metadata),
            "source_hashes": source_hashes,
        },
        "summary": {
            "retrieval_source_recall": mean(
                row["retrieval_source_recall"] for row in rows
            ),
            "vector": aggregate(rows, "vector"),
            "graphrag": aggregate(rows, "graphrag"),
            "router": routing_summary(rows),
            "by_category": category_summary(rows),
        },
        "questions": rows,
    }

    results_directory.mkdir(parents=True, exist_ok=True)
    write_json_atomic(results_directory / "benchmark_results.json", payload)
    with (results_directory / "benchmark_summary.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        fieldnames = [
            "question_id",
            "category",
            "expected_retrieval_mode",
            "selected_retrieval_mode",
            "router_correct",
            "retrieval_source_recall",
            "vector_claim_coverage",
            "vector_claim_coverage_stddev",
            "graphrag_claim_coverage",
            "graphrag_claim_coverage_stddev",
            "vector_prompt_tokens",
            "graphrag_prompt_tokens",
            "vector_latency_ms",
            "vector_latency_ms_stddev",
            "graphrag_latency_ms",
            "graphrag_latency_ms_stddev",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "question_id": row["question_id"],
                    "category": row["category"],
                    "expected_retrieval_mode": row["expected_retrieval_mode"],
                    "selected_retrieval_mode": row["router_decision"][
                        "selected_mode"
                    ],
                    "router_correct": row["router_correct"],
                    "retrieval_source_recall": row["retrieval_source_recall"],
                    "vector_claim_coverage": row["vector"]["claim_coverage"],
                    "vector_claim_coverage_stddev": row["vector"][
                        "claim_coverage_stddev"
                    ],
                    "graphrag_claim_coverage": row["graphrag"]["claim_coverage"],
                    "graphrag_claim_coverage_stddev": row["graphrag"][
                        "claim_coverage_stddev"
                    ],
                    "vector_prompt_tokens": row["vector"]["prompt_tokens"],
                    "graphrag_prompt_tokens": row["graphrag"]["prompt_tokens"],
                    "vector_latency_ms": row["vector"]["generation_latency_ms"],
                    "vector_latency_ms_stddev": row["vector"][
                        "generation_latency_ms_stddev"
                    ],
                    "graphrag_latency_ms": row["graphrag"]["generation_latency_ms"],
                    "graphrag_latency_ms_stddev": row["graphrag"][
                        "generation_latency_ms_stddev"
                    ],
                }
            )

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark Vector RAG and retrieval-seeded GraphRAG."
    )
    parser.add_argument("--runtime", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument(
        "--model", default=os.getenv("GRAPH_RAG_BENCHMARK_MODEL", "qwen3:8b")
    )
    parser.add_argument(
        "--host", default=os.getenv("OLLAMA_HOST", "http://localhost:11434")
    )
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--graph-max-depth", type=int, default=6)
    parser.add_argument("--relevance-threshold", type=float, default=0.85)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Continue from a compatible per-question checkpoint.",
    )
    parser.add_argument(
        "--cooldown-seconds",
        type=float,
        default=0,
        help="Pause after each completed question.",
    )
    parser.add_argument(
        "--generation-cooldown-seconds",
        type=float,
        default=0,
        help="Pause between generation calls and repetitions.",
    )
    parser.add_argument(
        "--router-only",
        action="store_true",
        help="Measure routing labels without downloading sources or using models.",
    )
    arguments = parser.parse_args()
    if arguments.router_only:
        payload = run_router_benchmark(arguments.results)
    else:
        payload = run_benchmark(
            runtime_directory=arguments.runtime,
            results_directory=arguments.results,
            model=arguments.model,
            host=arguments.host,
            top_k=arguments.top_k,
            graph_max_depth=arguments.graph_max_depth,
            relevance_threshold=arguments.relevance_threshold,
            repetitions=arguments.repetitions,
            resume=arguments.resume,
            cooldown_seconds=arguments.cooldown_seconds,
            generation_cooldown_seconds=arguments.generation_cooldown_seconds,
        )
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
