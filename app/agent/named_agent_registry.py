from dataclasses import dataclass
from threading import Lock
from typing import Iterable


def normalize_route(
    route: str,
) -> str:
    """
    Normalize an agent route in domain:tool form.

    Supported wildcard examples:
        drug_discovery:*
        *:*
    """

    if not isinstance(
        route,
        str,
    ):
        raise TypeError(
            "Agent route must be a string."
        )

    normalized = (
        route
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    if normalized.count(":") != 1:
        raise ValueError(
            "Agent route must use domain:tool format."
        )

    domain, tool = normalized.split(
        ":",
        1,
    )

    if not domain or not tool:
        raise ValueError(
            "Agent route domain and tool "
            "cannot be empty."
        )

    return f"{domain}:{tool}"


def normalize_routes(
    routes: Iterable[str],
) -> tuple[str, ...]:
    """
    Normalize, deduplicate, and sort agent routes.
    """

    if isinstance(
        routes,
        str,
    ):
        raise TypeError(
            "routes must be an iterable, "
            "not one string."
        )

    normalized = {
        normalize_route(
            route
        )
        for route in routes
    }

    if not normalized:
        raise ValueError(
            "Named agent must have at least one route."
        )

    return tuple(
        sorted(
            normalized
        )
    )


@dataclass(frozen=True)
class NamedAgent:
    """
    Declarative named-agent definition.

    A named agent defines responsibility only. Scientific
    execution remains in JobDispatcher and JobManager.
    """

    agent_id: str
    description: str
    routes: tuple[str, ...]
    priority: int = 100

    def __post_init__(
        self,
    ) -> None:
        if not isinstance(
            self.agent_id,
            str,
        ):
            raise TypeError(
                "agent_id must be a string."
            )

        normalized_id = (
            self.agent_id.strip()
        )

        if not normalized_id:
            raise ValueError(
                "agent_id cannot be empty."
            )

        if not isinstance(
            self.priority,
            int,
        ):
            raise TypeError(
                "priority must be an integer."
            )

        if self.priority < 0:
            raise ValueError(
                "priority cannot be negative."
            )

        normalized_routes = (
            normalize_routes(
                self.routes
            )
        )

        object.__setattr__(
            self,
            "agent_id",
            normalized_id,
        )

        object.__setattr__(
            self,
            "description",
            str(
                self.description
            ).strip(),
        )

        object.__setattr__(
            self,
            "routes",
            normalized_routes,
        )

    def can_handle(
        self,
        domain: str,
        tool: str,
    ) -> bool:
        """
        Check exact and wildcard responsibility routes.
        """

        requested = normalize_route(
            f"{domain}:{tool}"
        )

        requested_domain, _ = (
            requested.split(
                ":",
                1,
            )
        )

        return any(
            route == requested
            or route
            == f"{requested_domain}:*"
            or route == "*:*"
            for route in self.routes
        )

    def to_dict(
        self,
    ) -> dict:
        return {
            "agent_id":
                self.agent_id,

            "description":
                self.description,

            "routes":
                list(
                    self.routes
                ),

            "priority":
                self.priority,
        }


class NamedAgentRegistry:
    """
    Thread-safe registry of bounded named-agent roles.

    This registry does not start threads, call LLMs, execute
    tools, or create jobs.
    """

    def __init__(
        self,
    ):
        self._agents: dict[
            str,
            NamedAgent,
        ] = {}

        self._lock = Lock()

    # =========================================================
    # Registration
    # =========================================================

    def register(
        self,
        agent: NamedAgent,
    ) -> None:
        if not isinstance(
            agent,
            NamedAgent,
        ):
            raise TypeError(
                "agent must be a NamedAgent."
            )

        with self._lock:

            if agent.agent_id in self._agents:
                raise ValueError(
                    "Named agent is already registered: "
                    f"{agent.agent_id}"
                )

            self._agents[
                agent.agent_id
            ] = agent

    # =========================================================
    # Lookup
    # =========================================================

    def get(
        self,
        agent_id: str,
    ) -> NamedAgent | None:
        if not isinstance(
            agent_id,
            str,
        ):
            raise TypeError(
                "agent_id must be a string."
            )

        normalized_id = agent_id.strip()

        if not normalized_id:
            raise ValueError(
                "agent_id cannot be empty."
            )

        with self._lock:
            return self._agents.get(
                normalized_id
            )

    def find_agents(
        self,
        domain: str,
        tool: str,
    ) -> list[NamedAgent]:
        """
        Return matching agents ordered by priority then ID.
        """

        with self._lock:

            matches = [
                agent
                for agent
                in self._agents.values()
                if agent.can_handle(
                    domain=domain,
                    tool=tool,
                )
            ]

        return sorted(
            matches,
            key=lambda agent: (
                agent.priority,
                agent.agent_id,
            ),
        )

    def select_agent(
        self,
        domain: str,
        tool: str,
    ) -> NamedAgent:
        """
        Select the highest-priority matching agent.
        """

        matches = self.find_agents(
            domain=domain,
            tool=tool,
        )

        if not matches:
            raise LookupError(
                "No named agent can handle "
                f"{domain}:{tool}"
            )

        return matches[0]

    # =========================================================
    # Listing
    # =========================================================

    def list_agents(
        self,
    ) -> list[str]:
        with self._lock:
            return sorted(
                self._agents.keys()
            )

    def describe_agents(
        self,
    ) -> list[dict]:
        with self._lock:

            agents = sorted(
                self._agents.values(),
                key=lambda agent: (
                    agent.priority,
                    agent.agent_id,
                ),
            )

            return [
                agent.to_dict()
                for agent in agents
            ]

    def count(
        self,
    ) -> int:
        with self._lock:
            return len(
                self._agents
            )