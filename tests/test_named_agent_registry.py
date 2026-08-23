import json

from app.agent.named_agent_registry import (
    NamedAgent,
    NamedAgentRegistry,
)


def main() -> None:
    registry = NamedAgentRegistry()

    print("1. Registering bounded named agents...")

    registry.register(
        NamedAgent(
            agent_id="docking-specialist",
            description=(
                "Handles molecular docking jobs."
            ),
            routes=(
                "drug_discovery:docking",
            ),
            priority=10,
        )
    )

    registry.register(
        NamedAgent(
            agent_id="drug-discovery-agent",
            description=(
                "Handles general drug-discovery jobs."
            ),
            routes=(
                "drug_discovery:*",
            ),
            priority=20,
        )
    )

    registry.register(
        NamedAgent(
            agent_id="engineering-agent",
            description=(
                "Handles FreeCAD and OpenFOAM jobs."
            ),
            routes=(
                "cad_simulation:freecad",
                "cad_simulation:openfoam",
                "CAD-SIMULATION:FREECAD",
            ),
            priority=10,
        )
    )

    registry.register(
        NamedAgent(
            agent_id="rendering-agent",
            description=(
                "Handles Blender rendering jobs."
            ),
            routes=(
                "cad_simulation:blender",
            ),
            priority=10,
        )
    )

    registry.register(
        NamedAgent(
            agent_id="fallback-agent",
            description=(
                "Fallback for future unassigned domains."
            ),
            routes=(
                "*:*",
            ),
            priority=1000,
        )
    )

    print(
        json.dumps(
            registry.describe_agents(),
            indent=2,
        )
    )

    assert registry.count() == 5

    print(
        "\n2. Selecting the docking specialist..."
    )

    docking = registry.select_agent(
        domain="drug_discovery",
        tool="docking",
    )

    assert (
        docking.agent_id
        == "docking-specialist"
    )

    docking_matches = registry.find_agents(
        domain="drug_discovery",
        tool="docking",
    )

    print(
        "Docking matches:",
        [
            agent.agent_id
            for agent in docking_matches
        ],
    )

    assert [
        agent.agent_id
        for agent in docking_matches
    ] == [
        "docking-specialist",
        "drug-discovery-agent",
        "fallback-agent",
    ]

    print(
        "\n3. Selecting engineering agents..."
    )

    freecad = registry.select_agent(
        domain="cad_simulation",
        tool="freecad",
    )

    openfoam = registry.select_agent(
        domain="cad_simulation",
        tool="openfoam",
    )

    blender = registry.select_agent(
        domain="cad_simulation",
        tool="blender",
    )

    assert (
        freecad.agent_id
        == "engineering-agent"
    )

    assert (
        openfoam.agent_id
        == "engineering-agent"
    )

    assert (
        blender.agent_id
        == "rendering-agent"
    )

    print(
        f"FreeCAD: {freecad.agent_id}"
    )

    print(
        f"OpenFOAM: {openfoam.agent_id}"
    )

    print(
        f"Blender: {blender.agent_id}"
    )

    print(
        "\n4. Testing fallback selection..."
    )

    fallback = registry.select_agent(
        domain="future_domain",
        tool="future_tool",
    )

    assert (
        fallback.agent_id
        == "fallback-agent"
    )

    print(
        f"Fallback: {fallback.agent_id}"
    )

    print(
        "\n5. Testing normalized duplicate routes..."
    )

    engineering = registry.get(
        "engineering-agent"
    )

    assert engineering is not None

    assert engineering.routes == (
        "cad_simulation:freecad",
        "cad_simulation:openfoam",
    )

    print(
        f"Engineering routes: "
        f"{engineering.routes}"
    )

    print(
        "\n6. Testing duplicate agent rejection..."
    )

    duplicate_rejected = False

    try:
        registry.register(
            NamedAgent(
                agent_id="engineering-agent",
                description="Duplicate",
                routes=(
                    "cad_simulation:*",
                ),
            )
        )

    except ValueError as exc:
        duplicate_rejected = True

        print(
            f"Duplicate rejected: {exc}"
        )

    assert duplicate_rejected is True
    assert registry.count() == 5

    print(
        "\nPASS: Named-agent registration passed."
    )

    print(
        "PASS: Exact, domain wildcard, and fallback "
        "matching passed."
    )

    print(
        "PASS: Priority-based delegation passed."
    )

    print(
        "PASS: Duplicate routes and agents were handled."
    )

    print(
        "PASS: No jobs or tools were executed."
    )


if __name__ == "__main__":
    main()


def test_main() -> None:
    main()
