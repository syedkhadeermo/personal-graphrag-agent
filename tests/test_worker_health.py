import json

from app.agent.workers.worker_health import (
    WorkerHealthRecord,
    WorkerHealthStatus,
)


def main() -> None:
    print("1. Creating an unknown health record...")

    health = WorkerHealthRecord(
        worker_id="mini-pc"
    )

    print(
        json.dumps(
            health.to_dict(),
            indent=2,
            default=str,
        )
    )

    assert (
        health.status
        == WorkerHealthStatus.UNKNOWN
    )

    assert health.checked_at is None
    assert health.consecutive_failures == 0

    print(
        "\n2. Recording an unhealthy result..."
    )

    health.mark_failure(
        status=WorkerHealthStatus.UNHEALTHY,
        message="SSH connection refused.",
        latency_seconds=0.25,
        details={
            "host": "192.168.137.2",
            "return_code": 255,
        },
    )

    print(
        json.dumps(
            health.to_dict(),
            indent=2,
            default=str,
        )
    )

    assert (
        health.status
        == WorkerHealthStatus.UNHEALTHY
    )

    assert health.checked_at is not None
    assert health.latency_seconds == 0.25
    assert health.consecutive_failures == 1

    print(
        "\n3. Recording a timeout..."
    )

    health.mark_failure(
        status=WorkerHealthStatus.TIMEOUT,
        message="SSH heartbeat timed out.",
        latency_seconds=10.0,
        details={
            "host": "192.168.137.2",
        },
    )

    print(
        json.dumps(
            health.to_dict(),
            indent=2,
            default=str,
        )
    )

    assert (
        health.status
        == WorkerHealthStatus.TIMEOUT
    )

    assert health.consecutive_failures == 2

    print(
        "\n4. Recording recovery..."
    )

    health.mark_healthy(
        latency_seconds=0.08,
        message="SSH heartbeat succeeded.",
        details={
            "host": "192.168.137.2",
            "hostname": "syed-pc",
        },
    )

    print(
        json.dumps(
            health.to_dict(),
            indent=2,
            default=str,
        )
    )

    assert (
        health.status
        == WorkerHealthStatus.HEALTHY
    )

    assert health.latency_seconds == 0.08
    assert health.consecutive_failures == 0

    assert (
        health.details["hostname"]
        == "syed-pc"
    )

    print(
        "\n5. Testing invalid transitions and values..."
    )

    invalid_failure_status_rejected = False

    try:
        health.mark_failure(
            status=WorkerHealthStatus.HEALTHY,
            message="Invalid failure state.",
        )

    except ValueError as exc:
        invalid_failure_status_rejected = True
        print(
            f"Invalid failure status rejected: {exc}"
        )

    assert invalid_failure_status_rejected is True

    negative_latency_rejected = False

    try:
        health.mark_healthy(
            latency_seconds=-1.0,
        )

    except ValueError as exc:
        negative_latency_rejected = True
        print(
            f"Negative latency rejected: {exc}"
        )

    assert negative_latency_rejected is True

    empty_worker_id_rejected = False

    try:
        WorkerHealthRecord(
            worker_id="   "
        )

    except ValueError as exc:
        empty_worker_id_rejected = True
        print(
            f"Empty worker ID rejected: {exc}"
        )

    assert empty_worker_id_rejected is True

    print(
        "\nPASS: Worker health states passed."
    )

    print(
        "PASS: Consecutive failures were tracked."
    )

    print(
        "PASS: Healthy recovery reset failures."
    )

    print(
        "PASS: Invalid health values were rejected."
    )


if __name__ == "__main__":
    main()


def test_main() -> None:
    main()
