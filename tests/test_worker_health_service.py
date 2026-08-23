import json

from app.agent.workers.worker_health_service import (
    WorkerHealthService,
)

from app.agent.workers.worker_registry import (
    WorkerRegistry,
)


class ScriptedWorker:
    """
    Worker with predetermined heartbeat responses.
    """

    def __init__(
        self,
        responses: list,
    ):
        self.responses = list(
            responses
        )

    def run(
        self,
        command: str,
    ) -> dict:
        return {
            "status": "completed",
            "command": command,
        }

    def ping(
        self,
    ) -> dict:
        if not self.responses:
            raise RuntimeError(
                "No scripted heartbeat response."
            )

        response = self.responses.pop(0)

        if isinstance(
            response,
            Exception,
        ):
            raise response

        return response


class WorkerWithoutPing:
    def run(
        self,
        command: str,
    ) -> dict:
        return {
            "status": "completed",
            "command": command,
        }


def print_health(
    title: str,
    health: dict,
) -> None:
    print(
        f"\n{title}"
    )

    print(
        json.dumps(
            health,
            indent=2,
            default=str,
        )
    )


def main() -> None:
    registry = WorkerRegistry()

    scripted_worker = ScriptedWorker(
        responses=[
            {
                "host": "192.168.137.2",
                "username": "syed",
                "status": "completed",
                "return_code": 0,
                "stdout": "syed-pc\n",
                "stderr": "",
            },
            {
                "host": "192.168.137.2",
                "username": "syed",
                "status": "failed",
                "return_code": 255,
                "stdout": "",
                "stderr": (
                    "SSH connection refused."
                ),
            },
            {
                "host": "192.168.137.2",
                "username": "syed",
                "status": "timeout",
                "return_code": None,
                "stdout": "",
                "stderr": "",
            },
            {
                "host": "192.168.137.2",
                "username": "syed",
                "status": "completed",
                "return_code": 0,
                "stdout": "syed-pc\n",
                "stderr": "",
            },
        ]
    )

    registry.register(
        worker_id="mini-pc",
        worker=scripted_worker,
        description="Simulated Mini-PC worker",
        capabilities=[
            "freecad",
            "blender",
            "openfoam",
            "gromacs",
        ],
    )

    registry.register(
        worker_id="no-ping-worker",
        worker=WorkerWithoutPing(),
    )

    service = WorkerHealthService(
        worker_registry=registry
    )

    print("1. Checking initial UNKNOWN state...")

    initial = service.get_health(
        "mini-pc"
    )

    print_health(
        "Initial:",
        initial,
    )

    assert initial["status"] == "unknown"
    assert initial["checked_at"] is None
    assert initial["consecutive_failures"] == 0

    print("\n2. Testing healthy heartbeat...")

    healthy = service.check_worker(
        "mini-pc"
    )

    print_health(
        "Healthy:",
        healthy,
    )

    assert healthy["status"] == "healthy"
    assert healthy["consecutive_failures"] == 0

    assert (
        healthy["details"]["hostname"]
        == "syed-pc"
    )

    print("\n3. Testing failed heartbeat...")

    unhealthy = service.check_worker(
        "mini-pc"
    )

    print_health(
        "Unhealthy:",
        unhealthy,
    )

    assert unhealthy["status"] == "unhealthy"

    assert (
        unhealthy["consecutive_failures"]
        == 1
    )

    assert (
        unhealthy["details"]["return_code"]
        == 255
    )

    print("\n4. Testing timeout heartbeat...")

    timeout = service.check_worker(
        "mini-pc"
    )

    print_health(
        "Timeout:",
        timeout,
    )

    assert timeout["status"] == "timeout"

    assert (
        timeout["consecutive_failures"]
        == 2
    )

    print("\n5. Testing worker recovery...")

    recovered = service.check_worker(
        "mini-pc"
    )

    print_health(
        "Recovered:",
        recovered,
    )

    assert recovered["status"] == "healthy"

    assert (
        recovered["consecutive_failures"]
        == 0
    )

    print(
        "\n6. Testing worker without ping()..."
    )

    missing_ping = service.check_worker(
        "no-ping-worker"
    )

    print_health(
        "Missing ping:",
        missing_ping,
    )

    assert (
        missing_ping["status"]
        == "unhealthy"
    )

    assert (
        missing_ping["details"]["error"]
        == "missing_ping_method"
    )

    print(
        "\n7. Testing missing worker..."
    )

    missing_worker_rejected = False

    try:
        service.check_worker(
            "unknown-worker"
        )

    except ValueError as exc:
        missing_worker_rejected = True

        print(
            f"Missing worker rejected: {exc}"
        )

    assert missing_worker_rejected is True

    assert (
        service.get_health(
            "unknown-worker"
        )
        is None
    )

    print(
        "\n8. Listing current health records..."
    )

    all_health = service.list_health()

    print(
        json.dumps(
            all_health,
            indent=2,
            default=str,
        )
    )

    assert len(all_health) == 2

    print(
        "\nPASS: Healthy heartbeat classification passed."
    )

    print(
        "PASS: Unhealthy and timeout classification passed."
    )

    print(
        "PASS: Consecutive failures and recovery passed."
    )

    print(
        "PASS: Missing ping and worker handling passed."
    )

    print(
        "PASS: No SSH connection was attempted."
    )


if __name__ == "__main__":
    main()


def test_main() -> None:
    main()
