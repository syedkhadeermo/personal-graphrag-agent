import json
import tempfile

from pathlib import Path

from app.agent.artifacts.artifact_manifest import ArtifactManifest
from app.agent.workers.remote_compute_worker import RemoteComputeWorker


REMOTE_HOST = "192.168.137.2"
REMOTE_USERNAME = "syed"

REMOTE_STEP_PATH = (
    r"C:\AI_Worker\results\remote_freecad_test.step"
)

EXPECTED_SHA256 = (
    "bf0a70ce7d3abeaa45571f422125d4caf"
    "69ca61e2f5c7dcafbf8dcb8128ee616"
)

EXPECTED_SIZE_BYTES = 6863


def main() -> None:
    worker = RemoteComputeWorker(
        host=REMOTE_HOST,
        username=REMOTE_USERNAME,
    )

    print("1. Validating remote STEP artifact...")

    validation = worker.validate_remote_file(
        path=REMOTE_STEP_PATH,
        expected_extensions=(".step",),
        timeout=30,
    )

    print(
        json.dumps(
            validation,
            indent=2,
            default=str,
        )
    )

    assert validation["exists"] is True
    assert validation["extension_valid"] is True
    assert validation["valid"] is True
    assert validation["size_bytes"] == EXPECTED_SIZE_BYTES

    print("\n2. Calculating remote SHA-256...")

    hash_result = worker.calculate_remote_sha256(
        path=REMOTE_STEP_PATH,
        timeout=120,
    )

    print(
        json.dumps(
            hash_result,
            indent=2,
            default=str,
        )
    )

    assert hash_result["exists"] is True
    assert hash_result["valid"] is True
    assert hash_result["size_bytes"] == EXPECTED_SIZE_BYTES
    assert hash_result["sha256"] == EXPECTED_SHA256

    print("\n3. Registering the remote artifact twice...")

    with tempfile.TemporaryDirectory(
        prefix="remote_artifact_manifest_test_"
    ) as temporary_directory:

        manifest = ArtifactManifest(
            job_id="REMOTE-ARTIFACT-TEST",
            base_directory=temporary_directory,
        )

        first_registration = (
            manifest.register_remote_artifact(
                remote_hash_result=hash_result,
                artifact_type="freecad_step",
                validated=validation["valid"],
                metadata={
                    "tool": "FreeCAD",
                    "validation": validation,
                },
                attempt=1,
            )
        )

        count_after_first = manifest.count()

        second_registration = (
            manifest.register_remote_artifact(
                remote_hash_result=hash_result,
                artifact_type="freecad_step",
                validated=validation["valid"],
                metadata={
                    "tool": "FreeCAD",
                    "validation": validation,
                },
                attempt=1,
            )
        )

        count_after_second = manifest.count()

        print("\nFirst registration:")
        print(
            json.dumps(
                first_registration,
                indent=2,
                default=str,
            )
        )

        print("\nSecond registration:")
        print(
            json.dumps(
                second_registration,
                indent=2,
                default=str,
            )
        )

        print("\nManifest:")
        print(
            Path(
                manifest.manifest_path
            ).read_text(
                encoding="utf-8"
            )
        )

        print(
            "\nCounts:",
            {
                "after_first": count_after_first,
                "after_second": count_after_second,
            },
        )

        assert first_registration["created"] is True
        assert first_registration["duplicate"] is False

        assert second_registration["created"] is False
        assert second_registration["duplicate"] is True

        assert (
            first_registration["artifact"]["artifact_id"]
            == second_registration["artifact"]["artifact_id"]
        )

        assert count_after_first == 1
        assert count_after_second == 1
        assert manifest.count() == 1

    print(
        "\nPASS: Remote STEP artifact registration "
        "is SHA-256 idempotent."
    )


if __name__ == "__main__":
    main()