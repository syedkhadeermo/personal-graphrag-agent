import json
import tempfile
import time

from pathlib import Path

from app.agent.jobs.job import Job
from app.agent.jobs.job_manager import JobManager
from app.agent.jobs.job_state import JobState
from app.agent.jobs.job_store import JobStore

from app.agent.workers.worker_registry import (
    WorkerRegistry,
)


class SimulatedWorker:
    """
    Simulated heartbeat-capable worker.

    No SSH connection or scientific process is used.
    """

    def __init__(
        self,
        hostname: str,
        delay_seconds: float,
    ):
        self.hostname = hostname
        self.delay_seconds = delay_seconds
        self.host = hostname
        self.username = "test"

    def run(
        self,
        command: str,
    ) -> dict:
        return {
            "status": "completed",
            "return_code": 0,
            "command": command,
            "stdout": "",
            "stderr": "",
        }

    def ping(
        self,
    ) -> dict:
        if self.delay_seconds > 0:
            time.sleep(
                self.delay_seconds
            )

        return {
            "host": self.host,
            "username": self.username,
            "status": "completed",
            "return_code": 0,
            "stdout": (
                f"{self.hostname}\n"
            ),
            "stderr": "",
        }


def main() -> None:
    temporary_root = Path(
        tempfile.mkdtemp(
            prefix="job_manager_routing_test_"
        )
    )

    jobs_directory = (
        temporary_root
        / "jobs"
    )

    database_path = (
        temporary_root
        / "state"
        / "jobs.db"
    )

    registry = WorkerRegistry()

    registry.register(
        worker_id="fast-cad-worker",
        worker=SimulatedWorker(
            hostname="fast-cad-worker",
            delay_seconds=0.001,
        ),
        capabilities=[
            "freecad",
            "openfoam",
        ],
        metadata={
            "connection": "simulated",
        },
    )

    registry.register(
        worker_id="blender-worker",
        worker=SimulatedWorker(
            hostname="blender-worker",
            delay_seconds=0.02,
        ),
        capabilities=[
            "freecad",
            "blender",
        ],
        metadata={
            "connection": "simulated",
        },
    )

    job_store = JobStore(
        database_path=str(
            database_path
        )
    )

    manager = JobManager(
        base_directory=str(
            jobs_directory
        ),
        job_store=job_store,
        worker_registry=registry,
    )

    print(
        "1. Verifying routing components "
        "were created..."
    )

    assert manager.worker_registry is registry
    assert manager.worker_health_service is not None
    assert manager.workload_router is not None

    print(
        "Routing components are available."
    )

    print(
        "\n2. Testing inferred FreeCAD routing..."
    )

    freecad_job = Job(
        job_id="JOB-ROUTING-FREECAD",
        domain="cad_simulation",
        tool="freecad",
        status=JobState.RUNNING.value,
        attempt=1,
    )

    job_store.create(
        freecad_job
    )

    manager._prepare_remote_worker(
        freecad_job
    )

    print(
        json.dumps(
            {
                "job_id":
                    freecad_job.job_id,

                "tool":
                    freecad_job.tool,

                "selected_worker":
                    freecad_job.worker,
            },
            indent=2,
        )
    )

    assert (
        freecad_job.worker
        == "fast-cad-worker"
    )

    print(
        "\n3. Testing inferred Blender routing..."
    )

    blender_job = Job(
        job_id="JOB-ROUTING-BLENDER",
        domain="cad_simulation",
        tool="blender",
        status=JobState.RUNNING.value,
        attempt=1,
    )

    job_store.create(
        blender_job
    )

    manager._prepare_remote_worker(
        blender_job
    )

    print(
        json.dumps(
            {
                "job_id":
                    blender_job.job_id,

                "tool":
                    blender_job.tool,

                "selected_worker":
                    blender_job.worker,
            },
            indent=2,
        )
    )

    assert (
        blender_job.worker
        == "blender-worker"
    )

    print(
        "\n4. Testing explicit capability routing..."
    )

    explicit_job = Job(
        job_id="JOB-ROUTING-EXPLICIT",
        domain="scientific_computing",
        tool="custom_solver",
        status=JobState.RUNNING.value,
        attempt=1,
        request={
            "_required_capabilities": [
                "openfoam",
            ]
        },
    )

    job_store.create(
        explicit_job
    )

    manager._prepare_remote_worker(
        explicit_job
    )

    print(
        json.dumps(
            {
                "job_id":
                    explicit_job.job_id,

                "required_capabilities":
                    explicit_job.request[
                        "_required_capabilities"
                    ],

                "selected_worker":
                    explicit_job.worker,
            },
            indent=2,
        )
    )

    assert (
        explicit_job.worker
        == "fast-cad-worker"
    )

    print(
        "\n5. Inspecting health records..."
    )

    print(
        json.dumps(
            manager
            .worker_health_service
            .list_health(),
            indent=2,
            default=str,
        )
    )

    assert (
        manager
        .worker_health_service
        .get_health(
            "fast-cad-worker"
        )["status"]
        == "healthy"
    )

    assert (
        manager
        .worker_health_service
        .get_health(
            "blender-worker"
        )["status"]
        == "healthy"
    )

    print(
        "\nPASS: JobManager routing integration passed."
    )

    print(
        "PASS: FreeCAD selected the lower-latency worker."
    )

    print(
        "PASS: Blender selected its capable worker."
    )

    print(
        "PASS: Explicit scientific capabilities passed."
    )

    print(
        "PASS: No SSH or scientific workload was executed."
    )

    print(
        f"Temporary test data: {temporary_root}"
    )


if __name__ == "__main__":
    main()