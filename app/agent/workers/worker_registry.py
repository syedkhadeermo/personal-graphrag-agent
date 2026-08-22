from threading import Lock
from typing import Any, Iterable

from app.agent.workers.worker_capabilities import (
    WorkerCapability,
    normalize_capabilities,
    normalize_capability,
)


class WorkerRegistry:
    """
    Thread-safe registry of compute worker instances.

    Responsibilities:
        - register workers under stable worker IDs
        - associate workers with explicit capabilities
        - reject accidental duplicate worker IDs
        - retrieve registered worker instances
        - query workers by capability
        - list and describe registered workers
        - unregister workers explicitly

    Heartbeats, health state, workload routing, and persistence
    are intentionally handled by later architecture layers.
    """

    def __init__(self):
        self._workers: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    # =========================================================
    # Registration
    # =========================================================

    def register(
        self,
        worker_id: str,
        worker: Any,
        description: str = "",
        metadata: dict[str, Any] | None = None,
        capabilities: Iterable[
            WorkerCapability | str
        ] | None = None,
    ) -> None:
        """
        Register one worker instance and its capabilities.

        Duplicate worker IDs are rejected to prevent accidental
        replacement of an active worker.
        """

        normalized_id = self._normalize_worker_id(
            worker_id
        )

        if worker is None:
            raise ValueError(
                "Worker instance cannot be None."
            )

        if not callable(
            getattr(
                worker,
                "run",
                None,
            )
        ):
            raise TypeError(
                "Worker must provide a callable run() method."
            )

        normalized_capabilities = (
            normalize_capabilities(
                capabilities
            )
        )

        record = {
            "worker_id": normalized_id,
            "worker": worker,
            "description": (
                description.strip()
                if isinstance(description, str)
                else str(description)
            ),
            "metadata": dict(
                metadata or {}
            ),
            "capabilities":
                normalized_capabilities,
        }

        with self._lock:
            if normalized_id in self._workers:
                raise ValueError(
                    "Worker is already registered: "
                    f"{normalized_id}"
                )

            self._workers[
                normalized_id
            ] = record

    # =========================================================
    # Lookup
    # =========================================================

    def get_worker(
        self,
        worker_id: str,
    ) -> Any | None:
        """
        Return the registered worker instance, or None.
        """

        normalized_id = self._normalize_worker_id(
            worker_id
        )

        with self._lock:
            record = self._workers.get(
                normalized_id
            )

            if record is None:
                return None

            return record["worker"]

    def get_record(
        self,
        worker_id: str,
    ) -> dict[str, Any] | None:
        """
        Return a copy of the worker registration record.

        The worker instance itself is not copied.
        """

        normalized_id = self._normalize_worker_id(
            worker_id
        )

        with self._lock:
            record = self._workers.get(
                normalized_id
            )

            if record is None:
                return None

            return {
                "worker_id":
                    record["worker_id"],
                "worker":
                    record["worker"],
                "description":
                    record["description"],
                "metadata":
                    dict(record["metadata"]),
                "capabilities":
                    tuple(record["capabilities"]),
            }

    # =========================================================
    # Presence
    # =========================================================

    def contains(
        self,
        worker_id: str,
    ) -> bool:
        normalized_id = self._normalize_worker_id(
            worker_id
        )

        with self._lock:
            return (
                normalized_id
                in self._workers
            )

    # =========================================================
    # Capabilities
    # =========================================================

    def supports(
        self,
        worker_id: str,
        capability: WorkerCapability | str,
    ) -> bool:
        """
        Return whether a registered worker supports one
        capability.

        Missing workers return False.
        """

        normalized_id = self._normalize_worker_id(
            worker_id
        )

        normalized_capability = (
            normalize_capability(
                capability
            )
        )

        with self._lock:
            record = self._workers.get(
                normalized_id
            )

            if record is None:
                return False

            return (
                normalized_capability
                in record["capabilities"]
            )

    def find_workers(
        self,
        required_capabilities: Iterable[
            WorkerCapability | str
        ] | None = None,
    ) -> list[str]:
        """
        Return worker IDs supporting every required capability.

        With no required capabilities, all registered worker IDs
        are returned.

        This performs capability filtering only. It does not
        choose, reserve, or route work to a worker.
        """

        normalized_required = (
            normalize_capabilities(
                required_capabilities
            )
        )

        required_set = set(
            normalized_required
        )

        with self._lock:
            matching = []

            for worker_id, record in (
                self._workers.items()
            ):
                worker_capabilities = set(
                    record["capabilities"]
                )

                if required_set.issubset(
                    worker_capabilities
                ):
                    matching.append(
                        worker_id
                    )

            return sorted(
                matching
            )

    # =========================================================
    # Removal
    # =========================================================

    def unregister(
        self,
        worker_id: str,
    ) -> bool:
        """
        Remove a worker explicitly.

        Returns True if a worker was removed and False if the
        worker ID was not registered.
        """

        normalized_id = self._normalize_worker_id(
            worker_id
        )

        with self._lock:
            return (
                self._workers.pop(
                    normalized_id,
                    None,
                )
                is not None
            )

    # =========================================================
    # Listing
    # =========================================================

    def list_workers(
        self,
    ) -> list[str]:
        with self._lock:
            return sorted(
                self._workers.keys()
            )

    def describe_workers(
        self,
    ) -> list[dict[str, Any]]:
        """
        Return serializable worker registration information.

        Worker objects are deliberately excluded.
        """

        with self._lock:
            return [
                {
                    "worker_id": worker_id,
                    "description":
                        record["description"],
                    "metadata":
                        dict(record["metadata"]),
                    "capabilities":
                        list(record["capabilities"]),
                }
                for worker_id, record
                in sorted(self._workers.items())
            ]

    # =========================================================
    # Count
    # =========================================================

    def count(
        self,
    ) -> int:
        with self._lock:
            return len(
                self._workers
            )

    # =========================================================
    # Validation
    # =========================================================

    @staticmethod
    def _normalize_worker_id(
        worker_id: str,
    ) -> str:
        if not isinstance(
            worker_id,
            str,
        ):
            raise TypeError(
                "worker_id must be a string."
            )

        normalized = worker_id.strip()

        if not normalized:
            raise ValueError(
                "worker_id cannot be empty."
            )

        return normalized

