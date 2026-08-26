from pathlib import Path

import pytest

from app.graphrag.graphrag_service import GraphRAGService
from app.graphrag.retrieval_router import RetrievalRouter
from app.knowledge_graph.graph_store import KnowledgeGraphStore


ALIASES = GraphRAGService._QUESTION_ENTITY_ALIASES


@pytest.mark.parametrize(
    "question",
    [
        "According to RDKit documentation, what function parses SMILES?",
        "What does GROMACS gmx rmsf calculate?",
        "What is the AutoDock Vina default exhaustiveness?",
        "An uncertain question with no recognized entity.",
    ],
)
def test_direct_or_uncertain_questions_use_vector(question: str) -> None:
    decision = RetrievalRouter(ALIASES).route(question)

    assert decision.selected_mode == "vector"


@pytest.mark.parametrize(
    "question",
    [
        "What steps connect a docking pose to molecular dynamics stability?",
        "How does FreeCAD become an OpenFOAM case and then a Blender animation?",
        "Does a low Vina docking score guarantee dynamic stability?",
    ],
)
def test_workflow_and_boundary_questions_use_graph(question: str) -> None:
    decision = RetrievalRouter(ALIASES).route(question)

    assert decision.selected_mode == "graph"
    assert decision.entity_nodes


@pytest.mark.parametrize("mode", ["vector", "graph"])
def test_explicit_override_is_respected(mode: str) -> None:
    decision = RetrievalRouter(ALIASES).route(
        "What does RDKit do?",
        requested_mode=mode,
    )

    assert decision.selected_mode == mode
    assert decision.confidence == 1.0
    assert decision.signals == ("explicit_override",)


def test_invalid_mode_is_rejected() -> None:
    with pytest.raises(ValueError, match="retrieval_mode"):
        RetrievalRouter(ALIASES).route("Question", requested_mode="invalid")


class CountingRetrieval:
    def __init__(self):
        self.calls = 0

    def search(self, **_):
        self.calls += 1
        return [
            {
                "text": "Retrieved evidence.",
                "metadata": {"source": "source.txt", "domain": "test"},
                "distance": 0.1,
            }
        ]


class RecordingGraph(KnowledgeGraphStore):
    def __init__(self, path: Path):
        super().__init__(str(path))
        self.traversal_calls = 0

    def traverse(self, *args, **kwargs):
        self.traversal_calls += 1
        return super().traverse(*args, **kwargs)


class FakeGenerator:
    def generate(self, question: str, context: str) -> str:
        return f"{question}: {context}"


def make_service(tmp_path: Path):
    retrieval = CountingRetrieval()
    graph = RecordingGraph(tmp_path / "graph.json")
    graph.add_node("rdkit", "tool", {"domain": "test"})
    graph.add_node("molecular_docking", "concept", {"domain": "test"})
    graph.add_node("molecular_dynamics", "concept", {"domain": "test"})
    graph.add_edge(
        "molecular_docking",
        "followed_by",
        "molecular_dynamics",
        {"domain": "test"},
    )
    return (
        GraphRAGService(
            retrieval_service=retrieval,
            graph_store=graph,
            generator=FakeGenerator(),
        ),
        retrieval,
        graph,
    )


def test_vector_route_retrieves_once_and_skips_graph(tmp_path: Path) -> None:
    service, retrieval, graph = make_service(tmp_path)

    result = service.answer(
        "According to RDKit documentation, what does RDKit do?",
        domain="test",
    )

    assert retrieval.calls == 1
    assert graph.traversal_calls == 0
    assert result["retrieval_mode_used"] == "vector"
    assert result["graph_seed_nodes"] == []
    assert result["graph_context"] == []


def test_graph_route_retrieves_once_and_audits_decision(tmp_path: Path) -> None:
    service, retrieval, graph = make_service(tmp_path)

    result = service.answer(
        "What steps connect molecular docking to molecular dynamics?",
        domain="test",
    )

    assert retrieval.calls == 1
    assert graph.traversal_calls > 0
    assert result["retrieval_mode_requested"] == "auto"
    assert result["retrieval_mode_used"] == "graph"
    assert "workflow_language" in result["routing_signals"]
    assert result["routing_confidence"] > 0
    assert result["graph_context"]


def test_forced_modes_override_automatic_decision(tmp_path: Path) -> None:
    service, _, graph = make_service(tmp_path)

    vector_result = service.answer(
        "What steps connect molecular docking to molecular dynamics?",
        domain="test",
        retrieval_mode="vector",
    )
    graph_result = service.answer(
        "According to RDKit documentation, what does RDKit do?",
        domain="test",
        retrieval_mode="graph",
    )

    assert vector_result["retrieval_mode_used"] == "vector"
    assert vector_result["graph_context"] == []
    assert graph_result["retrieval_mode_used"] == "graph"
    assert graph.traversal_calls > 0
