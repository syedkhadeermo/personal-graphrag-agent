import json
import tempfile
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

DOMAIN = "drug_discovery"
COLLECTION_NAME = "technical_knowledge_test"
SAMPLE_NONEMPTY_PAGES = 12


def create_sample_document(
    document: dict,
    nonempty_page_limit: int,
) -> dict:
    """
    Create a small document sample for isolated pipeline testing.

    The production PDF is not modified.
    """

    selected_pages = []

    for page in document.get("pages", []):
        text = (
            page.get("text", "")
            or ""
        ).strip()

        if not text:
            continue

        selected_pages.append(page)

        if len(selected_pages) >= nonempty_page_limit:
            break

    if not selected_pages:
        raise RuntimeError(
            "No extractable text was found in the GROMACS manual."
        )

    return {
        **document,
        "page_count": len(selected_pages),
        "pages": selected_pages,
    }


def format_results(
    results: list[dict],
) -> list[dict]:
    """
    Shorten retrieved text for readable test output.
    """

    formatted = []

    for result in results:
        text = (
            result.get("text", "")
            or ""
        )

        formatted.append(
            {
                "text_preview": text[:300],
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
    if not GROMACS_MANUAL.is_file():
        raise FileNotFoundError(
            f"GROMACS manual not found: {GROMACS_MANUAL}"
        )

    temporary_directory = Path(
        tempfile.mkdtemp(
            prefix="gromacs_knowledge_test_"
        )
    )

    chroma_directory = (
        temporary_directory
        / "chroma"
    )

    print("1. Loading the GROMACS manual...")

    loader = DocumentLoader()

    document = loader.load(
        path=str(GROMACS_MANUAL),
        domain=DOMAIN,
    )

    print(
        json.dumps(
            {
                "filename": document["filename"],
                "domain": document["domain"],
                "page_count": document["page_count"],
                "extension": document["extension"],
            },
            indent=2,
        )
    )

    assert document["filename"] == "gromacs_manual.pdf"
    assert document["domain"] == DOMAIN
    assert document["page_count"] > 0

    print(
        "\n2. Selecting a small non-empty page sample..."
    )

    sample_document = create_sample_document(
        document=document,
        nonempty_page_limit=SAMPLE_NONEMPTY_PAGES,
    )

    print(
        json.dumps(
            {
                "sample_page_count": (
                    sample_document["page_count"]
                ),
                "page_numbers": [
                    page["page"]
                    for page in sample_document["pages"]
                ],
            },
            indent=2,
        )
    )

    print("\n3. Chunking the sampled pages...")

    chunker = KnowledgeChunker(
        chunk_size=1200,
        overlap=200,
    )

    chunks = chunker.chunk_document(
        sample_document
    )

    if not chunks:
        raise RuntimeError(
            "KnowledgeChunker produced no chunks."
        )

    print(
        json.dumps(
            {
                "chunk_count": len(chunks),
                "first_chunk_id": (
                    chunks[0]["chunk_id"]
                ),
                "last_chunk_id": (
                    chunks[-1]["chunk_id"]
                ),
                "sources": sorted(
                    {
                        chunk["source"]
                        for chunk in chunks
                    }
                ),
                "domains": sorted(
                    {
                        chunk["domain"]
                        for chunk in chunks
                    }
                ),
            },
            indent=2,
        )
    )

    assert all(
        chunk["source"] == "gromacs_manual.pdf"
        for chunk in chunks
    )

    assert all(
        chunk["domain"] == DOMAIN
        for chunk in chunks
    )

    print(
        "\n4. Creating an isolated technical collection..."
    )

    vector_store = ChromaVectorStore(
        persist_directory=str(
            chroma_directory
        ),
        collection_name=COLLECTION_NAME,
    )

    count_before = vector_store.count()

    assert count_before == 0

    print(
        f"Collection count before indexing: "
        f"{count_before}"
    )

    print(
        "\n5. Embedding and indexing sampled chunks..."
    )

    embedding_service = (
        OllamaEmbeddingService()
    )

    indexer = KnowledgeIndexer(
        embedding_service=embedding_service,
        vector_store=vector_store,
        batch_size=16,
    )

    indexing_result = indexer.index_chunks(
        chunks
    )

    print(
        json.dumps(
            indexing_result,
            indent=2,
            default=str,
        )
    )

    count_after = vector_store.count()

    print(
        f"Collection count after indexing: "
        f"{count_after}"
    )

    assert count_after == len(chunks)
    assert (
        indexing_result["chunks_indexed"]
        == len(chunks)
    )

    print(
        "\n6. Running domain-filtered GROMACS retrieval..."
    )

    retrieval_service = RetrievalService(
        embedding_service=embedding_service,
        vector_store=vector_store,
        relevance_threshold=2.0,
    )

    results = retrieval_service.search_by_domain(
        query=(
            "What is GROMACS used for in "
            "molecular simulation?"
        ),
        domain=DOMAIN,
        n_results=min(
            5,
            count_after,
        ),
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
            "No GROMACS retrieval results were returned."
        )

    assert all(
        result.get(
            "metadata",
            {},
        ).get("domain") == DOMAIN
        for result in results
    )

    assert any(
        result.get(
            "metadata",
            {},
        ).get("source")
        == "gromacs_manual.pdf"
        for result in results
    )

    print(
        "\nPASS: GROMACS PDF loading passed."
    )
    print(
        "PASS: GROMACS knowledge chunking passed."
    )
    print(
        "PASS: Isolated technical indexing passed."
    )
    print(
        "PASS: Domain-filtered GROMACS retrieval passed."
    )
    print(
        "PASS: Production technical_knowledge was not modified."
    )
    print(
        f"Temporary test data: {temporary_directory}"
    )


if __name__ == "__main__":
    main()


def test_main() -> None:
    main()
