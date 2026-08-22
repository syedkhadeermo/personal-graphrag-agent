from typing import Callable, Any


class ToolRegistry:
    """
    Central registry for domain-specific agent tools.

    Structure:
        domain -> tool name -> function + description
    """

    def __init__(self):
        self._tools: dict[str, dict[str, dict[str, Any]]] = {}

    def register(
        self,
        domain: str,
        name: str,
        function: Callable,
        description: str = "",
    ) -> None:

        if not domain or not domain.strip():
            raise ValueError("Tool domain cannot be empty.")

        if not name or not name.strip():
            raise ValueError("Tool name cannot be empty.")

        if not callable(function):
            raise TypeError("Tool function must be callable.")

        domain = domain.strip()
        name = name.strip()

        self._tools.setdefault(domain, {})[name] = {
            "function": function,
            "description": description,
        }

    def get_tool(
        self,
        domain: str,
        name: str,
    ) -> dict[str, Any] | None:

        return self._tools.get(domain, {}).get(name)

    def execute(
        self,
        domain: str,
        name: str,
        request: Any,
    ) -> Any:

        tool = self.get_tool(domain, name)

        if tool is None:
            raise ValueError(
                f"Tool '{name}' is not registered "
                f"for domain '{domain}'."
            )

        function = tool["function"]

        if isinstance(request, dict):
            return function(**request)

        return function(request)

    def list_domains(self) -> list[str]:
        return sorted(self._tools.keys())

    def list_tools(self, domain: str) -> list[str]:
        return sorted(self._tools.get(domain, {}).keys())

    def describe_tools(
        self,
        domain: str,
    ) -> list[dict[str, str]]:

        tools = self._tools.get(domain, {})

        return [
            {
                "name": name,
                "description": info.get("description", ""),
            }
            for name, info in sorted(tools.items())
        ]

    def summary(self) -> dict[str, list[str]]:
        return {
            domain: self.list_tools(domain)
            for domain in self.list_domains()
        }