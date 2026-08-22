import json
import threading
import time

from pathlib import Path
from typing import Any

from app.agent.jobs.job import Job
from app.agent.jobs.job_manager import JobManager
from app.agent.jobs.job_queue import JobQueue, Empty
from app.agent.jobs.job_recovery import JobRecoveryService
from app.agent.jobs.job_state import (
    JobState,
    validate_transition,
)


class JobDispatcher:
    """
    Crash-aware local asynchronous job dispatcher.

    Architecture:

        SQLite JobStore
            = durable operational source of truth

        JobQueue
            = temporary in-memory dispatch queue containing
              job IDs only

        JobManager
            = actual execution engine

    Guarantees implemented in this version:

        1. Job is persisted as QUEUED before enqueue.

        2. Queue contains job_id rather than Job objects.

        3. Persisted QUEUED jobs are recovered before worker
           threads start.

        4. RUNNING / VALIDATING jobs left from a previous
           process are detected through JobRecoveryService.

        5. Workers atomically claim:
               QUEUED -> RUNNING

        6. Only the worker that successfully claims the job
           may execute it.

    This remains a single-process dispatcher. A future
    distributed dispatcher can replace the in-memory queue
    without changing the durable JobStore contract.
    """

    def __init__(
        self,
        registry,
        job_manager: JobManager | None = None,
        job_queue: JobQueue | None = None,
        worker_count: int = 1,
        poll_timeout: float = 0.5,
        recover_on_start: bool = True,
        stale_after_seconds: int = 0,
    ):
        if worker_count <= 0:
            raise ValueError(
                "worker_count must be greater than zero."
            )

        if poll_timeout <= 0:
            raise ValueError(
                "poll_timeout must be greater than zero."
            )

        if stale_after_seconds < 0:
            raise ValueError(
                "stale_after_seconds cannot be negative."
            )

        self.registry = registry

        self.job_manager = (
            job_manager
            or JobManager()
        )

        self.job_store = (
            self.job_manager.job_store
        )

        self.job_queue = (
            job_queue
            or JobQueue()
        )

        self.worker_count = worker_count
        self.poll_timeout = poll_timeout

        self.recover_on_start = (
            recover_on_start
        )

        self.stale_after_seconds = (
            stale_after_seconds
        )

        self._threads: list[
            threading.Thread
        ] = []

        self._stop_event = (
            threading.Event()
        )

        self._started = False

        self._lock = (
            threading.Lock()
        )

    # =========================================================
    # Job reconstruction
    # =========================================================

    def _load_job(
        self,
        job_id: str,
    ) -> Job | None:
        """
        Reconstruct a Job object.

        Prefer detailed job.json because it contains event
        history.

        SQLite remains authoritative for the current durable
        state and operational fields.
        """

        stored = self.job_store.get(
            job_id
        )

        if stored is None:
            return None

        job_file = (
            Path(
                self.job_manager.base_directory
            )
            / job_id
            / "job.json"
        )

        details: dict[str, Any] = {}

        if job_file.exists():

            try:

                details = json.loads(
                    job_file.read_text(
                        encoding="utf-8"
                    )
                )

            except (
                json.JSONDecodeError,
                OSError,
            ):
                details = {}

        job = Job(
            job_id=stored["job_id"],
            domain=stored["domain"],
            tool=stored["tool"],

            status=stored["status"],

            worker=stored.get(
                "worker"
            ),

            request=stored.get(
                "request",
                {},
            ),

            artifacts=stored.get(
                "artifacts",
                [],
            ),

            events=details.get(
                "events",
                [],
            ),

            created_at=stored[
                "created_at"
            ],

            started_at=stored.get(
                "started_at"
            ),

            completed_at=stored.get(
                "completed_at"
            ),

            duration_seconds=stored.get(
                "duration_seconds"
            ),

            result=stored.get(
                "result"
            ),

            error=stored.get(
                "error"
            ),

            attempt=stored.get(
                "attempt",
                0,
            ),

            max_attempts=stored.get(
                "max_attempts",
                3,
            ),

            last_failure_type=stored.get(
                "last_failure_type"
            ),
        )

        return job

    # =========================================================
    # Persist QUEUED before enqueue
    # =========================================================

    def _persist_queued(
        self,
        job: Job,
    ) -> None:
        """
        Transition CREATED -> QUEUED and persist before
        inserting the job ID into the in-memory queue.

        Commit-before-enqueue invariant:

            SQLite QUEUED commit
                    ↓
            queue.put(job_id)

        If the process dies after SQLite commit but before
        queue.put(), startup recovery will rediscover the job.
        """

        current = JobState(
            job.status
        )

        if current == JobState.CREATED:

            validate_transition(
                current=JobState.CREATED,
                target=JobState.QUEUED,
            )

            job.status = (
                JobState.QUEUED.value
            )

            # _save_job persists both job.json and SQLite.
            # SQLite commit occurs before this method returns.
            self.job_manager._save_job(
                job
            )

            self.job_manager._record_event(
                job,
                event=self._queued_event(),
                async_submission=True,
            )

            return

        if current == JobState.QUEUED:

            # Already durable.
            self.job_manager._save_job(
                job
            )

            return

        raise ValueError(
            "Only CREATED or QUEUED jobs may "
            "be submitted to the dispatcher. "
            f"Current state={current.value}"
        )

    # =========================================================
    # Queue event helper
    # =========================================================

    @staticmethod
    def _queued_event():
        """
        Local import avoids unnecessary circular imports.
        """

        from app.agent.jobs.job_events import (
            JobEvent,
        )

        return JobEvent.QUEUED

    # =========================================================
    # Startup recovery
    # =========================================================

    def _recover_before_start(
        self,
    ) -> dict[str, Any]:
        """
        Recovery MUST happen before worker threads start.

        Phase 1:
            detect stale RUNNING / VALIDATING jobs and mark
            RECOVERY_REQUIRED.

        Phase 2:
            reload persisted QUEUED jobs into the in-memory
            queue.

        QUEUED jobs are safe to replay because workers still
        need to atomically claim them before execution.
        """

        recovery_required = []

        if self.recover_on_start:

            recovery_service = (
                JobRecoveryService(
                    job_store=(
                        self.job_store
                    ),
                    base_directory=str(
                        self.job_manager
                        .base_directory
                    ),
                )
            )

            recovery_required = (
                recovery_service.scan(
                    stale_after_seconds=(
                        self.stale_after_seconds
                    ),
                    include_queued=False,
                )
            )

        queued_jobs = (
            self.job_store
            .list_queued_jobs()
        )

        queued_ids = []

        for item in queued_jobs:

            job_id = item[
                "job_id"
            ]

            self.job_queue.put(
                job_id
            )

            queued_ids.append(
                job_id
            )

        return {
            "recovery_required": [
                item["job_id"]
                for item
                in recovery_required
            ],
            "requeued": queued_ids,
        }

    # =========================================================
    # Start
    # =========================================================

    def start(
        self,
    ) -> dict[str, Any]:
        """
        Start dispatcher.

        Critical ordering:

            recovery
                ↓
            rebuild queue
                ↓
            start workers

        Never start workers before recovery.
        """

        with self._lock:

            if self._started:

                return {
                    "started": False,
                    "reason": (
                        "Dispatcher already running."
                    ),
                    "workers": len(
                        self._threads
                    ),
                    "requeued": [],
                    "recovery_required": [],
                }

            self._stop_event.clear()

            # ---------------------------------------------
            # Recovery BEFORE workers
            # ---------------------------------------------

            recovery = (
                self._recover_before_start()
            )

            # ---------------------------------------------
            # Start workers only after durable queue
            # reconstruction is complete.
            # ---------------------------------------------

            self._threads = []

            for index in range(
                self.worker_count
            ):

                thread = threading.Thread(
                    target=self._worker_loop,
                    name=(
                        "job-dispatcher-"
                        f"{index + 1}"
                    ),
                    daemon=True,
                )

                thread.start()

                self._threads.append(
                    thread
                )

            self._started = True

            return {
                "started": True,
                "workers": (
                    self.worker_count
                ),
                "requeued": recovery[
                    "requeued"
                ],
                "recovery_required": (
                    recovery[
                        "recovery_required"
                    ]
                ),
            }

    # =========================================================
    # Submit existing job
    # =========================================================

    def submit(
        self,
        job: Job,
    ) -> str:
        """
        Persist job as QUEUED, then enqueue job_id.

        The job ID enters the in-memory queue ONLY after
        durable SQLite persistence succeeds.
        """

        if not self._started:
            raise RuntimeError(
                "JobDispatcher has not been started."
            )

        # ---------------------------------------------
        # COMMIT BEFORE ENQUEUE
        # ---------------------------------------------

        self._persist_queued(
            job
        )

        # Only after durable persistence succeeds:
        self.job_queue.put(
            job.job_id
        )

        return job.job_id

    # =========================================================
    # Create + submit
    # =========================================================

    def create_and_submit(
        self,
        domain: str,
        tool: str,
        request: dict[str, Any] | None = None,
        artifacts: list[
            dict[str, Any]
        ] | None = None,
        max_attempts: int | None = None,
    ) -> str:
        """
        Create, durably queue, and submit a job.

        Returns immediately with job_id.
        """

        job = (
            self.job_manager
            .create_job(
                domain=domain,
                tool=tool,
                request=request,
                artifacts=artifacts,
                max_attempts=(
                    max_attempts
                ),
            )
        )

        return self.submit(
            job
        )

    # =========================================================
    # Worker loop
    # =========================================================

    def _worker_loop(
        self,
    ) -> None:
        """
        Background worker.

        Queue contains only job IDs.

        Every worker must atomically claim QUEUED -> RUNNING
        before executing.
        """

        while not self._stop_event.is_set():

            try:

                job_id = (
                    self.job_queue.get(
                        timeout=(
                            self.poll_timeout
                        )
                    )
                )

            except Empty:
                continue

            try:

                # -----------------------------------------
                # Atomic claim
                # -----------------------------------------

                claimed = (
                    self.job_store
                    .claim_queued_job(
                        job_id
                    )
                )

                if not claimed:

                    # Another worker already claimed it,
                    # or the durable state changed.
                    continue

                # -----------------------------------------
                # Reload authoritative job state
                # -----------------------------------------

                job = self._load_job(
                    job_id
                )

                if job is None:

                    continue

                # claim_queued_job already persisted RUNNING.
                job.status = (
                    JobState.RUNNING.value
                )

                # -----------------------------------------
                # Execute through existing JobManager
                # -----------------------------------------

                self.job_manager.execute(
                    job,
                    self.registry,
                )

            except Exception as exc:

                # JobManager normally owns execution failure
                # handling. This catches dispatcher-level
                # problems that happen outside JobManager.
                try:

                    stored = (
                        self.job_store.get(
                            job_id
                        )
                    )

                    if (
                        stored is not None
                        and stored["status"]
                        not in {
                            JobState.COMPLETED.value,
                            JobState.FAILED.value,
                            JobState.TIMED_OUT.value,
                            JobState.CANCELLED.value,
                            JobState.RECOVERY_REQUIRED.value,
                        }
                    ):

                        self.job_store.set_status(
                            job_id=job_id,
                            status=(
                                JobState
                                .RECOVERY_REQUIRED
                                .value
                            ),
                            error=(
                                "Dispatcher-level failure: "
                                f"{exc}"
                            ),
                        )

                except Exception:
                    # Avoid killing the dispatcher worker
                    # because failure-state persistence also
                    # failed.
                    pass

            finally:

                self.job_queue.task_done()

    # =========================================================
    # Wait for currently queued work
    # =========================================================

    def wait_until_idle(
        self,
    ) -> None:

        self.job_queue.join()

    # =========================================================
    # Stop
    # =========================================================

    def stop(
        self,
        wait: bool = True,
        timeout: float | None = None,
    ) -> None:
        """
        Request worker shutdown.

        Running tool processes are not forcibly killed in v1.
        """

        self._stop_event.set()

        if (
            wait
            and self._threads
        ):

            start = (
                time.perf_counter()
            )

            for thread in self._threads:

                remaining = None

                if timeout is not None:

                    elapsed = (
                        time.perf_counter()
                        - start
                    )

                    remaining = max(
                        0.0,
                        timeout - elapsed,
                    )

                thread.join(
                    timeout=remaining
                )

        with self._lock:

            self._started = False

    # =========================================================
    # Status helpers
    # =========================================================

    def is_running(
        self,
    ) -> bool:

        return self._started

    def queue_size(
        self,
    ) -> int:

        return self.job_queue.size()

    def worker_status(
        self,
    ) -> list[dict[str, Any]]:

        return [
            {
                "name":
                    thread.name,

                "alive":
                    thread.is_alive(),

                "daemon":
                    thread.daemon,
            }

            for thread
            in self._threads
        ]