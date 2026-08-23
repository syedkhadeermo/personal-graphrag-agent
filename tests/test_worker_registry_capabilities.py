import json

from app.agent.workers.remote_compute_worker import (
    RemoteComputeWorker,
)

from app.agent.workers.worker_capabilities import (
    WorkerCapability,
)

from app.agent.workers.worker_registry import (
    WorkerRegistry,
)


class LocalTestWorker:
    """
    Minimal worker used only for registry testing.
    """

    def run(
        self,
        command: str,
    ) -> dict:
        return {
            "status": "completed",
            "command": command,
        }


def main() -> None:
    registry = WorkerRegistry()

    mini_pc = RemoteComputeWorker(
        host="192.168.137.2",
        username="syed",
    )

    local_worker = LocalTestWorker()

    print("1. Registering capability-aware workers...")

    registry.register(
        worker_id="mini-pc",
        worker=mini_pc,
        description=(
            "Remote Windows scientific compute worker"
        ),
        metadata={
            "hostname": "syed-pc",
            "connection": "ssh",
        },
        capabilities=[
            WorkerCapability.REMOTE_COMMAND,
            WorkerCapability.FREECAD,
            WorkerCapability.BLENDER,
            WorkerCapability.OPENFOAM,
            WorkerCapability.GROMACS,
            "FreeCAD",
        ],
    )

    registry.register(
        worker_id="local-controller",
        worker=local_worker,
        description="Laptop controller worker",
        metadata={
            "connection": "local",
        },
        capabilities=[
            WorkerCapability.GROMACS,
            "remote-command",
        ],
    )

    descriptions = (
        registry.describe_workers()
    )

    print(
        json.dumps(
            descriptions,
            indent=2,
            default=str,
        )
    )

    assert registry.count() == 2

    print(
        "\n2. Checking individual capabilities..."
    )

    assert registry.supports(
        "mini-pc",
        WorkerCapability.FREECAD,
    ) is True

    assert registry.supports(
        "mini-pc",
        "Blender",
    ) is True

    assert registry.supports(
        "mini-pc",
        "openfoam",
    ) is True

    assert registry.supports(
        "mini-pc",
        "gromacs",
    ) is True

    assert registry.supports(
        "local-controller",
        "gromacs",
    ) is True

    assert registry.supports(
        "local-controller",
        "freecad",
    ) is False

    assert registry.supports(
        "missing-worker",
        "freecad",
    ) is False

    print(
        "Individual capability checks passed."
    )

    print(
        "\n3. Filtering workers by capability..."
    )

    freecad_workers = (
        registry.find_workers(
            [
                WorkerCapability.FREECAD,
            ]
        )
    )

    gromacs_workers = (
        registry.find_workers(
            [
                WorkerCapability.GROMACS,
            ]
        )
    )

    remote_gromacs_workers = (
        registry.find_workers(
            [
                WorkerCapability.REMOTE_COMMAND,
                WorkerCapability.GROMACS,
            ]
        )
    )

    blender_openfoam_workers = (
        registry.find_workers(
            [
                WorkerCapability.BLENDER,
                WorkerCapability.OPENFOAM,
            ]
        )
    )

    unavailable_workers = (
        registry.find_workers(
            [
                "nonexistent_capability",
            ]
        )
    )

    all_workers = (
        registry.find_workers()
    )

    print(
        "FreeCAD:",
        freecad_workers,
    )

    print(
        "GROMACS:",
        gromacs_workers,
    )

    print(
        "Remote + GROMACS:",
        remote_gromacs_workers,
    )

    print(
        "Blender + OpenFOAM:",
        blender_openfoam_workers,
    )

    print(
        "Unavailable:",
        unavailable_workers,
    )

    print(
        "All:",
        all_workers,
    )

    assert freecad_workers == [
        "mini-pc"
    ]

    assert gromacs_workers == [
        "local-controller",
        "mini-pc",
    ]

    assert remote_gromacs_workers == [
        "local-controller",
        "mini-pc",
    ]

    assert blender_openfoam_workers == [
        "mini-pc"
    ]

    assert unavailable_workers == []

    assert all_workers == [
        "local-controller",
        "mini-pc",
    ]

    print(
        "\n4. Inspecting Mini-PC record..."
    )

    mini_pc_record = registry.get_record(
        "mini-pc"
    )

    assert mini_pc_record is not None

    assert mini_pc_record["capabilities"] == (
        "blender",
        "freecad",
        "gromacs",
        "openfoam",
        "remote_command",
    )

    assert (
        mini_pc_record["metadata"]["hostname"]
        == "syed-pc"
    )

    assert (
        mini_pc_record["worker"]
        is mini_pc
    )

    print(
        f"Mini-PC capabilities: "
        f"{mini_pc_record['capabilities']}"
    )

    print(
        "\nPASS: Worker capability integration passed."
    )

    print(
        "PASS: Duplicate capability values were removed."
    )

    print(
        "PASS: Multi-capability filtering passed."
    )

    print(
        "PASS: No SSH connection was attempted."
    )


if __name__ == "__main__":
    main()


def test_main() -> None:
    main()
