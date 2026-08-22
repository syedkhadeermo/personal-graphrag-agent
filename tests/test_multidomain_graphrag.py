import json
import tempfile
from pathlib import Path
from typing import Any

from app.graphrag.graphrag_service import GraphRAGService
from app.knowledge_graph.graph_builder import KnowledgeGraphBuilder
from app.knowledge_graph.graph_store import KnowledgeGraphStore


class FakeRetrievalService:
    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    def search(self, **kwargs) -> list[dict]:
        self.calls.append(dict(kwargs))

        domain = kwargs.get("domain")
        tool = kwargs.get("tool")

        if domain == "cad_simulation" and tool == "blender":
            return [
                {
                    "text": (
                        "Blender supports Python scripting, camera and "
                        "lighting setup, keyframe animation, background "
                        "execution, and rendered animation output."
                    ),
                    "metadata": {
                        "source": "python_api_quickstart.txt",
                        "domain": "cad_simulation",
                        "subdomain": "rendering_animation",
                        "tool": "blender",
                        "version": "5.0.1",
                        "visibility": "private",
                        "document_type": "official_documentation",
                        "page": 1,
                        "chunk_index": 1,
                    },
                    "distance": 0.42,
                }
            ]

        if domain == "cad_simulation":
            return [
                {
                    "text": (
                        "A FreeCAD model can provide geometry for an "
                        "OpenFOAM case. The case contains a computational "
                        "mesh and boundary conditions. Simulation results "
                        "can be presented as a Blender animation."
                    ),
                    "metadata": {
                        "source": "Openfoam_UserGuide.pdf",
                        "domain": "cad_simulation",
                        "subdomain": "computational_fluid_dynamics",
                        "tool": "openfoam",
                        "version": "v2606",
                        "visibility": "private",
                        "document_type": "official_documentation",
                        "page": 15,
                        "chunk_index": 2,
                    },
                    "distance": 0.43,
                }
            ]

        if domain == "cybersecurity":
            return [
                {
                    "text": (
                        "An authorized security assessment requires an "
                        "assessment plan, defined scope, rules of "
                        "engagement, safe execution, finding validation, "
                        "risk analysis, and remediation reporting."
                    ),
                    "metadata": {
                        "source": "nist_sp_800_115.pdf",
                        "domain": "cybersecurity",
                        "subdomain": "security_assessment",
                        "tool": "vulnerability_scan",
                        "version": "2008",
                        "visibility": "private",
                        "document_type": "security_standard",
                        "page": 13,
                        "chunk_index": 1,
                    },
                    "distance": 0.41,
                }
            ]

        return []


class FakeGenerator:
    def __init__(self):
        self.calls: list[dict[str, str]] = []

    def generate(self, question: str, context: str) -> str:
        self.calls.append(
            {
                "question": question,
                "context": context,
            }
        )
        return "Grounded multi-domain test answer."


def edge_keys(result: dict) -> set[tuple[str, str, str]]:
    return {
        (
            edge["source"],
            edge["relation"],
            edge["target"],
        )
        for edge in result["graph_context"]
    }


def assert_only_domain(result: dict, domain: str) -> None:
    assert result["graph_context"]
    assert all(
        edge.get("properties", {}).get("domain") == domain
        for edge in result["graph_context"]
    )


