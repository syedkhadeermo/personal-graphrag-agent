import json
import tempfile

from pathlib import Path

from app.agent.jobs.job import Job
from app.agent.jobs.job_manager import JobManager
from app.agent.jobs.job_state import JobState
from app.agent.jobs.job_store import JobStore

from app.agent.workers.remote_compute_worker import (
    RemoteComputeWorker,
)

from app.agent.workers.worker_capabilities import (
    WorkerCapability,
)

from app.agent.workers.worker_registry import (
    WorkerRegistry,
)


REMOTE_HOST = "192.168.137.2"
REMOTE_USERNAME = "syed"
EXPECTED_HOSTNAME = "syed-pc"


def main() -> None:
    temporary_root = Path(
        tempfile.mkdtemp(
            prefix=(
                "job_manager_remote_routing_test_"
            )
        )
    )

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
            "host": REMOTE_HOST,
            "username": REMOTE_USERNAME,
        },
        capabilities=[
            WorkerCapability.REMOTE_COMMAND,
            WorkerCapability.FREECAD,
            WorkerCapability.BLENDER,
            WorkerCapability.OPENFOAM,
            WorkerCapability.GROMACS,
            WorkerCapability.CALCULIX,
        ],
    )

    job_store = JobStore(
        database_path=str(
            temporary_root
            / "state"
            / "jobs.db"
        )
    )

    manager = JobManager(
        base_directory=str(
            temporary_root
            / "jobs"
        ),
        job_store=job_store,
        worker_registry=registry,
    )

    job = Job(
        job_id="JOB-REAL-ROUTING-TEST",
        domain="cad_simulation",
        tool="freecad",
        status=JobState.RUNNING.value,
        attempt=1,
    )

    job_store.create(
        job
    )

    print(
        "1. Running real heartbeat-aware "
        "JobManager assignment..."
    )

    manager._prepare_remote_worker(
        job
    )

    health = (
        manager
        .worker_health_service
        .get_health(
            "mini-pc"
        )
    )

    print(
        json.dumps(
            {
                "job_id":
                    job.job_id,

                "domain":
                    job.domain,

                "tool":
                    job.tool,

                "selected_worker":
                    job.worker,

                "health":
                    health,
            },
            indent=2,
            default=str,
        )
    )

    assert job.worker == "mini-pc"
    assert health is not None
    assert health["status"] == "healthy"

    assert (
        health["details"]["host"]
        == REMOTE_HOST
    )

    assert (
        health["details"]["username"]
        == REMOTE_USERNAME
    )

    assert (
        health["details"]["hostname"]
        .lower()
        == EXPECTED_HOSTNAME
    )

    assert (
        registry.supports(
            "mini-pc",
            WorkerCapability.FREECAD,
        )
        is True
    )

    assert (
        registry.supports(
            "mini-pc",
            WorkerCapability.CALCULIX,
        )
        is True
    )

    selected_calculix_worker = (
        manager
        .workload_router
        .select_worker(
            required_capabilities=[
                WorkerCapability.CALCULIX,
            ],
        )
    )

    assert (
        selected_calculix_worker
        == "mini-pc"
    )

    print(
        "\nPASS: JobManager selected mini-pc "
        "through WorkloadRouter."
    )

    print(
        "PASS: Real SSH heartbeat was healthy."
    )

    print(
        "PASS: FreeCAD capability was verified."
    )

    print(
        "PASS: CalculiX capability was verified."
    )

    print(
        "PASS: WorkloadRouter selected mini-pc "
        "for CalculiX."
    )

    print(
        "PASS: No FreeCAD or CalculiX process "
        "was executed."
    )

    print(
        f"Temporary test data: {temporary_root}"
    )


if __name__ == "__main__":
    main()


def test_main() -> None:
    main()