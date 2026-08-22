import json

from pathlib import Path
from typing import Any

from app.embeddings.ollama_embeddings import (
    OllamaEmbeddingService,
)
from app.knowledge.knowledge_ingestion_service import (
    KnowledgeIngestionService,
)
from app.retrieval.retrieval_service import RetrievalService
from app.vectorstore.chroma_store import ChromaVectorStore


CHROMA_DIRECTORY = "data/chroma"
COLLECTION_NAME = "technical_knowledge"


def resolve_one(
    pattern: str,
) -> Path:
    """
    Resolve a filename pattern that must match exactly one file.

    This safely handles Unicode filename differences such as
    an em dash versus a normal hyphen.
    """

    matches = list(
        Path(".").glob(pattern)
    )

    file_matches = [
        path
        for path in matches
        if path.is_file()
    ]

    if not file_matches:
        raise FileNotFoundError(
            f"No document matched: {pattern}"
        )

    if len(file_matches) > 1:
        raise RuntimeError(
            "Document pattern matched more than "
            f"one file: {pattern}; "
            f"matches={file_matches}"
        )

    return file_matches[0]


def build_manifest() -> list[dict[str, Any]]:
    """
    Build the first controlled private multi-domain manifest.
    """

    return [
        {
            "path": resolve_one(
                "data/knowledge/private/"
                "drug_discovery/cheminformatics/"
                "RDKit Cookbook*.pdf"
            ),
            "domain": "drug_discovery",
            "subdomain": "cheminformatics",
            "tool": "rdkit",
            "version": "2026.03.5",
            "visibility": "private",
            "document_type": (
                "official_documentation"
            ),
            "retrieval_query": (
                "How does RDKit parse SMILES and "
                "calculate molecular descriptors?"
            ),
        },
        {
            "path": resolve_one(
                "data/knowledge/private/"
                "cad_cfd/freecad/"
                "Python scripting tutorial*.pdf"
            ),
            "domain": "cad_simulation",
            "subdomain": "freecad",
            "tool": "freecad",
            "version": "1.0",
            "visibility": "private",
            "document_type": (
                "official_documentation"
            ),
            "retrieval_query": (
                "How can Python create documents "
                "and geometric objects in FreeCAD?"
            ),
        },
        {
            "path": resolve_one(
                "data/knowledge/private/"
                "cybersecurity/"
                "nist_sp_800_115.pdf"
            ),
            "domain": "cybersecurity",
            "subdomain": (
                "security_assessment"
            ),
            "tool": "vulnerability_scan",
            "version": "2008",
            "visibility": "private",
            "document_type": "security_standard",
            "retrieval_query": (
                "How should an authorized technical "
                "security assessment be planned and "
                "conducted?"
            ),
        },
    ]


