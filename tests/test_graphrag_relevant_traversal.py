import json
import tempfile

from pathlib import Path
from typing import Any

from app.graphrag.graphrag_service import (
    GraphRAGService,
)
from app.knowledge_graph.graph_builder import (
    KnowledgeGraphBuilder,
)
from app.knowledge_graph.graph_store import (
    KnowledgeGraphStore,
)


class FakeRetrievalService:
    def __init__(
        self,
        results: list[dict],
    ):
        self.results = results
        self.calls: list[
            dict[str, Any]
        ] = []

    def search(
        self,
        **kwargs,
    ) -> list[dict]:

        self.calls.append(
            kwargs
        )

        return self.results


class FakeGenerator:
    def __init__(self):
        self.calls: list[
            dict[str, str]
        ] = []

    def generate(
        self,
        question: str,
        context: str,
    ) -> str:

        self.calls.append(
            {
                "question":
                    question,

                "context":
                    context,
            }
        )

        return (
            "Grounded test answer."
        )


def edge_keys(
    edges: list[dict],
) -> set[tuple[str, str, str]]:

    return {
        (
            edge["source"],
            edge["relation"],
            edge["target"],
        )
        for edge in edges
    }


def main() -> None:

    temporary_root = Path(
        tempfile.mkdtemp(
            prefix=(
                "graphrag_relevant_"
                "traversal_test_"
            )
        )
    )

    graph_path = (
        temporary_root
        / "knowledge_graph.json"
    )

    print(
        "1. Creating isolated drug-discovery graph..."
    )

    graph = KnowledgeGraphStore(
        persist_path=str(
            graph_path
        )
    )

    builder = KnowledgeGraphBuilder(
        graph_store=graph
    )

    build_result = (
        builder
        .build_drug_discovery_workflow()
    )

    print(
        json.dumps(
            build_result,
            indent=2,
        )
    )

    assert graph.node_count() == 24
    assert graph.edge_count() == 24

    print(
        "\n2. Testing focused ADMET GraphRAG traversal..."
    )

    admet_retrieval = (
        FakeRetrievalService(
            results=[
                {
                    "text": (
                        "ADMET-AI uses Chemprop "
                        "models to predict ADMET "
                        "and toxicity endpoints."
                    ),
                    "metadata": {
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
                        "page":
                            1,
                        "chunk_index":
                            1,
                    },
                    "distance":
                        0.25,
                }
            ]
        )
    )

    admet_generator = (
        FakeGenerator()
    )

    admet_service = (
        GraphRAGService(
            retrieval_service=(
                admet_retrieval
            ),
            graph_store=graph,
            generator=(
                admet_generator
            ),
        )
    )

    admet_response = (
        admet_service.answer(
            question=(
                "How does ADMET-AI use "
                "Chemprop to predict DILI "
                "and hERG toxicity?"
            ),
            domain="drug_discovery",
            n_results=5,
            subdomain="admet",
            tool="admet_ai",
            version="2.0.1",
            visibility="private",
            document_type=(
                "official_documentation"
            ),
            graph_max_depth=3,
        )
    )

    print(
        json.dumps(
            {
                "seed_nodes":
                    admet_response[
                        "graph_seed_nodes"
                    ],

                "graph_context":
                    admet_response[
                        "graph_context"
                    ],

                "sources":
                    admet_response[
                        "sources"
                    ],
            },
            indent=2,
        )
    )

    admet_edges = edge_keys(
        admet_response[
            "graph_context"
        ]
    )

    required_admet_edges = {
        (
            "admet_ai",
            "uses",
            "chemprop",
        ),
        (
            "admet_ai",
            "predicts",
            "dili",
        ),
        (
            "admet_ai",
            "predicts",
            "herg",
        ),
        (
            "dili",
            "belongs_to",
            "toxicity",
        ),
        (
            "herg",
            "indicates",
            "cardiotoxicity_risk",
        ),
    }

    assert required_admet_edges.issubset(
        admet_edges
    )

    assert "admet_ai" in (
        admet_response[
            "graph_seed_nodes"
        ]
    )

    assert not any(
        (
            source
            in {
                "autodock_vina",
                "smina",
                "molecular_docking",
                "molecular_dynamics",
                "gromacs",
            }
            or target
            in {
                "autodock_vina",
                "smina",
                "molecular_docking",
                "molecular_dynamics",
                "gromacs",
            }
        )
        for source, relation, target
        in admet_edges
    )

    assert (
        admet_retrieval.calls[0][
            "tool"
        ]
        == "admet_ai"
    )

    assert (
        admet_retrieval.calls[0][
            "version"
        ]
        == "2.0.1"
    )

    assert len(
        admet_generator.calls
    ) == 1

    admet_context = (
        admet_generator.calls[0][
            "context"
        ]
    )

    assert (
        "ADMET-AI uses Chemprop"
        in admet_context
    )

    assert (
        "admet_ai predicts dili"
        in admet_context
    )

    print(
        "\n3. Testing docking-to-GROMACS GraphRAG traversal..."
    )

    docking_retrieval = (
        FakeRetrievalService(
            results=[
                {
                    "text": (
                        "Molecular docking "
                        "produces a docking pose."
                    ),
                    "metadata": {
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
                        "page":
                            10,
                        "chunk_index":
                            2,
                    },
                    "distance":
                        0.30,
                },
                {
                    "text": (
                        "GROMACS molecular dynamics "
                        "evaluates protein-ligand "
                        "complex stability."
                    ),
                    "metadata": {
                        "domain":
                            "drug_discovery",
                        "subdomain":
                            "molecular_dynamics",
                        "tool":
                            "gromacs",
                        "version":
                            "2025.0",
                        "visibility":
                            "public",
                        "document_type":
                            "official_documentation",
                        "source":
                            "gromacs_manual.pdf",
                        "page":
                            372,
                        "chunk_index":
                            1,
                    },
                    "distance":
                        0.35,
                },
            ]
        )
    )

    docking_generator = (
        FakeGenerator()
    )

    docking_service = (
        GraphRAGService(
            retrieval_service=(
                docking_retrieval
            ),
            graph_store=graph,
            generator=(
                docking_generator
            ),
        )
    )

    docking_response = (
        docking_service.answer(
            question=(
                "How does a docking pose "
                "progress into a protein-ligand "
                "complex and GROMACS molecular "
                "dynamics stability analysis?"
            ),
            domain="drug_discovery",
            n_results=5,
            graph_max_depth=3,
        )
    )

    print(
        json.dumps(
            {
                "seed_nodes":
                    docking_response[
                        "graph_seed_nodes"
                    ],

                "graph_context":
                    docking_response[
                        "graph_context"
                    ],

                "sources":
                    docking_response[
                        "sources"
                    ],
            },
            indent=2,
        )
    )

    docking_edges = edge_keys(
        docking_response[
            "graph_context"
        ]
    )

    required_structural_edges = {
        (
            "docking_pose",
            "forms",
            "protein_ligand_complex",
        ),
        (
            "protein_ligand_complex",
            "evaluated_by",
            "molecular_dynamics",
        ),
        (
            "molecular_dynamics",
            "performed_by",
            "gromacs",
        ),
        (
            "molecular_dynamics",
            "evaluates",
            "dynamic_stability",
        ),
        (
            "molecular_dynamics",
            "measures",
            "rmsd",
        ),
        (
            "molecular_dynamics",
            "measures",
            "rmsf",
        ),
        (
            "molecular_dynamics",
            "measures",
            "radius_of_gyration",
        ),
        (
            "molecular_dynamics",
            "measures",
            "hydrogen_bond_persistence",
        ),
    }

    assert (
        required_structural_edges
        .issubset(
            docking_edges
        )
    )

    assert "docking_pose" in (
        docking_response[
            "graph_seed_nodes"
        ]
    )

    assert "gromacs" in (
        docking_response[
            "graph_seed_nodes"
        ]
    )

    assert not any(
        (
            source
            in {
                "admet_ai",
                "dili",
                "herg",
            }
            or target
            in {
                "admet_ai",
                "dili",
                "herg",
            }
        )
        for source, relation, target
        in docking_edges
    )

    docking_context = (
        docking_generator.calls[0][
            "context"
        ]
    )

    assert (
        "docking_pose forms "
        "protein_ligand_complex"
        in docking_context
    )

    assert (
        "molecular_dynamics "
        "performed_by gromacs"
        in docking_context
    )

    print(
        "\n4. Verifying source tracking..."
    )

    assert len(
        docking_response[
            "sources"
        ]
    ) == 2

    source_names = {
        source["source"]
        for source in docking_response[
            "sources"
        ]
    }

    assert source_names == {
        "autodock_vina_documentation.pdf",
        "gromacs_manual.pdf",
    }

    print(
        "\nPASS: ADMET retrieval seeded only relevant graph traversal."
    )
    print(
        "PASS: Docking-to-GROMACS multi-hop GraphRAG traversal passed."
    )
    print(
        "PASS: Unrelated drug-discovery branches were excluded."
    )
    print(
        "PASS: Metadata filters were forwarded to retrieval."
    )
    print(
        "PASS: Retrieved text and graph relationships reached generation."
    )
    print(
        "PASS: Metadata-rich source tracking passed."
    )
    print(
        "PASS: No Ollama, Chroma, production graph, tools, jobs, or workers were used."
    )
    print(
        "Temporary test data:",
        temporary_root,
    )


if __name__ == "__main__":
    main()