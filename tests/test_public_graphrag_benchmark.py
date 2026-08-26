from pathlib import Path

from evaluation.public_graphrag.benchmark import (
    MainTextExtractor,
    claim_is_present,
    evidence_audit,
    load_json,
    score_answer,
)
from app.graphrag.graphrag_service import GraphRAGService
from app.knowledge_graph.graph_store import KnowledgeGraphStore


ROOT = Path("evaluation/public_graphrag")


def test_public_source_and_gold_manifests_are_independent() -> None:
    sources = load_json(ROOT / "sources.json")
    questions = load_json(ROOT / "gold_questions.json")
    source_ids = {source["source_id"] for source in sources}

    assert len(sources) >= 6
    assert len(questions) >= 6
    assert {question["category"] for question in questions} == {
        "direct",
        "cross_source",
        "boundary",
    }
    for question in questions:
        assert set(question["gold_source_ids"]).issubset(source_ids)
        assert question["claims"]


def test_claim_scoring_requires_every_term_group() -> None:
    claim = {
        "claim_id": "example",
        "term_groups": [["gmx rmsf"], ["fluctuation", "rmsf"]],
    }
    assert claim_is_present("gmx rmsf calculates atomic fluctuation.", claim)
    assert not claim_is_present("gmx rms calculates deviation.", claim)
    score = score_answer("gmx rmsf calculates RMSF.", [claim])
    assert score["claim_coverage"] == 1.0


def test_html_extractor_excludes_script_content() -> None:
    parser = MainTextExtractor()
    parser.feed(
        "<html><script>ignore me</script><main><h1>Title</h1>"
        "<p>Scientific documentation.</p></main></html>"
    )
    assert parser.text() == "Title\nScientific documentation."


def test_evidence_audit_preserves_identity_distance_and_text() -> None:
    chunks = [
        {
            "id": "chunk-1",
            "distance": 0.12,
            "text": "Exact evidence.",
            "metadata": {"source_id": "source-1"},
        }
    ]
    assert evidence_audit(chunks)[0] == {
        "chunk_id": "chunk-1",
        "distance": 0.12,
        "relevance_score": None,
        "source_id": "source-1",
        "metadata": {"source_id": "source-1"},
        "text": "Exact evidence.",
    }


def test_terminal_seed_steps_back_then_resumes_outward(tmp_path: Path) -> None:
    graph = KnowledgeGraphStore(str(tmp_path / "graph.json"))
    for node_id in ("analysis", "rmsd", "rmsf"):
        graph.add_node(node_id, "concept", {"domain": "drug_discovery"})
    graph.add_edge(
        "analysis", "measures", "rmsd", {"domain": "drug_discovery"}
    )
    graph.add_edge(
        "analysis", "measures", "rmsf", {"domain": "drug_discovery"}
    )

    service = GraphRAGService(graph_store=graph)
    context = service._collect_graph_context(
        seed_nodes=["rmsd"], domain="drug_discovery", max_depth=2
    )

    identities = {
        (edge["source"], edge["relation"], edge["target"]) for edge in context
    }
    assert ("analysis", "measures", "rmsd") in identities
    assert ("analysis", "measures", "rmsf") in identities


def test_nonterminal_seed_remains_outgoing_only(tmp_path: Path) -> None:
    graph = KnowledgeGraphStore(str(tmp_path / "graph.json"))
    for node_id in ("parent", "seed", "child"):
        graph.add_node(node_id, "concept", {"domain": "drug_discovery"})
    graph.add_edge("parent", "leads_to", "seed", {"domain": "drug_discovery"})
    graph.add_edge("seed", "leads_to", "child", {"domain": "drug_discovery"})

    service = GraphRAGService(graph_store=graph)
    context = service._collect_graph_context(
        seed_nodes=["seed"], domain="drug_discovery", max_depth=2
    )

    assert [(edge["source"], edge["target"]) for edge in context] == [
        ("seed", "child")
    ]


def test_seed_selection_ignores_entities_in_retrieved_prose(tmp_path: Path) -> None:
    graph = KnowledgeGraphStore(str(tmp_path / "graph.json"))
    for node_id in ("rdkit", "autodock_vina", "rmsd", "admet_ai_v2"):
        graph.add_node(node_id, "tool", {"domain": "drug_discovery"})

    service = GraphRAGService(graph_store=graph)
    seeds = service._identify_seed_nodes(
        question="Which RDKit function parses a SMILES string?",
        retrieved_chunks=[
            {
                "text": "A distractor mentions RMSD and ADMET-AI v2.",
                "metadata": {"source_id": "rdkit_getting_started"},
            },
            {
                "text": "Another distractor mentions AutoDock Vina.",
                "metadata": {},
            },
        ],
        domain="drug_discovery",
    )

    assert seeds == ["rdkit"]


def test_seed_selection_uses_trusted_source_metadata(tmp_path: Path) -> None:
    graph = KnowledgeGraphStore(str(tmp_path / "graph.json"))
    for node_id in ("gromacs", "rmsd", "rmsf"):
        graph.add_node(node_id, "tool", {"domain": "drug_discovery"})

    service = GraphRAGService(graph_store=graph)
    seeds = service._identify_seed_nodes(
        question="What analysis is documented?",
        retrieved_chunks=[
            {
                "text": "No entity names are required in retrieved prose.",
                "metadata": {"source_id": "gromacs_rmsf"},
            }
        ],
        domain="drug_discovery",
    )

    assert seeds == ["gromacs", "rmsf"]
