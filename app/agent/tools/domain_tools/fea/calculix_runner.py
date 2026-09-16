import re
from pathlib import PureWindowsPath
from typing import Any

from app.agent.workers.remote_compute_worker import (
    RemoteComputeWorker,
)


class CalculixRunner:
    """
    Execute a pre-existing CalculiX input case on a
    remote Windows scientific-compute worker.

    This runner intentionally supports a narrow execution
    surface for the initial Structural FEA integration.
    """

    CALCULIX_EXECUTABLE = (
        r"C:\Program Files\FreeCAD 1.0\bin\ccx.exe"
    )

    ALLOWED_WORKSPACE = PureWindowsPath(
        r"C:\AI_Worker\structural_fea"
    )

    _JOB_NAME_PATTERN = re.compile(
        r"^[A-Za-z0-9_.-]+$"
    )

    def __init__(
        self,
        host: str,
        username: str,
    ) -> None:
        if not isinstance(host, str):
            raise TypeError(
                "host must be a string."
            )

        if not isinstance(username, str):
            raise TypeError(
                "username must be a string."
            )

        normalized_host = host.strip()
        normalized_username = username.strip()

        if not normalized_host:
            raise ValueError(
                "host cannot be empty."
            )

        if not normalized_username:
            raise ValueError(
                "username cannot be empty."
            )

        self.worker = RemoteComputeWorker(
            host=normalized_host,
            username=normalized_username,
        )

    @classmethod
    def _validate_job_name(
        cls,
        job_name: str,
    ) -> str:
        if not isinstance(
            job_name,
            str,
        ):
            raise TypeError(
                "job_name must be a string."
            )

        normalized = job_name.strip()

        if not normalized:
            raise ValueError(
                "job_name cannot be empty."
            )

        if (
            cls._JOB_NAME_PATTERN.fullmatch(
                normalized
            )
            is None
        ):
            raise ValueError(
                "job_name may contain only letters, "
                "numbers, underscore, hyphen, and dot."
            )

        if normalized in {
            ".",
            "..",
        }:
            raise ValueError(
                "Invalid CalculiX job name."
            )

        return normalized

    @classmethod
    def _validate_case_directory(
        cls,
        case_directory: str,
    ) -> PureWindowsPath:
        if not isinstance(
            case_directory,
            str,
        ):
            raise TypeError(
                "case_directory must be a string."
            )

        raw_directory = case_directory.strip()

        if not raw_directory:
            raise ValueError(
                "case_directory cannot be empty."
            )

        path = PureWindowsPath(
            raw_directory
        )

        if not path.is_absolute():
            raise ValueError(
                "case_directory must be an "
                "absolute Windows path."
            )

        workspace_parts = tuple(
            part.lower()
            for part
            in cls.ALLOWED_WORKSPACE.parts
        )

        path_parts = tuple(
            part.lower()
            for part
            in path.parts
        )

        if (
            path_parts[
                :len(workspace_parts)
            ]
            != workspace_parts
        ):
            raise ValueError(
                "case_directory must be inside "
                r"C:\AI_Worker\structural_fea."
            )

        if ".." in path.parts:
            raise ValueError(
                "case_directory cannot contain "
                "parent-directory traversal."
            )

        return path

    def run(
        self,
        case_directory: str,
        job_name: str,
        timeout: int = 600,
    ) -> dict[str, Any]:
        validated_directory = (
            self._validate_case_directory(
                case_directory
            )
        )

        validated_job_name = (
            self._validate_job_name(
                job_name
            )
        )

        if (
            not isinstance(
                timeout,
                int,
            )
            or isinstance(
                timeout,
                bool,
            )
            or timeout <= 0
            or timeout > 3600
        ):
            raise ValueError(
                "timeout must be an integer "
                "between 1 and 3600 seconds."
            )

        executable = (
            self.CALCULIX_EXECUTABLE
        )

        remote_command = (
            'powershell.exe -NoProfile '
            '-NonInteractive -Command '
            f'"Set-Location -LiteralPath '
            f"'{validated_directory}'; "
            f"& '{executable}' "
            f"-i '{validated_job_name}'\""
        )

        result = self.worker.run(
            command=remote_command,
            timeout=timeout,
        )

        return {
            "tool": "calculix",
            "domain": "structural_fea",
            "worker": self.worker.host,
            "case_directory": str(
                validated_directory
            ),
            "job_name": validated_job_name,
            **result,
        }