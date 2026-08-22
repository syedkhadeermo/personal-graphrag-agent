import json
import tempfile
import time

from pathlib import Path

from app.agent.jobs.job_dispatcher import (
    JobDispatcher,
)
from app.agent.jobs.job_manager import (
    JobManager,
)
from app.agent.jobs.job_store import (
    JobStore,
)
from app.agent.tools.default_tools import (
    create_default_registry,
)


TERMINAL_STATES = {
    "COMPLETED",
    "FAILED",
    "CANCELLED",
}


def wait_for_terminal_job(
    job_store: JobStore,
    job_id: str,
    timeout_seconds: float = 90.0,
    poll_interval: float = 0.1,
) -> dict:

    deadline = (
        time.monotonic()
        + timeout_seconds
    )

    while time.monotonic() < deadline:

        record = job_store.get(
            job_id
        )

        if (
            record is not None
            and record.get("status")
            in TERMINAL_STATES
        ):
            return record

        time.sleep(
            poll_interval
        )

    latest = job_store.get(
        job_id
    )

    raise TimeoutError(
        "RDKit job did not reach a terminal state "
        f"within {timeout_seconds} seconds. "
        f"Latest record: {latest}"
    )


def main() -> None:

    temporary_root = Path(
        tempfile.mkdtemp(
            prefix="rdkit_dispatcher_test_"
        )
    )

    database_path = (
        temporary_root
        / "state"
        / "jobs.db"
    )

    job_directory = (
        temporary_root
        / "jobs"
    )

    database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "1. Creating isolated persistent pipeline..."
    )

    print(
        json.dumps(
            {
                "temporary_root":
                    str(temporary_root),

                "database_path":
                    str(database_path),

                "job_directory":
                    str(job_directory),
            },
            indent=2,
        )
    )

    job_store = JobStore(
        database_path=str(
            database_path
        )
    )

    job_manager = JobManager(
        base_directory=str(
            job_directory
        ),
        job_store=job_store,
    )

    registry = create_default_registry()

    dispatcher = JobDispatcher(
        registry=registry,
        job_manager=job_manager,
        worker_count=1,
        poll_timeout=0.1,
        recover_on_start=True,
        stale_after_seconds=0,
    )

    try:

        print(
            "\n2. Starting JobDispatcher..."
        )

        start_result = dispatcher.start()

        print(
            json.dumps(
                start_result,
                indent=2,
            )
        )

        assert dispatcher.is_running()
        assert (
            start_result.get("started")
            is True
        )

        print(
            "\n3. Submitting persistent RDKit job..."
        )

        job_id = (
            dispatcher.create_and_submit(
                domain="drug_discovery",
                tool="rdkit_descriptors",
                request={
                    "smiles":
                        "CC(=O)Oc1ccccc1C(=O)O",

                    "timeout":
                        60,
                },
                artifacts=[],
                max_attempts=1,
            )
        )

        print(
            json.dumps(
                {
                    "job_id": job_id,
                    "status": "submitted",
                },
                indent=2,
            )
        )

        assert job_id
        assert (
            job_store.get(job_id)
            is not None
        )

        print(
            "\n4. Waiting for asynchronous RDKit execution..."
        )

        record = wait_for_terminal_job(
            job_store=job_store,
            job_id=job_id,
        )

        print(
            json.dumps(
                record,
                indent=2,
                default=str,
            )
        )

        assert record["job_id"] == job_id
        assert (
            record["domain"]
            == "drug_discovery"
        )
        assert (
            record["tool"]
            == "rdkit_descriptors"
        )
        assert record["status"] == "COMPLETED"
        assert record["attempt"] == 1
        assert record["max_attempts"] == 1
        assert record["error"] is None

        print(
            "\n5. Verifying persisted RDKit result..."
        )

        result = record["result"]

        assert isinstance(
            result,
            dict,
        )

        assert result["status"] == "completed"
        assert result["tool"] == "RDKit"
        assert (
            result["domain"]
            == "drug_discovery"
        )
        assert result["return_code"] == 0
        assert result["valid"] is True

        assert (
            result["canonical_smiles"]
            == "CC(=O)Oc1ccccc1C(=O)O"
        )

        assert (
            result["molecular_formula"]
            == "C9H8O4"
        )

        assert round(
            result["descriptors"][
                "molecular_weight"
            ],
            3,
        ) == 180.159

        assert (
            result["descriptors"][
                "h_bond_acceptors"
            ]
            == 3
        )

        assert (
            result["descriptors"][
                "h_bond_donors"
            ]
            == 1
        )

        assert (
            result["rules"]["lipinski"][
                "passed"
            ]
            is True
        )

        assert (
            result["rules"]["veber"][
                "passed"
            ]
            is True
        )

        print(
            json.dumps(
                {
                    "canonical_smiles":
                        result[
                            "canonical_smiles"
                        ],

                    "molecular_formula":
                        result[
                            "molecular_formula"
                        ],

                    "molecular_weight":
                        result[
                            "descriptors"
                        ][
                            "molecular_weight"
                        ],

                    "lipinski_passed":
                        result[
                            "rules"
                        ][
                            "lipinski"
                        ][
                            "passed"
                        ],

                    "veber_passed":
                        result[
                            "rules"
                        ][
                            "veber"
                        ][
                            "passed"
                        ],
                },
                indent=2,
            )
        )

        print(
            "\n6. Verifying durable SQLite state..."
        )

        persisted = job_store.get(
            job_id
        )

        assert persisted is not None
        assert (
            persisted["status"]
            == "COMPLETED"
        )
        assert persisted["result"] == result
        assert (
            job_store.count(
                domain="drug_discovery"
            )
            == 1
        )
        assert (
            dispatcher.queue_size()
            == 0
        )

        print(
            "\nPASS: RDKit persistent job submission passed."
        )
        print(
            "PASS: Existing JobDispatcher executed RDKit asynchronously."
        )
        print(
            "PASS: SQLite persisted the completed RDKit result."
        )
        print(
            "PASS: Aspirin descriptors and drug-likeness rules passed."
        )
        print(
            "PASS: Temporary job data was isolated from production."
        )
        print(
            "PASS: No docking, GROMACS, SSH, or remote worker was used."
        )

    finally:

        dispatcher.stop(
            wait=True,
            timeout=10.0,
        )

        print(
            "Temporary test data: "
            f"{temporary_root}"
        )


if __name__ == "__main__":
    main()