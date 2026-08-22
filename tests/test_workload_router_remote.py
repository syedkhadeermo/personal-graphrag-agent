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

from app.agent.workers.workload_router import (
    WorkloadRouter,
)


REMOTE_HOST = "192.168.137.2"
REMOTE_USERNAME = "syed"
EXPECTED_HOSTNAME = "syed-pc"


def main() -> None:
    registry = WorkerRegistry()

    mini_pc = RemoteComputeWorker(
        host=REMOTE_HOST,
        username=REMOTE_USERNAME,
    )

    registry.register(
        worker_id="mini-pc",
        worker=mini_pc,
        description=(
            "Remote scientific compute worker"
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

    router = WorkloadRouter(
        worker_registry=registry,
        health_service=health_service,
    )

    print(
        "1. Verifying UNKNOWN worker is not "
        "routed by default..."
    )

    unknown_rejected = False

    try:
        router.select_worker(
            required_capabilities=[
                WorkerCapability.FREECAD,
            ]
        )

    except LookupError as exc:
        unknown_rejected = True

        print(
            f"UNKNOWN worker rejected: {exc}"
        )

    assert unknown_rejected is True

    print(
        "\n2. Running real Mini-PC heartbeat..."
    )

    health = health_service.check_worker(
        "mini-pc"
    )

    print(
        json.dumps(
            health,
            indent=2,
            default=str,
        )
    )

    assert health["status"] == "healthy"

    assert (
        health["details"]["hostname"].lower()
        == EXPECTED_HOSTNAME
    )

    print(
        "\n3. Routing scientific workloads..."
    )

    expected_routes = {
        "remote_command":
            WorkerCapability.REMOTE_COMMAND,

        "freecad":
            WorkerCapability.FREECAD,

        "blender":
            WorkerCapability.BLENDER,

        "openfoam":
            WorkerCapability.OPENFOAM,

        "gromacs":
            WorkerCapability.GROMACS,
    }

    selected_routes = {}

    for workload_name, capability in (
        expected_routes.items()
    ):

        selected_worker = (
            router.select_worker(
                required_capabilities=[
                    capability
                ]
            )
        )

        selected_routes[
            workload_name
        ] = selected_worker

        assert selected_worker == "mini-pc"

    print(
        json.dumps(
            selected_routes,
            indent=2,
        )
    )

    print(
        "\n4. Inspecting FreeCAD candidates..."
    )

    candidates = router.get_candidates(
        required_capabilities=[
            WorkerCapability.FREECAD,
        ]
    )

    print(
        json.dumps(
            candidates,
            indent=2,
            default=str,
        )
    )

    assert len(candidates) == 1

    assert (
        candidates[0]["worker_id"]
        == "mini-pc"
    )

    assert (
        candidates[0]["health"]["status"]
        == "healthy"
    )

    print(
        "\nPASS: Real health-aware routing passed."
    )

    print(
        "PASS: Mini PC selected for FreeCAD."
    )

    print(
        "PASS: Mini PC selected for Blender."
    )

    print(
        "PASS: Mini PC selected for OpenFOAM."
    )

    print(
        "PASS: Mini PC selected for future GROMACS."
    )

    print(
        "PASS: No scientific workload was executed."
    )


if __name__ == "__main__":
    main()