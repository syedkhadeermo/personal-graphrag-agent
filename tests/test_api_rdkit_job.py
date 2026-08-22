import json
import tempfile
import time

from pathlib import Path

from fastapi.testclient import TestClient

import app.api.main as api_main

from app.agent.jobs.job_dispatcher import (
    JobDispatcher,
)
from app.agent.jobs.job_manager import (
    JobManager,
)
from app.agent.jobs.job_store import (
    JobStore,
)
from app.agent.named_agent_registry import (
    NamedAgent,
    NamedAgentRegistry,
)
from app.agent.tools.default_tools import (
    create_default_registry,
)
from app.api.runtime import (
    ApiRuntime,
)


TERMINAL_STATES = {
    "COMPLETED",
    "FAILED",
    "CANCELLED",
}


def wait_for_api_job(
    client: TestClient,
    job_id: str,
    timeout_seconds: float = 90.0,
    poll_interval: float = 0.1,
) -> dict:

    deadline = (
        time.monotonic()
        + timeout_seconds
    )

    latest: dict = {}

    while time.monotonic() < deadline:

        response = client.get(
            f"/jobs/{job_id}"
        )

        assert response.status_code == 200

        latest = response.json()

        if (
            latest.get("status")
            in TERMINAL_STATES
        ):
            return latest

        time.sleep(
            poll_interval
        )

    raise TimeoutError(
        "API RDKit job did not reach a terminal "
        f"state within {timeout_seconds} seconds. "
        f"Latest response: {latest}"
    )


def main() -> None:

    temporary_root = Path(
        tempfile.mkdtemp(
            prefix="api_rdkit_job_test_"
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
        "1. Creating isolated API runtime..."
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

    tool_registry = (
        create_default_registry()
    )

    agent_registry = (
        NamedAgentRegistry()
    )

    agent_registry.register(
        NamedAgent(
            agent_id="drug-discovery-agent",
            description=(
                "Isolated drug-discovery API agent."
            ),
            routes=(
                "drug_discovery:*",
            ),
            priority=10,
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

    dispatcher = JobDispatcher(
        registry=tool_registry,
        job_manager=job_manager,
        worker_count=1,
        poll_timeout=0.1,
        recover_on_start=True,
        stale_after_seconds=0,
    )

    isolated_runtime = ApiRuntime(
        tool_registry=tool_registry,
        agent_registry=agent_registry,
        job_manager=job_manager,
        dispatcher=dispatcher,
    )

    original_runtime = (
        api_main.runtime
    )

    api_main.runtime = (
        isolated_runtime
    )

    try:

        print(
            "\n2. Starting FastAPI lifespan..."
        )

        with TestClient(
            api_main.app
        ) as client:

            health_response = client.get(
                "/health"
            )

            assert (
                health_response.status_code
                == 200
            )

            health = (
                health_response.json()
            )

            print(
                json.dumps(
                    health,
                    indent=2,
                )
            )

            assert (
                health[
                    "dispatcher_running"
                ]
                is True
            )

            print(
                "\n3. Verifying RDKit API discovery..."
            )

            capabilities_response = (
                client.get(
                    "/capabilities"
                )
            )

            assert (
                capabilities_response.status_code
                == 200
            )

            capabilities = (
                capabilities_response.json()
            )

            print(
                json.dumps(
                    capabilities,
                    indent=2,
                )
            )

            assert (
                "rdkit_descriptors"
                in capabilities[
                    "domains"
                ][
                    "drug_discovery"
                ]
            )

            print(
                "\n4. Submitting RDKit job through POST /jobs..."
            )

            submission_response = (
                client.post(
                    "/jobs",
                    json={
                        "domain":
                            "drug_discovery",

                        "tool":
                            "rdkit_descriptors",

                        "request": {
                            "smiles":
                                "CC(=O)Oc1ccccc1C(=O)O",

                            "timeout":
                                60,
                        },

                        "artifacts":
                            [],

                        "max_attempts":
                            1,
                    },
                )
            )

            print(
                "Status code:",
                submission_response.status_code,
            )

            print(
                json.dumps(
                    submission_response.json(),
                    indent=2,
                )
            )

            assert (
                submission_response.status_code
                == 202
            )

            submission = (
                submission_response.json()
            )

            job_id = submission["job_id"]

            assert job_id
            assert (
                submission["agent_id"]
                == "drug-discovery-agent"
            )
            assert (
                submission["domain"]
                == "drug_discovery"
            )
            assert (
                submission["tool"]
                == "rdkit_descriptors"
            )
            assert (
                submission["status"]
                == "submitted"
            )

            print(
                "\n5. Polling GET /jobs/{job_id}..."
            )

            job = wait_for_api_job(
                client=client,
                job_id=job_id,
            )

            print(
                json.dumps(
                    job,
                    indent=2,
                    default=str,
                )
            )

            assert (
                job["status"]
                == "COMPLETED"
            )
            assert (
                job["domain"]
                == "drug_discovery"
            )
            assert (
                job["tool"]
                == "rdkit_descriptors"
            )
            assert job["attempt"] == 1
            assert job["max_attempts"] == 1
            assert job["error"] is None

            print(
                "\n6. Verifying persisted RDKit result..."
            )

            result = job["result"]

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
                result["rules"][
                    "lipinski"
                ][
                    "passed"
                ]
                is True
            )

            assert (
                result["rules"][
                    "veber"
                ][
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

                        "qed":
                            result[
                                "descriptors"
                            ][
                                "qed"
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
                "\n7. Verifying durable SQLite state..."
            )

            persisted = job_store.get(
                job_id
            )

            assert persisted is not None
            assert (
                persisted["status"]
                == "COMPLETED"
            )
            assert (
                persisted["result"]
                == result
            )
            assert (
                persisted["request"][
                    "_delegated_agent_id"
                ]
                == "drug-discovery-agent"
            )

        print(
            "\n8. Verifying API shutdown..."
        )

        assert (
            isolated_runtime.dispatcher.is_running()
            is False
        )

        print(
            "\nPASS: POST /jobs accepted the RDKit workload."
        )
        print(
            "PASS: Named-agent delegation selected the drug-discovery agent."
        )
        print(
            "PASS: API dispatcher executed RDKit asynchronously."
        )
        print(
            "PASS: GET /jobs/{job_id} returned the completed result."
        )
        print(
            "PASS: SQLite persisted the RDKit result and delegation identity."
        )
        print(
            "PASS: FastAPI lifespan started and stopped the dispatcher."
        )
        print(
            "PASS: Production jobs.db was not used."
        )
        print(
            "PASS: No docking, GROMACS, SSH, or remote worker was used."
        )

    finally:

        if isolated_runtime.dispatcher.is_running():
            isolated_runtime.stop()

        api_main.runtime = (
            original_runtime
        )

        print(
            "Temporary test data: "
            f"{temporary_root}"
        )


if __name__ == "__main__":
    main()