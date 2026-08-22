import json
import time
from pathlib import Path

from app.embeddings.ollama_embeddings import (
    OllamaEmbeddingService,
)
from app.knowledge.chunker import KnowledgeChunker
from app.knowledge.document_loader import DocumentLoader
from app.knowledge.knowledge_indexer import KnowledgeIndexer
from app.retrieval.retrieval_service import RetrievalService
from app.vectorstore.chroma_store import ChromaVectorStore


GROMACS_MANUAL = (
    Path("data")
    / "knowledge"
    / "drug_discovery"
    / "gromacs_manual.pdf"
)

CHROMA_DIRECTORY = Path("data") / "chroma"
COLLECTION_NAME = "technical_knowledge"
DOMAIN = "drug_discovery"
SOURCE = "gromacs_manual.pdf"

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
BATCH_SIZE = 32


def get_source_records(
    vector_store: ChromaVectorStore,
    source: str,
) -> dict:
    """
    Retrieve records belonging to one source document.

    Chroma always returns IDs. Only metadata is additionally
    requested because documents and embeddings are unnecessary
    for the duplicate preflight.
    """

    return vector_store.collection.get(
        where={
            "source": source,
        },
        include=[
            "metadatas",
        ],
    )


def retrieve_gromacs_evidence(
    embedding_service: OllamaEmbeddingService,
    vector_store: ChromaVectorStore,
) -> list[dict]:
    """
    Run a production retrieval check after indexing.
    """

    retrieval_service = RetrievalService(
        embedding_service=embedding_service,
        vector_store=vector_store,
        relevance_threshold=0.85,
    )

    return retrieval_service.search_by_domain(
        query=(
            "How are energy minimization, NVT equilibration, "
            "NPT equilibration, and molecular dynamics "
            "performed in GROMACS?"
        ),
        domain=DOMAIN,
        n_results=5,
    )


def format_results(
    results: list[dict],
) -> list[dict]:
    """
    Produce readable retrieval output.
    """

    formatted = []

    for result in results:
        text = (
            result.get("text", "")
            or ""
        )

        formatted.append(
            {
                "text_preview": text[:400],
                "metadata": result.get(
                    "metadata",
                    {},
                ),
                "distance": result.get(
                    "distance"
                ),
            }
        )

    return formatted


