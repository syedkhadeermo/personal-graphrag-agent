from app.agent.workers.worker_capabilities import (
    WorkerCapability,
    normalize_capabilities,
    normalize_capability,
)


def main() -> None:
    print("1. Testing standard capability normalization...")

    assert (
        normalize_capability(
            WorkerCapability.FREECAD
        )
        == "freecad"
    )

    assert (
        normalize_capability(
            " OpenFOAM "
        )
        == "openfoam"
    )

    assert (
        normalize_capability(
            "REMOTE-COMMAND"
        )
        == "remote_command"
    )

    print(
        "Standard normalization passed."
    )

    print(
        "\n2. Testing sorting and deduplication..."
    )

    capabilities = normalize_capabilities(
        [
            WorkerCapability.FREECAD,
            "Blender",
            "openfoam",
            "FREECAD",
            WorkerCapability.GROMACS,
            WorkerCapability.REMOTE_COMMAND,
        ]
    )

    print(
        f"Normalized capabilities: {capabilities}"
    )

    assert capabilities == (
        "blender",
        "freecad",
        "gromacs",
        "openfoam",
        "remote_command",
    )

    print(
        "Sorting and deduplication passed."
    )

    print(
        "\n3. Testing future custom capability..."
    )

    custom = normalize_capability(
        "CUDA Scientific Workload"
    )

    assert custom == (
        "cuda_scientific_workload"
    )

    print(
        f"Custom capability: {custom}"
    )

    print(
        "\n4. Testing invalid inputs..."
    )

    single_string_rejected = False

    try:
        normalize_capabilities(
            "freecad"
        )

    except TypeError as exc:
        single_string_rejected = True
        print(
            f"Single string rejected: {exc}"
        )

    assert single_string_rejected is True

    empty_capability_rejected = False

    try:
        normalize_capability(
            "   "
        )

    except ValueError as exc:
        empty_capability_rejected = True
        print(
            f"Empty capability rejected: {exc}"
        )

    assert empty_capability_rejected is True

    invalid_type_rejected = False

    try:
        normalize_capability(
            123
        )

    except TypeError as exc:
        invalid_type_rejected = True
        print(
            f"Invalid type rejected: {exc}"
        )

    assert invalid_type_rejected is True

    print(
        "\nPASS: Worker capability normalization passed."
    )

    print(
        "PASS: Capabilities were sorted and deduplicated."
    )

    print(
        "PASS: Future custom capabilities remain supported."
    )

    print(
        "PASS: Invalid capability inputs were rejected."
    )


if __name__ == "__main__":
    main()


def test_main() -> None:
    main()