def main() -> None:
    temporary_root = Path(
        tempfile.mkdtemp(
            prefix="multidomain_graphrag_test_",
        )
    )
    graph_path = temporary_root / "knowledge_graph.json"

    print("1. Creating isolated multi-domain GraphRAG graph...")
    graph = KnowledgeGraphStore(
        persist_path=str(graph_path),
    )
    build_result = KnowledgeGraphBuilder(
        graph_store=graph,
    ).build_all_domain_workflows()
    print(json.dumps(build_result, indent=2))

    assert graph.node_count() == 57
    assert graph.edge_count() == 57

    retrieval = FakeRetrievalService()
    generator = FakeGenerator()
    service = GraphRAGService(
        retrieval_service=retrieval,
        graph_store=graph,
        generator=generator,
    )

    print("\n2. Testing FreeCAD-to-OpenFOAM-to-Blender GraphRAG...")
    cad_result = service.answer(
        question=(
            "How does a FreeCAD model become an OpenFOAM case "
            "with a mesh and boundary conditions, and how are "
            "the simulation results turned into a Blender animation?"
        ),
        domain="cad_simulation",
        n_results=5,
        visibility="private",
        graph_max_depth=20,
    )
    print(
        json.dumps(
            {
                "seed_nodes": cad_result["graph_seed_nodes"],
                "graph_context": cad_result["graph_context"],
                "sources": cad_result["sources"],
            },
            indent=2,
        )
    )

    assert_only_domain(cad_result, "cad_simulation")
    cad_edges = edge_keys(cad_result)
    assert (
        "freecad",
        "creates",
        "parametric_cad_model",
    ) in cad_edges
    assert (
        "openfoam_case",
        "simulated_by",
        "openfoam",
    ) in cad_edges
    assert (
        "simulation_results",
        "visualized_in",
        "visualization_scene",
    ) in cad_edges
    assert (
        "keyframe_animation",
        "rendered_as",
        "rendered_animation",
    ) in cad_edges

    print("\n3. Testing focused Blender GraphRAG...")
    blender_result = service.answer(
        question=(
            "How can Blender configure a visualization scene, "
            "camera setup, lighting setup and keyframe animation "
            "for headless rendering?"
        ),
        domain="cad_simulation",
        subdomain="rendering_animation",
        tool="blender",
        version="5.0.1",
        visibility="private",
        n_results=5,
        graph_max_depth=4,
    )
    print(
        json.dumps(
            {
                "seed_nodes": blender_result["graph_seed_nodes"],
                "graph_context": blender_result["graph_context"],
                "sources": blender_result["sources"],
            },
            indent=2,
        )
    )

    assert_only_domain(blender_result, "cad_simulation")
    blender_edges = edge_keys(blender_result)
    assert (
        "visualization_scene",
        "configured_with",
        "camera",
    ) in blender_edges
    assert (
        "visualization_scene",
        "configured_with",
        "lighting",
    ) in blender_edges
    assert (
        "visualization_scene",
        "animated_with",
        "keyframe_animation",
    ) in blender_edges

    print("\n4. Testing authorization-bounded cybersecurity GraphRAG...")
    cyber_result = service.answer(
        question=(
            "How should an authorized security assessment use "
            "an assessment plan and rules of engagement for "
            "vulnerability scanning, validate findings, analyze "
            "risk, and report remediation recommendations?"
        ),
        domain="cybersecurity",
        subdomain="security_assessment",
        tool="vulnerability_scan",
        version="2008",
        visibility="private",
        document_type="security_standard",
        n_results=5,
        graph_max_depth=20,
    )
    print(
        json.dumps(
            {
                "seed_nodes": cyber_result["graph_seed_nodes"],
                "graph_context": cyber_result["graph_context"],
                "sources": cyber_result["sources"],
            },
            indent=2,
        )
    )

    assert_only_domain(cyber_result, "cybersecurity")
    assert all(
        edge.get("properties", {}).get("authorized_only") is True
        for edge in cyber_result["graph_context"]
    )
    cyber_edges = edge_keys(cyber_result)
    assert (
        "authorized_security_assessment",
        "requires",
        "written_authorization",
    ) in cyber_edges
    assert (
        "assessment_plan",
        "includes",
        "rules_of_engagement",
    ) in cyber_edges
    assert (
        "potential_finding",
        "verified_by",
        "finding_validation",
    ) in cyber_edges
    assert (
        "risk_analysis",
        "informs",
        "remediation_recommendation",
    ) in cyber_edges

    print("\n5. Verifying retrieval filters and generation context...")
    assert retrieval.calls[0]["domain"] == "cad_simulation"
    assert retrieval.calls[0]["visibility"] == "private"
    assert retrieval.calls[1]["tool"] == "blender"
    assert retrieval.calls[1]["version"] == "5.0.1"
    assert retrieval.calls[2]["domain"] == "cybersecurity"
    assert retrieval.calls[2]["document_type"] == "security_standard"

    assert len(generator.calls) == 3
    assert "Knowledge graph relationships:" in generator.calls[0]["context"]
    assert "FreeCAD model" in generator.calls[0]["context"]
    assert "Blender supports Python scripting" in generator.calls[1]["context"]
    assert "authorized security assessment" in generator.calls[2]["context"]

    assert cad_result["sources"][0]["source"] == "Openfoam_UserGuide.pdf"
    assert blender_result["sources"][0]["source"] == "python_api_quickstart.txt"
    assert cyber_result["sources"][0]["source"] == "nist_sp_800_115.pdf"

    print("\nPASS: CAD multi-hop GraphRAG traversal passed.")
    print("PASS: Focused Blender GraphRAG traversal passed.")
    print("PASS: Authorization-bounded cybersecurity GraphRAG passed.")
    print("PASS: Cross-domain graph relationships were excluded.")
    print("PASS: Retrieval filters reached the retrieval service.")
    print("PASS: Retrieved evidence and graph context reached generation.")
    print("PASS: No Ollama, Chroma, production graph, tools, jobs, SSH, or workers were used.")
    print(f"Temporary test data: {temporary_root}")


if __name__ == "__main__":
    main()
