import json
import socket
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.api.main as api_main
from app.agent.jobs.job_dispatcher import JobDispatcher
from app.agent.jobs.job_manager import JobManager
from app.agent.jobs.job_store import JobStore
from app.agent.named_agent_registry import NamedAgent, NamedAgentRegistry
from app.agent.tools.default_tools import create_default_registry
from app.api.runtime import ApiRuntime


TERMINAL_STATES = {"COMPLETED", "FAILED", "CANCELLED"}


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False


def fake_create_connection(address, timeout):
    host, port = address
    assert host == "192.168.137.2"
    assert timeout == 1.0

    if port == 22:
        return FakeConnection()
    if port == 445:
        raise ConnectionRefusedError()
    raise socket.timeout()


def wait_for_api_job(
    client: TestClient,
    job_id: str,
    timeout_seconds: float = 30.0,
    poll_interval: float = 0.05,
) -> dict:
    deadline = time.monotonic() + timeout_seconds
    latest: dict = {}

    while time.monotonic() < deadline:
        response = client.get(f"/jobs/{job_id}")
        assert response.status_code == 200
        latest = response.json()

        if latest.get("status") in TERMINAL_STATES:
            return latest

        time.sleep(poll_interval)

    raise TimeoutError(
        "API cybersecurity job did not reach a terminal state "
        f"within {timeout_seconds} seconds. Latest response: {latest}"
    )


def main() -> None:
    temporary_root = Path(
        tempfile.mkdtemp(prefix="api_cybersecurity_job_test_")
    )
    database_path = temporary_root / "state" / "jobs.db"
    job_directory = temporary_root / "jobs"
    database_path.parent.mkdir(parents=True, exist_ok=True)

    print("1. Creating isolated cybersecurity API runtime...")
    print(
        json.dumps(
            {
                "temporary_root": str(temporary_root),
                "database_path": str(database_path),
                "job_directory": str(job_directory),
            },
            indent=2,
        )
    )

    tool_registry = create_default_registry()
    agent_registry = NamedAgentRegistry()
    agent_registry.register(
        NamedAgent(
            agent_id="cybersecurity-agent",
            description="Isolated authorized defensive-security API agent.",
            routes=("cybersecurity:*",),
            priority=10,
        )
    )

    job_store = JobStore(database_path=str(database_path))
    job_manager = JobManager(
        base_directory=str(job_directory),
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

    original_runtime = api_main.runtime
    api_main.runtime = isolated_runtime

    try:
        print("\n2. Starting FastAPI lifespan...")

        with patch(
            "socket.create_connection",
            side_effect=fake_create_connection,
        ):
            with TestClient(api_main.app) as client:
                health_response = client.get("/health")
                assert health_response.status_code == 200
                health = health_response.json()
                print(json.dumps(health, indent=2))
                assert health["dispatcher_running"] is True

                print("\n3. Verifying cybersecurity API discovery...")
                capabilities_response = client.get("/capabilities")
                assert capabilities_response.status_code == 200
                capabilities = capabilities_response.json()
                print(json.dumps(capabilities, indent=2))
                assert (
                    "vulnerability_scan"
                    in capabilities["domains"]["cybersecurity"]
                )

                print("\n4. Submitting authorized assessment through POST /jobs...")
                submission_response = client.post(
                    "/jobs",
                    json={
                        "domain": "cybersecurity",
                        "tool": "vulnerability_scan",
                        "request": {
                            "target": "192.168.137.2",
                            "ports": [22, 445, 8000],
                            "authorization_confirmed": True,
                            "timeout": 1.0,
                        },
                        "artifacts": [],
                        "max_attempts": 1,
                    },
                )
                print("Status code:", submission_response.status_code)
                print(json.dumps(submission_response.json(), indent=2))
                assert submission_response.status_code == 202

                submission = submission_response.json()
                job_id = submission["job_id"]
                assert job_id
                assert submission["agent_id"] == "cybersecurity-agent"
                assert submission["domain"] == "cybersecurity"
                assert submission["tool"] == "vulnerability_scan"
                assert submission["status"] == "submitted"

                print("\n5. Polling GET /jobs/{job_id}...")
                job = wait_for_api_job(client=client, job_id=job_id)
                print(json.dumps(job, indent=2, default=str))

                assert job["status"] == "COMPLETED"
                assert job["domain"] == "cybersecurity"
                assert job["tool"] == "vulnerability_scan"
                assert job["attempt"] == 1
                assert job["max_attempts"] == 1
                assert job["error"] is None

                print("\n6. Verifying structured assessment result...")
                result = job["result"]
                assert result["status"] == "completed"
                assert result["tool"] == "Defensive TCP Assessment"
                assert result["domain"] == "cybersecurity"
                assert result["authorization_confirmed"] is True
                assert result["target"] == "192.168.137.2"
                assert result["summary"]["open_ports"] == [22]
                assert result["summary"]["open_count"] == 1
                assert result["methodology_reference"]["standard"] == "NIST SP 800-115"

                states = {
                    item["port"]: item["state"]
                    for item in result["observations"]
                }
                assert states == {
                    22: "open",
                    445: "closed",
                    8000: "filtered_or_unresponsive",
                }

                print(
                    json.dumps(
                        {
                            "target": result["target"],
                            "assessment_type": result["assessment_type"],
                            "open_ports": result["summary"]["open_ports"],
                            "states": states,
                            "standard": result["methodology_reference"]["standard"],
                        },
                        indent=2,
                    )
                )

                print("\n7. Verifying durable SQLite state...")
                persisted = job_store.get(job_id)
                assert persisted is not None
                assert persisted["status"] == "COMPLETED"
                assert persisted["result"] == result
                assert (
                    persisted["request"]["_delegated_agent_id"]
                    == "cybersecurity-agent"
                )
                assert (
                    persisted["request"]["_delegation_route"]
                    == "cybersecurity:vulnerability_scan"
                )

        print("\n8. Verifying API shutdown...")
        assert isolated_runtime.dispatcher.is_running() is False

        print("\nPASS: POST /jobs accepted the authorized security workload.")
        print("PASS: Named-agent delegation selected the cybersecurity agent.")
        print("PASS: API dispatcher executed the assessment asynchronously.")
        print("PASS: GET /jobs/{job_id} returned the structured result.")
        print("PASS: SQLite persisted the result and delegation identity.")
        print("PASS: NIST SP 800-115 methodology metadata passed.")
        print("PASS: FastAPI lifespan started and stopped the dispatcher.")
        print("PASS: Production jobs.db was not used.")
        print("PASS: No real network connection or exploitation was performed.")

    finally:
        if isolated_runtime.dispatcher.is_running():
            isolated_runtime.stop()

        api_main.runtime = original_runtime
        api_main.app.state.runtime = original_runtime
        print(f"Temporary test data: {temporary_root}")


if __name__ == "__main__":
    main()


def test_main() -> None:
    main()
