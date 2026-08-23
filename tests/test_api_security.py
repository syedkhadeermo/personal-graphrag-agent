from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.main import app


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
