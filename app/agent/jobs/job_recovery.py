from typing import Any

from app.agent.jobs.job_events import JobEvent
from app.agent.jobs.job_state import (
    JobState,
    validate_transition,
)
from app.agent.jobs.job_store import JobStore
from app.agent.observability.structured_logger import (
    StructuredLogger,
)


class JobRecoveryService:
    """
    Detect stale jobs left behind by an interrupted manager.

    Recovery v1 does NOT automatically rerun work.

    It performs:

        stale RUNNING / VALIDATING
                ↓
        validate state transition
                ↓
        RECOVERY_REQUIRED
                ↓
        persist SQLite status
                ↓
        write RECOVERY_DETECTED event

    Future versions can decide whether to:
        - resume
        - requeue
        - retry
        - fail
        - cancel
    """

    def __init__(
        self,
        job_store: JobStore | None = None,
        base_directory: str = "data/jobs",
    ):
        self.job_store = (
            job_store
            or JobStore()
        )

        self.logger = StructuredLogger(
            base_directory=base_directory
        )

    # =========================================================
    # Detect and mark stale jobs
    # =========================================================

    def scan(
        self,
        stale_after_seconds: int = 300,
        include_queued: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Scan operational state and mark stale jobs as
        RECOVERY_REQUIRED.

        Returns:
            List of jobs transitioned during this scan.
        """

        candidates = (
            self.job_store
            .list_recovery_candidates(
                stale_after_seconds=(
                    stale_after_seconds
                ),
                include_queued=(
                    include_queued
                ),
            )
        )

        recovered = []

        for job in candidates:

            job_id = job[
                "job_id"
            ]

            current_state = JobState(
                job["status"]
            )

            validate_transition(
                current=current_state,
                target=(
                    JobState
                    .RECOVERY_REQUIRED
                ),
            )

            error_message = (
                "Stale in-flight job detected "
                "after manager/process restart. "
                f"Previous state="
                f"{current_state.value}."
            )

            self.job_store.set_status(
                job_id=job_id,
                status=(
                    JobState
                    .RECOVERY_REQUIRED
                    .value
                ),
                error=error_message,
            )

            self.logger.log(
                job_id=job_id,
                event=(
                    JobEvent
                    .RECOVERY_DETECTED
                    .value
                ),
                previous_state=(
                    current_state.value
                ),
                state=(
                    JobState
                    .RECOVERY_REQUIRED
                    .value
                ),
                stale_age_seconds=(
                    job.get(
                        "stale_age_seconds"
                    )
                ),
                reason=error_message,
            )

            updated = (
                self.job_store.get(
                    job_id
                )
            )

            if updated is not None:
                recovered.append(
                    updated
                )

        return recovered