import json
import tempfile

from pathlib import Path

from app.agent.artifacts.artifact_manifest import ArtifactManifest
from app.agent.jobs.job import Job
from app.agent.jobs.job_manager import JobManager
from app.agent.jobs.job_state import JobState
from app.agent.jobs.job_store import JobStore


REMOTE_STEP_PATH = (
    r"C:\AI_Worker\results\remote_freecad_test.step"
)

EXPECTED_SHA256 = (
    "bf0a70ce7d3abeaa45571f422125d4caf"
    "69ca61e2f5c7dcafbf8dcb8128ee616"
)

EXPECTED_SIZE_BYTES = 6863


def main() -> None:
    with tempfile.TemporaryDirectory(
        prefix="job_manager_remote_artifact_test_"
    ) as temporary_directory:

        temporary_root = Path(
            temporary_directory
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

        database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
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
        )

        job = Job(
            job_id="JOB-REMOTE-ARTIFACT-TEST",
            domain="cad_simulation",
            tool="freecad",
            status=JobState.RUNNING.value,
            attempt=1,
            request={
                "_expected_artifacts": [
                    {
                        "type": "remote_file",
                        "path": REMOTE_STEP_PATH,
                        "host": "192.168.137.2",
                        "username": "syed",
                        "extensions": [".step"],
                        "artifact_type": "freecad_step",
                    }
                ]
            },
        )

        job_store.create(
            job
        )

        print(
            "1. First JobManager remote artifact "
            "validation and registration..."
        )

        first_validation = (
            manager._validate_artifacts(
                job
            )
        )

        manifest = ArtifactManifest(
            job_id=job.job_id,
            base_directory=str(
                jobs_directory
            ),
        )

        first_artifacts = (
            manifest.list_artifacts()
        )

        first_manifest_text = (
            manifest.manifest_path.read_text(
                encoding="utf-8"
            )
        )

        print(
            json.dumps(
                first_validation,
                indent=2,
                default=str,
            )
        )

        print(
            "\nArtifacts after first registration:"
        )

        print(
            json.dumps(
                first_artifacts,
                indent=2,
                default=str,
            )
        )

        assert len(first_validation) == 1
        assert first_validation[0]["valid"] is True
        assert manifest.count() == 1

        first_artifact = first_artifacts[0]

        assert (
            first_artifact["sha256"]
            == EXPECTED_SHA256
        )

        assert (
            first_artifact["size_bytes"]
            == EXPECTED_SIZE_BYTES
        )

        assert first_artifact["validated"] is True

        assert (
            first_artifact["metadata"][
                "storage_location"
            ]
            == "remote"
        )

        assert (
            first_artifact["metadata"][
                "remote_host"
            ]
            == "192.168.137.2"
        )

        print(
            "\n2. Repeating through JobManager..."
        )

        second_validation = (
            manager._validate_artifacts(
                job
            )
        )

        second_artifacts = (
            manifest.list_artifacts()
        )

        second_manifest_text = (
            manifest.manifest_path.read_text(
                encoding="utf-8"
            )
        )

        print(
            json.dumps(
                second_validation,
                indent=2,
                default=str,
            )
        )

        print(
            "\nArtifacts after second registration:"
        )

        print(
            json.dumps(
                second_artifacts,
                indent=2,
                default=str,
            )
        )

        print(
            "\nCounts:",
            {
                "after_first": len(
                    first_artifacts
                ),
                "after_second": len(
                    second_artifacts
                ),
            },
        )

        assert len(second_validation) == 1
        assert second_validation[0]["valid"] is True

        assert len(first_artifacts) == 1
        assert len(second_artifacts) == 1
        assert manifest.count() == 1

        assert (
            second_artifacts[0]["artifact_id"]
            == first_artifact["artifact_id"]
        )

        # Duplicate registration must not rewrite or alter
        # the artifact manifest.
        assert (
            second_manifest_text
            == first_manifest_text
        )

        assert job.artifacts == [
            REMOTE_STEP_PATH
        ]

        print(
            "\nPASS: JobManager validated, hashed, "
            "and registered the remote STEP idempotently."
        )

        print(
            "PASS: Temporary SQLite store and job "
            "directory were isolated from production data."
        )


if __name__ == "__main__":
    main()