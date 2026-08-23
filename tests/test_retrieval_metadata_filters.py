import json
from typing import Any

from app.retrieval.retrieval_service import (
    RetrievalService,
)


class FakeEmbeddingService:
    def __init__(self):
        self.queries: list[str] = []

    def embed(
        self,
        text: str,
    ) -> list[float]:

        self.queries.append(text)

        return [
            1.0,
            0.0,
            0.0,
        ]


class FakeVectorStore:
    def __init__(self):
        self.calls: list[
            dict[str, Any]
        ] = []

    def search(
        self,
        **kwargs,
    ) -> dict:

        self.calls.append(kwargs)

        return {
            "documents": [
                [
                    "Relevant result",
                    "Rejected distant result",
                ]
            ],
            "metadatas": [
                [
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
                    },
                ]
            ],
            "distances": [
                [
                    0.25,
                    0.95,
                ]
            ],
        }


def main() -> None:

    embedding_service = (
        FakeEmbeddingService()
    )

    vector_store = FakeVectorStore()

    service = RetrievalService(
        embedding_service=embedding_service,
        vector_store=vector_store,
        relevance_threshold=0.85,
    )

    print(
        "1. Testing backward-compatible unfiltered search..."
    )

    results = service.search(
        query="ADMET prediction",
        n_results=5,
    )

    assert len(results) == 1
    assert (
        results[0]["text"]
        == "Relevant result"
    )
    assert (
        vector_store.calls[-1]
        == {
            "query_embedding": [
                1.0,
                0.0,
                0.0,
            ],
            "n_results": 5,
        }
    )

    print(
        json.dumps(
            results,
            indent=2,
        )
    )

    print(
        "\n2. Testing original domain filter..."
    )

    service.search_by_domain(
        query="molecular dynamics",
        domain="drug_discovery",
        n_results=3,
    )

    domain_call = (
        vector_store.calls[-1]
    )

    print(
        json.dumps(
            domain_call,
            indent=2,
        )
    )

    assert domain_call["where"] == {
        "domain": "drug_discovery",
    }

    print(
        "\n3. Testing domain-and-tool convenience filter..."
    )

    service.search_by_tool(
        query="How does ADMET-AI predict toxicity?",
        domain="drug_discovery",
        tool="admet_ai",
        n_results=4,
    )

    tool_call = (
        vector_store.calls[-1]
    )

    print(
        json.dumps(
            tool_call["where"],
            indent=2,
        )
    )

    assert tool_call["where"] == {
        "$and": [
            {
                "domain": {
                    "$eq":
                        "drug_discovery"
                }
            },
            {
                "tool": {
                    "$eq":
                        "admet_ai"
                }
            },
        ]
    }

    print(
        "\n4. Testing complete metadata filter..."
    )

    service.search(
        query="ADMET-AI version 2 usage",
        n_results=2,
        domain=" drug_discovery ",
        subdomain=" admet ",
        tool=" admet_ai ",
        version=" 2.0.1 ",
        visibility=" private ",
        document_type=(
            " official_documentation "
        ),
        source=(
            " admet_ai_v2_readme.txt "
        ),
    )

    complete_call = (
        vector_store.calls[-1]
    )

    print(
        json.dumps(
            complete_call["where"],
            indent=2,
        )
    )

    expected_values = {
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
    }

    conditions = (
        complete_call["where"]["$and"]
    )

    assert len(conditions) == 7

    observed_values = {
        field: expression["$eq"]
        for condition in conditions
        for field, expression
        in condition.items()
    }

    assert (
        observed_values
        == expected_values
    )

    print(
        "\n5. Testing invalid inputs..."
    )

    try:
        service.search(
            query="test",
            n_results=0,
        )

    except ValueError as exc:
        print(
            "Invalid n_results rejected:",
            exc,
        )

    else:
        raise AssertionError(
            "Invalid n_results was accepted."
        )

    try:
        service.search(
            query="test",
            tool="   ",
        )

    except ValueError as exc:
        print(
            "Empty tool rejected:",
            exc,
        )

    else:
        raise AssertionError(
            "Empty tool was accepted."
        )

    try:
        service.search(
            query="test",
            version=2,
        )

    except TypeError as exc:
        print(
            "Invalid version type rejected:",
            exc,
        )

    else:
        raise AssertionError(
            "Invalid version type was accepted."
        )

    assert embedding_service.queries == [
        "ADMET prediction",
        "molecular dynamics",
        (
            "How does ADMET-AI "
            "predict toxicity?"
        ),
        "ADMET-AI version 2 usage",
    ]

    print(
        "\nPASS: Existing unfiltered retrieval remained compatible."
    )
    print(
        "PASS: Existing domain retrieval remained compatible."
    )
    print(
        "PASS: Tool-filtered retrieval passed."
    )
    print(
        "PASS: Compound metadata construction passed."
    )
    print(
        "PASS: Relevance filtering and validation passed."
    )
    print(
        "PASS: No Ollama, Chroma, network, or production data was used."
    )


if __name__ == "__main__":
    main()


def test_main() -> None:
    main()