def format_retrieval_results(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
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


def verify_document_metadata(
    vector_store: ChromaVectorStore,
    item: dict[str, Any],
    ingestion_result: dict[str, Any],
) -> None:
    """
    Verify that every stored chunk has the expected metadata.
    """

    document_sha256 = (
        ingestion_result[
            "document_sha256"
        ]
    )

    records = (
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

    ids = records.get(
        "ids",
        [],
    )

    metadatas = records.get(
        "metadatas",
        [],
    )

    if len(ids) != ingestion_result[
        "chunks_total"
    ]:
        raise RuntimeError(
            "Stored chunk count does not match "
            f"prepared chunk count for "
            f"{item['path'].name}."
        )

    for metadata in metadatas:
        expected = {
            "source": item["path"].name,
            "domain": item["domain"],
            "subdomain": (
                item["subdomain"]
            ),
            "tool": item["tool"],
            "version": item["version"],
            "visibility": (
                item["visibility"]
            ),
            "document_type": (
                item["document_type"]
            ),
            "document_sha256": (
                document_sha256
            ),
        }

        for key, expected_value in (
            expected.items()
        ):
            actual_value = (
                metadata.get(key)
            )

            if actual_value != expected_value:
                raise RuntimeError(
                    "Metadata verification failed: "
                    f"source={item['path'].name}; "
                    f"key={key}; "
                    f"expected={expected_value}; "
                    f"actual={actual_value}"
                )


def main() -> None:
    print(
        "1. Building controlled private "
        "knowledge manifest..."
    )

    manifest = build_manifest()

    print(
        json.dumps(
            [
                {
                    "path": str(item["path"]),
                    "size_bytes": (
                        item["path"]
                        .stat()
                        .st_size
                    ),
                    "domain": item["domain"],
                    "subdomain": (
                        item["subdomain"]
                    ),
                    "tool": item["tool"],
                    "version": item["version"],
                    "visibility": (
                        item["visibility"]
                    ),
                }
                for item in manifest
            ],
            indent=2,
        )
    )

    print(
        "\n2. Connecting to production "
        "technical_knowledge..."
    )

    vector_store = ChromaVectorStore(
        persist_directory=(
            CHROMA_DIRECTORY
        ),
        collection_name=(
            COLLECTION_NAME
        ),
    )

    embedding_service = (
        OllamaEmbeddingService()
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
        f"Production count before ingestion: "
        f"{count_before}"
    )

    if count_before < 2674:
        raise RuntimeError(
            "Production technical_knowledge "
            "contains fewer records than expected."
        )

    print(
        "\n3. Ingesting one private document "
        "from each domain..."
    )

    ingestion_results = []
    total_chunks_indexed = 0

    for index, item in enumerate(
        manifest,
        start=1,
    ):
        print(
            f"\nDocument {index}/"
            f"{len(manifest)}: "
            f"{item['path'].name}"
        )

        result = (
            ingestion_service.ingest_file(
                path=str(item["path"]),
                domain=item["domain"],
                subdomain=(
                    item["subdomain"]
                ),
                tool=item["tool"],
                version=item["version"],
                visibility=(
                    item["visibility"]
                ),
                document_type=(
                    item["document_type"]
                ),
            )
        )

        print(
            json.dumps(
                result,
                indent=2,
                default=str,
            )
        )

        verify_document_metadata(
            vector_store=vector_store,
            item=item,
            ingestion_result=result,
        )

        ingestion_results.append(
            result
        )

        total_chunks_indexed += (
            result["chunks_indexed"]
        )

    print(
        "\n4. Verifying collection count..."
    )

    count_after = vector_store.count()

    expected_count_after = (
        count_before
        + total_chunks_indexed
    )

    print(
        json.dumps(
            {
                "count_before": count_before,
                "chunks_indexed": (
                    total_chunks_indexed
                ),
                "expected_count_after": (
                    expected_count_after
                ),
                "count_after": count_after,
            },
            indent=2,
        )
    )

    if count_after != expected_count_after:
        raise RuntimeError(
            "Production collection count "
            "verification failed."
        )

    print(
        "\n5. Running domain-isolated retrieval..."
    )

    retrieval_service = RetrievalService(
        embedding_service=embedding_service,
        vector_store=vector_store,
        relevance_threshold=0.85,
    )

    retrieval_summary = []

    for item in manifest:
        results = (
            retrieval_service
            .search_by_domain(
                query=(
                    item[
                        "retrieval_query"
                    ]
                ),
                domain=item["domain"],
                n_results=5,
            )
        )

        print(
            f"\nDomain: {item['domain']}"
        )

        print(
            json.dumps(
                format_retrieval_results(
                    results
                ),
                indent=2,
                default=str,
            )
        )

        expected_source_found = any(
            result.get(
                "metadata",
                {},
            ).get("source")
            == item["path"].name
            for result in results
        )

        if not expected_source_found:
            raise RuntimeError(
                "Expected private source was not "
                "retrieved for domain "
                f"{item['domain']}: "
                f"{item['path'].name}"
            )

        if not all(
            result.get(
                "metadata",
                {},
            ).get("domain")
            == item["domain"]
            for result in results
        ):
            raise RuntimeError(
                "Cross-domain retrieval leakage "
                f"detected for "
                f"{item['domain']}."
            )

        retrieval_summary.append(
            {
                "domain": item["domain"],
                "expected_source": (
                    item["path"].name
                ),
                "result_count": len(
                    results
                ),
                "expected_source_found": (
                    expected_source_found
                ),
            }
        )

    print(
        "\n6. Final production summary..."
    )

    print(
        json.dumps(
            {
                "collection": COLLECTION_NAME,
                "count_before": count_before,
                "count_after": count_after,
                "documents": (
                    ingestion_results
                ),
                "retrieval": (
                    retrieval_summary
                ),
            },
            indent=2,
            default=str,
        )
    )

    print(
        "\nPASS: Private RDKit knowledge "
        "was registered."
    )
    print(
        "PASS: Private FreeCAD knowledge "
        "was registered."
    )
    print(
        "PASS: Private cybersecurity knowledge "
        "was registered."
    )
    print(
        "PASS: SHA-256 document identity passed."
    )
    print(
        "PASS: Production metadata passed."
    )
    print(
        "PASS: Domain-isolated retrieval passed."
    )


if __name__ == "__main__":
    main()