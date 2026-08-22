import json
import tempfile

from pathlib import Path
from threading import Lock

from app.agent.agent_delegation_service import (
    AgentDelegationService,
)

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


def main() -> None:
    temporary_root = Path(
        tempfile.mkdtemp(
            prefix=(
                "agent_delegation_dispatcher_test_"
            )
        )
    )

    received_requests = []
    received_lock = Lock()

    def echo_tool(
        message: str,
    ) -> dict:
        """
        Simulated tool.

        Its strict signature proves internal orchestration
        metadata was removed before execution.
        """

        with received_lock:
            received_requests.append(
                {
                    "message": message,
                }
            )

        return {
            "status": "completed",
            "return_code": 0,
            "echo": message,
            "stdout": message,
            "stderr": "",
        }

    print("1. Creating isolated persistent pipeline...")

    tool_registry = ToolRegistry()

    tool_registry.register(
        domain="test_domain",
        name="echo",
        function=echo_tool,
        description="Isolated echo tool.",
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

    agent_registry = NamedAgentRegistry()

    agent_registry.register(
        NamedAgent(
            agent_id="echo-agent",
            description=(
                "Handles isolated echo jobs."
            ),
            routes=(
                "test_domain:echo",
            ),
            priority=10,
        )
    )

    delegation_service = (
        AgentDelegationService(
            agent_registry=agent_registry,
            dispatcher=dispatcher,
        )
    )

    print("\n2. Starting existing JobDispatcher...")

    start_result = dispatcher.start()

    print(
        json.dumps(
            start_result,
            indent=2,
        )
    )

    assert start_result["started"] is True
    assert dispatcher.is_running() is True

    try:
        print(
            "\n3. Delegating through named agent..."
        )

        delegation = (
            delegation_service.delegate(
                domain="test_domain",
                tool="echo",
                request={
                    "message":
                        "agent-pipeline-ok",
                },
                max_attempts=1,
            )
        )

        print(
            json.dumps(
                delegation,
                indent=2,
            )
        )

        assert (
            delegation["agent_id"]
            == "echo-agent"
        )

        job_id = delegation["job_id"]

        print(
            "\n4. Waiting for persistent "
            "asynchronous execution..."
        )

        dispatcher.wait_until_idle()

        stored = job_store.get(
            job_id
        )

        print(
            json.dumps(
                stored,
                indent=2,
                default=str,
            )
        )

        assert stored is not None

        assert (
            stored["status"]
            == JobState.COMPLETED.value
        )

        assert stored["attempt"] == 1
        assert stored["error"] is None

        assert (
            stored["result"]["echo"]
            == "agent-pipeline-ok"
        )

        print(
            "\n5. Verifying durable delegation "
            "identity..."
        )

        assert (
            stored["request"][
                "_delegated_agent_id"
            ]
            == "echo-agent"
        )

        assert (
            stored["request"][
                "_delegation_route"
            ]
            == "test_domain:echo"
        )

        assert (
            stored["request"]["message"]
            == "agent-pipeline-ok"
        )

        print(
            json.dumps(
                {
                    "delegated_agent_id":
                        stored["request"][
                            "_delegated_agent_id"
                        ],

                    "delegation_route":
                        stored["request"][
                            "_delegation_route"
                        ],
                },
                indent=2,
            )
        )

        print(
            "\n6. Verifying internal metadata "
            "was not sent to the tool..."
        )

        with received_lock:
            captured = list(
                received_requests
            )

        print(
            json.dumps(
                captured,
                indent=2,
            )
        )

        assert captured == [
            {
                "message":
                    "agent-pipeline-ok"
            }
        ]

    finally:
        dispatcher.stop(
            wait=True,
            timeout=5.0,
        )

    assert dispatcher.is_running() is False

    print(
        "\nPASS: Named agent selected the job route."
    )

    print(
        "PASS: Existing dispatcher executed the job."
    )

    print(
        "PASS: SQLite persisted the completed job."
    )

    print(
        "PASS: Delegation identity remained durable."
    )

    print(
        "PASS: Internal metadata was removed "
        "before tool execution."
    )

    print(
        "PASS: Lightweight orchestration pipeline passed."
    )

    print(
        f"Temporary test data: {temporary_root}"
    )


if __name__ == "__main__":
    main()