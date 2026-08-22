from enum import Enum


class JobState(str, Enum):
    """
    Durable states for executable jobs.

    Events describe what happened.
    States describe where the job currently is.
    """

    CREATED = "CREATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    VALIDATING = "VALIDATING"

    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"

    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"


ALLOWED_TRANSITIONS = {

    JobState.CREATED: {
        JobState.QUEUED,
        JobState.CANCELLED,
        JobState.FAILED,
    },

    JobState.QUEUED: {
        JobState.RUNNING,
        JobState.RECOVERY_REQUIRED,
        JobState.CANCELLED,
        JobState.FAILED,
        JobState.TIMED_OUT,
    },

    JobState.RUNNING: {
        JobState.VALIDATING,
        JobState.COMPLETED,
        JobState.RECOVERY_REQUIRED,
        JobState.FAILED,
        JobState.TIMED_OUT,
        JobState.CANCELLED,
    },

    JobState.VALIDATING: {
        JobState.COMPLETED,
        JobState.RECOVERY_REQUIRED,
        JobState.FAILED,
        JobState.TIMED_OUT,
        JobState.CANCELLED,
    },

    # Once recovery is required, a later recovery policy
    # can decide whether to requeue, resume, fail, or cancel.
    JobState.RECOVERY_REQUIRED: {
        JobState.QUEUED,
        JobState.RUNNING,
        JobState.FAILED,
        JobState.CANCELLED,
    },

    # Terminal states
    JobState.COMPLETED: set(),
    JobState.FAILED: set(),
    JobState.TIMED_OUT: set(),
    JobState.CANCELLED: set(),
}


def validate_transition(
    current: JobState,
    target: JobState,
) -> None:
    """
    Validate one durable state transition.

    Raises:
        ValueError:
            If the transition is not permitted.
    """

    if current == target:
        return

    allowed = ALLOWED_TRANSITIONS.get(
        current,
        set(),
    )

    if target not in allowed:
        raise ValueError(
            f"Invalid job state transition: "
            f"{current.value} -> {target.value}"
        )