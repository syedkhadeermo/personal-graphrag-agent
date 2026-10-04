import pytest


EXTERNAL_TEST_FILES = {
    "test_admet_production_retrieval.py",
    "test_admet_runner.py",
    "test_embeddings.py",
    "test_gromacs_knowledge_indexing.py",
    "test_gromacs_production_indexing.py",
    "test_job_manager_remote_artifact.py",
    "test_job_manager_routing_remote.py",
    "test_private_knowledge_ingestion.py",
    "test_private_knowledge_production_multidomain.py",
    "test_remote_artifact_manifest.py",
    "test_similarity.py",
    "test_vectorstore.py",
    "test_worker_health_service_remote.py",
    "test_workload_router_remote.py",
}


@pytest.fixture(autouse=True)
def explicit_local_api_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep portable API tests explicit about their local auth bypass."""

    monkeypatch.setenv("GRAPH_RAG_ALLOW_INSECURE_LOCAL", "true")


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-external",
        action="store_true",
        default=False,
        help="run tests that require local models, private data, WSL, or SSH workers",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    external_marker = pytest.mark.external
    skip_external = pytest.mark.skip(
        reason="requires --run-external and its documented external services/data",
    )

    for item in items:
        if item.path.name not in EXTERNAL_TEST_FILES:
            continue

        item.add_marker(external_marker)
        if not config.getoption("--run-external"):
            item.add_marker(skip_external)
