import time


class RetryTestTool:
    """
    Deterministic retry test tool.

    Attempt 1:
        raises a transient SSH-like failure

    Attempt 2+:
        succeeds
    """

    def __init__(self):
        self.calls = 0

    def run(self) -> dict:
        self.calls += 1

        if self.calls == 1:
            raise RuntimeError(
                "SSH connection failed: connection refused"
            )

        return {
            "tool": "RetryTestTool",
            "status": "completed",
            "return_code": 0,
            "calls": self.calls,
            "message": (
                "Transient failure recovered successfully."
            ),
        }


class SlowTestTool:
    """
    Deterministic slow-running tool.

    Used to prove that asynchronous submission returns
    immediately while execution continues in the background.
    """

    def __init__(
        self,
        delay_seconds: float = 5.0,
    ):
        if delay_seconds <= 0:
            raise ValueError(
                "delay_seconds must be greater than zero."
            )

        self.delay_seconds = delay_seconds

    def run(self) -> dict:

        time.sleep(
            self.delay_seconds
        )

        return {
            "tool": "SlowTestTool",
            "status": "completed",
            "return_code": 0,
            "delay_seconds": self.delay_seconds,
            "message": (
                "Slow asynchronous test completed."
            ),
        }