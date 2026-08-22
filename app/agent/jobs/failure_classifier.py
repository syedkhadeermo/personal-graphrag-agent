from dataclasses import dataclass
from enum import Enum
from typing import Any


class FailureType(str, Enum):
    """
    High-level classification of execution failures.
    """

    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"
    TIMEOUT = "TIMEOUT"
    UNKNOWN = "UNKNOWN"


@dataclass
class FailureClassification:
    """
    Structured result returned by FailureClassifier.
    """

    failure_type: FailureType
    retryable: bool
    reason: str


class FailureClassifier:
    """
    Classify execution failures into transient, permanent,
    timeout, or unknown categories.

    The classifier intentionally starts conservative.

    Transient examples:
        - SSH/network interruption
        - connection refused
        - temporary worker unavailability

    Permanent examples:
        - missing executable
        - missing input file
        - invalid arguments
        - unsupported artifact type
        - invalid topology/input

    Timeout:
        - explicit TimeoutError
        - tool result with status='timeout'
    """

    TRANSIENT_PATTERNS = (
        "connection timed out",
        "connection refused",
        "connection reset",
        "connection closed",
        "network is unreachable",
        "no route to host",
        "ssh connection failed",
        "remote worker",
        "temporarily unavailable",
        "temporary failure",
        "broken pipe",
    )

    PERMANENT_PATTERNS = (
        "file not found",
        "does not exist",
        "no such file",
        "executable not found",
        "unexpected keyword argument",
        "invalid argument",
        "invalid input",
        "unsupported artifact type",
        "artifact validation failed",
        "syntax error",
        "not registered",
    )

    @classmethod
    def classify_exception(
        cls,
        exc: Exception,
    ) -> FailureClassification:

        if isinstance(exc, TimeoutError):
            return FailureClassification(
                failure_type=FailureType.TIMEOUT,
                retryable=True,
                reason="Execution timeout.",
            )

        message = str(exc).lower()

        for pattern in cls.PERMANENT_PATTERNS:
            if pattern in message:
                return FailureClassification(
                    failure_type=FailureType.PERMANENT,
                    retryable=False,
                    reason=(
                        f"Matched permanent failure pattern: "
                        f"{pattern}"
                    ),
                )

        for pattern in cls.TRANSIENT_PATTERNS:
            if pattern in message:
                return FailureClassification(
                    failure_type=FailureType.TRANSIENT,
                    retryable=True,
                    reason=(
                        f"Matched transient failure pattern: "
                        f"{pattern}"
                    ),
                )

        return FailureClassification(
            failure_type=FailureType.UNKNOWN,
            retryable=False,
            reason="Failure could not be classified safely.",
        )

    @classmethod
    def classify_result(
        cls,
        result: Any,
    ) -> FailureClassification | None:
        """
        Classify a structured tool result.

        Returns None when the result represents success.
        """

        if not isinstance(result, dict):
            return None

        status = str(
            result.get("status", "")
        ).strip().lower()

        return_code = result.get(
            "return_code"
        )

        if (
            status == "completed"
            and return_code in (None, 0)
        ):
            return None

        if status == "timeout":
            return FailureClassification(
                failure_type=FailureType.TIMEOUT,
                retryable=True,
                reason="Tool reported timeout.",
            )

        error_text = " ".join(
            str(value)
            for value in (
                result.get("error"),
                result.get("stderr"),
                result.get("stdout"),
            )
            if value
        )

        if not error_text:
            error_text = (
                f"status={status}, "
                f"return_code={return_code}"
            )

        return cls.classify_exception(
            RuntimeError(error_text)
        )