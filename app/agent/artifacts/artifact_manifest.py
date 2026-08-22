import hashlib
import json
import os
import string
import tempfile

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


class ArtifactManifest:
    """
    Idempotent artifact manifest for one job.

    Each artifact is identified primarily by SHA-256.

    Guarantees:
        - same file content -> same artifact identity
        - duplicate registration does not create duplicates
        - manifest writes are atomic
        - existing manifest survives process restart
        - no scientific artifact is modified by this class
        - remote artifact contents are not transferred
        - remote hash results are validated before registration

    Manifest location:

        data/jobs/<job_id>/artifacts.json
    """

    def __init__(
        self,
        job_id: str,
        base_directory: str = "data/jobs",
    ):
        if not job_id or not job_id.strip():
            raise ValueError(
                "job_id cannot be empty."
            )

        self.job_id = job_id.strip()

        self.job_directory = (
            Path(base_directory)
            / self.job_id
        )

        self.job_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.manifest_path = (
            self.job_directory
            / "artifacts.json"
        )

        self._lock = Lock()

        self._ensure_manifest()

    # =========================================================
    # Manifest creation
    # =========================================================

    def _ensure_manifest(
        self,
    ) -> None:

        if self.manifest_path.exists():
            return

        manifest = {
            "job_id": self.job_id,
            "version": 1,
            "artifacts": [],
            "created_at": self._now(),
            "updated_at": self._now(),
        }

        self._atomic_write(
            manifest
        )

    # =========================================================
    # Time
    # =========================================================

    @staticmethod
    def _now(
        ) -> str:

        return datetime.now(
            timezone.utc
        ).isoformat()

    # =========================================================
    # Hashing
    # =========================================================

    @staticmethod
    def calculate_sha256(
        path: str | Path,
        block_size: int = 1024 * 1024,
    ) -> str:
        """
        Calculate SHA-256 without loading the whole file
        into memory.

        Suitable for large scientific files such as
        GROMACS trajectories.
        """

        file_path = Path(path)

        if not file_path.is_file():
            raise FileNotFoundError(
                f"Artifact file not found: "
                f"{file_path}"
            )

        digest = hashlib.sha256()

        with file_path.open("rb") as handle:

            while True:

                block = handle.read(
                    block_size
                )

                if not block:
                    break

                digest.update(
                    block
                )

        return digest.hexdigest()

    @staticmethod
    def _normalize_sha256(
        sha256: Any,
    ) -> str:
        """
        Normalize and validate a SHA-256 value supplied by
        a remote compute worker.
        """

        if not isinstance(sha256, str):
            raise ValueError(
                "Remote SHA-256 must be a string."
            )

        normalized = sha256.strip().lower()

        if len(normalized) != 64:
            raise ValueError(
                "Remote SHA-256 must contain exactly "
                "64 hexadecimal characters."
            )

        if any(
            character not in string.hexdigits
            for character in normalized
        ):
            raise ValueError(
                "Remote SHA-256 contains non-hexadecimal "
                "characters."
            )

        return normalized

    # =========================================================
    # Read manifest
    # =========================================================

    def load(
        self,
    ) -> dict[str, Any]:

        if not self.manifest_path.exists():
            self._ensure_manifest()

        try:

            return json.loads(
                self.manifest_path.read_text(
                    encoding="utf-8"
                )
            )

        except json.JSONDecodeError as exc:

            raise RuntimeError(
                "Artifact manifest is corrupted: "
                f"{self.manifest_path}"
            ) from exc

    # =========================================================
    # Atomic write
    # =========================================================

    def _atomic_write(
        self,
        manifest: dict[str, Any],
    ) -> None:
        """
        Write temporary file then atomically replace manifest.

        Avoids partially-written JSON if the process crashes
        during the write.
        """

        self.job_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        fd, temporary_name = (
            tempfile.mkstemp(
                prefix="artifacts_",
                suffix=".tmp",
                dir=self.job_directory,
                text=True,
            )
        )

        temporary_path = Path(
            temporary_name
        )

        try:

            with os.fdopen(
                fd,
                "w",
                encoding="utf-8",
            ) as handle:

                json.dump(
                    manifest,
                    handle,
                    indent=2,
                    default=str,
                )

                handle.flush()

                os.fsync(
                    handle.fileno()
                )

            os.replace(
                temporary_path,
                self.manifest_path,
            )

        finally:

            if temporary_path.exists():

                try:
                    temporary_path.unlink()

                except OSError:
                    pass

    # =========================================================
    # Artifact lookup
    # =========================================================

    def find_by_sha256(
        self,
        sha256: str,
    ) -> dict[str, Any] | None:

        manifest = self.load()

        for artifact in manifest.get(
            "artifacts",
            [],
        ):

            if (
                artifact.get("sha256")
                == sha256
            ):
                return artifact

        return None

    # =========================================================
    # Local registration
    # =========================================================

    def register_local_file(
        self,
        path: str,
        artifact_type: str = "file",
        validated: bool = False,
        metadata: dict[str, Any] | None = None,
        attempt: int | None = None,
    ) -> dict[str, Any]:
        """
        Register one local artifact idempotently.

        If identical file contents are already registered,
        returns the existing entry instead of adding another.
        """

        file_path = Path(path)

        if not file_path.is_file():
            raise FileNotFoundError(
                f"Artifact file not found: "
                f"{file_path}"
            )

        sha256 = self.calculate_sha256(
            file_path
        )

        size_bytes = (
            file_path.stat().st_size
        )

        with self._lock:

            manifest = self.load()

            for artifact in manifest.get(
                "artifacts",
                [],
            ):

                if (
                    artifact.get("sha256")
                    == sha256
                ):

                    return {
                        "created": False,
                        "duplicate": True,
                        "artifact": artifact,
                    }

            artifact_id = (
                f"sha256:{sha256}"
            )

            record = {
                "artifact_id":
                    artifact_id,

                "job_id":
                    self.job_id,

                "path":
                    str(file_path),

                "filename":
                    file_path.name,

                "artifact_type":
                    artifact_type,

                "size_bytes":
                    size_bytes,

                "sha256":
                    sha256,

                "validated":
                    bool(validated),

                "attempt":
                    attempt,

                "metadata":
                    metadata or {},

                "registered_at":
                    self._now(),
            }

            manifest.setdefault(
                "artifacts",
                []
            ).append(
                record
            )

            manifest[
                "updated_at"
            ] = self._now()

            self._atomic_write(
                manifest
            )

            return {
                "created": True,
                "duplicate": False,
                "artifact": record,
            }

    # =========================================================
    # Remote registration
    # =========================================================

    def register_remote_artifact(
        self,
        remote_hash_result: dict[str, Any],
        artifact_type: str = "file",
        validated: bool = False,
        metadata: dict[str, Any] | None = None,
        attempt: int | None = None,
    ) -> dict[str, Any]:
        """
        Register one remote artifact idempotently.

        The supplied dictionary must be the successful result
        returned by RemoteComputeWorker.calculate_remote_sha256().

        The remote file is not downloaded. Its identity is based
        on the SHA-256 calculated by the remote worker.

        Required successful result fields:
            path
            host
            exists
            size_bytes
            sha256
            valid

        If identical content is already registered, the existing
        artifact is returned and the manifest is not modified.
        """

        if not isinstance(
            remote_hash_result,
            dict,
        ):
            raise TypeError(
                "remote_hash_result must be a dictionary."
            )

        remote_path = remote_hash_result.get(
            "path"
        )

        host = remote_hash_result.get(
            "host"
        )

        username = remote_hash_result.get(
            "username"
        )

        if not isinstance(
            remote_path,
            str,
        ) or not remote_path.strip():
            raise ValueError(
                "Remote artifact path is missing."
            )

        remote_path = remote_path.strip()

        if not isinstance(
            host,
            str,
        ) or not host.strip():
            raise ValueError(
                "Remote artifact host is missing."
            )

        host = host.strip()

        if not remote_hash_result.get(
            "exists",
            False,
        ):
            raise FileNotFoundError(
                "Remote artifact does not exist: "
                f"{remote_path}"
            )

        if not remote_hash_result.get(
            "valid",
            False,
        ):
            error = remote_hash_result.get(
                "error"
            )

            raise ValueError(
                "Remote artifact hash result is invalid"
                + (
                    f": {error}"
                    if error
                    else "."
                )
            )

        try:

            size_bytes = int(
                remote_hash_result.get(
                    "size_bytes",
                    0,
                )
            )

        except (
            TypeError,
            ValueError,
        ) as exc:

            raise ValueError(
                "Remote artifact size_bytes is invalid."
            ) from exc

        if size_bytes <= 0:
            raise ValueError(
                "Remote artifact is empty."
            )

        sha256 = self._normalize_sha256(
            remote_hash_result.get(
                "sha256"
            )
        )

        # Path.name on the Windows controller correctly handles
        # Windows paths. Replacing backslashes also keeps filename
        # extraction stable if this code later runs on Linux.
        filename = (
            remote_path
            .replace("\\", "/")
            .rstrip("/")
            .rsplit("/", 1)[-1]
        )

        if not filename:
            raise ValueError(
                "Remote artifact filename cannot be determined."
            )

        remote_metadata = dict(
            metadata or {}
        )

        remote_metadata.setdefault(
            "storage_location",
            "remote",
        )

        remote_metadata.setdefault(
            "remote_host",
            host,
        )

        if username:

            remote_metadata.setdefault(
                "remote_username",
                str(username),
            )

        with self._lock:

            manifest = self.load()

            for artifact in manifest.get(
                "artifacts",
                [],
            ):

                if (
                    artifact.get("sha256")
                    == sha256
                ):

                    return {
                        "created": False,
                        "duplicate": True,
                        "artifact": artifact,
                    }

            artifact_id = (
                f"sha256:{sha256}"
            )

            record = {
                "artifact_id":
                    artifact_id,

                "job_id":
                    self.job_id,

                "path":
                    remote_path,

                "filename":
                    filename,

                "artifact_type":
                    artifact_type,

                "size_bytes":
                    size_bytes,

                "sha256":
                    sha256,

                "validated":
                    bool(validated),

                "attempt":
                    attempt,

                "metadata":
                    remote_metadata,

                "registered_at":
                    self._now(),
            }

            manifest.setdefault(
                "artifacts",
                []
            ).append(
                record
            )

            manifest[
                "updated_at"
            ] = self._now()

            self._atomic_write(
                manifest
            )

            return {
                "created": True,
                "duplicate": False,
                "artifact": record,
            }

    # =========================================================
    # List
    # =========================================================

    def list_artifacts(
        self,
    ) -> list[dict[str, Any]]:

        manifest = self.load()

        return list(
            manifest.get(
                "artifacts",
                [],
            )
        )

    # =========================================================
    # Count
    # =========================================================

    def count(
        self,
    ) -> int:

        return len(
            self.list_artifacts()
        )