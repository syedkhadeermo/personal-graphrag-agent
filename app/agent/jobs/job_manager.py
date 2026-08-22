import json
import time

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from app.agent.jobs.job import Job
from app.agent.jobs.job_events import JobEvent
from app.agent.jobs.job_state import (
    JobState,
    validate_transition,
)
from app.agent.jobs.job_store import JobStore
from app.agent.jobs.failure_classifier import (
    FailureClassifier,
    FailureType,
)
from app.agent.jobs.retry_policy import RetryPolicy

from app.agent.observability.structured_logger import (
    StructuredLogger,
)

from app.agent.artifacts.artifact_validator import (
    ArtifactValidator,
)

from app.agent.artifacts.artifact_manifest import (
    ArtifactManifest,
)

from app.agent.workers.remote_compute_worker import (
    RemoteComputeWorker,
)

from app.agent.workers.worker_capabilities import (
    normalize_capabilities,
)

from app.agent.workers.worker_health_service import (
    WorkerHealthService,
)

from app.agent.workers.worker_registry import (
    WorkerRegistry,
)

from app.agent.workers.workload_router import (
    WorkloadRouter,
)


class JobManager:
    """
    Job execution engine.

    Supports both:

        synchronous execution
        CREATED -> QUEUED -> RUNNING

    and:

        dispatcher execution
        job already atomically claimed as RUNNING

    Responsibilities:
        - state transitions
        - lifecycle events
        - SQLite persistence
        - retries
        - failure classification
        - artifact validation
        - local artifact manifest registration
        - remote artifact manifest registration
        - remote worker checks
    """

    def __init__(
        self,
        base_directory: str = "data/jobs",
        job_store: JobStore | None = None,
        retry_policy: RetryPolicy | None = None,
        worker_registry: WorkerRegistry | None = None,
        worker_health_service: WorkerHealthService | None = None,
        workload_router: WorkloadRouter | None = None,
    ):
        self.base_directory = Path(
            base_directory
        )

        self.base_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.logger = StructuredLogger(
            base_directory=base_directory,
        )

        self.artifact_validator = (
            ArtifactValidator()
        )

        self.job_store = (
            job_store
            or JobStore()
        )

        self.retry_policy = (
            retry_policy
            or RetryPolicy(
                max_attempts=3,
                base_delay_seconds=1.0,
                max_delay_seconds=30.0,
            )
        )

        self.failure_classifier = (
            FailureClassifier()
        )

        # -----------------------------------------------------
        # Optional health-aware worker routing
        # -----------------------------------------------------

        if workload_router is not None:

            if not isinstance(
                workload_router,
                WorkloadRouter,
            ):
                raise TypeError(
                    "workload_router must be a "
                    "WorkloadRouter instance."
                )

            if (
                worker_registry is not None
                and workload_router.worker_registry
                is not worker_registry
            ):
                raise ValueError(
                    "workload_router and worker_registry "
                    "must use the same registry."
                )

            if (
                worker_health_service is not None
                and workload_router.health_service
                is not worker_health_service
            ):
                raise ValueError(
                    "workload_router and "
                    "worker_health_service must use the "
                    "same health service."
                )

            self.worker_registry = (
                workload_router.worker_registry
            )

            self.worker_health_service = (
                workload_router.health_service
            )

            self.workload_router = (
                workload_router
            )

        elif worker_registry is not None:

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

            if worker_health_service is None:

                self.worker_health_service = (
                    WorkerHealthService(
                        worker_registry=(
                            worker_registry
                        )
                    )
                )

            else:

                if not isinstance(
                    worker_health_service,
                    WorkerHealthService,
                ):
                    raise TypeError(
                        "worker_health_service must be a "
                        "WorkerHealthService instance."
                    )

                if (
                    worker_health_service
                    .worker_registry
                    is not worker_registry
                ):
                    raise ValueError(
                        "worker_health_service must use "
                        "the supplied worker_registry."
                    )

                self.worker_health_service = (
                    worker_health_service
                )

            self.workload_router = (
                WorkloadRouter(
                    worker_registry=(
                        self.worker_registry
                    ),
                    health_service=(
                        self.worker_health_service
                    ),
                )
            )

        elif worker_health_service is not None:

            if not isinstance(
                worker_health_service,
                WorkerHealthService,
            ):
                raise TypeError(
                    "worker_health_service must be a "
                    "WorkerHealthService instance."
                )

            self.worker_health_service = (
                worker_health_service
            )

            self.worker_registry = (
                worker_health_service
                .worker_registry
            )

            self.workload_router = (
                WorkloadRouter(
                    worker_registry=(
                        self.worker_registry
                    ),
                    health_service=(
                        self.worker_health_service
                    ),
                )
            )

        else:

            # Backward-compatible legacy mode. Existing local
            # jobs and tests continue to work without routing
            # dependencies. Docker/application bootstrap will
            # inject the registry for production routing.
            self.worker_registry = None
            self.worker_health_service = None
            self.workload_router = None

        self._lock = Lock()

    # =========================================================
    # Job ID
    # =========================================================

    def _generate_job_id(
        self,
    ) -> str:

        with self._lock:

            counter_file = (
                self.base_directory
                / ".job_counter"
            )

            if counter_file.exists():

                try:
                    current = int(
                        counter_file.read_text(
                            encoding="utf-8"
                        ).strip()
                    )

                except ValueError:
                    current = 0

            else:
                current = 0

            current += 1

            counter_file.write_text(
                str(current),
                encoding="utf-8",
            )

            return f"JOB-{current:06d}"

    # =========================================================
    # Job directory
    # =========================================================

    def _job_directory(
        self,
        job_id: str,
    ) -> Path:

        directory = (
            self.base_directory
            / job_id
        )

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        return directory

    # =========================================================
    # Persistence
    # =========================================================

    def _save_job(
        self,
        job: Job,
    ) -> None:

        directory = (
            self._job_directory(
                job.job_id
            )
        )

        job_file = (
            directory
            / "job.json"
        )

        job_file.write_text(
            json.dumps(
                job.to_dict(),
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )

        self.job_store.upsert(
            job
        )

    # =========================================================
    # Events
    # =========================================================

    def _record_event(
        self,
        job: Job,
        event: JobEvent,
        **details: Any,
    ) -> None:

        record = self.logger.log(
            job_id=job.job_id,
            event=event.value,
            state=job.status,
            attempt=job.attempt,
            **details,
        )

        job.events.append(
            record
        )

        self._save_job(
            job
        )

    # =========================================================
    # State
    # =========================================================

    def _set_state(
        self,
        job: Job,
        target: JobState,
    ) -> None:

        current = JobState(
            job.status
        )

        validate_transition(
            current=current,
            target=target,
        )

        job.status = (
            target.value
        )

        self._save_job(
            job
        )

    # =========================================================
    # Create job
    # =========================================================

    def create_job(
        self,
        domain: str,
        tool: str,
        request: dict[str, Any] | None = None,
        artifacts: list[
            dict[str, Any]
        ] | None = None,
        max_attempts: int | None = None,
        required_capabilities: list[str] | None = None,
    ) -> Job:

        if not domain or not domain.strip():
            raise ValueError(
                "Job domain cannot be empty."
            )

        if not tool or not tool.strip():
            raise ValueError(
                "Job tool cannot be empty."
            )

        if max_attempts is None:
            max_attempts = (
                self.retry_policy
                .max_attempts
            )

        if max_attempts <= 0:
            raise ValueError(
                "max_attempts must be greater than zero."
            )

        job = Job(
            job_id=self._generate_job_id(),
            domain=domain.strip(),
            tool=tool.strip(),
            request=request or {},
            max_attempts=max_attempts,
        )

        job.request[
            "_expected_artifacts"
        ] = artifacts or []

        if required_capabilities is not None:

            job.request[
                "_required_capabilities"
            ] = list(
                normalize_capabilities(
                    required_capabilities
                )
            )

        self.job_store.create(
            job
        )

        self._record_event(
            job,
            JobEvent.CREATED,
            domain=job.domain,
            tool=job.tool,
            max_attempts=job.max_attempts,
        )

        return job

    # =========================================================
    # Tool result validation
    # =========================================================

    @staticmethod
    def _validate_tool_result(
        result: Any,
    ) -> None:

        classification = (
            FailureClassifier
            .classify_result(
                result
            )
        )

        if classification is None:
            return

        if (
            classification.failure_type
            == FailureType.TIMEOUT
        ):
            raise TimeoutError(
                classification.reason
            )

        if isinstance(
            result,
            dict,
        ):

            error_message = (
                result.get("error")
                or result.get("stderr")
                or result.get("stdout")
                or classification.reason
            )

        else:

            error_message = (
                classification.reason
            )

        raise RuntimeError(
            error_message
        )

    # =========================================================
    # Remote worker
    # =========================================================

    @staticmethod
    def _required_worker_capabilities(
        job: Job,
    ) -> tuple[str, ...]:
        """
        Resolve explicit job requirements first.

        Existing CAD jobs remain compatible by inferring a
        capability from their registered tool name.
        """

        configured = job.request.get(
            "_required_capabilities"
        )

        if configured is not None:

            return normalize_capabilities(
                configured
            )

        if job.domain == "cad_simulation":

            inferred = (
                job.tool
                .strip()
                .lower()
                .replace("-", "_")
                .replace(" ", "_")
            )

            if inferred in {
                "freecad",
                "blender",
                "openfoam",
                "gromacs",
            }:
                return (
                    inferred,
                )

        return ()

    def _prepare_remote_worker(
        self,
        job: Job,
    ) -> None:
        """
        Verify and assign a worker before tool execution.

        With routing dependencies injected:
            capability match -> heartbeat -> healthy selection

        Without routing dependencies:
            preserve the existing Mini-PC behavior for current
            cad_simulation jobs.
        """

        required_capabilities = (
            self._required_worker_capabilities(
                job
            )
        )

        if not required_capabilities:
            return

        # -----------------------------------------------------
        # Health-aware routed mode
        # -----------------------------------------------------

        if self.workload_router is not None:

            matching_workers = (
                self.worker_registry
                .find_workers(
                    required_capabilities
                )
            )

            if not matching_workers:
                raise RuntimeError(
                    "No registered worker supports "
                    "required capabilities: "
                    f"{list(required_capabilities)}"
                )

            for worker_id in matching_workers:

                self.worker_health_service.check_worker(
                    worker_id
                )

            try:

                selected_worker_id = (
                    self.workload_router
                    .select_worker(
                        required_capabilities=(
                            required_capabilities
                        ),
                    )
                )

            except LookupError as exc:

                raise RuntimeError(
                    "No healthy worker is available "
                    "for required capabilities: "
                    f"{list(required_capabilities)}"
                ) from exc

            worker = (
                self.worker_registry
                .get_worker(
                    selected_worker_id
                )
            )

            if worker is None:
                raise RuntimeError(
                    "Selected worker disappeared from "
                    "the registry: "
                    f"{selected_worker_id}"
                )

            worker_record = (
                self.worker_registry
                .get_record(
                    selected_worker_id
                )
                or {}
            )

            health = (
                self.worker_health_service
                .get_health(
                    selected_worker_id
                )
                or {}
            )

            health_details = (
                health.get(
                    "details",
                    {},
                )
            )

            metadata = (
                worker_record.get(
                    "metadata",
                    {},
                )
            )

            worker_host = (
                getattr(
                    worker,
                    "host",
                    None,
                )
                or metadata.get(
                    "host"
                )
                or selected_worker_id
            )

            worker_username = (
                getattr(
                    worker,
                    "username",
                    None,
                )
                or metadata.get(
                    "username"
                )
            )

            job.worker = selected_worker_id

            self._save_job(
                job
            )

            self._record_event(
                job,
                JobEvent.WORKER_ASSIGNED,
                worker=selected_worker_id,
                host=worker_host,
                username=worker_username,
                required_capabilities=list(
                    required_capabilities
                ),
                routing_mode="health_aware",
            )

            self._record_event(
                job,
                JobEvent.SSH_CONNECTED,
                worker=selected_worker_id,
                host=worker_host,
                hostname=(
                    health_details.get(
                        "hostname",
                        "",
                    )
                ),
                latency_seconds=(
                    health.get(
                        "latency_seconds"
                    )
                ),
            )

            return

        # -----------------------------------------------------
        # Backward-compatible legacy mode
        # -----------------------------------------------------

        if job.domain != "cad_simulation":
            return

        worker_host = "192.168.137.2"
        worker_username = "syed"

        job.worker = worker_host

        self._save_job(
            job
        )

        self._record_event(
            job,
            JobEvent.WORKER_ASSIGNED,
            worker=worker_host,
            username=worker_username,
            required_capabilities=list(
                required_capabilities
            ),
            routing_mode="legacy",
        )

        worker = RemoteComputeWorker(
            host=worker_host,
            username=worker_username,
        )

        connection = worker.ping()

        if (
            connection.get("status")
            == "timeout"
        ):
            raise TimeoutError(
                "SSH connection to remote "
                "worker timed out."
            )

        if connection.get("return_code") != 0:

            raise RuntimeError(
                "SSH connection failed: "
                f"host={worker_host}; "
                f"stderr={connection.get('stderr')}"
            )

        self._record_event(
            job,
            JobEvent.SSH_CONNECTED,
            worker=worker_host,
            hostname=(
                connection.get(
                    "stdout",
                    "",
                ).strip()
            ),
        )

    # =========================================================
    # Local artifact manifest
    # =========================================================

    def _register_local_artifact(
        self,
        job: Job,
        artifact: dict[str, Any],
        validation_result: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Register a validated local artifact in the
        per-job SHA-256 artifact manifest.

        Registration is idempotent. Registering the same
        bytes more than once returns the existing record.
        """

        path = artifact.get(
            "path"
        )

        artifact_type = (
            artifact.get(
                "artifact_type"
            )
            or artifact.get(
                "name"
            )
            or "file"
        )

        metadata = {
            "domain": job.domain,
            "tool": job.tool,
        }

        # Preserve useful validation metadata without
        # coupling ArtifactManifest to ArtifactValidator.
        if (
            validation_result.get(
                "size_bytes"
            )
            is not None
        ):
            metadata[
                "validated_size_bytes"
            ] = validation_result.get(
                "size_bytes"
            )

        manifest = ArtifactManifest(
            job_id=job.job_id,
            base_directory=str(
                self.base_directory
            ),
        )

        registration = (
            manifest.register_local_file(
                path=path,
                artifact_type=artifact_type,
                validated=True,
                metadata=metadata,
                attempt=job.attempt,
            )
        )

        return registration

    # =========================================================
    # Remote artifact manifest
    # =========================================================

    def _register_remote_artifact(
        self,
        job: Job,
        artifact: dict[str, Any],
        validation_result: dict[str, Any],
        hash_result: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Register a validated remote artifact in the
        per-job SHA-256 artifact manifest.

        Registration is idempotent. The remote file is not
        downloaded to the controller.
        """

        artifact_type = (
            artifact.get(
                "artifact_type"
            )
            or artifact.get(
                "name"
            )
            or "file"
        )

        metadata = {
            "domain": job.domain,
            "tool": job.tool,
        }

        if (
            validation_result.get(
                "size_bytes"
            )
            is not None
        ):
            metadata[
                "validated_size_bytes"
            ] = validation_result.get(
                "size_bytes"
            )

        manifest = ArtifactManifest(
            job_id=job.job_id,
            base_directory=str(
                self.base_directory
            ),
        )

        return (
            manifest.register_remote_artifact(
                remote_hash_result=hash_result,
                artifact_type=artifact_type,
                validated=True,
                metadata=metadata,
                attempt=job.attempt,
            )
        )

    # =========================================================
    # Artifacts
    # =========================================================

    def _validate_artifacts(
        self,
        job: Job,
    ) -> list[dict[str, Any]]:

        expected = (
            job.request.get(
                "_expected_artifacts",
                [],
            )
        )

        if not expected:
            return []

        if (
            job.status
            != JobState.VALIDATING.value
        ):

            self._set_state(
                job,
                JobState.VALIDATING,
            )

        self._record_event(
            job,
            JobEvent.ARTIFACT_VALIDATING,
            count=len(expected),
        )

        validation_results = []

        validated_paths = []

        for artifact in expected:

            artifact_type = (
                artifact.get(
                    "type"
                )
            )

            path = artifact.get(
                "path"
            )

            extensions = (
                artifact.get(
                    "extensions"
                )
            )

            if extensions is not None:

                extensions = tuple(
                    extensions
                )

            # =================================================
            # Local artifact
            # =================================================

            if (
                artifact_type
                == "local_file"
            ):

                result = (
                    self.artifact_validator
                    .validate_local_file(
                        path=path,
                        expected_extensions=(
                            extensions
                        ),
                    )
                )

                validation_results.append(
                    result
                )

                if not result.get(
                    "valid",
                    False,
                ):

                    self._record_event(
                        job,
                        JobEvent.ARTIFACT_INVALID,
                        path=path,
                        error=result.get(
                            "error"
                        ),
                    )

                    raise RuntimeError(
                        "Artifact validation failed: "
                        f"{path}. "
                        f"{result.get('error')}"
                    )

                # -----------------------------------------
                # Idempotent manifest registration
                # -----------------------------------------

                registration = (
                    self._register_local_artifact(
                        job=job,
                        artifact=artifact,
                        validation_result=result,
                    )
                )

                manifest_artifact = (
                    registration.get(
                        "artifact",
                        {},
                    )
                )

                self._record_event(
                    job,
                    JobEvent.ARTIFACT_VALID,
                    path=path,
                    size_bytes=result.get(
                        "size_bytes"
                    ),
                    artifact_id=(
                        manifest_artifact.get(
                            "artifact_id"
                        )
                    ),
                    sha256=(
                        manifest_artifact.get(
                            "sha256"
                        )
                    ),
                    manifest_created=(
                        registration.get(
                            "created"
                        )
                    ),
                    duplicate=(
                        registration.get(
                            "duplicate"
                        )
                    ),
                )

                validated_paths.append(
                    path
                )

            # =================================================
            # Remote artifact
            # =================================================

            elif (
                artifact_type
                == "remote_file"
            ):

                host = artifact.get(
                    "host",
                    "192.168.137.2",
                )

                username = artifact.get(
                    "username",
                    "syed",
                )

                worker = (
                    RemoteComputeWorker(
                        host=host,
                        username=username,
                    )
                )

                result = (
                    worker
                    .validate_remote_file(
                        path=path,
                        expected_extensions=(
                            extensions
                        ),
                    )
                )

                validation_results.append(
                    result
                )

                if not result.get(
                    "valid",
                    False,
                ):

                    self._record_event(
                        job,
                        JobEvent.ARTIFACT_INVALID,
                        path=path,
                        error=result.get(
                            "error"
                        ),
                    )

                    raise RuntimeError(
                        "Artifact validation failed: "
                        f"{path}. "
                        f"{result.get('error')}"
                    )

                # -----------------------------------------
                # Remote SHA-256 calculation
                # -----------------------------------------

                hash_result = (
                    worker
                    .calculate_remote_sha256(
                        path=path,
                    )
                )

                if not hash_result.get(
                    "valid",
                    False,
                ):

                    self._record_event(
                        job,
                        JobEvent.ARTIFACT_INVALID,
                        path=path,
                        error=hash_result.get(
                            "error"
                        ),
                        remote=True,
                    )

                    raise RuntimeError(
                        "Remote artifact hashing failed: "
                        f"{path}. "
                        f"{hash_result.get('error')}"
                    )

                validated_size = (
                    result.get(
                        "size_bytes"
                    )
                )

                hashed_size = (
                    hash_result.get(
                        "size_bytes"
                    )
                )

                if (
                    validated_size
                    != hashed_size
                ):

                    self._record_event(
                        job,
                        JobEvent.ARTIFACT_INVALID,
                        path=path,
                        error=(
                            "Remote artifact size changed "
                            "between validation and hashing."
                        ),
                        validated_size_bytes=(
                            validated_size
                        ),
                        hashed_size_bytes=(
                            hashed_size
                        ),
                        remote=True,
                    )

                    raise RuntimeError(
                        "Remote artifact changed between "
                        "validation and hashing: "
                        f"{path}. "
                        f"validated_size={validated_size}; "
                        f"hashed_size={hashed_size}"
                    )

                # -----------------------------------------
                # Idempotent remote manifest registration
                # -----------------------------------------

                registration = (
                    self._register_remote_artifact(
                        job=job,
                        artifact=artifact,
                        validation_result=result,
                        hash_result=hash_result,
                    )
                )

                manifest_artifact = (
                    registration.get(
                        "artifact",
                        {},
                    )
                )

                self._record_event(
                    job,
                    JobEvent.ARTIFACT_VALID,
                    path=path,
                    size_bytes=result.get(
                        "size_bytes"
                    ),
                    artifact_id=(
                        manifest_artifact.get(
                            "artifact_id"
                        )
                    ),
                    sha256=(
                        manifest_artifact.get(
                            "sha256"
                        )
                    ),
                    manifest_created=(
                        registration.get(
                            "created"
                        )
                    ),
                    duplicate=(
                        registration.get(
                            "duplicate"
                        )
                    ),
                    remote=True,
                    manifest_registered=True,
                )

                validated_paths.append(
                    path
                )

            # =================================================
            # Unsupported artifact type
            # =================================================

            else:

                raise ValueError(
                    "Unsupported artifact "
                    f"type: {artifact_type}"
                )

        job.artifacts = (
            validated_paths
        )

        self._save_job(
            job
        )

        return validation_results

    # =========================================================
    # Failure handling
    # =========================================================

    def _handle_attempt_failure(
        self,
        job: Job,
        exc: Exception,
    ) -> bool:

        classification = (
            self.failure_classifier
            .classify_exception(
                exc
            )
        )

        job.last_failure_type = (
            classification
            .failure_type
            .value
        )

        job.error = str(
            exc
        )

        self._save_job(
            job
        )

        self._record_event(
            job,
            JobEvent.FAILURE_CLASSIFIED,
            failure_type=(
                classification
                .failure_type
                .value
            ),
            retryable=(
                classification
                .retryable
            ),
            reason=(
                classification
                .reason
            ),
            error=str(exc),
        )

        policy = RetryPolicy(
            max_attempts=job.max_attempts,
            base_delay_seconds=(
                self.retry_policy
                .base_delay_seconds
            ),
            max_delay_seconds=(
                self.retry_policy
                .max_delay_seconds
            ),
        )

        decision = policy.evaluate(
            classification=classification,
            attempt=job.attempt,
        )

        if not decision.retry:
            return False

        self._record_event(
            job,
            JobEvent.RETRYING,
            failed_attempt=job.attempt,
            next_attempt=job.attempt + 1,
            delay_seconds=(
                decision.delay_seconds
            ),
            reason=decision.reason,
        )

        if (
            decision.delay_seconds
            > 0
        ):

            time.sleep(
                decision.delay_seconds
            )

        return True

    # =========================================================
    # Execution preparation
    # =========================================================

    def _prepare_execution_state(
        self,
        job: Job,
    ) -> None:
        """
        Synchronous:
            CREATED -> QUEUED -> RUNNING

        Dispatcher:
            already RUNNING
        """

        current = JobState(
            job.status
        )

        if current == JobState.CREATED:

            self._set_state(
                job,
                JobState.QUEUED,
            )

            self._record_event(
                job,
                JobEvent.QUEUED,
                execution_mode="synchronous",
            )

            self._set_state(
                job,
                JobState.RUNNING,
            )

        elif current == JobState.QUEUED:

            self._set_state(
                job,
                JobState.RUNNING,
            )

        elif current == JobState.RUNNING:

            # Dispatcher already claimed the job.
            pass

        else:

            raise ValueError(
                "Job cannot enter execution from "
                f"state={current.value}"
            )

        if job.started_at is None:

            job.started_at = (
                datetime.now(
                    timezone.utc
                ).isoformat()
            )

            self._save_job(
                job
            )

    # =========================================================
    # Execute
    # =========================================================

    def execute(
        self,
        job: Job,
        registry,
    ) -> Job:

        overall_start = (
            time.perf_counter()
        )

        try:

            self._prepare_execution_state(
                job
            )

            tool_info = (
                registry.get_tool(
                    job.domain,
                    job.tool,
                )
            )

            if tool_info is None:

                raise ValueError(
                    f"Tool '{job.tool}' "
                    "is not registered for "
                    f"domain '{job.domain}'."
                )

            self._record_event(
                job,
                JobEvent.TOOL_SELECTED,
                domain=job.domain,
                tool=job.tool,
            )

            tool_request = dict(
                job.request
            )

            tool_request.pop(
                "_expected_artifacts",
                None,
            )

            tool_request.pop(
                "_required_capabilities",
                None,
            )

            tool_request.pop(
                "_delegated_agent_id",
                None,
            )

            tool_request.pop(
                "_delegation_route",
                None,
            )

            # =================================================
            # Retry loop
            # =================================================

            while (
                job.attempt
                < job.max_attempts
            ):

                job.attempt += 1

                self._save_job(
                    job
                )

                try:

                    self._prepare_remote_worker(
                        job
                    )

                    self._record_event(
                        job,
                        JobEvent.PROCESS_STARTED,
                        current_attempt=(
                            job.attempt
                        ),
                    )

                    result = (
                        registry.execute(
                            job.domain,
                            job.tool,
                            tool_request,
                        )
                    )

                    job.result = result

                    self._save_job(
                        job
                    )

                    self._validate_tool_result(
                        result
                    )

                    self._record_event(
                        job,
                        JobEvent.PROCESS_COMPLETED,
                        current_attempt=(
                            job.attempt
                        ),
                        return_code=(
                            result.get(
                                "return_code"
                            )
                            if isinstance(
                                result,
                                dict,
                            )
                            else None
                        ),
                    )

                    # -----------------------------------------
                    # Validate + register artifacts
                    # -----------------------------------------

                    self._validate_artifacts(
                        job
                    )

                    job.completed_at = (
                        datetime.now(
                            timezone.utc
                        ).isoformat()
                    )

                    job.duration_seconds = round(
                        time.perf_counter()
                        - overall_start,
                        3,
                    )

                    if (
                        job.status
                        != JobState.COMPLETED.value
                    ):

                        self._set_state(
                            job,
                            JobState.COMPLETED,
                        )

                    job.error = None

                    self._save_job(
                        job
                    )

                    self._record_event(
                        job,
                        JobEvent.COMPLETED,
                        duration_seconds=(
                            job.duration_seconds
                        ),
                        attempts_used=(
                            job.attempt
                        ),
                    )

                    return job

                except Exception as attempt_exc:

                    should_retry = (
                        self._handle_attempt_failure(
                            job,
                            attempt_exc,
                        )
                    )

                    if should_retry:
                        continue

                    raise attempt_exc

            raise RuntimeError(
                "Maximum execution attempts exhausted."
            )

        # =====================================================
        # Timeout
        # =====================================================

        except TimeoutError as exc:

            job.error = str(
                exc
            )

            job.completed_at = (
                datetime.now(
                    timezone.utc
                ).isoformat()
            )

            job.duration_seconds = round(
                time.perf_counter()
                - overall_start,
                3,
            )

            current = JobState(
                job.status
            )

            if (
                current
                not in {
                    JobState.COMPLETED,
                    JobState.TIMED_OUT,
                    JobState.FAILED,
                    JobState.CANCELLED,
                }
            ):

                validate_transition(
                    current,
                    JobState.TIMED_OUT,
                )

                job.status = (
                    JobState
                    .TIMED_OUT
                    .value
                )

            self._save_job(
                job
            )

            self._record_event(
                job,
                JobEvent.TIMEOUT,
                error=str(exc),
                duration_seconds=(
                    job.duration_seconds
                ),
                attempts_used=(
                    job.attempt
                ),
            )

            return job

        # =====================================================
        # Permanent / exhausted failure
        # =====================================================

        except Exception as exc:

            job.error = str(
                exc
            )

            job.completed_at = (
                datetime.now(
                    timezone.utc
                ).isoformat()
            )

            job.duration_seconds = round(
                time.perf_counter()
                - overall_start,
                3,
            )

            current = JobState(
                job.status
            )

            if (
                current
                not in {
                    JobState.COMPLETED,
                    JobState.FAILED,
                    JobState.TIMED_OUT,
                    JobState.CANCELLED,
                }
            ):

                validate_transition(
                    current,
                    JobState.FAILED,
                )

                job.status = (
                    JobState.FAILED.value
                )

            self._save_job(
                job
            )

            self._record_event(
                job,
                JobEvent.FAILED,
                error=str(exc),
                failure_type=(
                    job.last_failure_type
                ),
                attempts_used=(
                    job.attempt
                ),
                duration_seconds=(
                    job.duration_seconds
                ),
            )

            return job
