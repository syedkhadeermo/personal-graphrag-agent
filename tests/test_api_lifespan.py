import json
import tempfile
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
    )

    agent_registry = NamedAgentRegistry()

    agent_registry.register(
        NamedAgent(
            agent_id="test-agent",
            description="Isolated API agent.",
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

    return ApiRuntime(
        tool_registry=tool_registry,
        agent_registry=agent_registry,
        job_manager=job_manager,
        dispatcher=dispatcher,
    )


def main() -> None:
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
    )

    temporary_root = Path(
        tempfile.mkdtemp(
            prefix="api_lifespan_test_"
        )
    )

    test_runtime = create_isolated_runtime(
        temporary_root
    )

    original_runtime = api_main.runtime

    api_main.runtime = test_runtime
    api_main.app.state.runtime = test_runtime

    print(
        "1. Verifying dispatcher is stopped "
        "before API lifespan..."
    )

    assert test_runtime.is_running() is False

    try:
        print(
            "\n2. Entering FastAPI lifespan..."
        )

        with TestClient(
            api_main.app
        ) as client:

            assert (
                test_runtime.is_running()
                is True
            )

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

            runtime_response = client.get(
                "/runtime"
            )

            assert (
                runtime_response.status_code
                == 200
            )

            status = (
                runtime_response.json()
            )

            print(
                json.dumps(
                    status,
                    indent=2,
                )
            )

            assert (
                status[
                    "dispatcher_running"
                ]
                is True
            )

            assert len(
                status[
                    "dispatcher_workers"
                ]
            ) == 1

            assert (
                status[
                    "dispatcher_workers"
                ][0]["alive"]
                is True
            )

            agents_response = client.get(
                "/agents"
            )

            assert (
                agents_response.status_code
                == 200
            )

            assert (
                agents_response.json()[
                    "agents"
                ][0]["agent_id"]
                == "test-agent"
            )

        print(
            "\n3. Verifying shutdown after "
            "FastAPI lifespan..."
        )

        assert (
            test_runtime.is_running()
            is False
        )

    finally:
        api_main.runtime = (
            original_runtime
        )

        api_main.app.state.runtime = (
            original_runtime
        )

    print(
        "\nPASS: FastAPI lifespan started "
        "the dispatcher."
    )

    print(
        "PASS: GET /health reported "
        "dispatcher_running=True."
    )

    print(
        "PASS: GET /runtime reported "
        "the worker thread."
    )

    print(
        "PASS: FastAPI shutdown stopped "
        "the dispatcher."
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
