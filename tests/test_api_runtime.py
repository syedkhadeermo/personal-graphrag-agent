import json
import tempfile

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

from app.agent.named_agent_registry import (
    NamedAgent,
    NamedAgentRegistry,
)

from app.agent.tools.tool_registry import (
    ToolRegistry,
)

from app.api.runtime import ApiRuntime


def main() -> None:
    temporary_root = Path(
        tempfile.mkdtemp(
            prefix="api_runtime_test_"
        )
    )

    tool_registry = ToolRegistry()

    tool_registry.register(
        domain="test_domain",
        name="echo",
        function=(
            lambda message: {
                "status": "completed",
                "return_code": 0,
                "echo": message,
            }
        ),
        description="Isolated echo tool.",
    )

    agent_registry = NamedAgentRegistry()

    agent_registry.register(
        NamedAgent(
            agent_id="test-agent",
            description="Isolated test agent.",
            routes=(
                "test_domain:echo",
            ),
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

    runtime = ApiRuntime(
        tool_registry=tool_registry,
        agent_registry=agent_registry,
        job_manager=job_manager,
        dispatcher=dispatcher,
    )

    print("1. Checking initial runtime state...")

    assert runtime.is_running() is False

    initial_status = runtime.status()

    print(
        json.dumps(
            initial_status,
            indent=2,
            default=str,
        )
    )

    assert (
        initial_status[
            "dispatcher_running"
        ]
        is False
    )

    assert initial_status["queue_size"] == 0

    print("\n2. Starting API runtime...")

    start_result = runtime.start()

    print(
        json.dumps(
            start_result,
            indent=2,
            default=str,
        )
    )

    assert start_result["started"] is True
    assert runtime.is_running() is True

    running_status = runtime.status()

    print(
        json.dumps(
            running_status,
            indent=2,
            default=str,
        )
    )

    assert (
        running_status[
            "dispatcher_running"
        ]
        is True
    )

    assert len(
        running_status[
            "dispatcher_workers"
        ]
    ) == 1

    assert (
        running_status[
            "dispatcher_workers"
        ][0]["alive"]
        is True
    )

    assert (
        running_status[
            "tool_domains"
        ]
        == {
            "test_domain": [
                "echo"
            ]
        }
    )

    assert (
        running_status[
            "named_agents"
        ][0]["agent_id"]
        == "test-agent"
    )

    print("\n3. Testing idempotent start...")

    second_start = runtime.start()

    print(
        json.dumps(
            second_start,
            indent=2,
            default=str,
        )
    )

    assert second_start["started"] is False
    assert runtime.is_running() is True

    print("\n4. Stopping API runtime...")

    runtime.stop()

    assert runtime.is_running() is False

    stopped_status = runtime.status()

    print(
        json.dumps(
            stopped_status,
            indent=2,
            default=str,
        )
    )

    assert (
        stopped_status[
            "dispatcher_running"
        ]
        is False
    )

    print(
        "\nPASS: ApiRuntime construction passed."
    )

    print(
        "PASS: Dispatcher lifecycle passed."
    )

    print(
        "PASS: Duplicate start was handled safely."
    )

    print(
        "PASS: Runtime status reporting passed."
    )

    print(
        "PASS: Temporary SQLite isolation passed."
    )

    print(
        f"Temporary test data: {temporary_root}"
    )


if __name__ == "__main__":
    main()