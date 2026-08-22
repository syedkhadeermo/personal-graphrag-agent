from dataclasses import dataclass

from app.agent.jobs.failure_classifier import (
    FailureClassification,
)


@dataclass
class RetryDecision:
    """
    Result of evaluating whether another attempt is allowed.
    """

    retry: bool
    delay_seconds: float
    reason: str


class RetryPolicy:
    """
    Determine whether a failed job should be retried.

    Initial policy:
        maximum attempts = 3

    Attempt numbering:
        attempt 1 = initial execution
        attempt 2 = first retry
        attempt 3 = final retry
    """

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay_seconds: float = 1.0,
        max_delay_seconds: float = 30.0,
    ):
        if max_attempts <= 0:
            raise ValueError(
                "max_attempts must be greater than zero."
            )

        if base_delay_seconds < 0:
            raise ValueError(
                "base_delay_seconds cannot be negative."
            )

        if max_delay_seconds < 0:
            raise ValueError(
                "max_delay_seconds cannot be negative."
            )

        self.max_attempts = max_attempts
        self.base_delay_seconds = (
            base_delay_seconds
        )
        self.max_delay_seconds = (
            max_delay_seconds
        )

    def evaluate(
        self,
        classification: FailureClassification,
        attempt: int,
    ) -> RetryDecision:
        """
        Determine whether another attempt should occur.
        """

        if attempt <= 0:
            raise ValueError(
                "attempt must be greater than zero."
            )

        if not classification.retryable:
            return RetryDecision(
                retry=False,
                delay_seconds=0.0,
                reason=(
                    "Failure classification is not retryable."
                ),
            )

        if attempt >= self.max_attempts:
            return RetryDecision(
                retry=False,
                delay_seconds=0.0,
                reason=(
                    f"Maximum attempts reached: "
                    f"{self.max_attempts}"
                ),
            )

        # Exponential backoff:
        #
        # attempt 1 -> 1 sec
        # attempt 2 -> 2 sec
        # attempt 3 -> no further retry
        #
        delay = (
            self.base_delay_seconds
            * (2 ** (attempt - 1))
        )

        delay = min(
            delay,
            self.max_delay_seconds,
        )

        return RetryDecision(
            retry=True,
            delay_seconds=delay,
            reason=(
                f"Retryable "
                f"{classification.failure_type.value} "
                f"failure; next attempt permitted."
            ),
        )