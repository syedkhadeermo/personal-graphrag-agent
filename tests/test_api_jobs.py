import json
import tempfile
import time
import warnings

from pathlib import Path

from fastapi.testclient import TestClient

import app.api.main as api_main

from app.agent.jobs.job_dispatcher import (
    JobDispatcher,
)

from app.agent.jobs.job_manager import (
    JobManager,
)

from app.agent.jobs.job_state import (
    JobState,
)

from app.agent.jobs.job_store import (
    JobStore,
)

from app.agent.named_agent_registry import (
    NamedAgent,
    NamedAgentRegistry,
)

from app.agent.tools.tool_registry import (
    ToolRegistry,
)

from app.api.runtime import ApiRuntime


def create_isolated_runtime(
    temporary_root: Path,
) -> ApiRuntime:
    def echo_tool(
        message: str,
    ) -> dict:
        """
        Strict signature proves that internal delegation
        metadata is removed before execution.
        """

        return {
            "status": "completed",
            "return_code": 0,
            "echo": message,
            "stdout": message,
            "stderr": "",
        }

    tool_registry = ToolRegistry()

    tool_registry.register(
        domain="test_domain",
        name="echo",
        function=echo_tool,
        description="Isolated API echo tool.",
    )

    agent_registry = NamedAgentRegistry()

    agent_registry.register(
        NamedAgent(
            agent_id="test-agent",
            description="Handles the echo route.",
            routes=(
                "test_domain:echo",
            ),
            priority=10,
        )
    )

    agent_registry.register(
        NamedAgent(
            agent_id="other-agent",
            description="Handles another domain.",
            routes=(
                "other_domain:*",
            ),
            priority=10,
        )
    )

    job_store = JobStore(
        database_path=str(
            temporary_root
            / "state"
            / "jobs.db"
        )
    )

    job_manager = JobManager(
        base_directory=str(
            temporary_root
            / "jobs"
        ),
        job_store=job_store,
    )

    dispatcher = JobDispatcher(
        registry=tool_registry,
        job_manager=job_manager,
        worker_count=1,
        poll_timeout=0.05,
        recover_on_start=False,
    )

    return ApiRuntime(
        tool_registry=tool_registry,
        agent_registry=agent_registry,
        job_manager=job_manager,
        dispatcher=dispatcher,
    )


def wait_for_terminal_job(
    client: TestClient,
    job_id: str,
    timeout_seconds: float = 5.0,
) -> dict:
    deadline = (
        time.perf_counter()
        + timeout_seconds
    )

    while time.perf_counter() < deadline:
        response = client.get(
            f"/jobs/{job_id}"
        )

        assert response.status_code == 200

        job = response.json()

        if job["status"] in {
            JobState.COMPLETED.value,
            JobState.FAILED.value,
            JobState.TIMED_OUT.value,
            JobState.CANCELLED.value,
            JobState.RECOVERY_REQUIRED.value,
        }:
            return job

        time.sleep(0.05)

    raise TimeoutError(
        f"Job did not finish: {job_id}"
    )


def main() -> None:
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
    )

    temporary_root = Path(
        tempfile.mkdtemp(
            prefix="api_jobs_test_"
        )
    )

    test_runtime = create_isolated_runtime(
        temporary_root
    )

    original_runtime = api_main.runtime

    api_main.runtime = test_runtime
    api_main.app.state.runtime = test_runtime

    try:
        with TestClient(
            api_main.app
        ) as client:

            print(
                "1. Submitting a delegated API job..."
            )

            response = client.post(
                "/jobs",
                json={
                    "domain": "test_domain",
                    "tool": "echo",
                    "request": {
                        "message":
                            "api-pipeline-ok"
                    },
                    "max_attempts": 1,
                },
            )

            print(
                "Status code:",
                response.status_code,
            )

            print(
                json.dumps(
                    response.json(),
                    indent=2,
                )
            )

            assert response.status_code == 202

            submission = response.json()

            assert (
                submission["agent_id"]
                == "test-agent"
            )

            assert (
                submission["status"]
                == "submitted"
            )

            job_id = submission["job_id"]

            print(
                "\n2. Polling durable job state..."
            )

            job = wait_for_terminal_job(
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
                == JobState.COMPLETED.value
            )

            assert job["attempt"] == 1
            assert job["error"] is None

            assert (
                job["result"]["echo"]
                == "api-pipeline-ok"
            )

            assert (
                job["request"][
                    "_delegated_agent_id"
                ]
                == "test-agent"
            )

            assert (
                job["request"][
                    "_delegation_route"
                ]
                == "test_domain:echo"
            )

            print(
                "\n3. Testing explicit authorized "
                "agent submission..."
            )

            explicit_response = client.post(
                "/jobs",
                json={
                    "domain": "test_domain",
                    "tool": "echo",
                    "agent_id": "test-agent",
                    "request": {
                        "message":
                            "explicit-agent-ok"
                    },
                    "max_attempts": 1,
                },
            )

            assert (
                explicit_response.status_code
                == 202
            )

            assert (
                explicit_response.json()[
                    "agent_id"
                ]
                == "test-agent"
            )

            explicit_job = wait_for_terminal_job(
                client=client,
                job_id=(
                    explicit_response.json()[
                        "job_id"
                    ]
                ),
            )

            assert (
                explicit_job["status"]
                == JobState.COMPLETED.value
            )

            print(
                "\n4. Rejecting unauthorized agent..."
            )

            forbidden_response = client.post(
                "/jobs",
                json={
                    "domain": "test_domain",
                    "tool": "echo",
                    "agent_id": "other-agent",
                    "request": {
                        "message": "forbidden"
                    },
                },
            )

            print(
                forbidden_response.status_code,
                forbidden_response.json(),
            )

            assert (
                forbidden_response.status_code
                == 403
            )

            print(
                "\n5. Rejecting unknown tool..."
            )

            unknown_tool_response = client.post(
                "/jobs",
                json={
                    "domain": "test_domain",
                    "tool": "missing_tool",
                },
            )

            print(
                unknown_tool_response.status_code,
                unknown_tool_response.json(),
            )

            assert (
                unknown_tool_response.status_code
                == 404
            )

            print(
                "\n6. Rejecting missing job..."
            )

            missing_job_response = client.get(
                "/jobs/JOB-DOES-NOT-EXIST"
            )

            print(
                missing_job_response.status_code,
                missing_job_response.json(),
            )

            assert (
                missing_job_response.status_code
                == 404
            )

    finally:
        api_main.runtime = (
            original_runtime
        )

        api_main.app.state.runtime = (
            original_runtime
        )

    assert test_runtime.is_running() is False

    print(
        "\nPASS: POST /jobs returned HTTP 202."
    )

    print(
        "PASS: Named-agent delegation passed through API."
    )

    print(
        "PASS: Dispatcher completed the persistent job."
    )

    print(
        "PASS: GET /jobs/{job_id} returned durable state."
    )

    print(
        "PASS: Explicit authorization and error "
        "responses passed."
    )

    print(
        "PASS: Production jobs.db was not used."
    )

    print(
        f"Temporary test data: {temporary_root}"
    )


if __name__ == "__main__":
    main()


def test_main() -> None:
    main()
