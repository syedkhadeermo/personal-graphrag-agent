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
from statistics import mean
from typing import Any

from ollama import Client

from app.chunking.text_chunker import TextChunker
from app.embeddings.ollama_embeddings import OllamaEmbeddingService
from app.graphrag.graphrag_service import GraphRAGService
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


def aggregate(rows: list[dict], mode: str) -> dict:
    return {
        "claim_coverage": mean(row[mode]["claim_coverage"] for row in rows),
        "prompt_tokens": mean(row[mode]["prompt_tokens"] for row in rows),
        "answer_tokens": mean(row[mode]["answer_tokens"] for row in rows),
        "generation_latency_ms": mean(
            row[mode]["generation_latency_ms"] for row in rows
        ),
    }


def aggregate_runs(runs: list[dict]) -> dict:
    return {
        "claim_coverage": mean(run["claim_coverage"] for run in runs),
        "prompt_tokens": mean(run["prompt_tokens"] for run in runs),
        "answer_tokens": mean(run["answer_tokens"] for run in runs),
        "generation_latency_ms": mean(
            run["generation_latency_ms"] for run in runs
        ),
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


def run_benchmark(
    runtime_directory: Path,
    results_directory: Path,
    model: str,
    host: str,
    top_k: int,
    graph_max_depth: int,
    relevance_threshold: float,
    repetitions: int = 3,
) -> dict:
    if repetitions <= 0:
        raise ValueError("repetitions must be greater than zero")

    sources = load_json(ROOT / "sources.json")
    questions = load_json(ROOT / "gold_questions.json")
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
    generator = MeasuredGenerator(model=model, host=host)
    generator.generate(
        "Is this a benchmark warm-up?",
        "This is a benchmark warm-up request.",
    )
    rows = []

    for question_index, question in enumerate(questions):
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

            if vector_first:
                vector_answer, vector_metrics = answer_vector_only(
                    question["question"], chunks, generator
                )
                graph_result, graph_metrics = answer_with_graph(
                    question["question"], chunks, graph, generator, graph_max_depth
                )
            else:
                graph_result, graph_metrics = answer_with_graph(
                    question["question"], chunks, graph, generator, graph_max_depth
                )
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
            "source_hashes": {
                record["source_id"]: record["sha256"] for record in records
            },
        },
        "summary": {
            "retrieval_source_recall": mean(
                row["retrieval_source_recall"] for row in rows
            ),
            "vector": aggregate(rows, "vector"),
            "graphrag": aggregate(rows, "graphrag"),
            "by_category": category_summary(rows),
        },
        "questions": rows,
    }

    results_directory.mkdir(parents=True, exist_ok=True)
    (results_directory / "benchmark_results.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    with (results_directory / "benchmark_summary.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        fieldnames = [
            "question_id",
            "category",
            "retrieval_source_recall",
            "vector_claim_coverage",
            "graphrag_claim_coverage",
            "vector_prompt_tokens",
            "graphrag_prompt_tokens",
            "vector_latency_ms",
            "graphrag_latency_ms",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "question_id": row["question_id"],
                    "category": row["category"],
                    "retrieval_source_recall": row["retrieval_source_recall"],
                    "vector_claim_coverage": row["vector"]["claim_coverage"],
                    "graphrag_claim_coverage": row["graphrag"]["claim_coverage"],
                    "vector_prompt_tokens": row["vector"]["prompt_tokens"],
                    "graphrag_prompt_tokens": row["graphrag"]["prompt_tokens"],
                    "vector_latency_ms": row["vector"]["generation_latency_ms"],
                    "graphrag_latency_ms": row["graphrag"]["generation_latency_ms"],
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
        "--model", default=os.getenv("GRAPH_RAG_BENCHMARK_MODEL", "deepseek-coder:6.7b")
    )
    parser.add_argument(
        "--host", default=os.getenv("OLLAMA_HOST", "http://localhost:11434")
    )
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--graph-max-depth", type=int, default=6)
    parser.add_argument("--relevance-threshold", type=float, default=0.85)
    parser.add_argument("--repetitions", type=int, default=3)
    arguments = parser.parse_args()
    payload = run_benchmark(
        runtime_directory=arguments.runtime,
        results_directory=arguments.results,
        model=arguments.model,
        host=arguments.host,
        top_k=arguments.top_k,
        graph_max_depth=arguments.graph_max_depth,
        relevance_threshold=arguments.relevance_threshold,
        repetitions=arguments.repetitions,
    )
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
