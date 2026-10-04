from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.main import app, validate_security_configuration


def test_job_endpoints_require_configured_api_key() -> None:
    with patch.dict(
        "os.environ",
        {"GRAPH_RAG_API_KEY": "test-secret"},
    ):
        client = TestClient(app)

        missing = client.get("/jobs/unknown")
        invalid = client.get(
            "/jobs/unknown",
            headers={"X-API-Key": "wrong-secret"},
        )
        valid = client.get(
            "/jobs/unknown",
            headers={"X-API-Key": "test-secret"},
        )

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert valid.status_code == 404


def test_protected_endpoints_fail_closed_without_configuration() -> None:
    with patch.dict("os.environ", {}, clear=True):
        client = TestClient(app)

        for path in ("/runtime", "/capabilities", "/agents", "/jobs/unknown"):
            response = client.get(path)
            assert response.status_code == 503

        assert client.get("/health").status_code == 200


def test_explicit_local_bypass_allows_unauthenticated_discovery() -> None:
    with patch.dict(
        "os.environ",
        {"GRAPH_RAG_ALLOW_INSECURE_LOCAL": "true"},
        clear=True,
    ):
        client = TestClient(app)

        assert client.get("/runtime").status_code == 200
        assert client.get("/capabilities").status_code == 200
        assert client.get("/agents").status_code == 200


def test_startup_security_configuration_is_fail_closed() -> None:
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(RuntimeError, match="GRAPH_RAG_API_KEY is required"):
            validate_security_configuration()

    with patch.dict("os.environ", {"GRAPH_RAG_API_KEY": "test-secret"}, clear=True):
        validate_security_configuration()

    with patch.dict(
        "os.environ",
        {"GRAPH_RAG_ALLOW_INSECURE_LOCAL": "true"},
        clear=True,
    ):
        validate_security_configuration()


def test_local_cors_origin_is_allowed() -> None:
    client = TestClient(app)
    response = client.options(
        "/jobs",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-API-Key,Content-Type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "http://localhost:3000"
    )
