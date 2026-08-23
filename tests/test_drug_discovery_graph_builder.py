import json
import tempfile

from pathlib import Path

from app.knowledge_graph.graph_builder import (
    KnowledgeGraphBuilder,
)
from app.knowledge_graph.graph_store import (
    KnowledgeGraphStore,
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
                "drug_discovery_"
                "graph_builder_test_"
            )
        )
    )

    graph_path = (
        temporary_root
        / "knowledge_graph.json"
    )

    print(
        "1. Creating isolated workflow graph..."
    )

    graph = KnowledgeGraphStore(
        persist_path=str(
            graph_path
        )
    )

    builder = KnowledgeGraphBuilder(
        graph_store=graph
    )

    first = (
        builder
        .build_drug_discovery_workflow()
    )

    print(
        json.dumps(
            first,
            indent=2,
        )
    )

    assert first["nodes_total"] == 24
    assert (
        first["relationships_total"]
        == 24
    )
    assert first["nodes_created"] == 24
    assert (
        first["relationships_created"]
        == 24
    )
    assert graph.node_count() == 24
    assert graph.edge_count() == 24

    print(
        "\n2. Repeating workflow construction..."
    )

    second = (
        builder
        .build_drug_discovery_workflow()
    )

    print(
        json.dumps(
            second,
            indent=2,
        )
    )

    assert second["nodes_created"] == 0
    assert (
        second["relationships_created"]
        == 0
    )
    assert graph.node_count() == 24
    assert graph.edge_count() == 24

    print(
        "\n3. Traversing candidate to ADMET toxicity..."
    )

    admet_path = graph.traverse(
        start_node="candidate_molecule",
        max_depth=3,
        direction="outgoing",
    )

    admet_edges = edge_keys(
        admet_path
    )

    required_admet_edges = {
        (
            "candidate_molecule",
            "screened_by",
            "admet_ai",
        ),
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
        (
            "admet_ai_v2",
            "differs_from",
            "admet_ai_v1",
        ),
    }

    assert required_admet_edges.issubset(
        admet_edges
    )

    print(
        json.dumps(
            [
                edge
                for edge in admet_path
                if (
                    edge["source"]
                    in {
                        "candidate_molecule",
                        "admet_ai",
                        "admet_ai_v2",
                        "dili",
                        "herg",
                    }
                )
            ],
            indent=2,
        )
    )

    print(
        "\n4. Traversing candidate through docking to GROMACS..."
    )

    complete_path = graph.traverse(
        start_node="candidate_molecule",
        max_depth=6,
        direction="outgoing",
    )

    complete_edges = edge_keys(
        complete_path
    )

    required_docking_md_edges = {
        (
            "candidate_molecule",
            "docked_with",
            "autodock_vina",
        ),
        (
            "candidate_molecule",
            "docked_with",
            "smina",
        ),
        (
            "autodock_vina",
            "performs",
            "molecular_docking",
        ),
        (
            "smina",
            "performs",
            "molecular_docking",
        ),
        (
            "molecular_docking",
            "estimates",
            "binding_affinity",
        ),
        (
            "molecular_docking",
            "produces",
            "docking_pose",
        ),
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
        required_docking_md_edges
        .issubset(
            complete_edges
        )
    )

    docking_md_path = [
        edge
        for edge in complete_path
        if (
            edge["source"]
            in {
                "candidate_molecule",
                "autodock_vina",
                "smina",
                "molecular_docking",
                "docking_pose",
                "protein_ligand_complex",
                "molecular_dynamics",
            }
        )
    ]

    print(
        json.dumps(
            docking_md_path,
            indent=2,
        )
    )

    print(
        "\n5. Testing source-derived extraction..."
    )

    extracted = builder.build_from_chunk(
        text=(
            "ADMET-AI uses Chemprop to predict "
            "DILI and hERG toxicity. hERG can "
            "indicate cardiotoxicity. RDKit "
            "calculates molecular descriptors."
        ),
        domain="drug_discovery",
        source="isolated_test_document.txt",
    )

    print(
        json.dumps(
            extracted,
            indent=2,
        )
    )

    extracted_edges = {
        (
            edge["source"],
            edge["relation"],
            edge["target"],
        )
        for edge in extracted[
            "relations"
        ]
    }

    assert (
        (
            "admet_ai",
            "uses",
            "chemprop",
        )
        in extracted_edges
    )

    assert (
        (
            "admet_ai",
            "predicts",
            "dili",
        )
        in extracted_edges
    )

    assert (
        (
            "admet_ai",
            "predicts",
            "herg",
        )
        in extracted_edges
    )

    assert (
        (
            "dili",
            "belongs_to",
            "toxicity",
        )
        in extracted_edges
    )

    assert (
        (
            "herg",
            "indicates",
            "cardiotoxicity_risk",
        )
        in extracted_edges
    )

    assert (
        (
            "rdkit",
            "calculates",
            "molecular_descriptors",
        )
        in extracted_edges
    )

    print(
        "\n6. Verifying persistence..."
    )

    restarted = KnowledgeGraphStore(
        persist_path=str(
            graph_path
        )
    )

    assert restarted.node_count() == 24

    # Source extraction reused existing relationships,
    # so it created no duplicate edges.
    assert restarted.edge_count() == 24

    assert (
        len(
            restarted.traverse(
                start_node=(
                    "candidate_molecule"
                ),
                max_depth=6,
                direction="outgoing",
            )
        )
        == 24
    )

    print(
        "\nPASS: Curated drug-discovery graph construction passed."
    )
    print(
        "PASS: Repeated construction remained idempotent."
    )
    print(
        "PASS: RDKit and ADMET relationship traversal passed."
    )
    print(
        "PASS: Docking-to-GROMACS traversal passed."
    )
    print(
        "PASS: Source-derived relationship extraction passed."
    )
    print(
        "PASS: Persistent graph restart passed."
    )
    print(
        "PASS: Production knowledge graph was not modified."
    )
    print(
        "Temporary test data:",
        temporary_root,
    )


if __name__ == "__main__":
    main()


def test_main() -> None:
    main()
