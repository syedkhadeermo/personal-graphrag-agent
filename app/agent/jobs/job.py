from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.agent.jobs.job_state import JobState


@dataclass
class Job:
    """
    Represents one executable agent job.

    Durable operational information is persisted
    through JobStore.

    Detailed lifecycle history is stored in events.jsonl.
    """

    job_id: str
    domain: str
    tool: str

    status: str = JobState.CREATED.value

    worker: str | None = None

    request: dict[str, Any] = field(
        default_factory=dict
    )

    artifacts: list[str] = field(
        default_factory=list
    )

    events: list[dict[str, Any]] = field(
        default_factory=list
    )

    created_at: str = field(
        default_factory=lambda: (
            datetime.now(
                timezone.utc
            ).isoformat()
        )
    )

    started_at: str | None = None
    completed_at: str | None = None

    duration_seconds: float | None = None

    result: dict[str, Any] | None = None
    error: str | None = None

    # =========================================================
    # Retry information
    # =========================================================

    attempt: int = 0

    max_attempts: int = 3

    last_failure_type: str | None = None

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return {
            "job_id": self.job_id,
            "domain": self.domain,
            "tool": self.tool,
            "status": self.status,
            "worker": self.worker,

            "request": self.request,
            "artifacts": self.artifacts,
            "events": self.events,

            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,

            "duration_seconds": (
                self.duration_seconds
            ),

            "result": self.result,
            "error": self.error,

            "attempt": self.attempt,
            "max_attempts": (
                self.max_attempts
            ),
            "last_failure_type": (
                self.last_failure_type
            ),
        }