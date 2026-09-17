import os
from typing import Any

from app.agent.tools.domain_tools.fea.calculix_runner import (
    CalculixRunner,
)


class StructuralFEATools:
    """
    Domain-level tools for structural finite element analysis.

    The domain facade keeps Structural FEA-specific execution
    details outside the generic agent and tool registry.
    """

    def __init__(
        self,
        host: str | None = None,
        username: str | None = None,
    ) -> None:
        resolved_host = (
            host
            if host is not None
            else os.getenv(
                "GRAPH_RAG_REMOTE_HOST",
                "",
            )
        ).strip()

        resolved_username = (
            username
            if username is not None
            else os.getenv(
                "GRAPH_RAG_REMOTE_USERNAME",
                "",
            )
        ).strip()

        self.calculix_runner = (
            CalculixRunner(
                host=resolved_host,
                username=resolved_username,
            )
            if (
                resolved_host
                and resolved_username
            )
            else None
        )

    def run_calculix(
        self,
        case_directory: str,
        job_name: str,
        timeout: int = 600,
    ) -> dict[str, Any]:
        """
        Execute a validated pre-existing CalculiX input case
        on the configured remote Structural FEA worker.
        """

        if self.calculix_runner is None:
            raise RuntimeError(
                "CalculiX remote execution is not configured. "
                "Set GRAPH_RAG_REMOTE_HOST and "
                "GRAPH_RAG_REMOTE_USERNAME."
            )

        return self.calculix_runner.run(
            case_directory=case_directory,
            job_name=job_name,
            timeout=timeout,
        )