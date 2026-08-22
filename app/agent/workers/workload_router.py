from typing import Iterable

from app.agent.workers.worker_capabilities import (
    WorkerCapability,
    normalize_capabilities,
)

from app.agent.workers.worker_health import (
    WorkerHealthStatus,
)

from app.agent.workers.worker_health_service import (
    WorkerHealthService,
)

from app.agent.workers.worker_registry import (
    WorkerRegistry,
)


class WorkloadRouter:
    """
    Select a registered worker for a workload.

    Selection requirements:
        - worker supports every required capability
        - worker is HEALTHY
        - optionally, UNKNOWN workers may be considered
        - UNHEALTHY and TIMEOUT workers are excluded

    Selection is deterministic:
        1. HEALTHY before UNKNOWN
        2. lower heartbeat latency first
        3. worker ID alphabetically

    This class selects workers only. It does not execute,
    reserve, enqueue, or retry jobs.
    """

    def __init__(
        self,
        worker_registry: WorkerRegistry,
        health_service: WorkerHealthService,
    ):
        if not isinstance(
            worker_registry,
            WorkerRegistry,
        ):
            raise TypeError(
                "worker_registry must be a "
                "WorkerRegistry instance."
            )

        if not isinstance(
            health_service,
            WorkerHealthService,
        ):
            raise TypeError(
                "health_service must be a "
                "WorkerHealthService instance."
            )

        if (
            health_service.worker_registry
            is not worker_registry
        ):
            raise ValueError(
                "WorkerHealthService must use the "
                "same WorkerRegistry as WorkloadRouter."
            )

        self.worker_registry = (
            worker_registry
        )

        self.health_service = (
            health_service
        )

    # =========================================================
    # Candidate inspection
    # =========================================================

    def get_candidates(
        self,
        required_capabilities: Iterable[
            WorkerCapability | str
        ] | None = None,
        allow_unknown: bool = False,
    ) -> list[dict]:
        """
        Return eligible workers in selection order.
        """

        normalized_required = (
            normalize_capabilities(
                required_capabilities
            )
        )

        capability_matches = (
            self.worker_registry.find_workers(
                normalized_required
            )
        )

        candidates = []

        for worker_id in capability_matches:

            health = (
                self.health_service
                .get_health(
                    worker_id
                )
            )

            if health is None:
                continue

            status = health.get(
                "status"
            )

            if (
                status
                == WorkerHealthStatus
                .HEALTHY
                .value
            ):
                status_priority = 0

            elif (
                allow_unknown
                and status
                == WorkerHealthStatus
                .UNKNOWN
                .value
            ):
                status_priority = 1

            else:
                continue

            latency = health.get(
                "latency_seconds"
            )

            latency_priority = (
                float(latency)
                if latency is not None
                else float("inf")
            )

            candidates.append(
                {
                    "worker_id":
                        worker_id,

                    "required_capabilities":
                        list(
                            normalized_required
                        ),

                    "health":
                        health,

                    "_sort_key":
                        (
                            status_priority,
                            latency_priority,
                            worker_id,
                        ),
                }
            )

        candidates.sort(
            key=lambda candidate: (
                candidate["_sort_key"]
            )
        )

        for candidate in candidates:
            candidate.pop(
                "_sort_key",
                None,
            )

        return candidates

    # =========================================================
    # Selection
    # =========================================================

    def select_worker(
        self,
        required_capabilities: Iterable[
            WorkerCapability | str
        ] | None = None,
        allow_unknown: bool = False,
    ) -> str:
        """
        Select one eligible worker ID.

        Raises LookupError if no worker has the required
        capabilities or no matching worker is healthy.
        """

        normalized_required = (
            normalize_capabilities(
                required_capabilities
            )
        )

        capability_matches = (
            self.worker_registry.find_workers(
                normalized_required
            )
        )

        if not capability_matches:
            raise LookupError(
                "No registered worker supports "
                "all required capabilities: "
                f"{list(normalized_required)}"
            )

        candidates = self.get_candidates(
            required_capabilities=(
                normalized_required
            ),
            allow_unknown=allow_unknown,
        )

        if not candidates:

            observed_health = {
                worker_id:
                    self.health_service
                    .get_health(
                        worker_id
                    )
                for worker_id
                in capability_matches
            }

            raise LookupError(
                "No healthy worker is available "
                "for required capabilities "
                f"{list(normalized_required)}. "
                f"Observed health: "
                f"{observed_health}"
            )

        return candidates[0][
            "worker_id"
        ]