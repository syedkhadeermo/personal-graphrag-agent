import json
import tempfile
from pathlib import Path

from app.knowledge_graph.graph_builder import (
    KnowledgeGraphBuilder,
)
from app.knowledge_graph.graph_store import (
    KnowledgeGraphStore,
)


def edge_keys(edges: list[dict]) -> set[tuple[str, str, str]]:
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
            prefix="multidomain_graph_test_",
        )
    )
    graph_path = temporary_root / "knowledge_graph.json"

    print("1. Creating isolated multi-domain graph...")
    store = KnowledgeGraphStore(
        persist_path=str(graph_path),
    )
    builder = KnowledgeGraphBuilder(
        graph_store=store,
    )

    first = builder.build_all_domain_workflows()
    print(json.dumps(first, indent=2))

    assert first["domains"] == [
        "drug_discovery",
        "cad_simulation",
        "cybersecurity",
    ]
    assert first["nodes_created"] == 57
    assert first["relationships_created"] == 57
    assert store.node_count() == 57
    assert store.edge_count() == 57

    print("\n2. Repeating combined construction...")
    second = builder.build_all_domain_workflows()
    print(json.dumps(second, indent=2))

    assert second["nodes_created"] == 0
    assert second["relationships_created"] == 0
    assert store.node_count() == 57
    assert store.edge_count() == 57

    print("\n3. Traversing FreeCAD to OpenFOAM and Blender...")
    cad_edges = store.traverse(
        start_node="engineering_workflow",
        max_depth=20,
        direction="outgoing",
    )
    print(json.dumps(cad_edges, indent=2))

    cad_keys = edge_keys(cad_edges)
    required_cad_edges = {
        (
            "engineering_workflow",
            "modeled_with",
            "freecad",
        ),
        (
            "freecad",
            "creates",
            "parametric_cad_model",
        ),
        (
            "openfoam_case",
            "simulated_by",
            "openfoam",
        ),
        (
            "fluid_flow_simulation",
            "produces",
            "simulation_results",
        ),
        (
            "simulation_results",
            "visualized_in",
            "visualization_scene",
        ),
        (
            "visualization_scene",
            "assembled_by",
            "blender",
        ),
        (
            "keyframe_animation",
            "rendered_as",
            "rendered_animation",
        ),
    }
    assert required_cad_edges <= cad_keys

    assert all(
        edge["properties"].get("domain")
        == "cad_simulation"
        for edge in cad_edges
    )

    print("\n4. Traversing authorized security assessment...")
    cyber_edges = store.traverse(
        start_node="authorized_security_assessment",
        max_depth=20,
        direction="outgoing",
    )
    print(json.dumps(cyber_edges, indent=2))

    cyber_keys = edge_keys(cyber_edges)
    required_cyber_edges = {
        (
            "authorized_security_assessment",
            "requires",
            "written_authorization",
        ),
        (
            "assessment_plan",
            "includes",
            "rules_of_engagement",
        ),
        (
            "target_systems",
            "assessed_by",
            "vulnerability_scan",
        ),
        (
            "potential_finding",
            "verified_by",
            "finding_validation",
        ),
        (
            "confirmed_vulnerability",
            "evaluated_by",
            "risk_analysis",
        ),
        (
            "remediation_recommendation",
            "documented_in",
            "assessment_report",
        ),
    }
    assert required_cyber_edges <= cyber_keys

    assert all(
        edge["properties"].get("domain")
        == "cybersecurity"
        and edge["properties"].get(
            "authorized_only"
        ) is True
        for edge in cyber_edges
    )

    print("\n5. Verifying persistence across restart...")
    restarted = KnowledgeGraphStore(
        persist_path=str(graph_path),
    )

    assert restarted.node_count() == 57
    assert restarted.edge_count() == 57
    assert edge_keys(
        restarted.traverse(
            start_node="engineering_workflow",
            max_depth=20,
            direction="outgoing",
        )
    ) == cad_keys
    assert edge_keys(
        restarted.traverse(
            start_node="authorized_security_assessment",
            max_depth=20,
            direction="outgoing",
        )
    ) == cyber_keys

    print(
        "\nPASS: All three curated domain workflows passed."
    )
    print(
        "PASS: Combined workflow construction remained idempotent."
    )
    print(
        "PASS: FreeCAD-to-OpenFOAM-to-Blender traversal passed."
    )
    print(
        "PASS: Authorization-bounded cybersecurity traversal passed."
    )
    print(
        "PASS: Multi-domain graph persistence passed."
    )
    print(
        "PASS: No scientific tool, scanner, job, SSH, or worker was used."
    )
    print(f"Temporary test data: {temporary_root}")


if __name__ == "__main__":
    main()


def test_main() -> None:
    main()