def main() -> None:
    print(
        "1. Validating production GROMACS source..."
    )

    if not GROMACS_MANUAL.is_file():
        raise FileNotFoundError(
            f"GROMACS manual not found: "
            f"{GROMACS_MANUAL}"
        )

    print(
        json.dumps(
            {
                "path": str(GROMACS_MANUAL),
                "size_bytes": (
                    GROMACS_MANUAL.stat().st_size
                ),
                "collection": COLLECTION_NAME,
                "domain": DOMAIN,
                "source": SOURCE,
            },
            indent=2,
        )
    )

    print(
        "\n2. Loading the complete GROMACS manual..."
    )

    loader = DocumentLoader()

    document = loader.load(
        path=str(GROMACS_MANUAL),
        domain=DOMAIN,
    )

    assert document["filename"] == SOURCE
    assert document["domain"] == DOMAIN
    assert document["page_count"] > 0

    print(
        json.dumps(
            {
                "filename": document["filename"],
                "page_count": document["page_count"],
                "extension": document["extension"],
            },
            indent=2,
        )
    )

    print(
        "\n3. Chunking the complete GROMACS manual..."
    )

    chunker = KnowledgeChunker(
        chunk_size=CHUNK_SIZE,
        overlap=CHUNK_OVERLAP,
    )

    chunks = chunker.chunk_document(
        document
    )

    if not chunks:
        raise RuntimeError(
            "KnowledgeChunker produced no GROMACS chunks."
        )

    chunk_ids = {
        chunk["chunk_id"]
        for chunk in chunks
    }

    if len(chunk_ids) != len(chunks):
        raise RuntimeError(
            "KnowledgeChunker produced duplicate chunk IDs."
        )

    if not all(
        chunk["source"] == SOURCE
        for chunk in chunks
    ):
        raise RuntimeError(
            "Unexpected source metadata was generated."
        )

    if not all(
        chunk["domain"] == DOMAIN
        for chunk in chunks
    ):
        raise RuntimeError(
            "Unexpected domain metadata was generated."
        )

    print(
        json.dumps(
            {
                "chunks_prepared": len(chunks),
                "unique_chunk_ids": len(chunk_ids),
                "first_chunk_id": chunks[0]["chunk_id"],
                "last_chunk_id": chunks[-1]["chunk_id"],
                "batch_size": BATCH_SIZE,
            },
            indent=2,
        )
    )

    print(
        "\n4. Connecting to production "
        "technical_knowledge..."
    )

    vector_store = ChromaVectorStore(
        persist_directory=str(
            CHROMA_DIRECTORY
        ),
        collection_name=COLLECTION_NAME,
    )

    total_before = vector_store.count()

    source_records_before = get_source_records(
        vector_store=vector_store,
        source=SOURCE,
    )

    existing_ids = set(
        source_records_before.get(
            "ids",
            [],
        )
    )

    existing_source_count = len(
        existing_ids
    )

    print(
        json.dumps(
            {
                "total_collection_count": total_before,
                "existing_gromacs_records": (
                    existing_source_count
                ),
                "expected_gromacs_records": len(chunks),
            },
            indent=2,
        )
    )

    print(
        "\n5. Running source-level duplicate preflight..."
    )

    if existing_source_count > 0:
        if (
            existing_source_count == len(chunks)
            and existing_ids == chunk_ids
        ):
            print(
                "GROMACS manual is already fully indexed."
            )
            print(
                "No embeddings or Chroma writes were performed."
            )
            print(
                "\nPASS: Duplicate production ingestion "
                "was prevented safely."
            )
            print(
                f"PASS: Collection count remains "
                f"{total_before}."
            )
            return

        missing_ids = (
            chunk_ids
            - existing_ids
        )

        unexpected_ids = (
            existing_ids
            - chunk_ids
        )

        raise RuntimeError(
            "Partial or inconsistent GROMACS indexing "
            "was detected. Automatic writes were blocked. "
            f"existing={existing_source_count}; "
            f"expected={len(chunks)}; "
            f"missing={len(missing_ids)}; "
            f"unexpected={len(unexpected_ids)}."
        )

    print(
        "Preflight passed: no existing GROMACS "
        "records were found."
    )

    print(
        "\n6. Generating embeddings and indexing "
        "the complete manual..."
    )

    embedding_service = (
        OllamaEmbeddingService()
    )

    indexer = KnowledgeIndexer(
        embedding_service=embedding_service,
        vector_store=vector_store,
        batch_size=BATCH_SIZE,
    )

    start_time = time.perf_counter()

    indexing_result = indexer.index_chunks(
        chunks
    )

    indexing_seconds = round(
        time.perf_counter()
        - start_time,
        3,
    )

    print(
        json.dumps(
            {
                **indexing_result,
                "measured_indexing_seconds": (
                    indexing_seconds
                ),
            },
            indent=2,
            default=str,
        )
    )

    print(
        "\n7. Verifying production collection counts..."
    )

    total_after = vector_store.count()

    source_records_after = get_source_records(
        vector_store=vector_store,
        source=SOURCE,
    )

    indexed_ids = set(
        source_records_after.get(
            "ids",
            [],
        )
    )

    expected_total_after = (
        total_before
        + len(chunks)
    )

    verification = {
        "total_before": total_before,
        "total_after": total_after,
        "expected_total_after": expected_total_after,
        "gromacs_records": len(indexed_ids),
        "expected_gromacs_records": len(chunks),
    }

    print(
        json.dumps(
            verification,
            indent=2,
        )
    )

    if total_after != expected_total_after:
        raise RuntimeError(
            "Production collection count did not "
            "increase by the expected number of chunks."
        )

    if indexed_ids != chunk_ids:
        raise RuntimeError(
            "Stored GROMACS chunk IDs do not match "
            "the prepared chunk IDs."
        )

    print(
        "\n8. Running production GROMACS retrieval..."
    )

    results = retrieve_gromacs_evidence(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    print(
        json.dumps(
            format_results(results),
            indent=2,
            default=str,
        )
    )

    if not results:
        raise RuntimeError(
            "Production GROMACS retrieval returned "
            "no relevant results."
        )

    gromacs_results = [
        result
        for result in results
        if result.get(
            "metadata",
            {},
        ).get("source") == SOURCE
    ]

    if not gromacs_results:
        raise RuntimeError(
            "Retrieval returned no evidence from "
            "gromacs_manual.pdf."
        )

    print(
        "\nPASS: Complete GROMACS manual was loaded."
    )
    print(
        "PASS: Complete GROMACS manual was chunked."
    )
    print(
        "PASS: Source-level duplicate preflight passed."
    )
    print(
        "PASS: GROMACS chunks were indexed into "
        "technical_knowledge."
    )
    print(
        "PASS: Production collection counts passed."
    )
    print(
        "PASS: Production GROMACS retrieval passed."
    )


if __name__ == "__main__":
    main()