import time

from threading import Lock
from typing import Any

from app.agent.workers.worker_health import (
    WorkerHealthRecord,
    WorkerHealthStatus,
)

from app.agent.workers.worker_registry import (
    WorkerRegistry,
)


class WorkerHealthService:
    """
    Perform worker heartbeat checks and retain the latest
    health observation for each worker.

    Current heartbeat contract:
        - worker must provide ping()
        - return_code == 0 means healthy
        - status == "timeout" means timeout
        - exceptions and non-zero return codes mean unhealthy

    This service does not route workloads or run background
    heartbeat threads.
    """

    def __init__(
        self,
        worker_registry: WorkerRegistry,
    ):
        if not isinstance(
            worker_registry,
            WorkerRegistry,
        ):
            raise TypeError(
                "worker_registry must be a "
                "WorkerRegistry instance."
            )

        self.worker_registry = (
            worker_registry
        )

        self._health_records: dict[
            str,
            WorkerHealthRecord,
        ] = {}

        self._lock = Lock()

    # =========================================================
    # Record access
    # =========================================================

    def _get_or_create_record(
        self,
        worker_id: str,
    ) -> WorkerHealthRecord:

        with self._lock:

            record = self._health_records.get(
                worker_id
            )

            if record is None:

                record = WorkerHealthRecord(
                    worker_id=worker_id
                )

                self._health_records[
                    worker_id
                ] = record

            return record

    def get_health(
        self,
        worker_id: str,
    ) -> dict[str, Any] | None:
        """
        Return the latest health record.

        Registered workers that have not been checked return
        an UNKNOWN record. Missing workers return None.
        """

        if not self.worker_registry.contains(
            worker_id
        ):
            return None

        record = self._get_or_create_record(
            worker_id
        )

        with self._lock:
            return record.to_dict()

    def list_health(
        self,
    ) -> list[dict[str, Any]]:
        """
        Return current health information for every registered
        worker without performing new heartbeat checks.
        """

        return [
            self.get_health(
                worker_id
            )
            for worker_id
            in self.worker_registry.list_workers()
        ]

    # =========================================================
    # Heartbeat
    # =========================================================

    def check_worker(
        self,
        worker_id: str,
    ) -> dict[str, Any]:
        """
        Execute one heartbeat check for a registered worker.
        """

        worker = self.worker_registry.get_worker(
            worker_id
        )

        if worker is None:
            raise ValueError(
                "Worker is not registered: "
                f"{worker_id}"
            )

        record = self._get_or_create_record(
            worker_id
        )

        ping = getattr(
            worker,
            "ping",
            None,
        )

        if not callable(ping):

            with self._lock:

                record.mark_failure(
                    status=(
                        WorkerHealthStatus
                        .UNHEALTHY
                    ),
                    message=(
                        "Worker does not provide "
                        "a callable ping() method."
                    ),
                    details={
                        "error":
                            "missing_ping_method",
                    },
                )

                return record.to_dict()

        started = time.perf_counter()

        try:

            result = ping()

            latency_seconds = (
                time.perf_counter()
                - started
            )

        except TimeoutError as exc:

            latency_seconds = (
                time.perf_counter()
                - started
            )

            with self._lock:

                record.mark_failure(
                    status=(
                        WorkerHealthStatus
                        .TIMEOUT
                    ),
                    message=str(exc),
                    latency_seconds=(
                        latency_seconds
                    ),
                    details={
                        "exception_type":
                            type(exc).__name__,
                    },
                )

                return record.to_dict()

        except Exception as exc:

            latency_seconds = (
                time.perf_counter()
                - started
            )

            with self._lock:

                record.mark_failure(
                    status=(
                        WorkerHealthStatus
                        .UNHEALTHY
                    ),
                    message=str(exc),
                    latency_seconds=(
                        latency_seconds
                    ),
                    details={
                        "exception_type":
                            type(exc).__name__,
                    },
                )

                return record.to_dict()

        if not isinstance(
            result,
            dict,
        ):

            with self._lock:

                record.mark_failure(
                    status=(
                        WorkerHealthStatus
                        .UNHEALTHY
                    ),
                    message=(
                        "Worker ping() returned "
                        "an invalid result."
                    ),
                    latency_seconds=(
                        latency_seconds
                    ),
                    details={
                        "result_type":
                            type(result).__name__,
                    },
                )

                return record.to_dict()

        result_status = result.get(
            "status"
        )

        return_code = result.get(
            "return_code"
        )

        details = {
            "host":
                result.get("host"),

            "username":
                result.get("username"),

            "return_code":
                return_code,

            "stdout":
                result.get(
                    "stdout",
                    "",
                ),

            "stderr":
                result.get(
                    "stderr",
                    "",
                ),
        }

        if result_status == "timeout":

            message = (
                result.get("stderr")
                or "Worker heartbeat timed out."
            )

            with self._lock:

                record.mark_failure(
                    status=(
                        WorkerHealthStatus
                        .TIMEOUT
                    ),
                    message=message,
                    latency_seconds=(
                        latency_seconds
                    ),
                    details=details,
                )

                return record.to_dict()

        if return_code == 0:

            hostname = (
                result.get(
                    "stdout",
                    "",
                ).strip()
            )

            message = (
                "Worker heartbeat succeeded."
            )

            if hostname:
                details[
                    "hostname"
                ] = hostname

            with self._lock:

                record.mark_healthy(
                    latency_seconds=(
                        latency_seconds
                    ),
                    message=message,
                    details=details,
                )

                return record.to_dict()

        message = (
            result.get("stderr")
            or result.get("stdout")
            or (
                "Worker heartbeat failed with "
                f"return_code={return_code}."
            )
        )

        with self._lock:

            record.mark_failure(
                status=(
                    WorkerHealthStatus
                    .UNHEALTHY
                ),
                message=message,
                latency_seconds=(
                    latency_seconds
                ),
                details=details,
            )

            return record.to_dict()