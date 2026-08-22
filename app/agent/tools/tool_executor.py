from app.agent.tools.tool_registry import ToolRegistry


class ToolExecutor:
    """Execute registered domain tools safely."""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def execute(
        self,
        domain: str,
        tool_name: str,
        request: str,
    ) -> dict:
        tool = self.registry.get_tool(domain, tool_name)

        if tool is None:
            raise ValueError(
                f"Tool '{tool_name}' is not registered "
                f"for domain '{domain}'."
            )

        function = tool["function"]

        result = function(request)

        return {
            "domain": domain,
            "tool": tool_name,
            "request": request,
            "result": result,
        }