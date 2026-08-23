from pydantic import ValidationError

from app.api.schemas import (
    JobSubmissionRequest,
    JobSubmissionResponse,
)


def main() -> None:
    print("1. Testing valid job submission...")

    submission = JobSubmissionRequest(
        domain="  drug_discovery  ",
        tool="  vina_docking  ",
        request={
            "receptor": "protein.pdbqt",
            "ligand": "ligand.pdbqt",
        },
        max_attempts=3,
    )

    assert (
        submission.domain
        == "drug_discovery"
    )

    assert (
        submission.tool
        == "vina_docking"
    )

    assert submission.max_attempts == 3
    assert submission.agent_id is None
    assert submission.artifacts == []

    print(
        submission.model_dump()
    )

    print(
        "\n2. Testing explicit agent selection..."
    )

    explicit = JobSubmissionRequest(
        domain="cad_simulation",
        tool="freecad",
        agent_id=" engineering-agent ",
    )

    assert (
        explicit.agent_id
        == "engineering-agent"
    )

    print(
        explicit.model_dump()
    )

    print(
        "\n3. Testing independent defaults..."
    )

    first = JobSubmissionRequest(
        domain="test",
        tool="one",
    )

    second = JobSubmissionRequest(
        domain="test",
        tool="two",
    )

    first.request["value"] = 1
    first.artifacts.append(
        {
            "path": "artifact.txt"
        }
    )

    assert second.request == {}
    assert second.artifacts == []

    print(
        "Mutable defaults are isolated."
    )

    print(
        "\n4. Rejecting empty domain..."
    )

    empty_rejected = False

    try:
        JobSubmissionRequest(
            domain="   ",
            tool="echo",
        )

    except ValidationError as exc:
        empty_rejected = True
        print(exc)

    assert empty_rejected is True

    print(
        "\n5. Rejecting invalid max_attempts..."
    )

    attempts_rejected = False

    try:
        JobSubmissionRequest(
            domain="test",
            tool="echo",
            max_attempts=0,
        )

    except ValidationError as exc:
        attempts_rejected = True
        print(exc)

    assert attempts_rejected is True

    print(
        "\n6. Rejecting unexpected fields..."
    )

    extra_rejected = False

    try:
        JobSubmissionRequest(
            domain="test",
            tool="echo",
            unexpected="not-allowed",
        )

    except ValidationError as exc:
        extra_rejected = True
        print(exc)

    assert extra_rejected is True

    print(
        "\n7. Testing response schema..."
    )

    response = JobSubmissionResponse(
        job_id="JOB-000001",
        agent_id="test-agent",
        domain="test",
        tool="echo",
        status="submitted",
    )

    assert (
        response.model_dump()[
            "job_id"
        ]
        == "JOB-000001"
    )

    print(
        response.model_dump()
    )

    print(
        "\nPASS: Valid job schema passed."
    )

    print(
        "PASS: Text normalization passed."
    )

    print(
        "PASS: Mutable defaults are isolated."
    )

    print(
        "PASS: Invalid and extra fields were rejected."
    )

    print(
        "PASS: Submission response schema passed."
    )


if __name__ == "__main__":
    main()


def test_main() -> None:
    main()
