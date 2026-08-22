import os

from app.agent.agent_delegation_service import (
    AgentDelegationService,
)

from app.agent.default_agents import (
    create_default_agent_registry,
)

from app.agent.jobs.job_dispatcher import (
    JobDispatcher,
)

from app.agent.jobs.job_manager import (
    JobManager,
)

from app.agent.named_agent_registry import (
    NamedAgentRegistry,
)

from app.agent.tools.default_tools import (
    create_default_registry,
)

from app.agent.tools.tool_registry import (
    ToolRegistry,
)


class ApiRuntime:
    """
    Runtime composition for the HTTP API.

    Reuses:
        - ToolRegistry
        - NamedAgentRegistry
        - JobManager
        - JobDispatcher
        - AgentDelegationService

    The API owns lifecycle only. Scientific execution and
    persistence remain in the existing components.
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        agent_registry: NamedAgentRegistry,
        job_manager: JobManager,
        dispatcher: JobDispatcher,
    ):
        if not isinstance(
            tool_registry,
            ToolRegistry,
        ):
            raise TypeError(
                "tool_registry must be a ToolRegistry."
            )

        if not isinstance(
            agent_registry,
            NamedAgentRegistry,
        ):
            raise TypeError(
                "agent_registry must be a "
                "NamedAgentRegistry."
            )

        if not isinstance(
            job_manager,
            JobManager,
        ):
            raise TypeError(
                "job_manager must be a JobManager."
            )

        if not isinstance(
            dispatcher,
            JobDispatcher,
        ):
            raise TypeError(
                "dispatcher must be a JobDispatcher."
            )

        if dispatcher.registry is not tool_registry:
            raise ValueError(
                "dispatcher must use the supplied "
                "tool_registry."
            )

        if dispatcher.job_manager is not job_manager:
            raise ValueError(
                "dispatcher must use the supplied "
                "job_manager."
            )

        self.tool_registry = tool_registry
        self.agent_registry = agent_registry
        self.job_manager = job_manager
        self.job_store = job_manager.job_store
        self.dispatcher = dispatcher

        self.delegation_service = (
            AgentDelegationService(
                agent_registry=agent_registry,
                dispatcher=dispatcher,
            )
        )

    # =========================================================
    # Default construction
    # =========================================================

    @classmethod
    def create_default(
        cls,
    ) -> "ApiRuntime":
        """
        Construct the production API runtime.

        Environment variables:
            GRAPH_RAG_JOB_WORKERS
            GRAPH_RAG_POLL_TIMEOUT
            GRAPH_RAG_RECOVER_ON_START
            GRAPH_RAG_STALE_AFTER_SECONDS
        """

        worker_count = int(
            os.getenv(
                "GRAPH_RAG_JOB_WORKERS",
                "2",
            )
        )

        poll_timeout = float(
            os.getenv(
                "GRAPH_RAG_POLL_TIMEOUT",
                "0.5",
            )
        )

        recover_on_start = (
            os.getenv(
                "GRAPH_RAG_RECOVER_ON_START",
                "true",
            )
            .strip()
            .lower()
            in {
                "1",
                "true",
                "yes",
                "on",
            }
        )

        stale_after_seconds = int(
            os.getenv(
                "GRAPH_RAG_STALE_AFTER_SECONDS",
                "0",
            )
        )

        tool_registry = (
            create_default_registry()
        )

        agent_registry = (
            create_default_agent_registry()
        )

        job_manager = JobManager()

        dispatcher = JobDispatcher(
            registry=tool_registry,
            job_manager=job_manager,
            worker_count=worker_count,
            poll_timeout=poll_timeout,
            recover_on_start=(
                recover_on_start
            ),
            stale_after_seconds=(
                stale_after_seconds
            ),
        )

        return cls(
            tool_registry=tool_registry,
            agent_registry=agent_registry,
            job_manager=job_manager,
            dispatcher=dispatcher,
        )

    # =========================================================
    # Lifecycle
    # =========================================================

    def start(
        self,
    ) -> dict:
        return self.dispatcher.start()

    def stop(
        self,
    ) -> None:
        self.dispatcher.stop(
            wait=True,
            timeout=10.0,
        )

    def is_running(
        self,
    ) -> bool:
        return self.dispatcher.is_running()

    # =========================================================
    # Status
    # =========================================================

    def status(
        self,
    ) -> dict:
        return {
            "dispatcher_running":
                self.dispatcher.is_running(),

            "dispatcher_workers":
                self.dispatcher.worker_status(),

            "queue_size":
                self.dispatcher.queue_size(),

            "tool_domains":
                self.tool_registry.summary(),

            "named_agents":
                self.agent_registry
                .describe_agents(),
        }