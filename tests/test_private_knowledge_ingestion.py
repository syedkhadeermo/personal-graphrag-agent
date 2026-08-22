import json
import tempfile

from pathlib import Path
from typing import Any

from app.embeddings.ollama_embeddings import (
    OllamaEmbeddingService,
)
from app.knowledge.knowledge_ingestion_service import (
    KnowledgeIngestionService,
)
from app.vectorstore.chroma_store import ChromaVectorStore


TEST_DOCUMENT = (
    Path("data")
    / "knowledge"
    / "private"
    / "cad_cfd"
    / "freecad"
    / "Python scripting tutorial - FreeCAD Documentation.pdf"
)

COLLECTION_NAME = "private_knowledge_test"


class CountingEmbeddingService:
    """
    Wrap the real Ollama embedding service and count calls.

    This proves that duplicate document ingestion performs
    no additional embedding work.
    """

    def __init__(self):
        self.delegate = (
            OllamaEmbeddingService()
        )

        self.batch_calls = 0
        self.texts_embedded = 0

    def embed_batch(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        self.batch_calls += 1
        self.texts_embedded += len(texts)

        return self.delegate.embed_batch(
            texts
        )

    def embed(
        self,
        text: str,
    ) -> list[float]:
        return self.delegate.embed(
            text
        )


def summarize_metadata(
    metadatas: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Produce a compact metadata summary for test output.
    """

    return {
        "record_count": len(metadatas),
        "sources": sorted(
            {
                metadata.get("source")
                for metadata in metadatas
            }
        ),
        "domains": sorted(
            {
                metadata.get("domain")
                for metadata in metadatas
            }
        ),
        "subdomains": sorted(
            {
                metadata.get("subdomain")
                for metadata in metadatas
            }
        ),
        "tools": sorted(
            {
                metadata.get("tool")
                for metadata in metadatas
            }
        ),
        "versions": sorted(
            {
                metadata.get("version")
                for metadata in metadatas
            }
        ),
        "visibilities": sorted(
            {
                metadata.get("visibility")
                for metadata in metadatas
            }
        ),
        "document_types": sorted(
            {
                metadata.get(
                    "document_type"
                )
                for metadata in metadatas
            }
        ),
        "document_sha256_values": sorted(
            {
                metadata.get(
                    "document_sha256"
                )
                for metadata in metadatas
            }
        ),
    }


def main() -> None:
    if not TEST_DOCUMENT.is_file():
        raise FileNotFoundError(
            "Private FreeCAD test document "
            f"not found: {TEST_DOCUMENT}"
        )

    temporary_directory = Path(
        tempfile.mkdtemp(
            prefix=(
                "private_knowledge_"
                "ingestion_test_"
            )
        )
    )

    chroma_directory = (
        temporary_directory
        / "chroma"
    )

    print(
        "1. Creating isolated private "
        "knowledge collection..."
    )

    vector_store = ChromaVectorStore(
        persist_directory=str(
            chroma_directory
        ),
        collection_name=COLLECTION_NAME,
    )

    embedding_service = (
        CountingEmbeddingService()
    )

    ingestion_service = (
        KnowledgeIngestionService(
            embedding_service=(
                embedding_service
            ),
            vector_store=vector_store,
            batch_size=32,
        )
    )

    count_before = vector_store.count()

    print(
        json.dumps(
            {
                "document": str(
                    TEST_DOCUMENT
                ),
                "size_bytes": (
                    TEST_DOCUMENT
                    .stat()
                    .st_size
                ),
                "collection": (
                    COLLECTION_NAME
                ),
                "count_before": count_before,
                "temporary_directory": str(
                    temporary_directory
                ),
            },
            indent=2,
        )
    )

    assert count_before == 0

    print(
        "\n2. Performing first private "
        "document ingestion..."
    )

    first_result = (
        ingestion_service.ingest_file(
            path=str(TEST_DOCUMENT),
            domain="cad_simulation",
            subdomain="freecad",
            tool="freecad",
            version="1.0",
            visibility="private",
            document_type=(
                "official_documentation"
            ),
        )
    )

    print(
        json.dumps(
            first_result,
            indent=2,
            default=str,
        )
    )

    count_after_first = (
        vector_store.count()
    )

    batch_calls_after_first = (
        embedding_service.batch_calls
    )

    texts_after_first = (
        embedding_service.texts_embedded
    )

    assert first_result["created"] is True
    assert first_result["duplicate"] is False
    assert first_result["resumed"] is False
    assert first_result["chunks_indexed"] > 0

    assert (
        count_after_first
        == first_result["chunks_total"]
    )

    assert batch_calls_after_first > 0

    assert (
        texts_after_first
        == first_result["chunks_total"]
    )

    print(
        "\n3. Repeating the same ingestion..."
    )

    second_result = (
        ingestion_service.ingest_file(
            path=str(TEST_DOCUMENT),
            domain="cad_simulation",
            subdomain="freecad",
            tool="freecad",
            version="1.0",
            visibility="private",
            document_type=(
                "official_documentation"
            ),
        )
    )

    print(
        json.dumps(
            second_result,
            indent=2,
            default=str,
        )
    )

    count_after_second = (
        vector_store.count()
    )

    assert second_result["created"] is False
    assert second_result["duplicate"] is True
    assert second_result["resumed"] is False
    assert second_result["chunks_indexed"] == 0

    assert (
        count_after_second
        == count_after_first
    )

    assert (
        embedding_service.batch_calls
        == batch_calls_after_first
    )

    assert (
        embedding_service.texts_embedded
        == texts_after_first
    )

    print(
        "\n4. Inspecting stored private metadata..."
    )

    document_sha256 = (
        first_result[
            "document_sha256"
        ]
    )

    stored = (
        vector_store
        .collection
        .get(
            where={
                "document_sha256": (
                    document_sha256
                ),
            },
            include=[
                "metadatas",
            ],
        )
    )

    metadatas = stored.get(
        "metadatas",
        [],
    )

    summary = summarize_metadata(
        metadatas
    )

    print(
        json.dumps(
            summary,
            indent=2,
            default=str,
        )
    )

    assert (
        len(metadatas)
        == count_after_first
    )

    assert summary["sources"] == [
        TEST_DOCUMENT.name
    ]

    assert summary["domains"] == [
        "cad_simulation"
    ]

    assert summary["subdomains"] == [
        "freecad"
    ]

    assert summary["tools"] == [
        "freecad"
    ]

    assert summary["versions"] == [
        "1.0"
    ]

    assert summary["visibilities"] == [
        "private"
    ]

    assert summary[
        "document_types"
    ] == [
        "official_documentation"
    ]

    assert summary[
        "document_sha256_values"
    ] == [
        document_sha256
    ]

    print(
        "\n5. Verifying production collection "
        "was not used..."
    )

    production_store = ChromaVectorStore(
        persist_directory=(
            "data/chroma"
        ),
        collection_name=(
            "technical_knowledge"
        ),
    )

    production_count = (
        production_store.count()
    )

    print(
        f"Production technical_knowledge "
        f"count: {production_count}"
    )

    assert production_count == 2674

    print(
        "\nPASS: Private PDF loading passed."
    )
    print(
        "PASS: SHA-256 document identity passed."
    )
    print(
        "PASS: First private ingestion passed."
    )
    print(
        "PASS: Duplicate ingestion was prevented."
    )
    print(
        "PASS: Duplicate ingestion performed "
        "no embeddings."
    )
    print(
        "PASS: Private metadata was preserved."
    )
    print(
        "PASS: Production technical_knowledge "
        "was not modified."
    )
    print(
        f"Temporary test data: "
        f"{temporary_directory}"
    )


if __name__ == "__main__":
    main()