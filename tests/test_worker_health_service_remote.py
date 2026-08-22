import json

from app.agent.workers.remote_compute_worker import (
    RemoteComputeWorker,
)

from app.agent.workers.worker_capabilities import (
    WorkerCapability,
)

from app.agent.workers.worker_health_service import (
    WorkerHealthService,
)

from app.agent.workers.worker_registry import (
    WorkerRegistry,
)


REMOTE_HOST = "192.168.137.2"
REMOTE_USERNAME = "syed"
EXPECTED_HOSTNAME = "syed-pc"


def main() -> None:
    print("1. Creating Mini-PC worker...")

    mini_pc = RemoteComputeWorker(
        host=REMOTE_HOST,
        username=REMOTE_USERNAME,
    )

    registry = WorkerRegistry()

    registry.register(
        worker_id="mini-pc",
        worker=mini_pc,
        description=(
            "Remote Windows scientific compute worker"
        ),
        metadata={
            "hostname": EXPECTED_HOSTNAME,
            "connection": "ssh",
        },
        capabilities=[
            WorkerCapability.REMOTE_COMMAND,
            WorkerCapability.FREECAD,
            WorkerCapability.BLENDER,
            WorkerCapability.OPENFOAM,
            WorkerCapability.GROMACS,
        ],
    )

    health_service = WorkerHealthService(
        worker_registry=registry
    )

    print(
        "\n2. Health before heartbeat..."
    )

    before = health_service.get_health(
        "mini-pc"
    )

    print(
        json.dumps(
            before,
            indent=2,
            default=str,
        )
    )

    assert before["status"] == "unknown"
    assert before["checked_at"] is None

    print(
        "\n3. Running real SSH heartbeat..."
    )

    after = health_service.check_worker(
        "mini-pc"
    )

    print(
        json.dumps(
            after,
            indent=2,
            default=str,
        )
    )

    assert after["status"] == "healthy"
    assert after["checked_at"] is not None
    assert after["latency_seconds"] is not None
    assert after["latency_seconds"] >= 0
    assert after["consecutive_failures"] == 0

    details = after["details"]

    assert details["host"] == REMOTE_HOST

    assert (
        details["username"]
        == REMOTE_USERNAME
    )

    assert details["return_code"] == 0

    assert (
        details["hostname"].lower()
        == EXPECTED_HOSTNAME
    )

    assert (
        details["stdout"]
        .strip()
        .lower()
        == EXPECTED_HOSTNAME
    )

    print(
        "\n4. Verifying capability registry "
        "remains available..."
    )

    assert registry.supports(
        "mini-pc",
        WorkerCapability.FREECAD,
    ) is True

    assert registry.supports(
        "mini-pc",
        WorkerCapability.BLENDER,
    ) is True

    assert registry.supports(
        "mini-pc",
        WorkerCapability.OPENFOAM,
    ) is True

    assert registry.supports(
        "mini-pc",
        WorkerCapability.GROMACS,
    ) is True

    print(
        f"Heartbeat latency: "
        f"{after['latency_seconds']} seconds"
    )

    print(
        "\nPASS: Real Mini-PC SSH heartbeat passed."
    )

    print(
        "PASS: Worker status changed "
        "UNKNOWN -> HEALTHY."
    )

    print(
        "PASS: Hostname syed-pc was verified."
    )

    print(
        "PASS: Mini-PC capabilities remain registered."
    )


if __name__ == "__main__":
    main()