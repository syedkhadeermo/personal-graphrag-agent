import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class StructuredLogger:
    """JSONL event logger for agent jobs."""

    def __init__(self, base_directory: str = "data/jobs"):
        self.base_directory = Path(base_directory)

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    def log(
        self,
        job_id: str,
        event: str,
        **details: Any,
    ) -> dict[str, Any]:

        record = {
            "job_id": job_id,
            "event": event,
            "timestamp": self._timestamp(),
            **details,
        }

        job_directory = self.base_directory / job_id
        job_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        log_file = job_directory / "events.jsonl"

        with log_file.open(
            "a",
            encoding="utf-8",
        ) as handle:
            handle.write(
                json.dumps(record, default=str) + "\n"
            )

        return record