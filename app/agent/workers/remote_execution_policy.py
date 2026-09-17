"""Validation policy for values inserted into remote command templates."""

from __future__ import annotations

import os
import re
import shlex
from pathlib import PurePosixPath, PureWindowsPath


_WINDOWS_PATH = re.compile(r"^[A-Za-z0-9 _.:\\/\-]+$")
_POSIX_PATH = re.compile(r"^[A-Za-z0-9 _./\-]+$")
_COMMAND_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


def _windows_root(variable: str, default: str) -> PureWindowsPath:
    return PureWindowsPath(os.getenv(variable, default))


def _is_relative_to(path, root) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def validate_job_script(path: str) -> str:
    """Allow only absolute Python scripts below the configured job root."""
    value = _validate_text(path, "script_path")
    if not _WINDOWS_PATH.fullmatch(value):
        raise ValueError("script_path contains unsupported characters.")

    parsed = PureWindowsPath(value)
    root = _windows_root("GRAPH_RAG_REMOTE_JOB_ROOT", r"C:\AI_Worker\jobs")
    if not parsed.is_absolute() or ".." in parsed.parts:
        raise ValueError("script_path must be an absolute normalized path.")
    if not _is_relative_to(parsed, root):
        raise ValueError("script_path is outside the configured remote job root.")
    if parsed.suffix.lower() != ".py":
        raise ValueError("script_path must reference a Python file.")
    return str(parsed)


def validate_artifact_path(path: str) -> str:
    """Allow artifact operations only below configured Windows roots."""
    value = _validate_text(path, "path")
    if not _WINDOWS_PATH.fullmatch(value):
        raise ValueError("path contains unsupported characters.")

    parsed = PureWindowsPath(value)
    roots_text = os.getenv(
        "GRAPH_RAG_REMOTE_ARTIFACT_ROOTS",
        r"C:\AI_Worker\results",
    )
    roots = [PureWindowsPath(item.strip()) for item in roots_text.split(";") if item.strip()]
    if not parsed.is_absolute() or ".." in parsed.parts:
        raise ValueError("path must be an absolute normalized path.")
    if not any(_is_relative_to(parsed, root) for root in roots):
        raise ValueError("path is outside the configured remote artifact roots.")
    return str(parsed)


def validate_openfoam_case(path: str) -> str:
    """Allow OpenFOAM cases only below the configured WSL case root."""
    value = _validate_text(path, "case_directory")
    if not _POSIX_PATH.fullmatch(value):
        raise ValueError("case_directory contains unsupported characters.")

    parsed = PurePosixPath(value)
    root = PurePosixPath(
        os.getenv(
            "GRAPH_RAG_REMOTE_OPENFOAM_ROOT",
            "/mnt/c/AI_Worker/openfoam_cases",
        )
    )
    if not parsed.is_absolute() or ".." in parsed.parts:
        raise ValueError("case_directory must be an absolute normalized path.")
    if not _is_relative_to(parsed, root):
        raise ValueError("case_directory is outside the configured OpenFOAM root.")
    return str(parsed)


def validate_openfoam_solver(solver: str) -> str:
    """Require a simple command name present in the solver allowlist."""
    value = _validate_text(solver, "solver")
    if not _COMMAND_NAME.fullmatch(value):
        raise ValueError("solver must be one command name without shell syntax.")

    allowed = {
        item.strip()
        for item in os.getenv("GRAPH_RAG_OPENFOAM_SOLVERS", "foamRun").split(",")
        if item.strip()
    }
    if value not in allowed:
        raise ValueError("solver is not in GRAPH_RAG_OPENFOAM_SOLVERS.")
    return value


def quote_bash_argument(value: str) -> str:
    """Quote one already validated Bash argument."""
    return shlex.quote(value)


def quote_windows_argument(value: str) -> str:
    """Quote one already validated Windows command argument."""
    return f'"{value}"'


def _validate_text(value: str, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string.")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field} cannot be empty.")
    return normalized
