import json
import time

from app.agent.workers.worker_health_service import (
    WorkerHealthService,
)

from app.agent.workers.worker_registry import (
    WorkerRegistry,
)

from app.agent.workers.workload_router import (
    WorkloadRouter,
)


class SimulatedWorker:
    def __init__(
        self,
        hostname: str,
        delay_seconds: float = 0.0,
        return_code: int | None = 0,
        status: str = "completed",
        stderr: str = "",
    ):
        self.hostname = hostname
        self.delay_seconds = delay_seconds
        self.return_code = return_code
        self.status = status
        self.stderr = stderr

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
        if self.delay_seconds > 0:
            time.sleep(
                self.delay_seconds
            )

        return {
            "host": self.hostname,
            "username": "test",
            "status": self.status,
            "return_code": self.return_code,
            "stdout": (
                f"{self.hostname}\n"
                if self.return_code == 0
                else ""
            ),
            "stderr": self.stderr,
        }


def main() -> None:
    registry = WorkerRegistry()

    registry.register(
        worker_id="fast-worker",
        worker=SimulatedWorker(
            hostname="fast-worker",
            delay_seconds=0.001,
        ),
        capabilities=[
            "freecad",
            "openfoam",
        ],
    )

    registry.register(
        worker_id="slow-worker",
        worker=SimulatedWorker(
            hostname="slow-worker",
            delay_seconds=0.03,
        ),
        capabilities=[
            "freecad",
            "blender",
        ],
    )

    registry.register(
        worker_id="unhealthy-worker",
        worker=SimulatedWorker(
            hostname="unhealthy-worker",
            return_code=255,
            status="failed",
            stderr="Connection refused.",
        ),
        capabilities=[
            "freecad",
            "gromacs",
        ],
    )

    registry.register(
        worker_id="unknown-worker",
        worker=SimulatedWorker(
            hostname="unknown-worker",
        ),
        capabilities=[
            "gromacs",
        ],
    )

    health_service = WorkerHealthService(
        worker_registry=registry
    )

    router = WorkloadRouter(
        worker_registry=registry,
        health_service=health_service,
    )

    print("1. Establishing simulated health states...")

    fast_health = health_service.check_worker(
        "fast-worker"
    )

    slow_health = health_service.check_worker(
        "slow-worker"
    )

    unhealthy_health = (
        health_service.check_worker(
            "unhealthy-worker"
        )
    )

    # unknown-worker is intentionally not checked.

    print(
        json.dumps(
            [
                fast_health,
                slow_health,
                unhealthy_health,
                health_service.get_health(
                    "unknown-worker"
                ),
            ],
            indent=2,
            default=str,
        )
    )

    assert fast_health["status"] == "healthy"
    assert slow_health["status"] == "healthy"

    assert (
        unhealthy_health["status"]
        == "unhealthy"
    )

    print(
        "\n2. Routing a FreeCAD workload..."
    )

    freecad_candidates = router.get_candidates(
        required_capabilities=[
            "freecad",
        ]
    )

    print(
        json.dumps(
            freecad_candidates,
            indent=2,
            default=str,
        )
    )

    selected_freecad = router.select_worker(
        required_capabilities=[
            "freecad",
        ]
    )

    print(
        f"Selected FreeCAD worker: "
        f"{selected_freecad}"
    )

    assert selected_freecad == "fast-worker"

    assert [
        candidate["worker_id"]
        for candidate
        in freecad_candidates
    ] == [
        "fast-worker",
        "slow-worker",
    ]

    print(
        "\n3. Routing capability-specific workloads..."
    )

    selected_blender = router.select_worker(
        required_capabilities=[
            "blender",
        ]
    )

    selected_openfoam = router.select_worker(
        required_capabilities=[
            "openfoam",
        ]
    )

    print(
        f"Selected Blender worker: "
        f"{selected_blender}"
    )

    print(
        f"Selected OpenFOAM worker: "
        f"{selected_openfoam}"
    )

    assert selected_blender == "slow-worker"
    assert selected_openfoam == "fast-worker"

    print(
        "\n4. Excluding unhealthy workers..."
    )

    no_healthy_gromacs = False

    try:
        router.select_worker(
            required_capabilities=[
                "gromacs",
            ]
        )

    except LookupError as exc:
        no_healthy_gromacs = True

        print(
            f"GROMACS rejected safely: {exc}"
        )

    assert no_healthy_gromacs is True

    print(
        "\n5. Allowing an UNKNOWN worker explicitly..."
    )

    selected_unknown = router.select_worker(
        required_capabilities=[
            "gromacs",
        ],
        allow_unknown=True,
    )

    print(
        f"Selected UNKNOWN GROMACS worker: "
        f"{selected_unknown}"
    )

    assert selected_unknown == "unknown-worker"

    print(
        "\n6. Testing an unsupported capability..."
    )

    unsupported_rejected = False

    try:
        router.select_worker(
            required_capabilities=[
                "quantum_computing",
            ]
        )

    except LookupError as exc:
        unsupported_rejected = True

        print(
            f"Unsupported workload rejected: {exc}"
        )

    assert unsupported_rejected is True

    print(
        "\nPASS: Capability-aware routing passed."
    )

    print(
        "PASS: Lower-latency healthy worker was selected."
    )

    print(
        "PASS: Unhealthy workers were excluded."
    )

    print(
        "PASS: UNKNOWN workers required explicit permission."
    )

    print(
        "PASS: No SSH connection was attempted."
    )


if __name__ == "__main__":
    main()