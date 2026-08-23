import json
import tempfile

from pathlib import Path

from app.knowledge_graph.graph_store import (
    KnowledgeGraphStore,
)


def edge_summary(
    edges: list[dict],
) -> list[str]:

    return [
        (
            f"{edge['source']} "
            f"--{edge['relation']}--> "
            f"{edge['target']} "
            f"(depth={edge['depth']})"
        )
        for edge in edges
    ]


def main() -> None:

    temporary_root = Path(
        tempfile.mkdtemp(
            prefix="graph_traversal_test_"
        )
    )

    graph_path = (
        temporary_root
        / "knowledge_graph.json"
    )

    print(
        "1. Creating isolated scientific graph..."
    )

    graph = KnowledgeGraphStore(
        persist_path=str(
            graph_path
        )
    )

    nodes = {
        "candidate_molecule":
            "molecule",

        "autodock_vina":
            "software",

        "docking_pose":
            "artifact",

        "molecular_dynamics":
            "method",

        "gromacs":
            "software",

        "dynamic_stability":
            "scientific_concept",
    }

    for node_id, node_type in (
        nodes.items()
    ):
        graph.add_node(
            node_id=node_id,
            node_type=node_type,
            properties={
                "domain":
                    "drug_discovery",
            },
        )

    graph.add_edge(
        "candidate_molecule",
        "docked_with",
        "autodock_vina",
    )

    graph.add_edge(
        "autodock_vina",
        "produces",
        "docking_pose",
    )

    graph.add_edge(
        "docking_pose",
        "selected_for",
        "molecular_dynamics",
    )

    graph.add_edge(
        "molecular_dynamics",
        "performed_by",
        "gromacs",
    )

    graph.add_edge(
        "molecular_dynamics",
        "evaluates",
        "dynamic_stability",
    )

    # Duplicate edge must remain idempotent.
    graph.add_edge(
        "autodock_vina",
        "produces",
        "docking_pose",
    )

    print(
        json.dumps(
            {
                "node_count":
                    graph.node_count(),

                "edge_count":
                    graph.edge_count(),

                "path":
                    str(graph_path),
            },
            indent=2,
        )
    )

    assert graph.node_count() == 6
    assert graph.edge_count() == 5

    print(
        "\n2. Testing one-hop traversal..."
    )

    one_hop = graph.traverse(
        start_node="candidate_molecule",
        max_depth=1,
        direction="outgoing",
    )

    print(
        json.dumps(
            edge_summary(one_hop),
            indent=2,
        )
    )

    assert len(one_hop) == 1

    assert one_hop[0] == {
        "source":
            "candidate_molecule",

        "relation":
            "docked_with",

        "target":
            "autodock_vina",

        "properties":
            {},

        "depth":
            1,
    }

    print(
        "\n3. Testing complete outgoing traversal..."
    )

    complete_path = graph.traverse(
        start_node="candidate_molecule",
        max_depth=4,
        direction="outgoing",
    )

    print(
        json.dumps(
            edge_summary(
                complete_path
            ),
            indent=2,
        )
    )

    observed_edges = {
        (
            edge["source"],
            edge["relation"],
            edge["target"],
            edge["depth"],
        )
        for edge in complete_path
    }

    expected_edges = {
        (
            "candidate_molecule",
            "docked_with",
            "autodock_vina",
            1,
        ),
        (
            "autodock_vina",
            "produces",
            "docking_pose",
            2,
        ),
        (
            "docking_pose",
            "selected_for",
            "molecular_dynamics",
            3,
        ),
        (
            "molecular_dynamics",
            "performed_by",
            "gromacs",
            4,
        ),
        (
            "molecular_dynamics",
            "evaluates",
            "dynamic_stability",
            4,
        ),
    }

    assert observed_edges == (
        expected_edges
    )

    print(
        "\n4. Testing incoming traversal..."
    )

    incoming = graph.traverse(
        start_node="gromacs",
        max_depth=4,
        direction="incoming",
    )

    print(
        json.dumps(
            edge_summary(incoming),
            indent=2,
        )
    )

    incoming_keys = {
        (
            edge["source"],
            edge["relation"],
            edge["target"],
        )
        for edge in incoming
    }

    assert (
        (
            "molecular_dynamics",
            "performed_by",
            "gromacs",
        )
        in incoming_keys
    )

    assert (
        (
            "candidate_molecule",
            "docked_with",
            "autodock_vina",
        )
        in incoming_keys
    )

    print(
        "\n5. Testing relationship filtering..."
    )

    filtered = graph.traverse(
        start_node="molecular_dynamics",
        max_depth=1,
        direction="outgoing",
        relation="evaluates",
    )

    print(
        json.dumps(
            edge_summary(filtered),
            indent=2,
        )
    )

    assert len(filtered) == 1
    assert (
        filtered[0]["target"]
        == "dynamic_stability"
    )

    print(
        "\n6. Testing persistence across restart..."
    )

    restarted_graph = (
        KnowledgeGraphStore(
            persist_path=str(
                graph_path
            )
        )
    )

    assert (
        restarted_graph.node_count()
        == 6
    )

    assert (
        restarted_graph.edge_count()
        == 5
    )

    restarted_path = (
        restarted_graph.traverse(
            start_node=(
                "candidate_molecule"
            ),
            max_depth=4,
            direction="outgoing",
        )
    )

    assert len(restarted_path) == 5

    print(
        "\n7. Testing missing node and invalid inputs..."
    )

    assert (
        graph.traverse(
            start_node="missing_node",
        )
        == []
    )

    try:
        graph.traverse(
            start_node=(
                "candidate_molecule"
            ),
            max_depth=0,
        )

    except ValueError as exc:
        print(
            "Invalid depth rejected:",
            exc,
        )

    else:
        raise AssertionError(
            "Invalid depth was accepted."
        )

    try:
        graph.traverse(
            start_node=(
                "candidate_molecule"
            ),
            direction="sideways",
        )

    except ValueError as exc:
        print(
            "Invalid direction rejected:",
            exc,
        )

    else:
        raise AssertionError(
            "Invalid direction was accepted."
        )

    print(
        "\nPASS: One-hop graph traversal passed."
    )
    print(
        "PASS: Multi-hop docking-to-GROMACS traversal passed."
    )
    print(
        "PASS: Incoming and relation-filtered traversal passed."
    )
    print(
        "PASS: Duplicate relationships remained idempotent."
    )
    print(
        "PASS: Graph persistence across restart passed."
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
