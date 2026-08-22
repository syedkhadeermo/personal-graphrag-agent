import json
import tempfile

from pathlib import Path

from app.vectorstore.chroma_store import (
    ChromaVectorStore,
)


def flatten(
    result: dict,
    field: str,
) -> list:

    values = result.get(
        field,
        [],
    )

    if not values:
        return []

    return values[0]


def main() -> None:

    temporary_root = Path(
        tempfile.mkdtemp(
            prefix="chroma_metadata_filter_test_"
        )
    )

    print(
        "1. Creating isolated Chroma collection..."
    )

    store = ChromaVectorStore(
        persist_directory=str(
            temporary_root
        ),
        collection_name=(
            "metadata_filter_test"
        ),
    )

    store.add_documents(
        ids=[
            "admet-v2-readme",
            "admet-v1-paper",
            "vina-manual",
            "freecad-guide",
        ],
        documents=[
            (
                "ADMET-AI version 2 uses "
                "Chemprop version 2."
            ),
            (
                "The peer-reviewed ADMET-AI "
                "paper describes the version 1 model."
            ),
            (
                "AutoDock Vina performs "
                "molecular docking."
            ),
            (
                "FreeCAD Python scripting "
                "creates parametric geometry."
            ),
        ],
        embeddings=[
            [1.0, 0.0, 0.0],
            [0.95, 0.05, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        metadatas=[
            {
                "domain":
                    "drug_discovery",
                "subdomain":
                    "admet",
                "tool":
                    "admet_ai",
                "version":
                    "2.0.1",
                "visibility":
                    "private",
                "document_type":
                    "official_documentation",
                "source":
                    "admet_ai_v2_readme.txt",
            },
            {
                "domain":
                    "drug_discovery",
                "subdomain":
                    "admet",
                "tool":
                    "admet_ai",
                "version":
                    "2024-v1-paper",
                "visibility":
                    "private",
                "document_type":
                    "peer_reviewed_paper",
                "source":
                    "admet_ai_bioinformatics_2024.txt",
            },
            {
                "domain":
                    "drug_discovery",
                "subdomain":
                    "docking",
                "tool":
                    "autodock_vina",
                "version":
                    "1.2",
                "visibility":
                    "public",
                "document_type":
                    "official_documentation",
                "source":
                    "autodock_vina_documentation.pdf",
            },
            {
                "domain":
                    "cad_simulation",
                "subdomain":
                    "freecad",
                "tool":
                    "freecad",
                "version":
                    "1.0",
                "visibility":
                    "private",
                "document_type":
                    "official_documentation",
                "source":
                    "freecad_scripting.pdf",
            },
        ],
    )

    assert store.count() == 4

    print(
        "\n2. Filtering by one metadata field..."
    )

    tool_result = store.search(
        query_embedding=[
            1.0,
            0.0,
            0.0,
        ],
        n_results=4,
        where={
            "tool": "admet_ai",
        },
    )

    tool_metadatas = flatten(
        tool_result,
        "metadatas",
    )

    print(
        json.dumps(
            tool_metadatas,
            indent=2,
        )
    )

    assert len(tool_metadatas) == 2

    assert {
        metadata["tool"]
        for metadata in tool_metadatas
    } == {
        "admet_ai",
    }

    print(
        "\n3. Testing compound metadata filtering..."
    )

    compound_result = store.search(
        query_embedding=[
            1.0,
            0.0,
            0.0,
        ],
        n_results=4,
        where={
            "$and": [
                {
                    "domain": {
                        "$eq":
                            "drug_discovery"
                    }
                },
                {
                    "subdomain": {
                        "$eq":
                            "admet"
                    }
                },
                {
                    "tool": {
                        "$eq":
                            "admet_ai"
                    }
                },
                {
                    "version": {
                        "$eq":
                            "2.0.1"
                    }
                },
                {
                    "visibility": {
                        "$eq":
                            "private"
                    }
                },
                {
                    "document_type": {
                        "$eq":
                            "official_documentation"
                    }
                },
            ]
        },
    )

    compound_documents = flatten(
        compound_result,
        "documents",
    )

    compound_metadatas = flatten(
        compound_result,
        "metadatas",
    )

    print(
        json.dumps(
            {
                "documents":
                    compound_documents,

                "metadatas":
                    compound_metadatas,
            },
            indent=2,
        )
    )

    assert len(compound_documents) == 1

    assert (
        compound_metadatas[0]["source"]
        == "admet_ai_v2_readme.txt"
    )

    assert (
        compound_metadatas[0]["version"]
        == "2.0.1"
    )

    print(
        "\n4. Filtering the peer-reviewed paper..."
    )

    paper_result = store.search(
        query_embedding=[
            1.0,
            0.0,
            0.0,
        ],
        n_results=4,
        where={
            "$and": [
                {
                    "tool": {
                        "$eq":
                            "admet_ai"
                    }
                },
                {
                    "document_type": {
                        "$eq":
                            "peer_reviewed_paper"
                    }
                },
                {
                    "version": {
                        "$eq":
                            "2024-v1-paper"
                    }
                },
            ]
        },
    )

    paper_metadatas = flatten(
        paper_result,
        "metadatas",
    )

    print(
        json.dumps(
            paper_metadatas,
            indent=2,
        )
    )

    assert len(paper_metadatas) == 1

    assert (
        paper_metadatas[0]["source"]
        == (
            "admet_ai_"
            "bioinformatics_2024.txt"
        )
    )

    print(
        "\n5. Verifying unsupported combinations return no records..."
    )

    unavailable_result = store.search(
        query_embedding=[
            1.0,
            0.0,
            0.0,
        ],
        n_results=4,
        where={
            "$and": [
                {
                    "domain": {
                        "$eq":
                            "cad_simulation"
                    }
                },
                {
                    "tool": {
                        "$eq":
                            "admet_ai"
                    }
                },
            ]
        },
    )

    assert flatten(
        unavailable_result,
        "documents",
    ) == []

    print(
        "\nPASS: Single-field Chroma filtering passed."
    )
    print(
        "PASS: Compound metadata filtering passed."
    )
    print(
        "PASS: Version and document-type filtering passed."
    )
    print(
        "PASS: Unsupported metadata combinations returned no records."
    )
    print(
        "PASS: Production Chroma collections were not modified."
    )
    print(
        "Temporary test data:",
        temporary_root,
    )


if __name__ == "__main__":
    main()