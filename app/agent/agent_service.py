from typing import Any

from app.agent.tools.default_tools import create_default_registry
from app.agent.tools.tool_registry import ToolRegistry


class AgentService:
    """
    Main orchestration layer for the GraphRAG agent.

    The service does not implement scientific tools itself.
    It discovers and dispatches registered domain tools.

    Current drug-discovery backend:
        AutoDock Vina

    Planned backends:
        Smina
        GROMACS
        additional molecular-dynamics / scoring tools
    """

    def __init__(self, registry: ToolRegistry | None = None):
        self.registry = registry or create_default_registry()

    # ------------------------------------------------------------------
    # Registry / capability discovery
    # ------------------------------------------------------------------

    def list_domains(self) -> list[str]:
        """Return all registered computational domains."""
        return self.registry.list_domains()

    def list_tools(self, domain: str) -> list[str]:
        """Return tools registered for a domain."""
        return self.registry.list_tools(domain)

    def describe_tools(self, domain: str) -> list[dict[str, str]]:
        """Return tool descriptions for a domain."""
        return self.registry.describe_tools(domain)

    def capabilities(self) -> dict[str, list[str]]:
        """Return the complete agent capability map."""
        return self.registry.summary()

    # ------------------------------------------------------------------
    # Generic tool execution
    # ------------------------------------------------------------------

    def execute_tool(
        self,
        domain: str,
        tool: str,
        request: Any,
    ) -> Any:
        """
        Execute a registered tool.

        Structured dictionaries are passed as keyword arguments.
        Strings are passed as a single request argument.
        """
        return self.registry.execute(
            domain=domain,
            name=tool,
            request=request,
        )

    # ------------------------------------------------------------------
    # Drug discovery
    # ------------------------------------------------------------------

    def run_docking(
        self,
        receptor: str,
        ligand: str,
        center_x: float,
        center_y: float,
        center_z: float,
        size_x: float,
        size_y: float,
        size_z: float,
        exhaustiveness: int = 8,
        num_modes: int = 9,
    ) -> dict:
        """
        Run the registered molecular docking workflow.

        The AgentService does not directly call Vina.
        It dispatches through the ToolRegistry.

        This allows the backend to evolve later without changing
        the agent interface.
        """

        request = {
            "receptor": receptor,
            "ligand": ligand,
            "center_x": center_x,
            "center_y": center_y,
            "center_z": center_z,
            "size_x": size_x,
            "size_y": size_y,
            "size_z": size_z,
            "exhaustiveness": exhaustiveness,
            "num_modes": num_modes,
        }

        result = self.execute_tool(
            domain="drug_discovery",
            tool="docking",
            request=request,
        )

        if not isinstance(result, dict):
            raise TypeError(
                "Docking tool returned an unexpected result type."
            )

        return result

    # ------------------------------------------------------------------
    # High-level agent request
    # ------------------------------------------------------------------

    def handle_request(
        self,
        domain: str,
        tool: str,
        request: Any,
    ) -> Any:
        """
        Generic entry point for future LLM / GraphRAG routing.

        Example:

            agent.handle_request(
                "drug_discovery",
                "docking",
                {...}
            )
        """

        return self.execute_tool(
            domain=domain,
            tool=tool,
            request=request,
        )
