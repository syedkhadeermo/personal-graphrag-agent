from queue import Empty, Queue


class JobQueue:
    """
    Thread-safe in-memory queue of job IDs.

    SQLite is the durable source of truth.
    The queue only controls local dispatch order.
    """

    def __init__(
        self,
        maxsize: int = 0,
    ):
        if maxsize < 0:
            raise ValueError(
                "maxsize cannot be negative."
            )

        self._queue: Queue[str] = Queue(
            maxsize=maxsize
        )

    def put(
        self,
        job_id: str,
        block: bool = True,
        timeout: float | None = None,
    ) -> None:

        if not job_id or not job_id.strip():
            raise ValueError(
                "job_id cannot be empty."
            )

        self._queue.put(
            job_id,
            block=block,
            timeout=timeout,
        )

    def get(
        self,
        block: bool = True,
        timeout: float | None = None,
    ) -> str:

        return self._queue.get(
            block=block,
            timeout=timeout,
        )

    def get_nowait(
        self,
    ) -> str:

        return self._queue.get_nowait()

    def task_done(
        self,
    ) -> None:

        self._queue.task_done()

    def join(
        self,
    ) -> None:

        self._queue.join()

    def size(
        self,
    ) -> int:

        return self._queue.qsize()

    def empty(
        self,
    ) -> bool:

        return self._queue.empty()

    def full(
        self,
    ) -> bool:

        return self._queue.full()


__all__ = [
    "JobQueue",
    "Empty",
]