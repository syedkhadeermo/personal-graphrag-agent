import json

from app.retrieval.retrieval_service import (
    RetrievalService,
)
from app.vectorstore.chroma_store import (
    ChromaVectorStore,
)


def summarize(
    results: list[dict],
) -> list[dict]:

    return [
        {
            "text_preview":
                result["text"][:500],

            "metadata":
                result["metadata"],

            "distance":
                result["distance"],
        }
        for result in results
    ]


def main() -> None:

    print(
        "1. Connecting to production technical knowledge..."
    )

    vector_store = ChromaVectorStore(
        persist_directory="data/chroma",
        collection_name=(
            "technical_knowledge"
        ),
    )

    count_before = (
        vector_store.count()
    )

    print(
        "Production count:",
        count_before,
    )

    assert count_before == 3082

    retrieval = RetrievalService(
        vector_store=vector_store,
        relevance_threshold=0.85,
    )

    print(
        "\n2. Retrieving current ADMET-AI v2 documentation..."
    )

    v2_results = retrieval.search(
        query=(
            "How can ADMET-AI version 2 make "
            "predictions using its Python API?"
        ),
        n_results=5,
        domain="drug_discovery",
        subdomain="admet",
        tool="admet_ai",
        version="2.0.1",
        visibility="private",
        document_type=(
            "official_documentation"
        ),
        source=(
            "admet_ai_v2_readme.txt"
        ),
    )

    print(
        json.dumps(
            summarize(v2_results),
            indent=2,
        )
    )

    assert v2_results

    for result in v2_results:

        metadata = result["metadata"]

        assert (
            metadata["domain"]
            == "drug_discovery"
        )
        assert (
            metadata["subdomain"]
            == "admet"
        )
        assert (
            metadata["tool"]
            == "admet_ai"
        )
        assert (
            metadata["version"]
            == "2.0.1"
        )
        assert (
            metadata["visibility"]
            == "private"
        )
        assert (
            metadata["document_type"]
            == "official_documentation"
        )
        assert (
            metadata["source"]
            == "admet_ai_v2_readme.txt"
        )

    print(
        "\n3. Retrieving the peer-reviewed v1 paper..."
    )

    paper_results = retrieval.search(
        query=(
            "How were ADMET-AI models trained, "
            "and how should binary classification "
            "predictions be interpreted?"
        ),
        n_results=5,
        domain="drug_discovery",
        subdomain="admet",
        tool="admet_ai",
        version="2024-v1-paper",
        visibility="private",
        document_type=(
            "peer_reviewed_paper"
        ),
        source=(
            "admet_ai_bioinformatics_2024.txt"
        ),
    )

    print(
        json.dumps(
            summarize(paper_results),
            indent=2,
        )
    )

    assert paper_results

    for result in paper_results:

        metadata = result["metadata"]

        assert (
            metadata["domain"]
            == "drug_discovery"
        )
        assert (
            metadata["subdomain"]
            == "admet"
        )
        assert (
            metadata["tool"]
            == "admet_ai"
        )
        assert (
            metadata["version"]
            == "2024-v1-paper"
        )
        assert (
            metadata["visibility"]
            == "private"
        )
        assert (
            metadata["document_type"]
            == "peer_reviewed_paper"
        )
        assert (
            metadata["source"]
            == (
                "admet_ai_"
                "bioinformatics_2024.txt"
            )
        )

    print(
        "\n4. Verifying version isolation..."
    )

    v2_sources = {
        result["metadata"]["source"]
        for result in v2_results
    }

    paper_sources = {
        result["metadata"]["source"]
        for result in paper_results
    }

    assert v2_sources == {
        "admet_ai_v2_readme.txt",
    }

    assert paper_sources == {
        (
            "admet_ai_"
            "bioinformatics_2024.txt"
        ),
    }

    assert v2_sources.isdisjoint(
        paper_sources
    )

    print(
        "\n5. Verifying retrieval was read-only..."
    )

    count_after = (
        vector_store.count()
    )

    print(
        json.dumps(
            {
                "count_before":
                    count_before,

                "count_after":
                    count_after,

                "v2_results":
                    len(v2_results),

                "paper_results":
                    len(paper_results),
            },
            indent=2,
        )
    )

    assert count_after == count_before

    print(
        "\nPASS: Production ADMET-AI v2 retrieval passed."
    )
    print(
        "PASS: Peer-reviewed ADMET-AI paper retrieval passed."
    )
    print(
        "PASS: Tool, version, visibility, type, and source isolation passed."
    )
    print(
        "PASS: Current documentation and earlier paper remained distinguishable."
    )
    print(
        "PASS: Production Chroma count remained unchanged."
    )


if __name__ == "__main__":
    main()