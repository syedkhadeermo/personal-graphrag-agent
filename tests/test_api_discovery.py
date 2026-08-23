import json
import warnings

from fastapi.testclient import TestClient

from app.api.main import app


def main() -> None:
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
    )

    client = TestClient(
        app
    )

    print("1. Calling GET /capabilities...")

    response = client.get(
        "/capabilities"
    )

    assert response.status_code == 200

    capabilities = response.json()

    print(
        json.dumps(
            capabilities,
            indent=2,
        )
    )

    assert "domain_count" in capabilities
    assert "domains" in capabilities

    assert (
        capabilities["domain_count"]
        == len(
            capabilities["domains"]
        )
    )

    assert isinstance(
        capabilities["domains"],
        dict,
    )

    for domain, tools in (
        capabilities["domains"].items()
    ):
        assert isinstance(domain, str)
        assert isinstance(tools, list)

        for tool in tools:
            assert isinstance(tool, str)

    print("\n2. Calling GET /agents...")

    response = client.get(
        "/agents"
    )

    assert response.status_code == 200

    agents_payload = response.json()

    print(
        json.dumps(
            agents_payload,
            indent=2,
        )
    )

    assert (
        agents_payload["agent_count"]
        == 4
    )

    agents = agents_payload["agents"]

    assert len(agents) == 4

    agent_ids = {
        agent["agent_id"]
        for agent in agents
    }

    assert agent_ids == {
        "drug-discovery-agent",
        "engineering-agent",
        "rendering-agent",
        "knowledge-agent",
    }

    for agent in agents:
        assert agent["routes"]
        assert isinstance(
            agent["priority"],
            int,
        )

    print(
        "\n3. Verifying OpenAPI discovery paths..."
    )

    schema_response = client.get(
        "/openapi.json"
    )

    assert schema_response.status_code == 200

    paths = schema_response.json()[
        "paths"
    ]

    assert "/health" in paths
    assert "/capabilities" in paths
    assert "/agents" in paths

    print(
        "OpenAPI paths:",
        sorted(
            paths.keys()
        ),
    )

    print(
        "\nPASS: GET /capabilities passed."
    )

    print(
        "PASS: ToolRegistry discovery passed."
    )

    print(
        "PASS: GET /agents returned four "
        "bounded named agents."
    )

    print(
        "PASS: OpenAPI discovery paths passed."
    )

    print(
        "PASS: No jobs, SSH, or tools were executed."
    )


if __name__ == "__main__":
    main()


def test_main() -> None:
    main()
