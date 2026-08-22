from datetime import datetime

from fastapi.testclient import TestClient

from app.api.main import (
    APP_NAME,
    APP_VERSION,
    app,
)


def main() -> None:
    client = TestClient(
        app
    )

    print("1. Calling GET /health...")

    response = client.get(
        "/health"
    )

    print(
        "Status code:",
        response.status_code,
    )

    print(
        "Response:",
        response.json(),
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "healthy"
    assert payload["service"] == APP_NAME
    assert payload["version"] == APP_VERSION

    timestamp = datetime.fromisoformat(
        payload["timestamp"]
    )

    assert timestamp.tzinfo is not None

    print(
        "\n2. Verifying OpenAPI endpoint..."
    )

    openapi_response = client.get(
        "/openapi.json"
    )

    assert openapi_response.status_code == 200

    schema = openapi_response.json()

    assert "/health" in schema["paths"]

    print(
        "OpenAPI title:",
        schema["info"]["title"],
    )

    print(
        "\nPASS: GET /health returned HTTP 200."
    )

    print(
        "PASS: Health payload and UTC timestamp passed."
    )

    print(
        "PASS: OpenAPI schema contains /health."
    )

    print(
        "PASS: No network port or remote worker was used."
    )


if __name__ == "__main__":
    main()