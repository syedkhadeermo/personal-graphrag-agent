from app.agent.named_agent_registry import (
    NamedAgent,
    NamedAgentRegistry,
)


def create_default_agent_registry(
    ) -> NamedAgentRegistry:
    """
    Create the default lightweight named-agent registry.

    Named agents define bounded responsibilities only.
    All jobs continue through the shared dispatcher,
    JobManager, worker registry, and SQLite store.
    """

    registry = NamedAgentRegistry()

    registry.register(
        NamedAgent(
            agent_id="drug-discovery-agent",
            description=(
                "Handles docking, molecular dynamics, "
                "scoring, and drug-discovery workflows."
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
                "Handles FreeCAD and OpenFOAM "
                "engineering workflows."
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
                "Handles Blender rendering and "
                "animation workflows."
            ),
            routes=(
                "cad_simulation:blender",
            ),
            priority=10,
        )
    )

    registry.register(
        NamedAgent(
            agent_id="knowledge-agent",
            description=(
                "Handles RAG, GraphRAG, and technical "
                "knowledge retrieval."
            ),
            routes=(
                "knowledge:*",
            ),
            priority=10,
        )
    )

    return registry