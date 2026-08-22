from enum import Enum
from typing import Iterable


class WorkerCapability(str, Enum):
    """
    Workloads a compute worker can execute.

    Capability values are stable strings suitable for
    persistence, logging, APIs, and future routing.
    """

    REMOTE_COMMAND = "remote_command"
    FREECAD = "freecad"
    BLENDER = "blender"
    OPENFOAM = "openfoam"
    GROMACS = "gromacs"


def normalize_capability(
    capability: WorkerCapability | str,
) -> str:
    """
    Convert an enum or string into a validated capability name.
    """

    if isinstance(
        capability,
        WorkerCapability,
    ):
        return capability.value

    if not isinstance(
        capability,
        str,
    ):
        raise TypeError(
            "Worker capability must be a string "
            "or WorkerCapability."
        )

    normalized = (
        capability
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    if not normalized:
        raise ValueError(
            "Worker capability cannot be empty."
        )

    return normalized


def normalize_capabilities(
    capabilities: Iterable[
        WorkerCapability | str
    ] | None,
) -> tuple[str, ...]:
    """
    Normalize, deduplicate, and sort worker capabilities.
    """

    if capabilities is None:
        return ()

    if isinstance(
        capabilities,
        (
            str,
            WorkerCapability,
        ),
    ):
        raise TypeError(
            "capabilities must be an iterable of "
            "capability values, not one string."
        )

    normalized = {
        normalize_capability(
            capability
        )
        for capability in capabilities
    }

    return tuple(
        sorted(
            normalized
        )
    )