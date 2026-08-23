import json
import socket
from unittest.mock import patch

from app.agent.tools.default_tools import (
    create_default_registry,
)
from app.agent.tools.domain_tools.cybersecurity_tools import (
    CybersecurityTools,
)


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(
        self,
        exception_type,
        exception,
        traceback,
    ):
        return False


def fake_create_connection(
    address,
    timeout,
):
    host, port = address

    assert host == "192.168.137.2"
    assert timeout == 1.0

    if port == 22:
        return FakeConnection()

    if port == 445:
        raise ConnectionRefusedError()

    raise socket.timeout()


def expect_exception(
    exception_type,
    function,
):
    try:
        function()
    except exception_type as exc:
        print(
            f"{exception_type.__name__}: {exc}"
        )
        return

    raise AssertionError(
        f"Expected {exception_type.__name__}."
    )


def main():
    print(
        "1. Testing input and authorization validation..."
    )

    expect_exception(
        ValueError,
        lambda:
            CybersecurityTools.vulnerability_scan(
                target="8.8.8.8",
                ports=[53],
                authorization_confirmed=True,
            ),
    )

    expect_exception(
        PermissionError,
        lambda:
            CybersecurityTools.vulnerability_scan(
                target="192.168.137.2",
                ports=[22],
                authorization_confirmed=False,
            ),
    )

    expect_exception(
        ValueError,
        lambda:
            CybersecurityTools.vulnerability_scan(
                target="192.168.137.0/24",
                ports=[22],
                authorization_confirmed=True,
            ),
    )

    expect_exception(
        ValueError,
        lambda:
            CybersecurityTools.vulnerability_scan(
                target="192.168.137.2",
                ports=[],
                authorization_confirmed=True,
            ),
    )

    print(
        "\n2. Testing deterministic TCP assessment..."
    )

    with patch(
        "socket.create_connection",
        side_effect=fake_create_connection,
    ):
        result = (
            CybersecurityTools.vulnerability_scan(
                target="192.168.137.2",
                ports=[22, 445, 8000],
                authorization_confirmed=True,
                timeout=1.0,
            )
        )

    print(
        json.dumps(
            result,
            indent=2,
            default=str,
        )
    )

    assert result["status"] == "completed"
    assert result["authorization_confirmed"] is True
    assert result["target"] == "192.168.137.2"
    assert result["summary"]["open_ports"] == [22]

    states = {
        item["port"]: item["state"]
        for item in result["observations"]
    }

    assert states == {
        22: "open",
        445: "closed",
        8000: "filtered_or_unresponsive",
    }

    assert len(result["findings"]) == 1
    assert (
        result["findings"][0]["severity"]
        == "informational"
    )

    print(
        "\n3. Testing ToolRegistry execution..."
    )

    registry = create_default_registry()

    with patch(
        "socket.create_connection",
        side_effect=fake_create_connection,
    ):
        registry_result = registry.execute(
            domain="cybersecurity",
            name="vulnerability_scan",
            request={
                "target": "192.168.137.2",
                "ports": [22, 445, 8000],
                "authorization_confirmed": True,
                "timeout": 1.0,
            },
        )

    assert registry_result["status"] == "completed"
    assert registry_result["summary"]["open_ports"] == [22]

    assert registry.list_tools(
        "cybersecurity"
    ) == [
        "vulnerability_scan",
    ]

    print(
        "\nPASS: Authorization enforcement passed."
    )
    print(
        "PASS: Public targets and network ranges were rejected."
    )
    print(
        "PASS: Bounded TCP assessment passed."
    )
    print(
        "PASS: Structured findings passed."
    )
    print(
        "PASS: ToolRegistry execution passed."
    )
    print(
        "PASS: No real network connection was performed."
    )


if __name__ == "__main__":
    main()


def test_main() -> None:
    main()
