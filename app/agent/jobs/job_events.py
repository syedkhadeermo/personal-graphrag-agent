from enum import Enum


class JobEvent(str, Enum):
    """
    Lifecycle events.

    Events describe what happened.

    JobState separately describes the current
    durable operational state.
    """

    CREATED = "CREATED"
    QUEUED = "QUEUED"

    TOOL_SELECTED = "TOOL_SELECTED"

    WORKER_ASSIGNED = "WORKER_ASSIGNED"
    SSH_CONNECTED = "SSH_CONNECTED"

    PROCESS_STARTED = "PROCESS_STARTED"
    PROCESS_COMPLETED = "PROCESS_COMPLETED"

    # =========================================================
    # Failure / retry events
    # =========================================================

    FAILURE_CLASSIFIED = (
        "FAILURE_CLASSIFIED"
    )

    RETRYING = "RETRYING"

    TIMEOUT = "TIMEOUT"

    # =========================================================
    # Artifact events
    # =========================================================

    ARTIFACT_VALIDATING = (
        "ARTIFACT_VALIDATING"
    )

    ARTIFACT_VALID = "ARTIFACT_VALID"

    ARTIFACT_INVALID = (
        "ARTIFACT_INVALID"
    )

    # =========================================================
    # Recovery
    # =========================================================

    RECOVERY_DETECTED = (
        "RECOVERY_DETECTED"
    )

    # =========================================================
    # Terminal events
    # =========================================================

    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"