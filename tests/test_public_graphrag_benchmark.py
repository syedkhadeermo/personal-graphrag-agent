from pathlib import Path

from evaluation.public_graphrag.benchmark import (
    MainTextExtractor,
    checkpoint_signature,
    claim_is_present,
    evidence_audit,
    load_checkpoint,
    load_json,
    routing_summary,
    run_router_benchmark,
    run_to_run_dispersion,
    score_answer,
    summarize_metrics,
    write_json_atomic,
)
from app.graphrag.graphrag_service import GraphRAGService
from app.knowledge_graph.graph_store import KnowledgeGraphStore


ROOT = Path("evaluation/public_graphrag")


def test_public_source_and_gold_manifests_are_independent() -> None:
    sources = load_json(ROOT / "sources.json")
    questions = load_json(ROOT / "gold_questions.json")
    source_ids = {source["source_id"] for source in sources}

    assert len(sources) >= 6
    assert 30 <= len(questions) <= 50
    assert {question["category"] for question in questions} == {
        "direct",
        "cross_source",
        "boundary",
    }
    for question in questions:
        assert set(question["gold_source_ids"]).issubset(source_ids)
        assert question["claims"]
        assert question["expected_retrieval_mode"] in {"vector", "graph"}


def test_metric_summary_reports_population_standard_deviation() -> None:
    records = [
        {
            "claim_coverage": 0.0,
            "claim_group_coverage": 0.25,
            "prompt_tokens": 10,
            "answer_tokens": 2,
            "generation_latency_ms": 100,
        },
        {
            "claim_coverage": 1.0,
            "claim_group_coverage": 0.75,
            "prompt_tokens": 20,
            "answer_tokens": 4,
            "generation_latency_ms": 300,
        },
    ]

    summary = summarize_metrics(records)

    assert summary["claim_coverage"] == 0.5
    assert summary["claim_coverage_stddev"] == 0.5
    assert summary["claim_group_coverage"] == 0.5
    assert summary["claim_group_coverage_stddev"] == 0.25
    assert summary["generation_latency_ms_stddev"] == 100


def test_routing_summary_builds_confusion_matrix() -> None:
    rows = [
        {
            "expected_retrieval_mode": "vector",
            "router_decision": {"selected_mode": "vector"},
        },
        {
            "expected_retrieval_mode": "graph",
            "router_decision": {"selected_mode": "vector"},
        },
    ]

    summary = routing_summary(rows)

    assert summary["accuracy"] == 0.5
    assert summary["confusion_matrix"]["vector"]["vector"] == 1
    assert summary["confusion_matrix"]["graph"]["vector"] == 1


def test_current_gold_suite_router_result_is_reproducible(tmp_path: Path) -> None:
    payload = run_router_benchmark(tmp_path)

    assert payload["summary"] == {
        "correct": 32,
        "questions": 32,
        "accuracy": 1.0,
        "confusion_matrix": {
            "vector": {"vector": 17, "graph": 0},
            "graph": {"vector": 0, "graph": 15},
        },
    }
    assert (tmp_path / "router_results.json").is_file()


def test_checkpoint_round_trip_requires_matching_signature(tmp_path: Path) -> None:
    signature = checkpoint_signature(
        model="qwen3:8b",
        host="http://localhost:11434",
        top_k=6,
        graph_max_depth=6,
        relevance_threshold=0.85,
        repetitions=3,
        gold_questions_sha256="gold-sha",
        source_hashes={"source": "source-sha"},
    )
    path = tmp_path / "benchmark_checkpoint.json"
    rows = [{"question_id": "direct_01"}]
    write_json_atomic(path, {"signature": signature, "questions": rows})

    assert load_checkpoint(path, signature) == rows


def test_checkpoint_rejects_changed_run_configuration(tmp_path: Path) -> None:
    path = tmp_path / "benchmark_checkpoint.json"
    write_json_atomic(path, {"signature": {"model": "old"}, "questions": []})

    try:
        load_checkpoint(path, {"model": "new"})
    except RuntimeError as exc:
        assert "do not match" in str(exc)
    else:
        raise AssertionError("A mismatched checkpoint must not be resumed.")


def test_claim_scoring_requires_every_term_group() -> None:
    claim = {
        "claim_id": "example",
        "term_groups": [["gmx rmsf"], ["fluctuation", "rmsf"]],
    }
    assert claim_is_present("gmx rmsf calculates atomic fluctuation.", claim)
    assert not claim_is_present("gmx rms calculates deviation.", claim)
    score = score_answer("gmx rmsf calculates RMSF.", [claim])
    assert score["claim_coverage"] == 1.0
    assert score["claim_group_coverage"] == 1.0


def test_claim_group_coverage_preserves_partial_credit() -> None:
    claim = {
        "claim_id": "workflow",
        "term_groups": [["rdkit"], ["pdbqt"], ["vina"], ["sdf"]],
    }

    score = score_answer("RDKit prepares input for a Vina workflow.", [claim])

    assert score["claim_coverage"] == 0.0
    assert score["claim_group_coverage"] == 0.5
    assert score["claim_groups_passed"] == ["workflow:1", "workflow:3"]


def test_run_to_run_dispersion_is_within_question() -> None:
    rows = [
        {
            "vector": {
                "runs": [
                    {
                        "claim_coverage": 0.0,
                        "claim_group_coverage": 0.5,
                        "prompt_tokens": 10,
                        "answer_tokens": 5,
                        "generation_latency_ms": 100,
                    },
                    {
                        "claim_coverage": 1.0,
                        "claim_group_coverage": 1.0,
                        "prompt_tokens": 10,
                        "answer_tokens": 7,
                        "generation_latency_ms": 300,
                    },
                ]
            }
        }
    ]

    summary = run_to_run_dispersion(rows, "vector")

    assert summary["claim_coverage_stddev_mean"] == 0.5
    assert summary["answer_tokens_stddev_mean"] == 1
    assert summary["generation_latency_ms_stddev_mean"] == 100


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
