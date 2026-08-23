import json

from app.agent.agent_delegation_service import (
    AgentDelegationService,
)

from app.agent.named_agent_registry import (
    NamedAgent,
    NamedAgentRegistry,
)


class RecordingDispatcher:
    """
    Records submissions without SQLite, threads, or execution.
    """

    def __init__(
        self,
    ):
        self.submissions = []
        self.counter = 0

    def create_and_submit(
        self,
        domain,
        tool,
        request=None,
        artifacts=None,
        max_attempts=None,
    ):
        self.counter += 1

        job_id = (
            f"TEST-JOB-{self.counter:03d}"
        )

        self.submissions.append(
            {
                "job_id":
                    job_id,

                "domain":
                    domain,

                "tool":
                    tool,

                "request":
                    dict(
                        request or {}
                    ),

                "artifacts":
                    list(
                        artifacts or []
                    ),

                "max_attempts":
                    max_attempts,
            }
        )

        return job_id


def main() -> None:
    registry = NamedAgentRegistry()

    registry.register(
        NamedAgent(
            agent_id="drug-agent",
            description=(
                "Drug-discovery specialist."
            ),
            routes=(
                "drug_discovery:*",
            ),
            priority=10,
        )
    )

    registry.register(
        NamedAgent(
            agent_id="engineering-agent",
            description=(
                "FreeCAD and OpenFOAM specialist."
            ),
            routes=(
                "cad_simulation:freecad",
                "cad_simulation:openfoam",
            ),
            priority=10,
        )
    )

    registry.register(
        NamedAgent(
            agent_id="rendering-agent",
            description=(
                "Blender rendering specialist."
            ),
            routes=(
                "cad_simulation:blender",
            ),
            priority=10,
        )
    )

    dispatcher = RecordingDispatcher()

    service = AgentDelegationService(
        agent_registry=registry,
        dispatcher=dispatcher,
    )

    print(
        "1. Automatically delegating docking..."
    )

    docking = service.delegate(
        domain="drug_discovery",
        tool="docking",
        request={
            "receptor": "protein.pdbqt",
            "ligand": "ligand.pdbqt",
        },
        max_attempts=3,
    )

    print(
        json.dumps(
            docking,
            indent=2,
        )
    )

    assert docking == {
        "job_id": "TEST-JOB-001",
        "agent_id": "drug-agent",
        "domain": "drug_discovery",
        "tool": "docking",
        "status": "submitted",
    }

    docking_submission = (
        dispatcher.submissions[0]
    )

    assert (
        docking_submission["request"][
            "_delegated_agent_id"
        ]
        == "drug-agent"
    )

    assert (
        docking_submission["request"][
            "_delegation_route"
        ]
        == "drug_discovery:docking"
    )

    assert (
        docking_submission["request"][
            "receptor"
        ]
        == "protein.pdbqt"
    )

    print(
        "\n2. Automatically delegating FreeCAD..."
    )

    freecad = service.delegate(
        domain="cad_simulation",
        tool="freecad",
        request={
            "script_path":
                r"C:\AI_Worker\scripts\model.py"
        },
        artifacts=[
            {
                "type": "remote_file",
                "path": (
                    r"C:\AI_Worker\results"
                    r"\model.step"
                ),
            }
        ],
    )

    print(
        json.dumps(
            freecad,
            indent=2,
        )
    )

    assert (
        freecad["agent_id"]
        == "engineering-agent"
    )

    assert freecad["job_id"] == "TEST-JOB-002"

    print(
        "\n3. Explicitly delegating Blender..."
    )

    blender = service.delegate_to(
        agent_id="rendering-agent",
        domain="cad_simulation",
        tool="blender",
        request={
            "script_path":
                r"C:\AI_Worker\scripts\render.py"
        },
    )

    assert (
        blender["agent_id"]
        == "rendering-agent"
    )

    assert blender["job_id"] == "TEST-JOB-003"

    print(
        json.dumps(
            blender,
            indent=2,
        )
    )

    print(
        "\n4. Rejecting unauthorized delegation..."
    )

    unauthorized_rejected = False

    try:
        service.delegate_to(
            agent_id="drug-agent",
            domain="cad_simulation",
            tool="freecad",
        )

    except PermissionError as exc:
        unauthorized_rejected = True

        print(
            f"Unauthorized delegation rejected: {exc}"
        )

    assert unauthorized_rejected is True

    print(
        "\n5. Rejecting missing agent..."
    )

    missing_rejected = False

    try:
        service.delegate_to(
            agent_id="missing-agent",
            domain="cad_simulation",
            tool="freecad",
        )

    except LookupError as exc:
        missing_rejected = True

        print(
            f"Missing agent rejected: {exc}"
        )

    assert missing_rejected is True

    assert len(
        dispatcher.submissions
    ) == 3

    print(
        "\nRecorded submissions:"
    )

    print(
        json.dumps(
            dispatcher.submissions,
            indent=2,
        )
    )

    print(
        "\nPASS: Automatic named-agent delegation passed."
    )

    print(
        "PASS: Explicit authorized delegation passed."
    )

    print(
        "PASS: Agent identity metadata was attached."
    )

    print(
        "PASS: Unauthorized delegation was rejected."
    )

    print(
        "PASS: No SQLite, threads, SSH, or tools were used."
    )


if __name__ == "__main__":
    main()


def test_main() -> None:
    main()
