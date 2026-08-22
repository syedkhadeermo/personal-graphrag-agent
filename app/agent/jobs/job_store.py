import json
import sqlite3

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from app.agent.jobs.job import Job


class JobStore:
    """
    Persistent SQLite operational index for agent jobs.

    Responsibilities:
        - persist durable job state
        - retrieve jobs after restart
        - filter jobs by status/domain/tool/worker
        - persist retry metadata
        - identify stale in-flight jobs
        - recover queued jobs
        - atomically claim queued jobs for workers

    SQLite is the operational source of truth.

    Detailed provenance remains in:
        data/jobs/<job_id>/job.json
        data/jobs/<job_id>/events.jsonl
    """

    def __init__(
        self,
        database_path: str = "data/state/jobs.db",
    ):
        self.database_path = Path(
            database_path
        )

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._lock = Lock()

        self._initialize_database()

    # =========================================================
    # Connection
    # =========================================================

    def _connect(
        self,
    ) -> sqlite3.Connection:

        connection = sqlite3.connect(
            self.database_path,
            timeout=30,
        )

        connection.row_factory = sqlite3.Row

        # Better behavior for multiple worker threads.
        connection.execute(
            "PRAGMA busy_timeout = 30000"
        )

        return connection

    # =========================================================
    # Schema
    # =========================================================

    def _initialize_database(
        self,
    ) -> None:

        with self._connect() as connection:

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,

                    status TEXT NOT NULL,

                    domain TEXT NOT NULL,
                    tool TEXT NOT NULL,

                    worker TEXT,

                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,

                    duration_seconds REAL,

                    error TEXT,

                    request_json TEXT,
                    result_json TEXT,
                    artifacts_json TEXT,

                    attempt INTEGER DEFAULT 0,
                    max_attempts INTEGER DEFAULT 3,
                    last_failure_type TEXT,

                    updated_at TEXT
                    DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            self._migrate_schema(
                connection
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_jobs_status
                ON jobs(status)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_jobs_domain
                ON jobs(domain)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_jobs_tool
                ON jobs(tool)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_jobs_worker
                ON jobs(worker)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_jobs_created_at
                ON jobs(created_at)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_jobs_status_created
                ON jobs(status, created_at)
                """
            )

            connection.commit()

    # =========================================================
    # Schema migration
    # =========================================================

    @staticmethod
    def _migrate_schema(
        connection: sqlite3.Connection,
    ) -> None:
        """
        Add newer columns without deleting the existing DB.
        """

        rows = connection.execute(
            "PRAGMA table_info(jobs)"
        ).fetchall()

        existing_columns = {
            row[1]
            for row in rows
        }

        migrations = {
            "attempt":
                "INTEGER DEFAULT 0",

            "max_attempts":
                "INTEGER DEFAULT 3",

            "last_failure_type":
                "TEXT",
        }

        for column, definition in migrations.items():

            if column in existing_columns:
                continue

            connection.execute(
                f"""
                ALTER TABLE jobs
                ADD COLUMN {column}
                {definition}
                """
            )

        connection.commit()

    # =========================================================
    # JSON helpers
    # =========================================================

    @staticmethod
    def _json_dump(
        value: Any,
    ) -> str:

        return json.dumps(
            value,
            default=str,
        )

    @staticmethod
    def _json_load(
        value: str | None,
        default: Any,
    ) -> Any:

        if not value:
            return default

        try:
            return json.loads(
                value
            )

        except json.JSONDecodeError:
            return default

    # =========================================================
    # Create
    # =========================================================

    def create(
        self,
        job: Job,
    ) -> None:
        """
        Persist a newly-created job.

        The INSERT is committed before this method returns.
        """

        with self._lock:

            with self._connect() as connection:

                connection.execute(
                    """
                    INSERT INTO jobs (
                        job_id,
                        status,
                        domain,
                        tool,
                        worker,

                        created_at,
                        started_at,
                        completed_at,

                        duration_seconds,
                        error,

                        request_json,
                        result_json,
                        artifacts_json,

                        attempt,
                        max_attempts,
                        last_failure_type
                    )

                    VALUES (
                        ?, ?, ?, ?, ?,
                        ?, ?, ?,
                        ?, ?,
                        ?, ?, ?,
                        ?, ?, ?
                    )
                    """,
                    (
                        job.job_id,
                        job.status,
                        job.domain,
                        job.tool,
                        job.worker,

                        job.created_at,
                        job.started_at,
                        job.completed_at,

                        job.duration_seconds,
                        job.error,

                        self._json_dump(
                            job.request
                        ),

                        self._json_dump(
                            job.result
                        ),

                        self._json_dump(
                            job.artifacts
                        ),

                        job.attempt,
                        job.max_attempts,
                        job.last_failure_type,
                    ),
                )

                connection.commit()

    # =========================================================
    # Update
    # =========================================================

    def update(
        self,
        job: Job,
    ) -> None:

        with self._lock:

            with self._connect() as connection:

                cursor = connection.execute(
                    """
                    UPDATE jobs

                    SET
                        status = ?,
                        domain = ?,
                        tool = ?,
                        worker = ?,

                        started_at = ?,
                        completed_at = ?,

                        duration_seconds = ?,
                        error = ?,

                        request_json = ?,
                        result_json = ?,
                        artifacts_json = ?,

                        attempt = ?,
                        max_attempts = ?,
                        last_failure_type = ?,

                        updated_at = CURRENT_TIMESTAMP

                    WHERE job_id = ?
                    """,
                    (
                        job.status,
                        job.domain,
                        job.tool,
                        job.worker,

                        job.started_at,
                        job.completed_at,

                        job.duration_seconds,
                        job.error,

                        self._json_dump(
                            job.request
                        ),

                        self._json_dump(
                            job.result
                        ),

                        self._json_dump(
                            job.artifacts
                        ),

                        job.attempt,
                        job.max_attempts,
                        job.last_failure_type,

                        job.job_id,
                    ),
                )

                if cursor.rowcount == 0:
                    raise KeyError(
                        f"Job not found: "
                        f"{job.job_id}"
                    )

                connection.commit()

    # =========================================================
    # Upsert
    # =========================================================

    def upsert(
        self,
        job: Job,
    ) -> None:

        existing = self.get(
            job.job_id
        )

        if existing is None:
            self.create(
                job
            )
        else:
            self.update(
                job
            )

    # =========================================================
    # Direct status update
    # =========================================================

    def set_status(
        self,
        job_id: str,
        status: str,
        error: str | None = None,
    ) -> None:

        if not job_id or not job_id.strip():
            raise ValueError(
                "job_id cannot be empty."
            )

        if not status or not status.strip():
            raise ValueError(
                "status cannot be empty."
            )

        with self._lock:

            with self._connect() as connection:

                cursor = connection.execute(
                    """
                    UPDATE jobs

                    SET
                        status = ?,
                        error = ?,
                        updated_at = CURRENT_TIMESTAMP

                    WHERE job_id = ?
                    """,
                    (
                        status,
                        error,
                        job_id,
                    ),
                )

                if cursor.rowcount == 0:
                    raise KeyError(
                        f"Job not found: "
                        f"{job_id}"
                    )

                connection.commit()

    # =========================================================
    # Get
    # =========================================================

    def get(
        self,
        job_id: str,
    ) -> dict[str, Any] | None:

        if not job_id or not job_id.strip():
            raise ValueError(
                "job_id cannot be empty."
            )

        with self._connect() as connection:

            row = connection.execute(
                """
                SELECT *
                FROM jobs
                WHERE job_id = ?
                """,
                (
                    job_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_dict(
            row
        )

    # =========================================================
    # List jobs
    # =========================================================

    def list_jobs(
        self,
        status: str | None = None,
        domain: str | None = None,
        tool: str | None = None,
        worker: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero."
            )

        clauses = []
        parameters: list[Any] = []

        if status:
            clauses.append(
                "status = ?"
            )
            parameters.append(
                status
            )

        if domain:
            clauses.append(
                "domain = ?"
            )
            parameters.append(
                domain
            )

        if tool:
            clauses.append(
                "tool = ?"
            )
            parameters.append(
                tool
            )

        if worker:
            clauses.append(
                "worker = ?"
            )
            parameters.append(
                worker
            )

        where_clause = ""

        if clauses:
            where_clause = (
                "WHERE "
                + " AND ".join(
                    clauses
                )
            )

        query = f"""
            SELECT *
            FROM jobs
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ?
        """

        parameters.append(
            limit
        )

        with self._connect() as connection:

            rows = connection.execute(
                query,
                parameters,
            ).fetchall()

        return [
            self._row_to_dict(
                row
            )
            for row in rows
        ]

    # =========================================================
    # Durable queued jobs
    # =========================================================

    def list_queued_jobs(
        self,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """
        Return persisted QUEUED jobs in FIFO order.

        Used during dispatcher startup to rebuild
        the in-memory queue.
        """

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero."
            )

        with self._connect() as connection:

            rows = connection.execute(
                """
                SELECT *
                FROM jobs

                WHERE status = 'QUEUED'

                ORDER BY
                    created_at ASC,
                    job_id ASC

                LIMIT ?
                """,
                (
                    limit,
                ),
            ).fetchall()

        return [
            self._row_to_dict(
                row
            )
            for row in rows
        ]

    # =========================================================
    # Atomic worker claim
    # =========================================================

    def claim_queued_job(
        self,
        job_id: str,
    ) -> bool:
        """
        Atomically transition:

            QUEUED -> RUNNING

        Returns:
            True:
                this caller successfully claimed the job

            False:
                job no longer exists in QUEUED state

        The conditional UPDATE prevents two worker threads
        from claiming the same job.
        """

        if not job_id or not job_id.strip():
            raise ValueError(
                "job_id cannot be empty."
            )

        started_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        with self._connect() as connection:

            # BEGIN IMMEDIATE obtains the SQLite write lock
            # before we perform the conditional claim.
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            try:

                cursor = connection.execute(
                    """
                    UPDATE jobs

                    SET
                        status = 'RUNNING',

                        started_at =
                            COALESCE(
                                started_at,
                                ?
                            ),

                        error = NULL,

                        updated_at =
                            CURRENT_TIMESTAMP

                    WHERE
                        job_id = ?
                        AND status = 'QUEUED'
                    """,
                    (
                        started_at,
                        job_id,
                    ),
                )

                claimed = (
                    cursor.rowcount == 1
                )

                connection.commit()

                return claimed

            except Exception:

                connection.rollback()

                raise

    # =========================================================
    # Recovery candidates
    # =========================================================

    def list_recovery_candidates(
        self,
        stale_after_seconds: int = 300,
        include_queued: bool = False,
    ) -> list[dict[str, Any]]:

        if stale_after_seconds < 0:
            raise ValueError(
                "stale_after_seconds "
                "cannot be negative."
            )

        statuses = [
            "RUNNING",
            "VALIDATING",
        ]

        if include_queued:
            statuses.append(
                "QUEUED"
            )

        placeholders = ",".join(
            "?"
            for _ in statuses
        )

        with self._connect() as connection:

            rows = connection.execute(
                f"""
                SELECT *
                FROM jobs

                WHERE status IN (
                    {placeholders}
                )

                ORDER BY updated_at ASC
                """,
                statuses,
            ).fetchall()

        now = datetime.now(
            timezone.utc
        )

        candidates = []

        for row in rows:

            item = self._row_to_dict(
                row
            )

            updated_at = item.get(
                "updated_at"
            )

            if not updated_at:
                candidates.append(
                    item
                )
                continue

            try:

                updated = datetime.strptime(
                    updated_at,
                    "%Y-%m-%d %H:%M:%S",
                ).replace(
                    tzinfo=timezone.utc
                )

                age_seconds = (
                    now - updated
                ).total_seconds()

            except ValueError:

                age_seconds = float(
                    "inf"
                )

            item[
                "stale_age_seconds"
            ] = round(
                age_seconds,
                3,
            )

            if (
                age_seconds
                >= stale_after_seconds
            ):
                candidates.append(
                    item
                )

        return candidates

    # =========================================================
    # Count
    # =========================================================

    def count(
        self,
        status: str | None = None,
        domain: str | None = None,
    ) -> int:

        clauses = []
        parameters: list[Any] = []

        if status:
            clauses.append(
                "status = ?"
            )
            parameters.append(
                status
            )

        if domain:
            clauses.append(
                "domain = ?"
            )
            parameters.append(
                domain
            )

        where_clause = ""

        if clauses:
            where_clause = (
                "WHERE "
                + " AND ".join(
                    clauses
                )
            )

        query = f"""
            SELECT COUNT(*)
            FROM jobs
            {where_clause}
        """

        with self._connect() as connection:

            value = connection.execute(
                query,
                parameters,
            ).fetchone()[0]

        return int(
            value
        )

    # =========================================================
    # Row conversion
    # =========================================================

    def _row_to_dict(
        self,
        row: sqlite3.Row,
    ) -> dict[str, Any]:

        keys = set(
            row.keys()
        )

        return {
            "job_id":
                row["job_id"],

            "status":
                row["status"],

            "domain":
                row["domain"],

            "tool":
                row["tool"],

            "worker":
                row["worker"],

            "created_at":
                row["created_at"],

            "started_at":
                row["started_at"],

            "completed_at":
                row["completed_at"],

            "duration_seconds":
                row["duration_seconds"],

            "error":
                row["error"],

            "request":
                self._json_load(
                    row["request_json"],
                    {},
                ),

            "result":
                self._json_load(
                    row["result_json"],
                    None,
                ),

            "artifacts":
                self._json_load(
                    row["artifacts_json"],
                    [],
                ),

            "attempt":
                (
                    row["attempt"]
                    if "attempt" in keys
                    else 0
                ),

            "max_attempts":
                (
                    row["max_attempts"]
                    if "max_attempts" in keys
                    else 3
                ),

            "last_failure_type":
                (
                    row["last_failure_type"]
                    if (
                        "last_failure_type"
                        in keys
                    )
                    else None
                ),

            "updated_at":
                row["updated_at"],
        }