from typing import Any

from app.agent.named_agent_registry import (
    NamedAgent,
    NamedAgentRegistry,
)


class AgentDelegationService:
    """
    Select a bounded named agent and delegate a job through
    the existing JobDispatcher interface.

    The service does not:
        - execute scientific tools
        - create worker threads
        - manage retries
        - manage SQLite
        - route compute workers

    Those responsibilities remain in JobDispatcher,
    JobManager, and WorkloadRouter.
    """

    def __init__(
        self,
        agent_registry: NamedAgentRegistry,
        dispatcher: Any,
    ):
        if not isinstance(
            agent_registry,
            NamedAgentRegistry,
        ):
            raise TypeError(
                "agent_registry must be a "
                "NamedAgentRegistry instance."
            )

        create_and_submit = getattr(
            dispatcher,
            "create_and_submit",
            None,
        )

        if not callable(
            create_and_submit
        ):
            raise TypeError(
                "dispatcher must provide a callable "
                "create_and_submit() method."
            )

        self.agent_registry = (
            agent_registry
        )

        self.dispatcher = dispatcher

    # =========================================================
    # Selection
    # =========================================================

    def select_agent(
        self,
        domain: str,
        tool: str,
    ) -> NamedAgent:
        return self.agent_registry.select_agent(
            domain=domain,
            tool=tool,
        )

    # =========================================================
    # Delegation
    # =========================================================

    def delegate(
        self,
        domain: str,
        tool: str,
        request: dict[str, Any] | None = None,
        artifacts: list[
            dict[str, Any]
        ] | None = None,
        max_attempts: int | None = None,
    ) -> dict[str, Any]:
        """
        Select the highest-priority named agent and submit one
        asynchronous job.

        Delegation identity is added as internal request
        metadata for durable persistence. JobManager integration
        will remove these internal fields before tool execution.
        """

        agent = self.select_agent(
            domain=domain,
            tool=tool,
        )

        job_request = dict(
            request or {}
        )

        job_request[
            "_delegated_agent_id"
        ] = agent.agent_id

        job_request[
            "_delegation_route"
        ] = f"{domain}:{tool}"

        job_id = (
            self.dispatcher
            .create_and_submit(
                domain=domain,
                tool=tool,
                request=job_request,
                artifacts=artifacts,
                max_attempts=max_attempts,
            )
        )

        return {
            "job_id":
                job_id,

            "agent_id":
                agent.agent_id,

            "domain":
                domain,

            "tool":
                tool,

            "status":
                "submitted",
        }

    def delegate_to(
        self,
        agent_id: str,
        domain: str,
        tool: str,
        request: dict[str, Any] | None = None,
        artifacts: list[
            dict[str, Any]
        ] | None = None,
        max_attempts: int | None = None,
    ) -> dict[str, Any]:
        """
        Delegate explicitly to one named agent.

        The requested agent must be registered and authorized
        for the domain/tool route.
        """

        agent = self.agent_registry.get(
            agent_id
        )

        if agent is None:
            raise LookupError(
                "Named agent is not registered: "
                f"{agent_id}"
            )

        if not agent.can_handle(
            domain=domain,
            tool=tool,
        ):
            raise PermissionError(
                f"Named agent '{agent_id}' cannot "
                f"handle {domain}:{tool}"
            )

        job_request = dict(
            request or {}
        )

        job_request[
            "_delegated_agent_id"
        ] = agent.agent_id

        job_request[
            "_delegation_route"
        ] = f"{domain}:{tool}"

        job_id = (
            self.dispatcher
            .create_and_submit(
                domain=domain,
                tool=tool,
                request=job_request,
                artifacts=artifacts,
                max_attempts=max_attempts,
            )
        )

        return {
            "job_id":
                job_id,

            "agent_id":
                agent.agent_id,

            "domain":
                domain,

            "tool":
                tool,

            "status":
                "submitted",
        }