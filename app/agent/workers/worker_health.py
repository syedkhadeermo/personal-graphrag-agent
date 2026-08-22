from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class WorkerHealthStatus(str, Enum):
    """
    Current observed health state of a worker.
    """

    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    TIMEOUT = "timeout"


@dataclass
class WorkerHealthRecord:
    """
    Latest health information for one registered worker.

    This model stores observations only. It does not perform
    network checks or modify worker registration.
    """

    worker_id: str

    status: WorkerHealthStatus = (
        WorkerHealthStatus.UNKNOWN
    )

    checked_at: str | None = None

    latency_seconds: float | None = None

    consecutive_failures: int = 0

    message: str | None = None

    details: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:
        if not isinstance(
            self.worker_id,
            str,
        ):
            raise TypeError(
                "worker_id must be a string."
            )

        self.worker_id = (
            self.worker_id.strip()
        )

        if not self.worker_id:
            raise ValueError(
                "worker_id cannot be empty."
            )

        if isinstance(
            self.status,
            str,
        ):
            try:
                self.status = (
                    WorkerHealthStatus(
                        self.status
                        .strip()
                        .lower()
                    )
                )

            except ValueError as exc:
                raise ValueError(
                    "Unsupported worker health status: "
                    f"{self.status}"
                ) from exc

        if not isinstance(
            self.status,
            WorkerHealthStatus,
        ):
            raise TypeError(
                "status must be a WorkerHealthStatus "
                "or valid status string."
            )

        if self.consecutive_failures < 0:
            raise ValueError(
                "consecutive_failures cannot be negative."
            )

        if (
            self.latency_seconds is not None
            and self.latency_seconds < 0
        ):
            raise ValueError(
                "latency_seconds cannot be negative."
            )

        self.details = dict(
            self.details or {}
        )

    @staticmethod
    def now(
        ) -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()

    def mark_healthy(
        self,
        latency_seconds: float,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        if latency_seconds < 0:
            raise ValueError(
                "latency_seconds cannot be negative."
            )

        self.status = (
            WorkerHealthStatus.HEALTHY
        )

        self.checked_at = self.now()

        self.latency_seconds = round(
            float(latency_seconds),
            6,
        )

        self.consecutive_failures = 0

        self.message = message

        self.details = dict(
            details or {}
        )

    def mark_failure(
        self,
        status: WorkerHealthStatus | str,
        message: str,
        latency_seconds: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        if isinstance(
            status,
            str,
        ):
            status = WorkerHealthStatus(
                status.strip().lower()
            )

        if status not in {
            WorkerHealthStatus.UNHEALTHY,
            WorkerHealthStatus.TIMEOUT,
        }:
            raise ValueError(
                "Failure status must be unhealthy "
                "or timeout."
            )

        if (
            latency_seconds is not None
            and latency_seconds < 0
        ):
            raise ValueError(
                "latency_seconds cannot be negative."
            )

        self.status = status

        self.checked_at = self.now()

        self.latency_seconds = (
            round(
                float(latency_seconds),
                6,
            )
            if latency_seconds is not None
            else None
        )

        self.consecutive_failures += 1

        self.message = str(
            message
        )

        self.details = dict(
            details or {}
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "worker_id":
                self.worker_id,

            "status":
                self.status.value,

            "checked_at":
                self.checked_at,

            "latency_seconds":
                self.latency_seconds,

            "consecutive_failures":
                self.consecutive_failures,

            "message":
                self.message,

            "details":
                dict(
                    self.details
                ),
        }